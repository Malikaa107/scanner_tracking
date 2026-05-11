import customtkinter as ctk 
import os 
from PIL import Image
from datetime import datetime
from history_window import HistoryWindow
from api_server import start_api_server_in_thread
from dotenv import load_dotenv
from database import get_connection

# Load konfigurasi environment
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 

# Data Material Dummy
MATERIAL_RESEP_DUMMY = [
    {"nama": "TEPUNG TERIGU", "barcode": "20250418-329259"},
    {"nama": "MINYAK NABATI", "barcode": "20250418-277660"},
    {"nama": "BUBUK COKLAT", "barcode": "20250418-293111"},
    {"nama": "GULA PASIR", "barcode": "20250418-235100"},
    {"nama": "SUSU BUBUK", "barcode": "20250418-125894"},
    {"nama": "LECITHIN", "barcode": "20250418-198214"},
    {"nama": "AIR", "barcode": "-"}, # Contoh material tanpa barcode
]

class JoblistSelector(ctk.CTkFrame):
    def __init__(self, master, on_job_selected):
        super().__init__(master, fg_color="#0f172a")
        self.on_job_selected = on_job_selected
        self.setup_ui()

    def setup_ui(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=40, pady=(40, 20))
        ctk.CTkLabel(header_frame, text="Joblist Formulasi", font=("Arial", 28, "bold"), text_color="white").pack(side="left")
        
        self.table_frame = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=15)
        self.table_frame.pack(padx=40, pady=10, fill="x")

        header_row = ctk.CTkFrame(self.table_frame, fg_color="#334155", height=40)
        header_row.pack(fill="x", padx=10, pady=(10, 5))
        
        headers = [
            ("NO", 50), ("NOMOR JOB", 180), ("TANGGAL", 150), 
            ("RESEP TARGET", 200), ("TARGET QTY", 100), ("STATUS", 120), ("ACTIONS", 120)
        ]
        
        for text, width in headers:
            ctk.CTkLabel(header_row, text=text, width=width, font=("Arial", 12, "bold"), 
                         text_color="#94a3b8", anchor="w").pack(side="left", padx=10)

        jobs = self.fetch_jobs_from_db()
        for index, job in enumerate(jobs):
            row = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=5)
            
            status_map = {0: ("PENDING", "#94a3b8"), 1: ("ON PROGRESS", "#38bdf8"), 2: ("SELESAI", "#22c55e")}
            status_text, status_color = status_map.get(job['status'], ("UNKNOWN", "white"))

            ctk.CTkLabel(row, text=str(index+1), width=50, text_color="white", anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=job['nomor_job'], width=180, text_color="white", font=("Arial", 13, "bold"), anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=str(job['tanggal']), width=150, text_color="white", anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=job['nama_resep'], width=200, text_color="white", anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=f"{job['target_qty']} Batch", width=100, text_color="white", anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=status_text, width=120, text_color=status_color, font=("Arial", 12, "bold"), anchor="w").pack(side="left", padx=10)

            ctk.CTkButton(row, text="Lihat Detail", width=120, height=32, 
                         fg_color="#334155", 
                         command=lambda j=job: self.on_job_selected(j['nomor_job'], j['target_qty'], j['resepId'])
                         ).pack(side="left", padx=10)

    def fetch_jobs_from_db(self):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            query = """
                SELECT j.nomor_job, j.tanggal, j."resepId", j.target_qty, j.status, r.nama_resep
                FROM qc.formulasi_joblist j
                LEFT JOIN qc.master_resep r ON j."resepId" = r.id
                WHERE j.status IN (0, 1, 2) 
                ORDER BY j.status ASC, j.tanggal DESC
            """
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.close()
            return results
        except Exception as e:
            print(f"Database Error: {e}")
            return []

class AppScanner(ctk.CTk):
    def __init__(self): 
        super().__init__() 
        self.title("Sistem Scanner Formulasi") 
        self.geometry("1400x850")
        self.configure(fg_color="#0f172a") 
        
        self.selected_job_no = None 
        self.target_qty_total = 0
        self.current_batch_num = 1
        self.is_scanning = False 
        self.batch_active = False 
        self.material_resep = [] 
        
        self.scanned_materials = set() 
        self.completed_batches = [] 
        self.after_id = None 
        
        self.show_joblist_selector()
        self.bind("<Escape>", lambda e: self.konfirmasi_stop() if self.is_scanning else None)

    def fetch_materials_by_resep(self, resep_id):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            query = 'SELECT r.nama_material as nama, r.kode_sap as barcode FROM qc.master_resep_detail r WHERE r."resepId" = %s'
            cursor.execute(query, (resep_id,))
            columns = [column[0] for column in cursor.description]
            materials = [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.close()
            return materials if materials else MATERIAL_RESEP_DUMMY
        except:
            return MATERIAL_RESEP_DUMMY

    def show_joblist_selector(self):
        self.is_scanning = False
        self.batch_active = False
        self.current_batch_num = 1
        self.completed_batches.clear()
        self.scanned_materials.clear()
        for widget in self.winfo_children(): widget.destroy()
        self.job_selector = JoblistSelector(self, self.prepare_scanning_area)
        self.job_selector.pack(expand=True, fill="both")

    def prepare_scanning_area(self, job_no, target_qty, resep_id):
        self.reset_job_status(job_no)
        self.selected_job_no = job_no
        self.target_qty_total = int(target_qty)
        self.is_scanning = True
        self.batch_active = False
        self.scanned_materials = set() 
        self.completed_batches = []    
        self.current_batch_num = 1
        self.material_resep = self.fetch_materials_by_resep(resep_id)
        self.setup_scanner_ui()
        self.update_clock()

    def reset_job_status(self, job_no):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE qc.formulasi_joblist SET status = 0 WHERE nomor_job = %s', (job_no,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error Reset Status: {e}")

    def setup_scanner_ui(self):
        for widget in self.winfo_children(): widget.destroy()

        # HEADER
        self.header = ctk.CTkFrame(self, height=130, corner_radius=0, fg_color="#1e3d59")
        self.header.pack(side="top", fill="x")

        try:
            logo_img = Image.open(os.path.join(BASE_DIR, "logo2.png"))
            self.logo_icon = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(80, 80))
            ctk.CTkLabel(self.header, image=self.logo_icon, text="").place(x=20, y=25)
            title_x = 115 
        except: title_x = 30

        ctk.CTkLabel(self.header, text="SISTEM SCANNER FORMULASI", font=("Arial", 28, "bold"), text_color="white").place(x=title_x, y=30)
        self.batch_info_label = ctk.CTkLabel(self.header, text=f"JOB: {self.selected_job_no} | BATCH: {self.current_batch_num}/{self.target_qty_total}", 
                                            font=("Arial", 16, "bold"), text_color="#38bdf8", fg_color="#0f172a", corner_radius=10, padx=15, pady=5)
        self.batch_info_label.place(x=title_x, y=80)

        self.datetime_label = ctk.CTkLabel(self.header, text="", font=("Arial", 14, "bold"), text_color="#38bdf8", justify="right")
        self.datetime_label.place(relx=0.97, rely=0.15, anchor="ne")

        ctk.CTkButton(self.header, text="STOP JOB", fg_color="#ef4444", font=("Arial", 12, "bold"), width=100, height=35, command=self.konfirmasi_stop).place(relx=0.85, rely=0.6, anchor="ne")
        ctk.CTkButton(self.header, text="HISTORY", fg_color="#20C997", font=("Arial", 12, "bold"), width=100, height=35, command=lambda: HistoryWindow(self)).place(relx=0.97, rely=0.6, anchor="ne")

        # MAIN CONTENT
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(expand=True, fill="both", padx=20, pady=20)

        # LEFT SIDEBAR (History & Scan List)
        self.sidebar_left = ctk.CTkFrame(self.content, width=300, corner_radius=20, fg_color="#1e293b")
        self.sidebar_left.pack(side="left", fill="y", padx=(0, 10))
        
        self.btn_batch_start = ctk.CTkButton(self.sidebar_left, text=f"START BATCH {self.current_batch_num} ▶", font=("Arial", 15, "bold"), height=50, fg_color="#3b82f6", command=self.start_batch_logic)
        self.btn_batch_start.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(self.sidebar_left, text="LIST MATERIAL SCAN", text_color="#38bdf8", font=("Arial", 14, "bold")).pack(pady=(10, 5))
        self.scroll_sidebar_left = ctk.CTkScrollableFrame(self.sidebar_left, fg_color="transparent")
        self.scroll_sidebar_left.pack(expand=True, fill="both", padx=10, pady=5)

        # RIGHT SIDEBAR (Manual Checklist)
        self.sidebar_right = ctk.CTkFrame(self.content, width=280, corner_radius=20, fg_color="#1e293b")
        self.sidebar_right.pack(side="right", fill="y", padx=(10, 0))
        
        ctk.CTkLabel(self.sidebar_right, text="CHECKLIST", text_color="#fbbf24", font=("Arial", 15, "bold")).pack(pady=15)
        ctk.CTkLabel(self.sidebar_right, text="(Material Tidak Di Scan)", text_color="#94a3b8", font=("Arial", 11)).pack(pady=(0, 10))
        
        self.scroll_sidebar_right = ctk.CTkScrollableFrame(self.sidebar_right, fg_color="transparent")
        self.scroll_sidebar_right.pack(expand=True, fill="both", padx=10, pady=5)

        # CENTER AREA (Scanning Area)
        self.main_area = ctk.CTkFrame(self.content, corner_radius=20, fg_color="#1e293b") 
        self.main_area.pack(side="left", expand=True, fill="both")
        
        self.result_display = ctk.CTkLabel(self.main_area, text="TEKAN START UNTUK SCAN", font=("Arial", 32, "bold"), text_color="#94a3b8")
        self.result_display.pack(pady=(120, 10)) 

        self.entry_barcode = ctk.CTkEntry(self.main_area, width=400, height=70, justify="center", font=("Arial", 24), placeholder_text="Menunggu start...",
                                          fg_color="#0f172a", text_color="white", border_color="#334155", state="disabled") 
        self.entry_barcode.pack(pady=20)
        self.entry_barcode.bind('<KeyRelease>', self.auto_scan_handler)
        
        self.update_sidebar_lists()

    def start_batch_logic(self):
        self.batch_active = True
        self.btn_batch_start.configure(state="disabled", text=f"SCANNING BATCH {self.current_batch_num}...", fg_color="#1e3d59")
        self.entry_barcode.configure(state="normal", placeholder_text=f"Scan Batch {self.current_batch_num}...")
        self.entry_barcode.focus_set()
        self.result_display.configure(text=f"Silahkan Scan Barcode", text_color="#38bdf8")
        self.update_sidebar_lists()

    def auto_scan_handler(self, event): 
        if self.after_id: self.after_cancel(self.after_id)
        if len(self.entry_barcode.get()) >= 12:
            self.process_scan()
        else:
            self.after_id = self.after(500, self.process_scan)

    def process_scan(self):
        code = self.entry_barcode.get().strip()
        if not code: return
        self.entry_barcode.delete(0, 'end')

        target = next((i for i in self.material_resep if i["barcode"] == code and i["barcode"] not in ["-", "", None]), None)
        if target:
            if code in self.scanned_materials:
                self.show_notification("SUDAH DI SCAN!", "#f59e0b")
            else:
                self.scanned_materials.add(code)
                self.show_notification(f"{target['nama']}", "#22c55e")
                self.update_sidebar_lists()
                self.check_all_materials_completed()
        else:
            self.show_notification("BARCODE TIDAK VALID!", "#ef4444")

    def manual_check_handler(self, barcode):
        # Fungsi saat user klik centang manual di sidebar kanan
        if not self.batch_active: return
        
        if barcode in self.scanned_materials:
            self.scanned_materials.remove(barcode)
        else:
            self.scanned_materials.add(barcode)
        
        self.update_sidebar_lists()
        self.check_all_materials_completed()

    def check_all_materials_completed(self):
        # Memeriksa apakah semua item (Scan + Manual) sudah terpenuhi 
        if len(self.scanned_materials) == len(self.material_resep):
            self.handle_batch_complete()

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
            cursor.execute('UPDATE qc.formulasi_joblist SET status = 2 WHERE nomor_job = %s', (self.selected_job_no,))
            conn.commit() 
            conn.close()
        except Exception as e: print(f"Error Update: {e}")
        self.show_joblist_selector()

    def update_sidebar_lists(self):
        # Update Sidebar Kiri 
        for widget in self.scroll_sidebar_left.winfo_children(): widget.destroy()
        
        if self.completed_batches:
            ctk.CTkLabel(self.scroll_sidebar_left, text="RIWAYAT BATCH:", font=("Arial", 11, "bold"), text_color="#94a3b8").pack(anchor="w")
            for b in self.completed_batches:
                ctk.CTkLabel(self.scroll_sidebar_left, text=f"✓ {b} SELESAI", text_color="#22c55e", font=("Arial", 11)).pack(anchor="w", padx=10)

        ctk.CTkLabel(self.scroll_sidebar_left, text=f"SCAN LIST (B-{self.current_batch_num}):", font=("Arial", 12, "bold"), text_color="#38bdf8").pack(pady=(15,5), anchor="w")
        
        # Update Sidebar Kanan
        for widget in self.scroll_sidebar_right.winfo_children(): widget.destroy()

        for item in self.material_resep:
            is_manual = item["barcode"] in ["-", "", None]
            is_done = item["barcode"] in self.scanned_materials
            
            if not is_manual:
                # Masuk Sidebar Kiri (Scan)
                f = ctk.CTkFrame(self.scroll_sidebar_left, fg_color="#064e3b" if is_done else "#334155", height=35)
                f.pack(fill="x", pady=2)
                ctk.CTkLabel(f, text=f"{'✓' if is_done else '○'} {item['nama']}", text_color="#22c55e" if is_done else "white", font=("Arial", 12)).pack(side="left", padx=10)
            else:
                # DESAIN CHECKLIST MANUAL
                f = ctk.CTkFrame(self.scroll_sidebar_right, 
                                 fg_color="#1e293b" if not is_done else "#064e3b", 
                                 border_width=2, 
                                 border_color="#334155" if not is_done else "#10b981", 
                                 corner_radius=12,
                                 height=50) # Tinggi 
                f.pack(fill="x", pady=8, padx=6)
                
                # Nama Material dengan font lebih tegas
                lbl = ctk.CTkLabel(f, text=item['nama'], 
                                   text_color="#e2e8f0" if not is_done else "#34d399", 
                                   font=("Arial", 13, "bold"))
                lbl.pack(side="left", padx=15)
                
                # Checkbox 
                btn_check = ctk.CTkCheckBox(f, 
                                           text="", 
                                           width=30, 
                                           height=30,
                                           checkbox_width=27,
                                           checkbox_height=27,
                                           border_width=1,     # Border tebal agar efek timbul terasa
                                           corner_radius=10,   # Sudut kotak lebih halus
                                           border_color="#3B82F6", # Kuning Amber saat belum dicentang (High Contrast)
                                           fg_color="#10b981",     # Hijau Emerald saat aktif
                                           hover_color="#059669",
                                           checkmark_color="white",
                                           command=lambda b=item['barcode']: self.manual_check_handler(b))
                
                if is_done: 
                    btn_check.select()
                
                btn_check.pack(side="right", padx=10)

    def show_notification(self, text, color):
        self.result_display.configure(text=text, text_color=color)
        self.main_area.configure(border_width=2, border_color=color)
        self.after(1200, lambda: self.main_area.configure(border_width=0))

    def konfirmasi_stop(self):
        # Membuat jendela pop-up kecil (Toplevel)
        pop = ctk.CTkToplevel(self)
        pop.title("Konfirmasi Tindakan") 
        pop.geometry("400x220")
        pop.attributes("-topmost", True) # Agar selalu di depan
        pop.configure(fg_color="#0f172a")
        
        # Center pop-up di layar
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (400 // 2)
        y = (screen_height // 2) - (220 // 2)
        pop.geometry(f"400x220+{x}+{y}")

        ctk.CTkLabel(pop, text="⚠ Scanner Sedang Berjalan", 
                     font=("Arial", 18, "bold"), text_color="#f59e0b").pack(pady=(25, 10))
        
        ctk.CTkLabel(pop, text="Apakah anda ingin tetap di halaman scan\natau membatalkan dan keluar?", 
                     font=("Arial", 13), text_color="white").pack(pady=10)
        
        btn_frame = ctk.CTkFrame(pop, fg_color="transparent") 
        btn_frame.pack(pady=20)
        
        # Tombol Pilihan 1: Tetap di Halaman
        ctk.CTkButton(btn_frame, text="TETAP SCAN", width=130, height=40, 
                     fg_color="#334155", font=("Arial", 12, "bold"),
                     command=pop.destroy).pack(side="left", padx=10)
        
        # Tombol Pilihan 2: Keluar (Reset ke Joblist)
        ctk.CTkButton(btn_frame, text="KELUAR", width=130, height=40, 
                     fg_color="#ef4444", hover_color="#dc2626", font=("Arial", 12, "bold"),
                     command=lambda: [pop.destroy(), self.show_joblist_selector()]).pack(side="left", padx=10)

    def update_clock(self):
        if self.is_scanning:
            self.datetime_label.configure(text=datetime.now().strftime("%A, %d %B %Y\n%H:%M:%S"))
            self.after(1000, self.update_clock)

if __name__ == "__main__":
    start_api_server_in_thread()
    app = AppScanner()
    app.mainloop()