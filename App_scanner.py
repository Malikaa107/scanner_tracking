import os # library interaksi sistem (buat folder, file)
import logging # library untuk mencatat log (pesan sistem) 
import requests
from time import monotonic # untuk menghitung durasi waktu presisi secara linear untuk pelindung scan ganda 
from datetime import datetime #mengambil data waktu saat ini (tanggal, waktu)

import customtkinter as ctk #library ui / tampilan 
from PIL import Image # untuk mengolah dan menampilkan gambar

from app_logging import setup_logging #mengimpor fungsi eksternal untuk awal konfigurasi awal sistem log 
from api_server import start_api_server_in_thread #mengimpor fungsi untuk menjalankan server API di bg
from history_window import HistoryWindow #mengimpor window tambahan untuk menampilkan riwayat scan
from database import ( # mengimpor fungsi komunikasi database dari file database.py
    get_all_jobs,
    get_usage_scan_target,
    running_batch_joblist,
    update_material_usage,
    update_job_status,
)

setup_logging() # jalankan konfigurasi log di awal apk 
logger = logging.getLogger(__name__) #membuat instance logger khusus untuk mencatat eror 

# Lokasi base project (dipakai untuk load asset lokal seperti logo)
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 

# Mapping status job -> teks + warna di UI
STATUS_MAP = {
    0: ("PENDING", "#facc15"),
    1: ("ON PROGRESS", "#38bdf8"),
    2: ("SELESAI", "#22c55e"),
}


class AppScanner(ctk.CTk):
    # Aplikasi utama scanner formulasi.

    def __init__(self):
        # Inisialisasi window, state awal, dan halaman pertama.
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
        # Reset seluruh state runtime saat keluar/mulai job baru.
        pending_after = getattr(self, "scan_debounce_after_id", None)
        if pending_after is not None:
            try:
                self.after_cancel(pending_after)
            except Exception:
                logger.debug("scan debounce callback sudah tidak aktif", exc_info=True)

        self.is_scanning = False # menandakan layar scan sedang dalam mode scan aktif/tidak 
        self.batch_active = False # menandakan batch sedang aktif 
        self.current_job_id = None # menyimpan id job yang sedang aktif dikerjakan 
        self.selected_job_no = "-" # menyimpan no job aktif untuk ditampilkan di header 
        self.target_qty_total = 1 # menyimpan total batch target yang harus diselesaikan 
        self.current_batch_num = 1 # menyimpan urutan angka no batch yang sedang berjalan 
        self.completed_batches = [] # menyimpan daftar string nama batch yg sudah selesai 
        self.material_resep = []  # menyimpan list resep material lengkap untuk job aktif 
        self.scanned_materials = set() # menyimpan kode SAP material yg sudah selesai scan di batch aktif 
        self.all_batches_done = False # menandakan apakah seluruh batch job sudah selesai scan 
        self.scan_debounce_after_id = None # menyimpan id fungsi timer untuk sistem tunda (debounce) input data 

        # Pengaturan Sistem Scanner
        self.scan_debounce_ms = 180 # Durasi toleransi waktu jeda 
        self.scan_duplicate_guard_ms = 300 # Durasi minimal pencegah scan ganda untuk item yang sama (milidetik)
        self.scan_inflight = False # penanda apakah data scan sedang dalam proses simpan database 
        self.last_scan_payload = "" # menyimpan isi teks barcode terakhir yang berhasil di proses 
        self.last_scan_monotonic = 0.0 # menyimpan catatan waktu internal terakhir kali scan berhasil 

        # Data material aktif terakhir untuk payload ke DB
        self.current_material_data = {
            "sap_rm": "", # Kode SAP material aktif 
            "nama_bahan_baku": "", # nama bahan baku aktif 
            "target_qty": 0.0, # jumlah berat / volume target material aktif 
        }

    def _clear_main_container(self):
        # Hapus semua widget di halaman utama. 
        for widget in self.main_container.winfo_children(): # melakukan perulangan pada setiap widget 
            widget.destroy() # menghapus widget tsb dari memori dan layar 

    # Memunculkan notifikasi sementara (error/sukses)
    def show_toast_notification(self, message, color="green"):
        # Tampilkan notifikasi kecil sementara di bagian atas layar.
        toast = ctk.CTkLabel(self, text=message, fg_color=color, text_color="white", corner_radius=10)
        toast.place(relx=0.5, rely=0.1, anchor="center") # menempatkan di tengah layar 
        self.after(2000, toast.destroy) # mengatur penghapus otomatis label setelah 2  detik 

    # Membangun UI halaman daftar job, mengambil data dari database untuk menampilkan dalam bentuk tabel 
    def show_joblist_selector(self): 
        # Render halaman daftar job (status pending/on progress).
        self._clear_main_container() # bersihkan layar container utama 
        self.is_scanning = False # set status scanning menjadi tidak aktif 
        self.batch_active = False # set status batch berjalan menjadi tidak aktif 

        # Judul halaman + tombol history
        title_bar = ctk.CTkFrame(self.main_container, fg_color="transparent") 
        title_bar.pack(fill="x", padx=40, pady=(30, 10)) # pasang memenuhi arah horizontal 

        # Menampilkan teks judul halaman sisi kiri 
        ctk.CTkLabel(
            title_bar,
            text="Daftar Joblist Formulasi",
            font=("Arial", 28, "bold"),
            text_color="white",
        ).pack(side="left")

        # Menampilkan tombol history di sisi kanan 
        ctk.CTkButton(
            title_bar,
            text="HISTORY", 
            fg_color="#20C997",
            width=120,
            height=36,
            font=("Arial", 12, "bold"),
            command=self.open_history_window, # panggil fungsi buka window history saat di klik 
        ).pack(side="right")

        # Header kolom tabel job
        header_bar = ctk.CTkFrame(self.main_container, fg_color="#1e293b", height=45, corner_radius=5)
        header_bar.pack(fill="x", padx=40, pady=10)
        header_bar.pack_propagate(False) # mencegah ukuran frame mengecil mengikuti ukuran teks di dalam nya 

        # Daftar tuple yg berisi teks kolom & koordinat posisi 
        headers = [
            ("NOMOR JOB", 20),
            ("TANGGAL", 200),
            ("RESEP TARGET", 350),
            ("TARGET QTY", 550),
            ("STATUS", 700),
            ("ACTION", 900),
        ]
        for text, x_pos in headers: # perulangan memasang setiap label judul kolom 
            ctk.CTkLabel(header_bar, text=text, font=("Arial", 11, "bold"), text_color="#94a3b8").place(x=x_pos, y=10)

        # Area scroll untuk isi data job
        scroll_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent", label_text="")
        scroll_frame.pack(fill="both", expand=True, padx=30, pady=5)

        # Ambil data job dari database
        jobs = get_all_jobs() # ambil data job (database.py)
        if not jobs: # jika data job kosong / tidak ditemukan koneksi database 
            ctk.CTkLabel( 
                scroll_frame,
                text="TIDAK ADA JOBLIST AKTIF", 
                font=("Arial", 16),
                text_color="#475569",
            ).pack(pady=100) # tampilkan pesan peringatan di tengah area scroll 
            return # hentikan eksekusi fungsi 

        # Render tiap baris job 
        for job in jobs: 
            self._render_job_row(scroll_frame, job) # panggil fungsi pembantu proses pengerjaan baris tabel 

    # fungsi untuk membuat baris (row) data job spesifik 
    def _render_job_row(self, parent, job):
        # Render 1 baris job ke tabel daftar job.
        status_code = job.get("status", 0) # ambil angka status dari database (default 0 jika tdk ada)
        status_text, status_color = STATUS_MAP.get(status_code, ("UNKNOWN", "white")) 

        job_no = job.get("nomor_job") or "N/A" # ambil data dari no job, jika kosong ganti "N/A"
        resep = job.get("nama_resep") or "No Name" # ambil nama resep produk, jika kosong ganti "No name"
        tanggal = job.get("tanggal") # ambil data tanggal dibuatnya data job tersebut 
        tanggal_text = str(tanggal) if tanggal else "-" # ubah objek tanggal ke bentuk teks string 
        target_qty = job.get("target_qty", 1) # ambil total target qty batch dari job 

        # Ubah style tombol berdasarkan status job
        if status_code == 2: # logika pengaturan teks tombol : jika job sudah berstatus 2 (selesai)
            btn_txt, btn_clr, hvr_clr = "Lihat Detail", "#334155", "#475569"
        else: # jika status masih pending / on progress 
            btn_txt, btn_clr, hvr_clr = "PILIH JOB", "#1d4ed8", "#2563eb" 

        # buat frame utama untuk data ini 
        row = ctk.CTkFrame(parent, fg_color="#1e293b", height=60, corner_radius=8)
        row.pack(fill="x", pady=5, padx=10)
        row.pack_propagate(False) # kunci tinggi frame tetap di angka 60 pixel 

        # Menempatkan label data pada posisi koordinat 
        ctk.CTkLabel(row, text=job_no, font=("Arial", 13, "bold"), text_color="white").place(x=20, y=18)
        ctk.CTkLabel(row, text=tanggal_text, font=("Arial", 12), text_color="#94a3b8").place(x=200, y=18)
        ctk.CTkLabel(row, text=resep, font=("Arial", 12), text_color="white").place(x=350, y=18)
        ctk.CTkLabel(row, text=f"{target_qty} Batch", font=("Arial", 12), text_color="white").place(x=550, y=18)
        ctk.CTkLabel(row, text=status_text, text_color=status_color, font=("Arial", 12, "bold")).place(x=700, y=18)
        
        # tombol memilih job dan pindah ke scanner 
        ctk.CTkButton( 
            row,
            text=btn_txt,
            fg_color=btn_clr,
            hover_color=hvr_clr,
            width=120,
            height=32,
            font=("Arial", 12, "bold"),
            command=lambda j=job: self.start_job(j), # gunakan lambda agar data job terikat pada fungsi 
        ).place(x=900, y=14)

    # Dijalankan saat tombol "pilih job" ditekan, mengambil detail material 
    def start_job(self, job_data):
        # Saat user pilih job: ambil material resep lalu buka halaman scan.
        job_id = job_data.get("id") # ambil data id baris database dari job terpilih
        if not job_id: # jika id tidak valid / kosong 
            self.show_toast_notification("Job tidak valid", color="red") # tampilkan notifikasi eror 
            return # Hentikan fungsi 

        self.current_job_id = job_id # simpan id job aktif 
        self.selected_job_no = job_data.get("nomor_job") or "-" # simpan no ke variabel class
        self.target_qty_total = max(1, int(job_data.get("target_qty", 1) or 1)) # hitung total target qty minimal 1 
        resume_state = self._resolve_resume_state(job_id) # ambil riwayat status pengerjaan terakhir dari (database.py)
        if not resume_state: # jika gagal menarik data resep / resume dari database 
            self.show_toast_notification("Material resep tidak ditemukan", color="red") # Notifikasi eror 
            return # batalkan proses masuk ke halaman scan 

        # isi variabel status aplikasi menggunakan hasil olah data resume database 
        self.current_batch_num = resume_state["current_batch_num"] # nomor batch aktif saat ini 
        self.completed_batches = resume_state["completed_batches"] # list batch yang sudah selesai sebelumnya 
        self.scanned_materials = resume_state["scanned_materials"] # bahan yg sukses di scan di batch aktif 
        self.material_resep = resume_state["material_resep"] # daftar master resep untuk batch ini 
        self.all_batches_done = resume_state["all_batches_done"] # status apakah seluruh batch selesai 
        self.batch_active = False # set status pengetikan barcode menjadi terkunci (menunggu tombol start) 
        self.is_scanning = True # menandakan aplikasi ini telah pindah halaman utama monitor scanner 

        self.setup_scanner_ui() # panggil fungsi pembangun tata letak scanner 
        self._sync_resume_ui_state() # sinkronisasi tampilan tombol jika ternyata job resume sudah selesai semua 
        self.update_clock() # jalankan fungsi perulangan jam realtime 

    def _resolve_resume_state(self, job_id: int):
        # Tentukan batch resume dari DB + daftar item yang sudah selesai di batch aktif.
        batch_cache = {} # penampung sementara data item per no batch 
        completed_batches = [] # list lokal menampung penamaan string batch selesai scan 
        current_batch_num = 1 # Default mulai dari batch no 1
        scanned_materials = set() # set lokal menampung bahan yang sudah terscan 
        found_incomplete = False # penanda jika ditemukan batch yg belum lengkap ter scan
        done_codes_by_batch = {} # mencatat kumpulan kode SAP yg selesai scan per indeks batch 

        for batch_num in range(1, self.target_qty_total + 1): # looping sebanyak jumlah target batch total 
            try:
                batch_data = running_batch_joblist(job_id, batch_num) # tarik status batch dari (database.py) 
            except Exception: # jika terjadi error saat query database 
                logger.exception("Gagal membaca progress job_id=%s batch=%s", job_id, batch_num) # catat log eror 
                return None # kembalikan nilai kosong penanda eror 

            items = batch_data.get("items", []) # ambil list item bahan di dalam batch tersebut
            batch_cache[batch_num] = items # simpan ke cache lokal berdasarkan no urut batch nya 
            if not items: # jika list item kosong
                continue # lanjut ke no batch berikutnya 

            done_codes = set() # set lokal untuk menampung kode bahan yang selesai di dalam interal batch ini 
            all_done = True # anggap seluruh bahan di dalam batch ini sudah selesai ter scan 
            for item in items: # looping memeriksa setiap bahan baku di dalam satu batch 
                sap_rm = item.get("sap_rm") # ambil kode SAP bahan 
                qty_standard = float(item.get("qty_standard") or 0.0) # ambil target jumlah standar timbangan
                qty_terpakai = float(item.get("qty_terpakai") or 0.0) # ambil jumlah aktual lapangan yg tersimpan 
                # Bahan dianggap selesai jika aktual pemakaian sudah mencakup target standard nya
                is_done = qty_terpakai >= qty_standard if qty_standard > 0 else True 
                if is_done and sap_rm: # jika bahan sudah terpenuhi target nya 
                    done_codes.add(sap_rm) # tambahan kode SAP ke set selesai internal batch 
                else: # jika ada minimal 1 bahan yg belum cukup timbangannya 
                    all_done = False # maka status batch dinyatakan belum selesai 

            if all_done: # jika seluruh bahan di dalam no batch ini sudah selesai 
                done_codes_by_batch[batch_num] = done_codes # catat kumpulan kode selesai scan ke no batch tersebut
                completed_batches.append(f"Batch {batch_num}") # tambahan riwayat teks nama batch selesai 
                continue # lanjutkan ke pengecekan ke no batch berikutnya 

            current_batch_num = batch_num # atur batch aktif apk ke no ini untuk dilanjutkan 
            scanned_materials = done_codes # ambil bahan yg sudah sempat di scan/ceklis sebelumnya 
            found_incomplete = True #tandai jika menemukan batch yg belum lengkap 
            break # stop perulangan, tdk perlu cek batch diatasnya 

        if not found_incomplete: # jika ternyata semua baris batch sudah selesai dari DB 
            current_batch_num = min(self.target_qty_total, max(1, self.target_qty_total)) # set ke indeks terakhir 
            scanned_materials = done_codes_by_batch.get(current_batch_num, set()) # ambil data set selesai 

        current_items = batch_cache.get(current_batch_num, []) # ambil isi item resep dari batch aktif resume 
        if not current_items: # jika data item kosong 
            return None # batalkan proses resume 

        # memetakan struktur data database menjadi variabel list dictionary yg dikenali apk ui 
        material_resep = [ 
            {
                "kode_sap": item.get("sap_rm"), # sap_rm menjadi kode_sap 
                "nama": item.get("nama_bahan_baku"), #nama_bahan_baku menjadi nama 
                "target_qty": item.get("qty_standard", 0.0), # mengambil nilai target kualitas standard 
                "satuan": "Kg", # default menggunakan satuan kg (bisa diubah dinamis jika dibutuhkan) 
                "is_scan": item.get("is_scan", True), # penentu apakah barang wajib di scan / ceklist manual 
            }
            for item in current_items 
        ]
        return { # mengembalikan paket data resume dalam bentuk dictionary lengkap 
            "current_batch_num": current_batch_num,
            "completed_batches": completed_batches,
            "scanned_materials": scanned_materials,
            "material_resep": material_resep,
            "all_batches_done": len(completed_batches) >= self.target_qty_total,
        }

    def _sync_resume_ui_state(self):
        # Sinkronkan UI dengan state resume saat halaman scan dibuka ulang.
        if self.all_batches_done: # jika status semua batch dari  database sudah selesai
            self.result_display.configure(text="ALL BATCH COMPLETED!", text_color="#22c55e")
            # ubah tombol start batch menjadi tombol finish untuk menutup total pengerjaan job 
            self.btn_batch_start.configure(state="normal", text="FINISH", fg_color="#22c55e", command=self.finish_job)
            self.entry_barcode.configure(state="disabled") # kunci entry barcode karena tidak perlu scan kembali 

    def setup_scanner_ui(self):
        # Bangun layout halaman scan (header + sidebar + area scan).
        self._clear_main_container() # Bersihkan semua komponen menu utama dari layar

        # Header atas
        self.header = ctk.CTkFrame(self.main_container, height=130, corner_radius=0, fg_color="#1e3d59")
        self.header.pack(side="top", fill="x", pady=0)
        self.header.pack_propagate(False) # kunci tinggi header di 130 pixel 

        # Konten utama bawah header
        self.content_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_container.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))

        title_x = self._render_header_logo() # panggil fungsi penggambaran logo 
        ctk.CTkLabel(
            self.header,
            text="SISTEM SCANNER FORMULASI",
            font=("Franklin Gothic Heavy", 28, "bold"),
            text_color="white",
        ).place(x=title_x, y=30) # pasang judul aplikasi di samping logo 

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
        self.batch_info_label.place(x=title_x, y=80) # letakkan badge dibawah teks judul utama 

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
            command=self.konfirmasi_stop, # panggil fungsi dialog konfirmasi sata tombol keluar di klik 
        ).place(relx=0.85, rely=0.65, anchor="ne")

        ctk.CTkButton(
            self.header,
            text="HISTORY",
            fg_color="#20C997",
            width=100,
            height=35,
            font=("Arial", 12, "bold"),
            command=self.open_history_window,  # panggil fungsi pembuka sub-window log history saat di klik 
        ).place(relx=0.97, rely=0.65, anchor="ne")

        self._build_scanner_body() # panggil fungsi pembangun 3 kolom pembagi area scan 
        self.update_sidebar_lists() # panggil fungsi pembaruan daftar bahan sesuai dengan status scan terkini 

    def _render_header_logo(self):
        # Load dan tampilkan logo di header jika file tersedia.
        try:
            logo_img = Image.open(os.path.join(BASE_DIR, "logo2.png"))
            self.logo_icon = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(80, 80))
            ctk.CTkLabel(self.header, image=self.logo_icon, text="").place(x=20, y=25) # pasang di kiri header 
            return 115 # jika logo sukses di render, beri jarak 115 pixel agar teks judul tidak menabrak 
        except Exception: # jika file logo hilang / rusak 
            logger.exception("Gagal load logo header dari BASE_DIR=%s", BASE_DIR) #catat log eror tanpa stop aplikasi 
            return 30 # kembalikan jarak default 30 pixel 

    def open_history_window(self):
        # Buka window history atau fokus ke window yang sudah terbuka.
        try:
            # periksa apakah sub-window history sudah terbuka
            if hasattr(self, "history_window") and self.history_window and self.history_window.winfo_exists():
                self.history_window.focus_force() # fokus sistem ke jendela riwayat 
                self.history_window.lift() # naikkan jendela riwayat di atas jendela lain
                return # selesai tidak perlu buat baru 

            self.history_window = HistoryWindow(self) # buat instance objek jendela baru dari file (history_window.py)
        except Exception: # jika terjadi eror saat memuat window tambahan
            logger.exception("Gagal membuka history window") # catat log eror sistem 
            self.show_toast_notification("History gagal dibuka", color="red") # notifikasi error ke user 

    def _build_scanner_body(self): 
        # Buat sidebar kiri-kanan dan area scan di tengah. 
        # Sidebar kiri: daftar material scan + tombol start batch
        self.sidebar_left = ctk.CTkFrame(self.content_container, width=300, corner_radius=20, fg_color="#1e293b")
        self.sidebar_left.pack(side="left", fill="y", padx=(0, 10), pady=0)

        # Membuat tombol start batch 
        self.btn_batch_start = ctk.CTkButton(
            self.sidebar_left,
            text=f"START BATCH {self.current_batch_num} >",
            font=("Arial", 15, "bold"),
            height=50,
            fg_color="#3b82f6",
            command=self.start_batch_logic, # panggil fungsi pembuka input saat di tekan 
        )
        self.btn_batch_start.pack(fill="x", padx=15, pady=15) 

        ctk.CTkLabel(self.sidebar_left, text="LIST MATERIAL SCAN", text_color="#38bdf8", font=("Arial", 14, "bold")).pack(pady=(10, 5))
        # frame scroll untuk daftar bahan yg butuh scan 
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
        # frame komponen tengah agar posisi otomatis presisi di tengah  
        center_wrapper = ctk.CTkFrame(self.main_area, fg_color="transparent")
        center_wrapper.place(relx=0.5, rely=0.45, anchor="center")
        # Label teks petunjuk instruksi 
        self.result_display = ctk.CTkLabel(
            center_wrapper,
            text="TEKAN START UNTUK SCAN",
            font=("Arial", 32, "bold"),
            text_color="#94a3b8",
        )
        self.result_display.pack(pady=(0, 20))

        # Komponen kotak entry scanner 
        self.entry_barcode = ctk.CTkEntry(
            center_wrapper,
            width=450,
            height=80,
            justify="center", # set teks di tengah kotak entry 
            font=("Arial", 28),
            placeholder_text="Menunggu start...",
            fg_color="#0f172a",
            text_color="white",
            border_color="#334155",
            state="disabled", # kondisi awal terkunci (disabled) 
        )
        self.entry_barcode.pack(pady=0)

        # Event input scanner: support Enter + debounce saat scanner tidak kirim Enter
        self.entry_barcode.bind("<KeyRelease>", self.auto_scan_handler)
        # Menghubungkan tombol Enter (Return) dari keyboard untuk memicu pembacaan instan tanpa jeda tunda
        self.entry_barcode.bind("<Return>", lambda _e: self.auto_scan_handler(force=True))

    def start_batch_logic(self):
        # Aktifkan batch saat tombol START ditekan.
        self._cancel_scan_debounce() # batalkan timer tunda
        self.scan_inflight = False # reset penanda proses scan sedang berjalan
        self.batch_active = True # ubah status penanda batch aktif menjadi true
        
        # ubah style tombol menjadi warna gelap menandakan proses kerja sedang berjalan
        self.btn_batch_start.configure(
            state="disabled",
            text=f"SCANNING BATCH {self.current_batch_num}...",
            fg_color="#1e3d59",
        )
        
        # 1. BUKA KUNCI INPUT TERLEBIH DAHULU
        self.entry_barcode.configure(state="normal", placeholder_text=f"Scan Batch {self.current_batch_num}...")
        
        # 2. GUNAKAN DELAY 300 MILIDETIK UNTUK MENGHAPUS UUID YANG BARU MASUK
        # Kita beri waktu agar respon backend masuk dulu, baru kita sapu bersih!
        self.after(300, lambda: self.entry_barcode.delete(0, "end"))
        
        # 3. Posisikan kursor dan perbarui teks petunjuk
        self.entry_barcode.focus_set() # paksa kursor langsung aktif di kotak entry scan
        self.result_display.configure(text="Silahkan Scan Barcode", text_color="#38bdf8")

    def auto_scan_handler(self, _event=None, force=False):
        # Tangani input scanner dengan mode debounce + trigger paksa (Enter).
        if not self.batch_active: # jika tombol batch belum aktif 
            return # Abaikan dan batalkan 

        if force: # jika dipicu dengan tombol (enter) 
            self._cancel_scan_debounce() # Batalkan timer tunda 
            self._consume_scan_buffer() # Langsung proses isi entry tanpa menunggu tunda 
            return # selesai 

        self._schedule_scan_debounce() # jika dipicu input manual, jadwalkan timer tunda pemicu otomatis 

    def _cancel_scan_debounce(self):
        # Batalkan callback debounce scan yang masih pending. 
        if self.scan_debounce_after_id is None: # jika tidak ada timer tunda yang aktif, tidak perlu dibatalkan 
            return # hentikan fungsi 

        try: 
            self.after_cancel(self.scan_debounce_after_id) # batalkan eksekusi tunda 
        except Exception: # jika terjadi error
            logger.debug("after_cancel scan debounce gagal/expired", exc_info=True) # catat log debug 
        finally:
            self.scan_debounce_after_id = None # Kosongkan variabel penampung ID timer 

    def _schedule_scan_debounce(self):
        # Jadwalkan eksekusi scan setelah input stabil.
        self._cancel_scan_debounce() # Bersihkan jadwal lama terlebih dahulu 
        # Set jadwal baru : jalankan fungsi _consume_scan_buffer setelah (default 180ms)
        self.scan_debounce_after_id = self.after(self.scan_debounce_ms, self._consume_scan_buffer)

    def _consume_scan_buffer(self):
        # Proses isi entry barcode yang sudah stabil.
        self.scan_debounce_after_id = None # reset ID jadwal 
        if not self.batch_active: # jika batch tidak aktif, batalkan proses scan
            return
        if self.scan_inflight: # Jika proses penyimpanan ke database sedang berjalan, batalkan proses baru untuk mencegah duplikasi data 
            return # Abaikan input baru mencegah duplikasi baris data di postgre

        barcode_data = self.entry_barcode.get().strip().replace("\r", "").replace("\n", "") # Ambil isi teks dalam kotak entry 
        if not barcode_data: # jika kosong 
            return # abaikan input 
        
        now_mono = monotonic() # Ambil catatan waktu internal sistem saat ini
        # Pencegah double scan 
        if (
            barcode_data == self.last_scan_payload # jika isi barcode sama dengan hasil scan terakhir 
            and ((now_mono - self.last_scan_monotonic) * 1000.0) < self.scan_duplicate_guard_ms # jeda waktu di bawah 700 ms 
        ):
            self.entry_barcode.delete(0, "end") # kosongkan entry untuk scan berikutnya
            self.after(50,self.entry_barcode.focus_set)
            return # Batalkan proses, mencegah duplikasi data scan 

        self.scan_inflight = True # Tandai bahwa sistem sedang simpan data 
        try: 
            self.process_scan(barcode_data) # kirim data barcode ke fungsi validator resep 
            self.last_scan_payload = barcode_data # simpan data barcode yang selesai di scan 
            self.last_scan_monotonic = now_mono # simpan catatan waktu saat scan berhasil di proses
            self.entry_barcode.delete(0, "end") # kosongkan entry untuk scan berikutnya 
            self.after(100, self.entry_barcode.focus_set) 
        finally:
                self.after(200,lambda:setattr(self,"scan_inflight",False)) # reset penanda proses simpan data selesai, lanjut menerima input berikutnya

    def process_scan(self, barcode_data):
        # Validasi material scan terhadap resep, lalu simpan ke DB.
        if not self.current_job_id: # jika ID job kosong 
            self.show_toast_notification("Job belum dipilih", color="red") # Notifikasi eror 
            return 

        usage_id = None # Default awal ID baris tabel material usage kosong 
        barcode_pallet_value = barcode_data # Default nilai barcode yg disimpan teks input -

        # Cari item resep yang sap_rm-nya sama dengan barcode hasil scan
        material = next((item for item in self.material_resep if item.get("kode_sap") == barcode_data), None)
        if not material: # jika tidak ditemukan item resep dengan kode SAP yg cocok dengan barcode hasil scan
            # Fallback: anggap barcode_data adalah formulasi_material_usage.id 
            try:
            
                usage_target = get_usage_scan_target(self.current_job_id, self.current_batch_num, barcode_data) 
            except Exception: # jika query ke postgre eror 
                logger.exception( # catat detail baris eror ke sistem log 
                    "Gagal lookup usage_target job_id=%s batch=%s barcode=%s", 
                    self.current_job_id,
                    self.current_batch_num,
                    barcode_data, 
                )
                usage_target = None # Set nilai target kosong

            if usage_target: # jika data ditemukan di database 
                usage_id = usage_target.get("id") # ambil ID utama baris tabel untuk parameter update 
                barcode_pallet_value = usage_target.get("barcode_pallet") or barcode_data # Ambil nama asli 
                usage_sap = usage_target.get("sap_rm") # Ambil kode SAP yang terikat data pengguna
                # Cari ulang kecocokan resep berdasarkan Kode SAP yang terikat pada tabel 
                material = next((item for item in self.material_resep if item.get("kode_sap") == usage_sap), None)

            if not material: # Jika dicari masih tidak ditemukan kecocokan item resep
                self.show_toast_notification("Scan tidak cocok dengan material resep/job aktif", color="red") # Notifikasi eror 
                return # Hentikan proses, bahan di tolak sistem 

        # Simpan konteks material aktif
        self.current_material_data = {
            "sap_rm": material.get("kode_sap", ""), # kode SAP bahan baku yang terdeteksi 
            "nama_bahan_baku": material.get("nama", ""), # nama bahan baku yang terdeteksi 
            "target_qty": material.get("target_qty", 0.0), # berat target bahan baku terdeteksi 
        }

        # Kirim data usage ke DB (batch wajib, scan_at wajib) 
        try:
            update_result = update_material_usage( # fungsi pembaruan data pemakaian bahan baku di (database.py)
                joblist_id=self.current_job_id, # ID job aktif untuk parameter joblist_id di database 
                barcode_pallet=barcode_pallet_value, # 
                sap_rm=self.current_material_data["sap_rm"], # kode SAP bahan baku terdeteksi 
                batch=self.current_batch_num, # angka no batch aktif pengerjaan
                qty_dipakai=self.current_material_data["target_qty"], # berat target bahan baku terdeteksi 
                scan_at=datetime.now(), # catatan waktu saat ini untuk parameter scan_at di database 
                scan_oleh="Admin", # nama pengguna 
                usage_id=usage_id, # Mengirimkan ID jika update, None jika insert baru
            )
            is_saved = bool(update_result.get("saved")) # Ambil status berhasil simpan dari hasil fungsi update_material_usage (database.py)
        except Exception as exc: # jika terjadi error saat menyimpan data ke database
            logger.exception( # catat detail eror ke sistem log 
                "Error process_scan job_id=%s sap_rm=%s batch=%s",  
                self.current_job_id,
                self.current_material_data.get("sap_rm"),
                self.current_batch_num,
            )
            self.show_toast_notification(str(exc), color="red") # Notifikasi error ke user 
            return 

        # Tandai selesai hanya jika update DB berhasil 
        self.scanned_materials.add(self.current_material_data["sap_rm"]) # Tambahkan kode SAP bahan yang berhasil di scan ke set bahan yang sudah selesai
        self.update_sidebar_lists() # Perbarui tampilan daftar bahan sidebar sesuai status terkini 
        self.check_all_materials_completed() # Periksa apakah seluruh bahan di batch sudah selesai untuk lanjut ke penyelesaian batch 

        if is_saved: # Jika data berhasil disimpan ke database, tampilkan notifikasi sukses 
            self.show_toast_notification("Data berhasil di-update", color="green") # Notifikasi sukses ke

            #  INTEGRASI NODE-RED 
            try:
                # Siapkan data (payload) yang mau dikirim ke PLC lewat Node-RED
                payload = {
                    "joblist_id": self.current_job_id, # Mengambil id aktual yang sedang aktif di aplikasi scanner 
                    "batch": self.current_batch_num,# Mengambil no urut batch yang sedang berjalan 
                    "sap_rm": self.current_material_data["sap_rm"], # Mengambil data kode standar material SAP dari bahan baku sukses scan 
                    "nama_bahan": self.current_material_data["nama_bahan_baku"], # Mengambil data asli dari bahan baku scan
                    "qty": self.current_material_data["target_qty"], # Mengambil nilai angka target timbangan 
                    "status_scan": "SUCCESS" # Tambah teks penanda 
                }
                
                # Alamat URL Node-RED disesuaikan dengan node [post] /update_plc 
                node_red_url = "http://localhost:1880/update_plc"
                
                # Kirim data menggunakan metode POST secara async/timeout pendek agar UI tidak ngefreeze
                requests.post(node_red_url, json=payload, timeout=1.0)
                logger.info(f"Berhasil mengirim data scan {barcode_data} ke Node-RED")
            except Exception as e:
                logger.error(f"Gagal interkoneksi ke Node-RED: {e}")

        else: # jika data tidak berhasil disimpan ke database, tampilkan notifikasi eror  
            self.show_toast_notification("Data gagal di-update", color="red") # notifikasi eror ke user 

    def manual_check_handler(self, kode_sap): 
        # Checklist manual untuk item non-scan (toggle). 
        if not self.batch_active: # Jika tombol start batch belum diaktifkan oleh user 
            return # Abaikan input checklist manual 
        
        # Cari item resep yang sesuai dengan kode SAP dari (kode_sap) parameter fungsi 
        material = next((item for item in self.material_resep if item.get("kode_sap") == kode_sap), None) 
        if not material: # Jika tidak ditemukan item resep dengan kode SAP yang cocok
            self.show_toast_notification("Material tidak ditemukan", color="red") # Notifikasi eror ke user 
            return # Hentikan proses checklist manual 

        is_checked = kode_sap in self.scanned_materials # Tentukan status checklist saat ini (tercentang/tidak)
        qty_target = float(material.get("target_qty") or 0.0) # Ambil data jumlah volume target liter/kg 
        qty_update = 0.0 if is_checked else qty_target # Jika sudah tercentang, update menjadi 0 (batal checklist), jika belum tercentang update menjadi target (checklist) 

        try:
            update_material_usage( # simpan perubahan checklist manual ke database menggunakan fungsi update_material_usage (database.py)
                joblist_id=self.current_job_id, # ID job aktif untuk parameter joblist_id di database 
                barcode_pallet=kode_sap or "", # Gunakan kode_sap sebagai barcode_pallet untuk membedakan data checklist manual di database 
                sap_rm=kode_sap, # kode SAP bahan baku yang di checklist manual 
                batch=self.current_batch_num, # angka no batch aktif pengerjaan 
                qty_dipakai=qty_update, # mengirimkan angka aktual pemakaian sesuai dengan status checklist 
                scan_at=datetime.now(), # catatan waktu saat ini untuk parameter scan_at di database 
                scan_oleh="Admin", # nama pengguna untuk parameter scan_oleh di (database.py) 
            )
        except Exception as exc: # jika terjadi error saat menyimpan perubahan checklist manual ke database 
            logger.exception( # catat detail eror ke sistem log
                "Error manual_check_handler job_id=%s sap_rm=%s batch=%s", # format log 
                self.current_job_id, 
                kode_sap, 
                self.current_batch_num,
            )
            self.show_toast_notification(str(exc), color="red") # 
            return # Batalkan proses checklist manual 

        if is_checked: # Jika item sudah tercentang sebelumnya 
            self.scanned_materials.remove(kode_sap) # Hapus dari set bahan yang sudah selesai (batal checklist)
        else: # jika item belum tercentang sebelumnya 
            self.scanned_materials.add(kode_sap) # tambahkan ke set bahan yang sudah selesai (checklist)

        self.update_sidebar_lists() # Perbarui tampilan daftar bahan sidebar sesuai status terkini 
        self.check_all_materials_completed() # Periksa apakah seluruh bahan di batch sudah selesai 

    def check_all_materials_completed(self):
        # Jika semua item batch selesai, lanjut ke handler selesai batch. 
        if len(self.scanned_materials) == len(self.material_resep): # jika jumlah bahan yg sudah terscan sama dengan jumlah total bahan di resep batch 
            self.handle_batch_complete() # panggil fungsi penyelesaian batch 

    def handle_batch_complete(self):
        # Selesaikan batch aktif: lanjut batch berikutnya atau finalisasi job.
        self._cancel_scan_debounce() # Batalkan timer tunda jika masih aktif 
        self.scan_inflight = False # Reset penanda proses scan sedang berjalan 
        self.batch_active = False # set status batch aktif menjadi false, tanda proses scan batch ini selesai 
        self.result_display.configure(text=f"BATCH {self.current_batch_num} SELESAI!", text_color="#22c55e") 
        self.entry_barcode.configure(state="disabled") # kunci input scanner 

        if self.current_batch_num < self.target_qty_total: 
            # Masih ada batch berikutnya
            self.completed_batches.append(f"Batch {self.current_batch_num}") # Tambahkan batch yang baru selesai ke daftar riwayat batch selesai
            self.current_batch_num += 1 # Naikkan no batch aktif ke no berikutnya 
            self.scanned_materials.clear() # Reset set bahan yang sudah selesai untuk batch berikutnya 
            # Aktifkan kembali tombol start untuk memulai batch berikutnya
            self.btn_batch_start.configure( 
                state="normal",
                text=f"START BATCH {self.current_batch_num} >", 
                fg_color="#3b82f6",
            )
            self.batch_info_label.configure(  # Perbarui info job & batch di header 
                text=f"JOB: {self.selected_job_no} | BATCH: {self.current_batch_num}/{self.target_qty_total}"
            )
        else: 
            # Semua batch selesai, tombol jadi FINISH
            self.result_display.configure(text="ALL BATCH COMPLETED!", text_color="#22c55e") 
            self.btn_batch_start.configure(state="normal", text="FINISH", fg_color="#22c55e", command=self.finish_job) 
        
        self.update_sidebar_lists() # Panggil fungsi pembaruan daftar bahan

    def finish_job(self):
        # Set status job menjadi selesai (2) di database.
        if not self.current_job_id: # jika ID job kosong 
            self.show_toast_notification("Job tidak valid", color="red") # notifikasi eror 
            return # batalkan proses penyelesaian job 

        if update_job_status(self.current_job_id, 2): # panggil fungsi update_job_status (database.py) untuk set status job (2) 
            self.show_toast_notification("Job berhasil diselesaikan", color="#22c55e") # notifikasi sukses 
            try: 
                payload = {
                "job_id": self.current_job_id,
                "nomor_job": self.selected_job_no, 
                "status": "SELESAI", 
                "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                # Kirim data ke Node-RED (misal Node-RED jalan di port 1880)
                requests.post("http://localhost:1880/api/job-selesai", json=payload, timeout=2) 
            except Exception as e: 
                logger.error(f"Gagal mengirim data ke Node-RED: {e}")    

            self.after(1500, self.show_joblist_selector) # setelah 1.5 detik, kembali ke hal pemilihan jb utama 
        else: # jika update status jb gagal
            self.show_toast_notification("Gagal update status job", color="red") 
 
    def update_sidebar_lists(self):
        # Render ulang daftar item di sidebar kiri dan kanan 
        # Bersihkan isi lama agar tidak duplikat
        for widget in self.scroll_sidebar_left.winfo_children(): 
            widget.destroy() 
        for widget in self.scroll_sidebar_right.winfo_children(): 
            widget.destroy()

        # Riwayat batch yang sudah selesai
        if self.completed_batches: # jika ada batch selesai, tampilkan riwayat batch diatas bahan daftar scan (sidebar kiri)
            ctk.CTkLabel( 
                self.scroll_sidebar_left,
                text="RIWAYAT BATCH:",
                font=("Arial", 11, "bold"),
                text_color="#94a3b8", 
            ).pack(anchor="w", padx=10)
            for batch in self.completed_batches: # Looping menampilkan semua nama batch sukses scan yang terdaftar 
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

        for item in self.material_resep: # Looping memproses setiap baris bahan baku resep aktif
            self._render_material_item(item) # panggil fungsi penggambaran item grafis ke sidebar 

    def _render_material_item(self, item):
        # Tampilkan item material ke list scan atau checklist manual.
        nama = (item.get("nama") or "-").upper() # Ambil nama bahan baku 
        qty = item.get("target_qty", 0) # Ambil berat target kuantitas bahan baku 
        satuan = item.get("satuan", "Kg") # Ambil teks satuan bahan baku (default Kg jika kosong) 
        kode_sap = item.get("kode_sap") # Ambil kode SAP material bahan baku 
        is_done = kode_sap in self.scanned_materials # Logika cek status pengerjaan item bahan aktif saat ini 

        marker = "[OK]" if is_done else "[ ]" # tanda status checklist
        text = f"{marker} {nama} ({qty} {satuan})"

        # Material scan barcode -> sidebar kiri
        if item.get("is_scan", True):  #jika dari database is_scan bernilai true 
            frame = ctk.CTkFrame(self.scroll_sidebar_left, fg_color="#064e3b" if is_done else "#334155", height=35)
            frame.pack(fill="x", pady=2, padx=10)
            ctk.CTkLabel(frame, text=text, text_color="white", font=("Arial", 11)).pack(side="left", padx=10)
            return # done, keluar dari fungsi 

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
            command=lambda code=kode_sap: self.manual_check_handler(code), # klik checkbox akan memicu fungsi manual_check_handler dgn parameter kdoe_sap 
        )
        if is_done: # jika status item selesai, tampilkan checkbox dlm kondisi tercentang 
            checkbox.select() 
        checkbox.pack(side="right", padx=10)

    def eksekusi_keluar(self, window_target):
        # Keluar dari sesi scan dan kembali ke joblist.
        try:
            window_target.destroy()
        except Exception:
            logger.exception("Gagal menutup window konfirmasi")

        self._reset_scan_state()
        self.show_joblist_selector()

    def konfirmasi_stop(self):
        # Popup konfirmasi saat user ingin berhenti dari halaman scan.
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
        #Update jam di header tiap detik saat mode scanning aktif.
        if self.is_scanning and hasattr(self, "datetime_label"):
            self.datetime_label.configure(text=datetime.now().strftime("%A, %d %B %Y\n%H:%M:%S"))
            self.after(1000, self.update_clock)


if __name__ == "__main__":
    # Jalankan API internal sebagai thread daemon
    start_api_server_in_thread()

    # Jalankan aplikasi desktop
    app = AppScanner()
    app.mainloop()
