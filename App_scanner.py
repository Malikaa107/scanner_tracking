import os
import logging
from datetime import datetime

import customtkinter as ctk
from PIL import Image

from app_logging import setup_logging
from api_server import start_api_server_in_thread
from database import (
    get_all_jobs,
    get_job_materials,
    get_usage_scan_target,
    update_material_usage,
    update_job_status,
)

setup_logging()
logger = logging.getLogger(__name__)

# Lokasi base project (dipakai untuk load asset lokal seperti logo)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Mapping status job -> teks + warna di UI
STATUS_MAP = {
    0: ("PENDING", "#facc15"),
    1: ("ON PROGRESS", "#38bdf8"),
    2: ("SELESAI", "#22c55e"),
}


class AppScanner(ctk.CTk):
    """Aplikasi utama scanner formulasi."""

    def __init__(self):
        """Inisialisasi window, state awal, dan halaman pertama."""
        super().__init__()
        self.title("Sistem Scanner Formulasi")
        self.geometry("1400x850")
        self.configure(fg_color="#0f172a")

        # Container utama untuk merender semua halaman
        self.main_container = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=0)
        self.main_container.pack(fill="both", expand=True)

        # Set state awal scanner
        self._reset_scan_state()

        # Escape dipakai untuk konfirmasi stop saat scan aktif
        self.bind("<Escape>", lambda _e: self.konfirmasi_stop() if self.is_scanning else None)

        # Halaman awal = daftar joblist
        self.show_joblist_selector()

    def _reset_scan_state(self):
        """Reset seluruh state runtime saat keluar/mulai job baru."""
        self.is_scanning = False
        self.batch_active = False
        self.current_job_id = None
        self.selected_job_no = "-"
        self.target_qty_total = 1
        self.current_batch_num = 1
        self.completed_batches = []
        self.material_resep = []
        self.scanned_materials = set()

        # Data material aktif terakhir untuk payload ke DB
        self.current_material_data = {
            "sap_rm": "",
            "nama_bahan_baku": "",
            "target_qty": 0.0,
        }

    def _clear_main_container(self):
        """Hapus semua widget di halaman utama."""
        for widget in self.main_container.winfo_children():
            widget.destroy()

    def show_toast_notification(self, message, color="green"):
        """Tampilkan notifikasi kecil sementara di bagian atas layar."""
        toast = ctk.CTkLabel(self, text=message, fg_color=color, text_color="white", corner_radius=10)
        toast.place(relx=0.5, rely=0.1, anchor="center")
        self.after(2000, toast.destroy)

    def show_joblist_selector(self):
        """Render halaman daftar job (status pending/on progress)."""
        self._clear_main_container()
        self.is_scanning = False
        self.batch_active = False

        # Judul halaman
        ctk.CTkLabel(
            self.main_container,
            text="Daftar Joblist Formulasi",
            font=("Arial", 28, "bold"),
            text_color="white",
        ).pack(anchor="w", padx=40, pady=(30, 10))

        # Header kolom tabel job
        header_bar = ctk.CTkFrame(self.main_container, fg_color="#1e293b", height=45, corner_radius=5)
        header_bar.pack(fill="x", padx=40, pady=10)
        header_bar.pack_propagate(False)

        headers = [
            ("NOMOR JOB", 20),
            ("TANGGAL", 200),
            ("RESEP TARGET", 350),
            ("TARGET QTY", 550),
            ("STATUS", 700),
            ("ACTION", 900),
        ]
        for text, x_pos in headers:
            ctk.CTkLabel(header_bar, text=text, font=("Arial", 11, "bold"), text_color="#94a3b8").place(x=x_pos, y=10)

        # Area scroll untuk isi data job
        scroll_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent", label_text="")
        scroll_frame.pack(fill="both", expand=True, padx=30, pady=5)

        # Ambil data job dari database
        jobs = get_all_jobs()
        if not jobs:
            ctk.CTkLabel(
                scroll_frame,
                text="TIDAK ADA JOBLIST AKTIF DI DATABASE",
                font=("Arial", 16),
                text_color="#475569",
            ).pack(pady=100)
            return

        # Render tiap baris job
        for job in jobs:
            self._render_job_row(scroll_frame, job)

    def _render_job_row(self, parent, job):
        """Render 1 baris job ke tabel daftar job."""
        status_code = job.get("status", 0)
        status_text, status_color = STATUS_MAP.get(status_code, ("UNKNOWN", "white"))

        job_no = job.get("nomor_job") or "N/A"
        resep = job.get("nama_resep") or "No Name"
        tanggal = job.get("tanggal")
        tanggal_text = str(tanggal) if tanggal else "-"
        target_qty = job.get("target_qty", 1)

        # Ubah style tombol berdasarkan status job
        if status_code == 2:
            btn_txt, btn_clr, hvr_clr = "Lihat Detail", "#334155", "#475569"
        else:
            btn_txt, btn_clr, hvr_clr = "PILIH JOB", "#1d4ed8", "#2563eb"

        row = ctk.CTkFrame(parent, fg_color="#1e293b", height=60, corner_radius=8)
        row.pack(fill="x", pady=5, padx=10)
        row.pack_propagate(False)

        ctk.CTkLabel(row, text=job_no, font=("Arial", 13, "bold"), text_color="white").place(x=20, y=18)
        ctk.CTkLabel(row, text=tanggal_text, font=("Arial", 12), text_color="#94a3b8").place(x=200, y=18)
        ctk.CTkLabel(row, text=resep, font=("Arial", 12), text_color="white").place(x=350, y=18)
        ctk.CTkLabel(row, text=f"{target_qty} Batch", font=("Arial", 12), text_color="white").place(x=550, y=18)
        ctk.CTkLabel(row, text=status_text, text_color=status_color, font=("Arial", 12, "bold")).place(x=700, y=18)

        ctk.CTkButton(
            row,
            text=btn_txt,
            fg_color=btn_clr,
            hover_color=hvr_clr,
            width=120,
            height=32,
            font=("Arial", 12, "bold"),
            command=lambda j=job: self.start_job(j),
        ).place(x=900, y=14)

    def start_job(self, job_data):
        """Saat user pilih job: ambil material resep lalu buka halaman scan."""
        job_id = job_data.get("id")
        if not job_id:
            self.show_toast_notification("Job tidak valid", color="red")
            return

        materials = get_job_materials(job_id)
        if not materials:
            self.show_toast_notification("Material resep tidak ditemukan", color="red")
            return

        self.current_job_id = job_id
        self.material_resep = materials
        self.selected_job_no = job_data.get("nomor_job") or "-"
        self.target_qty_total = max(1, int(job_data.get("target_qty", 1) or 1))
        self.current_batch_num = 1
        self.completed_batches = []
        self.scanned_materials = set()
        self.batch_active = False
        self.is_scanning = True

        self.setup_scanner_ui()
        self.update_clock()

    def setup_scanner_ui(self):
        """Bangun layout halaman scan (header + sidebar + area scan)."""
        self._clear_main_container()

        # Header atas
        self.header = ctk.CTkFrame(self.main_container, height=130, corner_radius=0, fg_color="#1e3d59")
        self.header.pack(side="top", fill="x", pady=0)
        self.header.pack_propagate(False)

        # Konten utama bawah header
        self.content_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_container.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))

        title_x = self._render_header_logo()
        ctk.CTkLabel(
            self.header,
            text="SISTEM SCANNER FORMULASI",
            font=("Franklin Gothic Heavy", 28, "bold"),
            text_color="white",
        ).place(x=title_x, y=30)

        # Info job + batch aktif
        self.batch_info_label = ctk.CTkLabel(
            self.header,
            text=f"JOB: {self.selected_job_no} | BATCH: {self.current_batch_num}/{self.target_qty_total}",
            font=("Arial", 16, "bold"),
            text_color="#38bdf8",
            fg_color="#0f172a",
            corner_radius=10,
            padx=15,
            pady=5,
        )
        self.batch_info_label.place(x=title_x, y=80)

        # Jam realtime
        self.datetime_label = ctk.CTkLabel(self.header, text="", font=("Arial", 14, "bold"), text_color="#38bdf8")
        self.datetime_label.place(relx=0.97, rely=0.15, anchor="ne")

        # Tombol aksi kanan atas
        ctk.CTkButton(
            self.header,
            text="STOP JOB",
            fg_color="#ef4444",
            width=100,
            height=35,
            font=("Arial", 12, "bold"),
            command=self.konfirmasi_stop,
        ).place(relx=0.85, rely=0.65, anchor="ne")

        ctk.CTkButton(
            self.header,
            text="HISTORY",
            fg_color="#20C997",
            width=100,
            height=35,
            font=("Arial", 12, "bold"),
        ).place(relx=0.97, rely=0.65, anchor="ne")

        self._build_scanner_body()
        self.update_sidebar_lists()

    def _render_header_logo(self):
        """Load dan tampilkan logo di header jika file tersedia."""
        try:
            logo_img = Image.open(os.path.join(BASE_DIR, "logo2.png"))
            self.logo_icon = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(80, 80))
            ctk.CTkLabel(self.header, image=self.logo_icon, text="").place(x=20, y=25)
            return 115
        except Exception:
            logger.exception("Gagal load logo header dari BASE_DIR=%s", BASE_DIR)
            return 30

    def _build_scanner_body(self):
        """Buat sidebar kiri-kanan dan area scan di tengah."""
        # Sidebar kiri: daftar material scan + tombol start batch
        self.sidebar_left = ctk.CTkFrame(self.content_container, width=300, corner_radius=20, fg_color="#1e293b")
        self.sidebar_left.pack(side="left", fill="y", padx=(0, 10), pady=0)

        self.btn_batch_start = ctk.CTkButton(
            self.sidebar_left,
            text=f"START BATCH {self.current_batch_num} >",
            font=("Arial", 15, "bold"),
            height=50,
            fg_color="#3b82f6",
            command=self.start_batch_logic,
        )
        self.btn_batch_start.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(self.sidebar_left, text="LIST MATERIAL SCAN", text_color="#38bdf8", font=("Arial", 14, "bold")).pack(pady=(10, 5))
        self.scroll_sidebar_left = ctk.CTkScrollableFrame(self.sidebar_left, fg_color="transparent")
        self.scroll_sidebar_left.pack(expand=True, fill="both", padx=10, pady=5)

        # Sidebar kanan: checklist manual untuk material non-scan
        self.sidebar_right = ctk.CTkFrame(self.content_container, width=280, corner_radius=20, fg_color="#1e293b")
        self.sidebar_right.pack(side="right", fill="y", padx=(10, 0), pady=0)

        ctk.CTkLabel(self.sidebar_right, text="CHECKLIST", text_color="#fbbf24", font=("Arial", 15, "bold")).pack(pady=15)
        self.scroll_sidebar_right = ctk.CTkScrollableFrame(self.sidebar_right, fg_color="transparent")
        self.scroll_sidebar_right.pack(expand=True, fill="both", padx=10, pady=5)

        # Area tengah: instruksi dan entry barcode
        self.main_area = ctk.CTkFrame(self.content_container, corner_radius=20, fg_color="#1e293b")
        self.main_area.pack(side="left", expand=True, fill="both", pady=0)

        center_wrapper = ctk.CTkFrame(self.main_area, fg_color="transparent")
        center_wrapper.place(relx=0.5, rely=0.45, anchor="center")

        self.result_display = ctk.CTkLabel(
            center_wrapper,
            text="TEKAN START UNTUK SCAN",
            font=("Arial", 32, "bold"),
            text_color="#94a3b8",
        )
        self.result_display.pack(pady=(0, 20))

        self.entry_barcode = ctk.CTkEntry(
            center_wrapper,
            width=450,
            height=80,
            justify="center",
            font=("Arial", 28),
            placeholder_text="Menunggu start...",
            fg_color="#0f172a",
            text_color="white",
            border_color="#334155",
            state="disabled",
        )
        self.entry_barcode.pack(pady=0)

        # Event input scanner
        self.entry_barcode.bind("<KeyRelease>", self.auto_scan_handler)
        self.entry_barcode.bind("<Return>", lambda _e: self.auto_scan_handler(force=True))

    def start_batch_logic(self):
        """Aktifkan batch saat tombol START ditekan."""
        self.batch_active = True
        self.btn_batch_start.configure(
            state="disabled",
            text=f"SCANNING BATCH {self.current_batch_num}...",
            fg_color="#1e3d59",
        )
        self.entry_barcode.configure(state="normal", placeholder_text=f"Scan Batch {self.current_batch_num}...")
        self.entry_barcode.focus_set()
        self.result_display.configure(text="Silahkan Scan Barcode", text_color="#38bdf8")

    def auto_scan_handler(self, _event=None, force=False):
        """Ambil input barcode dan jalankan proses scan."""
        if not self.batch_active:
            return

        barcode_data = self.entry_barcode.get().strip()
        if not barcode_data:
            return

        self.process_scan(barcode_data)
        if force or len(barcode_data) >= 1:
            self.entry_barcode.delete(0, "end")

    def process_scan(self, barcode_data):
        """Validasi material scan terhadap resep, lalu simpan ke DB."""
        if not self.current_job_id:
            self.show_toast_notification("Job belum dipilih", color="red")
            return

        usage_id = None
        barcode_pallet_value = barcode_data

        # Cari item resep yang sap_rm-nya sama dengan barcode hasil scan
        material = next((item for item in self.material_resep if item.get("kode_sap") == barcode_data), None)
        if not material:
            # Fallback: anggap barcode_data adalah formulasi_material_usage.id
            usage_target = get_usage_scan_target(self.current_job_id, self.current_batch_num, barcode_data)
            if usage_target:
                usage_id = usage_target.get("id")
                barcode_pallet_value = usage_target.get("barcode_pallet") or barcode_data
                usage_sap = usage_target.get("sap_rm")
                material = next((item for item in self.material_resep if item.get("kode_sap") == usage_sap), None)

            if not material:
                self.show_toast_notification("Scan tidak cocok dengan material resep/job aktif", color="red")
                return

        # Simpan konteks material aktif
        self.current_material_data = {
            "sap_rm": material.get("kode_sap", ""),
            "nama_bahan_baku": material.get("nama", ""),
            "target_qty": material.get("target_qty", 0.0),
        }

        # Tandai bahwa material ini sudah discan untuk batch aktif
        self.scanned_materials.add(self.current_material_data["sap_rm"])

        # Kirim data usage ke DB (batch wajib, scan_at wajib)
        try:
            update_result = update_material_usage(
                joblist_id=self.current_job_id,
                barcode_pallet=barcode_pallet_value,
                sap_rm=self.current_material_data["sap_rm"],
                batch=self.current_batch_num,
                qty_dipakai=self.current_material_data["target_qty"],
                scan_at=datetime.now(),
                scan_oleh="Admin",
                usage_id=usage_id,
            )
            is_saved = bool(update_result.get("saved"))
        except Exception as exc:
            logger.exception(
                "Error process_scan job_id=%s sap_rm=%s batch=%s",
                self.current_job_id,
                self.current_material_data.get("sap_rm"),
                self.current_batch_num,
            )
            self.show_toast_notification(str(exc), color="red")
            return

        self.update_sidebar_lists()
        self.check_all_materials_completed()

        if is_saved:
            self.show_toast_notification("Data berhasil di-update", color="green")
        else:
            self.show_toast_notification("Data gagal di-update", color="red")

    def manual_check_handler(self, kode_sap):
        """Checklist manual untuk item non-scan (toggle)."""
        if not self.batch_active:
            return

        if kode_sap in self.scanned_materials:
            self.scanned_materials.remove(kode_sap)
        else:
            self.scanned_materials.add(kode_sap)

        self.update_sidebar_lists()
        self.check_all_materials_completed()

    def check_all_materials_completed(self):
        """Jika semua item batch selesai, lanjut ke handler selesai batch."""
        if len(self.scanned_materials) == len(self.material_resep):
            self.handle_batch_complete()

    def handle_batch_complete(self):
        """Selesaikan batch aktif; lanjut batch berikutnya atau finalisasi job."""
        self.batch_active = False
        self.result_display.configure(text=f"BATCH {self.current_batch_num} SELESAI!", text_color="#22c55e")
        self.entry_barcode.configure(state="disabled")

        if self.current_batch_num < self.target_qty_total:
            # Masih ada batch berikutnya
            self.completed_batches.append(f"Batch {self.current_batch_num}")
            self.current_batch_num += 1
            self.scanned_materials.clear()
            self.btn_batch_start.configure(
                state="normal",
                text=f"START BATCH {self.current_batch_num} >",
                fg_color="#3b82f6",
            )
            self.batch_info_label.configure(
                text=f"JOB: {self.selected_job_no} | BATCH: {self.current_batch_num}/{self.target_qty_total}"
            )
        else:
            # Semua batch selesai, tombol jadi FINISH
            self.result_display.configure(text="ALL BATCH COMPLETED!", text_color="#22c55e")
            self.btn_batch_start.configure(state="normal", text="FINISH", fg_color="#22c55e", command=self.finish_job)

        self.update_sidebar_lists()

    def finish_job(self):
        """Set status job menjadi selesai (2) di database."""
        if not self.current_job_id:
            self.show_toast_notification("Job tidak valid", color="red")
            return

        if update_job_status(self.current_job_id, 2):
            self.show_toast_notification("Job berhasil diselesaikan", color="#22c55e")
            self.after(1500, self.show_joblist_selector)
        else:
            self.show_toast_notification("Gagal update status job", color="red")

    def update_sidebar_lists(self):
        """Render ulang daftar item di sidebar kiri dan kanan."""
        # Bersihkan isi lama agar tidak duplikat
        for widget in self.scroll_sidebar_left.winfo_children():
            widget.destroy()
        for widget in self.scroll_sidebar_right.winfo_children():
            widget.destroy()

        # Riwayat batch yang sudah selesai
        if self.completed_batches:
            ctk.CTkLabel(
                self.scroll_sidebar_left,
                text="RIWAYAT BATCH:",
                font=("Arial", 11, "bold"),
                text_color="#94a3b8",
            ).pack(anchor="w", padx=10)
            for batch in self.completed_batches:
                ctk.CTkLabel(
                    self.scroll_sidebar_left,
                    text=f"[OK] {batch} SELESAI",
                    text_color="#22c55e",
                    font=("Arial", 11),
                ).pack(anchor="w", padx=20)

        ctk.CTkLabel(
            self.scroll_sidebar_left,
            text=f"SCAN LIST (B-{self.current_batch_num}):",
            font=("Arial", 12, "bold"),
            text_color="#38bdf8",
        ).pack(pady=(15, 5), anchor="w", padx=10)

        for item in self.material_resep:
            self._render_material_item(item)

    def _render_material_item(self, item):
        """Tampilkan item material ke list scan atau checklist manual."""
        nama = (item.get("nama") or "-").upper()
        qty = item.get("target_qty", 0)
        satuan = item.get("satuan", "Kg")
        kode_sap = item.get("kode_sap")
        is_done = kode_sap in self.scanned_materials

        marker = "[OK]" if is_done else "[ ]"
        text = f"{marker} {nama} ({qty} {satuan})"

        # Material scan barcode -> sidebar kiri
        if item.get("is_scan", True):
            frame = ctk.CTkFrame(self.scroll_sidebar_left, fg_color="#064e3b" if is_done else "#334155", height=35)
            frame.pack(fill="x", pady=2, padx=10)
            ctk.CTkLabel(frame, text=text, text_color="white", font=("Arial", 11)).pack(side="left", padx=10)
            return

        # Material checklist manual -> sidebar kanan
        frame = ctk.CTkFrame(self.scroll_sidebar_right, fg_color="#064e3b" if is_done else "#334155", height=40)
        frame.pack(fill="x", pady=2, padx=10)
        ctk.CTkLabel(
            frame,
            text=text,
            text_color="#34d399" if is_done else "white",
            font=("Arial", 11),
        ).pack(side="left", padx=10)

        checkbox = ctk.CTkCheckBox(
            frame,
            text="",
            width=24,
            checkbox_width=24,
            checkbox_height=24,
            border_width=3,
            border_color="#ffffff",
            fg_color="#22c55e",
            checkmark_color="#ffffff",
            hover_color="#38bdf8",
            command=lambda code=kode_sap: self.manual_check_handler(code),
        )
        if is_done:
            checkbox.select()
        checkbox.pack(side="right", padx=10)

    def eksekusi_keluar(self, window_target):
        """Keluar dari sesi scan dan kembali ke joblist."""
        try:
            window_target.destroy()
        except Exception:
            logger.exception("Gagal menutup window konfirmasi")

        self._reset_scan_state()
        self.show_joblist_selector()

    def konfirmasi_stop(self):
        """Popup konfirmasi saat user ingin berhenti dari halaman scan."""
        pop = ctk.CTkToplevel(self)
        pop.title("Konfirmasi Tindakan")
        pop.geometry("400x220")
        pop.attributes("-topmost", True)
        pop.configure(fg_color="#0f172a")

        # Posisi popup di tengah layar
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - 200
        y = (screen_height // 2) - 110
        pop.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            pop,
            text="Scanner Sedang Berjalan",
            font=("Arial", 18, "bold"),
            text_color="#f59e0b",
        ).pack(pady=(25, 10))
        ctk.CTkLabel(
            pop,
            text="Apakah anda ingin tetap di halaman scan\natau membatalkan dan keluar?",
            font=("Arial", 13),
            text_color="white",
        ).pack(pady=10)

        btn_frame = ctk.CTkFrame(pop, fg_color="transparent")
        btn_frame.pack(pady=20)

        ctk.CTkButton(
            btn_frame,
            text="TETAP SCAN",
            width=130,
            height=40,
            fg_color="#334155",
            font=("Arial", 12, "bold"),
            command=pop.destroy,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="KELUAR",
            width=130,
            height=40,
            fg_color="#ef4444",
            hover_color="#dc2626",
            font=("Arial", 12, "bold"),
            command=lambda p=pop: self.eksekusi_keluar(p),
        ).pack(side="left", padx=10)

    def update_clock(self):
        """Update jam di header tiap detik saat mode scanning aktif."""
        if self.is_scanning and hasattr(self, "datetime_label"):
            self.datetime_label.configure(text=datetime.now().strftime("%A, %d %B %Y\n%H:%M:%S"))
            self.after(1000, self.update_clock)


if __name__ == "__main__":
    # Jalankan API internal sebagai thread daemon
    start_api_server_in_thread()

    # Jalankan aplikasi desktop
    app = AppScanner()
    app.mainloop()
