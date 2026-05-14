import customtkinter as ctk 
import os 
import psycopg2
from psycopg2 import extras # Dibutuhkan untuk RealDictCursor agar data sinkron dengan UI 
from PIL import Image
from datetime import datetime
from history_window import HistoryWindow
from api_server import start_api_server_in_thread
from dotenv import load_dotenv
from database import get_connection

# Load konfigurasi environment
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 


class JoblistSelector(ctk.CTkFrame):
    def __init__(self, master, on_job_selected):
        super().__init__(master, fg_color="#0f172a")
        self.on_job_selected = on_job_selected
        self.setup_ui()

    def setup_ui(self):
        # 1. Hapus total 
        for widget in self.winfo_children():
            widget.destroy()

        # 2. Main container
        self.main_container = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=0)
        self.main_container.pack(fill="both", expand=True)

        # 3. HEADER
        self.header = ctk.CTkFrame(self.main_container, height=130, corner_radius=0, fg_color="#1e3d59")
        self.header.pack(side="top", fill="x", pady=0) 

        self.content_area = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True, padx=40, pady=(0)) 

        ctk.CTkLabel(self.content_area, text="Joblist Formulasi", 
                     font=("Arial", 28, "bold"), text_color="white").pack(anchor="w", pady=(20, 10))

        # 5. TABEL
        self.table_frame = ctk.CTkFrame(self.content_area, fg_color="#1e293b", corner_radius=15)
        self.table_frame.pack(fill="x", pady=0)

        self.render_job_rows()

        # Header Baris Tabel
        header_row = ctk.CTkFrame(self.table_frame, fg_color="#334155", height=40)
        header_row.pack(fill="x", padx=10, pady=(10, 5))
        header_row.pack_propagate(False)
        
        headers = [
            ("NO", 50), ("NOMOR JOB", 180), ("TANGGAL", 150), 
            ("RESEP TARGET", 250), ("TARGET QTY", 120), ("STATUS", 120), ("ACTIONS", 120)
        ]
        
        for text, width in headers:
            ctk.CTkLabel(header_row, text=text, width=width, font=("Arial", 12, "bold"), 
                         text_color="#94a3b8", anchor="w").pack(side="left", padx=10)

        # 5. DATA FETCHING
        jobs = self.fetch_jobs_from_db()
        
        # 6. RENDER DATA
        for index, job in enumerate(jobs):
            row = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=5)
            
            status_map = {
                0: ("PENDING", "#facc15"), # Kuning
                1: ("ON PROGRESS", "#38bdf8"), # Biru muda
                2: ("SELESAI", "#22c55e") # Hijau
            }
            status_text, status_color = status_map.get(job['status'], ("UNKNOWN", "white"))

            # Render Kolom
            ctk.CTkLabel(row, text=str(index+1), width=50, text_color="white", anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=job['nomor_job'], width=180, text_color="white", font=("Arial", 13, "bold"), anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=str(job['tanggal']), width=150, text_color="white", anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=f"{job['nama_resep']}", width=250, text_color="white", anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=f"{job['target_qty']} Batch", width=120, text_color="white", anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=status_text, width=120, text_color=status_color, font=("Arial", 12, "bold"), anchor="w").pack(side="left", padx=10)

            # Tombol Action: Dinamis
            btn_text = "Lihat Detail" if job['status'] == 2 else "PILIH JOB"
            btn_color = "#334155" if job['status'] == 2 else "#1d4ed8"
            
            ctk.CTkButton(
                row, text=btn_text, width=120, height=32, 
                fg_color=btn_color,
                font=("Arial", 12, "bold"),
                command=lambda j=job: self.start_job(j) 
            ).pack(side="left", padx=10)
            
    def get_all_jobs_from_db(self): 
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # 2. Query dengan JOIN untuk mendapatkan Nama Resep dari tabel Master
            query = """
                SELECT 
                    j.id, 
                    j.nomor_job, 
                    j.tanggal, 
                    j."resepId", 
                    j.target_qty, 
                    j.status, 
                    r.nama_resep 
                FROM qc.formulasi_joblist j 
                LEFT JOIN qc.master_resep r ON j."resepId" = r.id 
                WHERE j.status IN (0, 1) 
                ORDER BY j.status ASC, j.tanggal DESC 
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            return results

        except Exception as e:
            print(f"❌ Database Error saat tarik Joblist: {e}")
            return []
            
        finally:
            # 3. Selalu tutup koneksi
            if conn:
                conn.close()

class AppScanner(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistem Scanner Formulasi")
        self.geometry("1400x850")
        self.configure(fg_color="#0f172a")
        
        # koneksi database 
        try:
            import psycopg2 # Gunakan psycopg2 untuk PostgreSQL
            from psycopg2.extras import RealDictCursor
            
            self.db = psycopg2.connect(
                host="localhost",
                database="postgres",
                user="postgres",     
                password="",         
                port="5432"         
            )
            self.cursor = self.db.cursor(cursor_factory=RealDictCursor)
            print("Database Connected Successfully!")
        except Exception as e:
            print(f"Database Connection Error: {e}")

        # CONTAINER UTAMA
        self.main_container = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=0)
        self.main_container.pack(fill="both", expand=True)
        
    
        self.is_scanning = False
        self.current_batch = 1
        self.completed_batches = []
        self.batch_active = False
        self.current_selected_sap = None
        self.selected_job_no = None
        self.current_job_id = None      
        self.material_resep = []
        self.scanned_materials = set()
        
        self.current_material_data = {
            'sap_rm': '',
            'nama_bahan_baku': '',
            'target_qty': 0.0
        }

        self.show_joblist_selector()
        self.bind("<Escape>", lambda e: self.konfirmasi_stop() if self.is_scanning else None)

    def eksekusi_keluar(self, window_target):
        try:
            window_target.destroy()
        except:
            pass
        
        self.is_scanning = False
        
        # Bersihkan layar utama
        for widget in self.main_container.winfo_children():
            widget.destroy()
            
        # Panggil fungsi tampilkan joblist
        self.tampilkan_joblist()

    def tampilkan_joblist(self):
        # 1. Bersihkan ulang untuk memastikan
        for widget in self.main_container.winfo_children():
            widget.destroy()

        print("DEBUG: Menampilkan Joblist")

        # 2. Header Judul
        ctk.CTkLabel(self.main_container, text="Joblist Formulasi", 
                     font=("Arial", 28, "bold"), text_color="white").pack(pady=(20, 10), padx=30, anchor="w")

        # 3. Buat Frame Tabel
        container_tabel = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        container_tabel.pack(fill="both", expand=True, padx=30, pady=10)

        # 4. Ambil Data (Ganti self.all_jobs dengan sumber data kamu)
        # Jika error get_all_jobs muncul lagi, pastikan data jobs sudah terisi di awal
        if hasattr(self, 'all_jobs') and self.all_jobs:
            for index, job in enumerate(self.all_jobs):
                self.buat_baris_tabel_custom(container_tabel, job, index)
        else:
            ctk.CTkLabel(container_tabel, text="Data Job tidak ditemukan atau kosong", 
                         font=("Arial", 14)).pack(pady=20)

    def manual_check_handler(self, kode_sap):
        # 1. Logika internal (tambahkan ke scanned_materials)
        self.scanned_materials.add(kode_sap)
        
        # 2. PANGGIL SIMPAN DATABASE DISINI
        self.save_material_usage(kode_sap) 
        
        # 3. Refresh UI
        self.update_sidebar_lists()

    def save_material_usage(self, barcode):
        try:
            # Gunakan data material yang sedang aktif di-scan
            material = self.current_material_data 
            
            # Query INSERT ke tabel sesuai ERD: formulasi_material_usage
            query = """
                INSERT INTO "qc"."formulasi_material_usage" 
                ("joblistId", "barcode_pallet", "sap_rm", "nama_bahan_baku", "qty_dipakai", "batch", "scan_at", "scan_oleh") 
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
            """
            values = (
                self.current_job_id,     
                barcode,                  # Barcode pallet
                material['sap_rm'],       # Kode SAP
                material['nama_bahan_baku'], 
                material['target_qty'],   # Nilai ini yang akan menambah angka di Web 
                self.current_batch, 
                "Admin"
            )

            self.cursor.execute(query, values)
            self.db.commit()
            print(f"DEBUG: Berhasil sinkron")
            
        except Exception as e:
            print(f"Error Database: {e}")
            self.db.rollback()

    def show_toast_notification(self, message, color="green"):
        # Buat label notifikasi kecil di atas atau bawah
        toast = ctk.CTkLabel(self, text=message, fg_color=color, text_color="white", corner_radius=10)
        toast.place(relx=0.5, rely=0.1, anchor="center")
        
        # Hilangkan otomatis setelah 2 detik
        self.after(2000, toast.destroy)

    def on_job_selected(self, job_id, job_no, target_qty, resep_id):
        self.material_resep = self.fetch_materials_by_resep(job_id) 
        
        self.update_sidebar_lists()
        self.prepare_scanning_area(job_id, job_no, target_qty, resep_id)

    def fetch_materials_by_resep(self, job_id):
        try:
            conn = get_connection()
            # Menggunakan RealDictCursor agar hasil query berupa dictionary
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Query tetap mengambil data asli dari database
            query = """
                SELECT 
                    mi.sap_rm AS kode_sap, 
                    mi.nama_bahan_baku AS nama,
                    mi.no_scan,
                    (mi.qty_standard * j.target_qty) AS target_qty,
                    CASE
                        WHEN mi.nama_bahan_baku ILIKE '%%AIR%%' THEN 'Liter' 
                        ELSE 'Kg'
                    END AS satuan 
                FROM qc.master_resep_item mi
                JOIN qc.formulasi_joblist j ON j."resepId" = mi."resepId"
                WHERE j.id = %s 
            """
            cursor.execute(query, (job_id,))
            raw_materials = cursor.fetchall()
            
            # proses data logika nama bahan baku
            final_materials = []
            for item in raw_materials:
                if "AIR" in item['nama'].upper():
                    item['is_scan'] = False
                else:
                    # Jika bukan air, ikuti logika: jika no_scan False maka is_scan True
                    item['is_scan'] = not item['no_scan']
                
                final_materials.append(item)
            
            conn.close()
            
            # Simpan ke attribute agar Sidebar bisa membaca
            self.material_resep = final_materials
            return final_materials
            
        except Exception as e:
            print(f"Error Database: {e}")
            return []

    def get_all_jobs_from_db(self):
        try:
            conn = get_connection()
            # Gunakan RealDictCursor agar kita bisa memanggil data dengan nama kolom
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            query = """
                SELECT 
                    id, 
                    nomor_job, 
                    tanggal, 
                    "resepId", 
                    target_qty, 
                    status 
                FROM qc.formulasi_joblist 
                ORDER BY tanggal DESC
            """
            cursor.execute(query)
            jobs = cursor.fetchall()
            conn.close()
            return jobs
        except Exception as e:
            # message error
            print(f"Error Database saat ambil Joblist: {e}")
            return []
        
    def show_joblist_selector(self):
        # 1. Bersihkan layar scanner sebelumnya
        for widget in self.main_container.winfo_children():
            widget.destroy()

        # 2. Reset status aplikasi
        self.is_scanning = False
        self.batch_active = False
        self.main_container.configure(fg_color="#0f172a") 

        # 3. Header Judul
        title_lbl = ctk.CTkLabel(
            self.main_container, 
            text="Daftar Joblist Formulasi", 
            font=("Arial", 28, "bold"), 
            text_color="white"
        )
        title_lbl.pack(anchor="w", padx=40, pady=(30, 10))

        # 4. Header Tabel (Kolom Statis)
        header_bar = ctk.CTkFrame(self.main_container, fg_color="#1e293b", height=45, corner_radius=5)
        header_bar.pack(fill="x", padx=40, pady=10)
        header_bar.pack_propagate(False)

        headers = [
            ("NOMOR JOB", 20), ("TANGGAL", 200), ("RESEP TARGET", 350), 
            ("TARGET QTY", 550), ("STATUS", 700), ("ACTION", 900)
        ]
        for text, x_pos in headers:
            ctk.CTkLabel(
                header_bar, text=text, font=("Arial", 11, "bold"), text_color="#94a3b8"
            ).place(x=x_pos, y=10)

        # 5. Area Scrollable untuk List Job
        scroll_frame = ctk.CTkScrollableFrame(
            self.main_container, 
            fg_color="transparent", 
            label_text=""
        )
        scroll_frame.pack(fill="both", expand=True, padx=30, pady=5)

        # 6. Ambil data dari database
        jobs = self.get_all_jobs_from_db() 

        if not jobs:
            ctk.CTkLabel(
                scroll_frame, 
                text="TIDAK ADA JOBLIST AKTIF DI DATABASE", 
                font=("Arial", 16), 
                text_color="#475569"
            ).pack(pady=100)
            return

        # 7. Looping Baris Data
        for job in jobs:
            # Gunakan .get() dengan fallback jika kolom berbeda
            val_status = job.get('status', 0) 
            job_no = job.get('job_no') or job.get('nomor_job') or "N/A"
            resep = job.get('nama_produk') or job.get('nama_resep') or "No Name"
            
            # Logika Status: 2 = SELESAI, 1 = PROSES, 0 = PENDING
            if val_status == 2:
                status_txt, status_clr = "SELESAI", "#22c55e"
                btn_txt, btn_clr = "Lihat Detail", "#334155"
                hvr_clr = "#475569"
                # Jika sudah selesai, mungkin tombolnya didisable atau buka detail
                cmd = lambda j=job: self.start_job(j)
            else:
                status_txt, status_clr = "PENDING", "#facc15"
                btn_txt, btn_clr = "PILIH JOB", "#1d4ed8"
                hvr_clr = "#2563eb"
                cmd = lambda j=job: self.start_job(j)

            # Frame Baris (Row)
            row = ctk.CTkFrame(scroll_frame, fg_color="#1e293b", height=60, corner_radius=8)
            row.pack(fill="x", pady=5, padx=10)
            row.pack_propagate(False)

            # Isi Data ke Label (Posisi X harus sama dengan Header) 
            ctk.CTkLabel(row, text=job_no, font=("Arial", 13, "bold"), text_color="white").place(x=20, y=18)
            ctk.CTkLabel(row, text=str(job.get('created_at', job.get('tanggal', ''))), font=("Arial", 12), text_color="#94a3b8").place(x=200, y=18)
            ctk.CTkLabel(row, text=resep, font=("Arial", 12), text_color="white").place(x=350, y=18)
            
            target_qty = f"{job.get('target_batch', '1')} Batch"
            ctk.CTkLabel(row, text=target_qty, font=("Arial", 12), text_color="white").place(x=550, y=18)
            
            ctk.CTkLabel(row, text=status_txt, text_color=status_clr, font=("Arial", 12, "bold")).place(x=700, y=18)

            # Tombol Action
            ctk.CTkButton(
                row, text=btn_txt, fg_color=btn_clr, hover_color=hvr_clr,
                width=120, height=32, font=("Arial", 12, "bold"),
                command=cmd
            ).place(x=900, y=14)

    def show_detail(self, job):
         # Fungsi ini dipanggil saat tombol Lihat Detail diklik
        print(f"Membuka detail untuk job: {job.get('nomor_job')}")
        # Sementara tampilkan popup saja agar tidak error
        from tkinter import messagebox
        messagebox.showinfo("Detail Job", f"Nomor Job: {job.get('nomor_job')}\nStatus: Selesai")

    def prepare_scanning_area(self, job_id, job_no, target_qty, resep_id):
        self.selected_job_id = job_id  # Menyimpan id dari database
        self.selected_job_no = job_no
        self.target_qty_total = int(target_qty)
        self.is_scanning = True
    
        self.material_resep = self.fetch_materials_by_resep(job_id) 
        
        self.setup_scanner_ui()
        self.update_clock()

    def reset_job_status(self, job_no):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE qc.formulasi_joblist SET status = 0 WHERE nomor_job = %s', (job_no,))
            conn.commit()
            conn.close()
        except: pass

    def setup_scanner_ui(self):
        # 1. Bersihkan semua widget lama
        for widget in self.main_container.winfo_children():
            widget.destroy()

        # 2. Reset tampilan dasar
        self.main_container.configure(fg_color="#0f172a")

        # 3. HEADER (Nempel paling atas)
        self.header = ctk.CTkFrame(self.main_container, height=130, corner_radius=0, fg_color="#1e3d59")
        self.header.pack(side="top", fill="x", pady=0)
        self.header.pack_propagate(False) 

        # 4. AREA CONTENT UTAMA 
        self.content_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_container.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))

        # DRAW HEADER CONTENT
        try:
            logo_img = Image.open(os.path.join(BASE_DIR, "logo2.png"))
            self.logo_icon = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(80, 80))
            ctk.CTkLabel(self.header, image=self.logo_icon, text="").place(x=20, y=25)
            title_x = 115 
        except: 
            title_x = 30

        ctk.CTkLabel(self.header, text="SISTEM SCANNER FORMULASI", 
                     font=("Franklin Gothic Heavy", 28, "bold"), text_color="white").place(x=title_x, y=30)
        
        self.batch_info_label = ctk.CTkLabel(
            self.header, 
            text=f"JOB: {self.selected_job_no} | BATCH: {self.current_batch_num}/{self.target_qty_total}", 
            font=("Arial", 16, "bold"), text_color="#38bdf8", fg_color="#0f172a", 
            corner_radius=10, padx=15, pady=5
        )
        self.batch_info_label.place(x=title_x, y=80)

        # Jam & Tombol (Stop/History)
        self.datetime_label = ctk.CTkLabel(self.header, text="", font=("Arial", 14, "bold"), text_color="#38bdf8")
        self.datetime_label.place(relx=0.97, rely=0.15, anchor="ne")

        ctk.CTkButton(self.header, text="STOP JOB", fg_color="#ef4444", font=("Arial", 12, "bold"), 
                      width=100, height=35, command=self.konfirmasi_stop).place(relx=0.85, rely=0.65, anchor="ne")
        
        ctk.CTkButton(self.header, text="HISTORY", fg_color="#20C997", font=("Arial", 12, "bold"), 
                      width=100, height=35).place(relx=0.97, rely=0.65, anchor="ne")

        # SIDEBAR KIRI
        self.sidebar_left = ctk.CTkFrame(self.content_container, width=300, corner_radius=20, fg_color="#1e293b") 
        self.sidebar_left.pack(side="left", fill="y", padx=(0, 10), pady=0)
        
        self.btn_batch_start = ctk.CTkButton(self.sidebar_left, text=f"START BATCH {self.current_batch_num} ▶", 
                                             font=("Arial", 15, "bold"), height=50, fg_color="#3b82f6", 
                                             command=self.start_batch_logic)
        self.btn_batch_start.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(self.sidebar_left, text="LIST MATERIAL SCAN", text_color="#38bdf8", font=("Arial", 14, "bold")).pack(pady=(10, 5))
        self.scroll_sidebar_left = ctk.CTkScrollableFrame(self.sidebar_left, fg_color="transparent")
        self.scroll_sidebar_left.pack(expand=True, fill="both", padx=10, pady=5)

        # SIDEBAR KANAN
        self.sidebar_right = ctk.CTkFrame(self.content_container, width=280, corner_radius=20, fg_color="#1e293b")
        self.sidebar_right.pack(side="right", fill="y", padx=(10, 0), pady=0)
        
        ctk.CTkLabel(self.sidebar_right, text="CHECKLIST", text_color="#fbbf24", font=("Arial", 15, "bold")).pack(pady=15)
        self.scroll_sidebar_right = ctk.CTkScrollableFrame(self.sidebar_right, fg_color="transparent")
        self.scroll_sidebar_right.pack(expand=True, fill="both", padx=10, pady=5) 

        # area tengah
        self.main_area = ctk.CTkFrame(self.content_container, corner_radius=20, fg_color="#1e293b") 
        self.main_area.pack(side="left", expand=True, fill="both", pady=0)
        
        # 1. Gunakan Frame tambahan di dalam main_area
        self.center_wrapper = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.center_wrapper.place(relx=0.5, rely=0.45, anchor="center") # relx & rely adalah kunci posisi

        # 2. Teks Instruksi
        self.result_display = ctk.CTkLabel(self.center_wrapper, text="TEKAN START UNTUK SCAN", 
                                           font=("Arial", 32, "bold"), text_color="#94a3b8")
        self.result_display.pack(pady=(0, 20)) # Jarak bawah teks ke kotak entry

        # 3. Kotak Entry (Kolom Scan)
        self.entry_barcode = ctk.CTkEntry(self.center_wrapper, width=450, height=80,
                                          justify="center", font=("Arial", 28), 
                                          placeholder_text="Menunggu start...", 
                                          fg_color="#0f172a", text_color="white", 
                                          border_color="#334155", state="disabled") 
        self.entry_barcode.pack(pady=0)
        
        # Bindings
        self.entry_barcode.bind('<KeyRelease>', self.auto_scan_handler) 
        self.entry_barcode.bind('<Return>', lambda e: self.auto_scan_handler(e, force=True))
        
        self.update_sidebar_lists() 

    def eksekusi_keluar(self, window_target):
        # 1. Tutup popup konfirmasi
        try:
            window_target.destroy()
        except:
            pass
        
        # 2. Matikan status scanning
        self.is_scanning = False
        
        # 3. Bersih layar
        for widget in self.main_container.winfo_children():
            widget.destroy()

        # 4. PANGGIL MENU UTAMA
        if hasattr(self, 'setup_ui'):
            self.setup_ui()
        elif hasattr(self, 'tampilkan_joblist'):
            self.tampilkan_joblist()
        else:
            print("DEBUG: Fungsi Tidak Ditemukan!")

    def start_batch_logic(self):
        self.batch_active = True
        self.btn_batch_start.configure(state="disabled", text=f"SCANNING BATCH {self.current_batch_num}...", fg_color="#1e3d59")
        self.entry_barcode.configure(state="normal", placeholder_text=f"Scan Batch {self.current_batch_num}...")
        self.entry_barcode.focus_set()
        self.result_display.configure(text=f"Silahkan Scan Barcode", text_color="#38bdf8")
        self.update_sidebar_lists()

    def auto_scan_handler(self, event=None, force=False):
        # 1. Ambil teks dari entry/inputan barcode
        barcode_data = self.entry_barcode.get().strip()
        
        if barcode_data:
            # 2. Kirim data barcode tersebut ke fungsi process_scan
            self.process_scan(barcode_data) 
            
            # 3. Kosongkan lagi inputannya untuk scan berikutnya
            self.entry_barcode.delete(0, 'end')

    def process_scan(self, barcode_data): 
        print(f"Memproses scan: {barcode_data}")
        
        # 1. Cari data material lengkap dari list resep berdasarkan barcode/SAP
        material_terpilih = next((item for item in self.material_resep if item['kode_sap'] == barcode_data), None)
        
        if material_terpilih:
            self.current_material_data = {
                'sap_rm': material_terpilih.get('kode_sap') or material_terpilih.get('sap_rm'),
                'nama_bahan_baku': material_terpilih.get('nama_bahan_baku') or material_terpilih.get('nama_bahan'),
                'target_qty': material_terpilih.get('target_qty') or material_terpilih.get('qty_dipakai')
            }
            
            # 3. Tandai sudah di-scan
            self.scanned_materials.add(barcode_data)
            
            # 4. Jalankan fungsi simpan ke database (formulasi_material_usage)
            self.save_material_usage(barcode_data)
            
            # 5. Update tampilan
            self.update_sidebar_lists()
            self.show_toast_notification("DATA TERSIMPAN KE DATABASE!", color="green")
        else:
            self.show_toast_notification("Material tidak cocok dengan resep!", color="red")

    def manual_check_handler(self, barcode):
        if not self.batch_active: return 
        if barcode in self.scanned_materials: self.scanned_materials.remove(barcode)
        else: self.scanned_materials.add(barcode)
        self.update_sidebar_lists()
        self.check_all_materials_completed()

    def check_all_materials_completed(self):
        if len(self.scanned_materials) == len(self.material_resep): self.handle_batch_complete()

    def handle_batch_complete(self):
        self.batch_active = False
        self.result_display.configure(text=f"BATCH {self.current_batch_num} SELESAI!", text_color="#22c55e")
        self.entry_barcode.configure(state="disabled")
        if self.current_batch_num < self.target_qty_total:
            self.completed_batches.append(f"Batch {self.current_batch_num}")
            self.current_batch_num += 1
            self.scanned_materials.clear()
            self.btn_batch_start.configure(state="normal", text=f"START BATCH {self.current_batch_num} ▶", fg_color="#3b82f6")
            self.batch_info_label.configure(text=f"JOB: {self.selected_job_no} | BATCH: {self.current_batch_num}/{self.target_qty_total}")
        else:
            self.result_display.configure(text="ALL BATCH COMPLETED!", text_color="#22c55e")
            self.btn_batch_start.configure(state="normal", text="FINISH ✔", fg_color="#22c55e", command=self.finish_job)
        self.update_sidebar_lists()

    def finish_job(self):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Update status job menjadi 2 (Selesai)
            query = "UPDATE qc.formulasi_joblist SET status = 2 WHERE nomor_job = %s"
            cursor.execute(query, (self.selected_job_no,))
            
            conn.commit()
            conn.close()
            
            self.show_toast_notification("DATA TERSIMPAN KE DATABASE!", color="#22c55e")
            
            # Kembali ke daftar job setelah 1.5 detik
            self.after(1500, self.show_joblist_selector)
            
        except Exception as e:
            print(f"Gagal Finalisasi: {e}")
            self.show_toast_notification("GAGAL UPDATE DATABASE!", color="red")

    def update_sidebar_lists(self):
        # 1. Bersihkan semua widget lama agar tidak terjadi duplikasi tampilan
        for widget in self.scroll_sidebar_left.winfo_children():
            widget.destroy()
        for widget in self.scroll_sidebar_right.winfo_children():
            widget.destroy()

        # 2. Tampilkan Riwayat Batch (Jika ada batch yang sudah selesai)
        if hasattr(self, 'completed_batches') and self.completed_batches:
            ctk.CTkLabel(self.scroll_sidebar_left, text="RIWAYAT BATCH:", 
                        font=("Arial", 11, "bold"), text_color="#94a3b8").pack(anchor="w", padx=10)
            for b in self.completed_batches:
                ctk.CTkLabel(self.scroll_sidebar_left, text=f"✓ {b} SELESAI", 
                            text_color="#22c55e", font=("Arial", 11)).pack(anchor="w", padx=20)

        # Header untuk area Scan (Sisi Kiri)
        ctk.CTkLabel(self.scroll_sidebar_left, text=f"SCAN LIST (B-{self.current_batch_num}):", 
                    font=("Arial", 12, "bold"), text_color="#38bdf8").pack(pady=(15, 5), anchor="w", padx=10)

        # 3. Looping untuk memisahkan material ke Kiri (Scan) atau Kanan (Checklist)
        for item in self.material_resep:
            nama = item['nama'].upper()
            qty = item['target_qty']
            sat = item['satuan']
            # Cek apakah material ini sudah di-scan atau dicentang manual 
            is_done = item["kode_sap"] in self.scanned_materials
            
            teks = f"{'✓' if is_done else '○'} {nama} ({qty} {sat})"

            # LOGIKA PEMISAHAN: Berdasarkan kolom 'is_scan' dari database
            if item['is_scan']:
                #  SIDEBAR KIRI (Bahan Scan Pallet)
                f = ctk.CTkFrame(self.scroll_sidebar_left, 
                                 fg_color="#064e3b" if is_done else "#334155", 
                                 height=35)
                f.pack(fill="x", pady=2, padx=10)
                
                ctk.CTkLabel(f, text=teks, 
                             text_color="white", 
                             font=("Arial", 11)).pack(side="left", padx=10)
            else:
                #  SIDEBAR KANAN (Manual Checklist)
                f = ctk.CTkFrame(self.scroll_sidebar_right, 
                                 fg_color="#064e3b" if is_done else "#334155", 
                                 height=40)
                f.pack(fill="x", pady=2, padx=10) 
                
                ctk.CTkLabel(f, text=teks, 
                             text_color="#34d399" if is_done else "white", 
                             font=("Arial", 11)).pack(side="left", padx=10)
                
                # Checkbox interaktif (Settingan Tebal & Kontras)
                cb = ctk.CTkCheckBox(
                    f, 
                    text="", 
                    width=24, 
                    checkbox_width=24, 
                    checkbox_height=24, 
                    border_width=3,            # Ketebalan border
                    border_color="#ffffff",    # Warna putih agar kontras
                    fg_color="#22c55e",        # Warna saat tercentang (Hijau)
                    checkmark_color="#ffffff",
                    hover_color="#38bdf8",
                    command=lambda b=item['kode_sap']: self.manual_check_handler(b)
                )
                
                if is_done: 
                    cb.select()
                cb.pack(side="right", padx=10) 

    def start_job(self, job_data):
        job_id_db = job_data.get('id')
        if not job_id_db: return

        # Ambil material & siapkan data
        materials = self.fetch_materials_by_resep(job_id_db)
        self.current_job_id = job_id_db
        self.material_resep = materials
        self.selected_job_no = job_data.get('nomor_job')
        self.target_qty_total = int(job_data.get('target_qty', 1))
        
        self.current_batch_num = 1 
        self.completed_batches = [] 
        self.scanned_materials = set() 
        self.is_scanning = True

        # Tampilkan UI Scanner
        self.setup_scanner_ui() 
        self.update_clock()
        print(f"Job {self.selected_job_no} Dimulai")

    def show_notification(self, text, color):
        self.result_display.configure(text=text, text_color=color)
        self.main_area.configure(border_width=2, border_color=color)
        self.after(1200, lambda: self.main_area.configure(border_width=0))

    def konfirmasi_stop(self):
        pop = ctk.CTkToplevel(self)
        pop.title("Konfirmasi Tindakan") 
        pop.geometry("400x220")
        pop.attributes("-topmost", True) 
        pop.configure(fg_color="#0f172a")
        
        # Penempatan di tengah layar
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - 200
        y = (screen_height // 2) - 110
        pop.geometry(f"+{x}+{y}") 

        ctk.CTkLabel(pop, text="⚠ Scanner Sedang Berjalan", font=("Arial", 18, "bold"), text_color="#f59e0b").pack(pady=(25, 10))
        ctk.CTkLabel(pop, text="Apakah anda ingin tetap di halaman scan\natau membatalkan dan keluar?", font=("Arial", 13), text_color="white").pack(pady=10)

        btn_frame = ctk.CTkFrame(pop, fg_color="transparent") 
        btn_frame.pack(pady=20)

        # Tombol Batal
        ctk.CTkButton(btn_frame, text="TETAP SCAN", width=130, height=40, fg_color="#334155", font=("Arial", 12, "bold"), command=pop.destroy).pack(side="left", padx=10)

        # Tombol Keluar
        ctk.CTkButton(
            btn_frame, 
            text="KELUAR", 
            width=130, 
            height=40, 
            fg_color="#ef4444", 
            hover_color="#dc2626", 
            font=("Arial", 12, "bold"), 
            command=lambda p=pop: self.eksekusi_keluar(p) 
        ).pack(side="left", padx=10)


    def update_clock(self):
        if self.is_scanning:
            self.datetime_label.configure(text=datetime.now().strftime("%A, %d %B %Y\n%H:%M:%S"))
            self.after(1000, self.update_clock)

if __name__ == "__main__":  
    start_api_server_in_thread()
    app = AppScanner()
    app.mainloop()