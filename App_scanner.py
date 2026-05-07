import customtkinter as ctk 
import time
import os 
import requests 
from PIL import Image
from datetime import datetime
from history_window import HistoryWindow
from api_server import start_api_server_in_thread
from dotenv import load_dotenv
from database import get_connection

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
NODE_RED_URL = os.getenv("NODE_RED_URL", "http://127.0.0.1:1880/update_plc")

# KOMPONEN UI: JOBLIST SELECTOR
class JoblistSelector(ctk.CTkFrame):
    def __init__(self, master, on_job_selected):
        super().__init__(master, fg_color="#0f172a")
        self.on_job_selected = on_job_selected
        self.setup_ui()

    def setup_ui(self):
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=40, pady=(40, 20))
        
        ctk.CTkLabel(header_frame, text="Joblist Formulasi", 
                     font=("Arial", 28, "bold"), text_color="white").pack(side="left")
        
        # Table Frame
        self.table_frame = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=15)
        self.table_frame.pack(padx=40, pady=10, fill="x") 

        
        # Format: (Nama Kolom, Lebar)
        cols = [
            ("NO", 50), 
            ("NOMOR JOB", 200), 
            ("TANGGAL", 150), 
            ("RESEP TARGET", 200), 
            ("TARGET QTY", 120), 
            ("ACTIONS", 80) 
        ]
        
        head_row = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        head_row.pack(fill="x", padx=20, pady=15)

        for txt, w in cols:
            ctk.CTkLabel(head_row, text=txt, width=w, font=("Arial", 12, "bold"), 
                         text_color="#94a3b8", anchor="w").pack(side="left")

        # Data Dummy
        jobs = [
            ("1", "JOB-260507-0002", "Kamis, 07 Mei", "RESEP MALKIST", "2 Batch"),
            ("2", "JOB-260507-0001", "Kamis, 07 Mei", "RESEP MALKIST", "1 Batch")
        ]

        for job in jobs:
            row = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=10)
            
            ctk.CTkLabel(row, text=job[0], width=50, text_color="white", anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=job[1], width=200, text_color="white", font=("Arial", 13, "bold"), anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=job[2], width=150, text_color="#38bdf8", font=("Arial", 12), anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=job[3], width=200, text_color="white", anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=job[4], width=120, text_color="white", anchor="w").pack(side="left")
            
        
            action_btn = ctk.CTkButton(row, text="👁", width=40, height=30, fg_color="#334155",
                                       hover_color="#475569",
                                       command=lambda j=job[1]: self.on_job_selected(j))
            action_btn.pack(side="left", padx=10)
        
        head_row = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        head_row.pack(fill="x", padx=20, pady=15)

        for txt, w in cols:
            ctk.CTkLabel(head_row, text=txt, width=w, font=("Arial", 12, "bold"), 
                         text_color="#94a3b8", anchor="w").pack(side="l")

class BatchSelector(ctk.CTkFrame):
    def __init__(self, master, on_start_callback, completed_batches=None, selected_job="---"):
        super().__init__(master, fg_color="#0f172a")
        self.on_start_callback = on_start_callback
        self.completed_batches = completed_batches if completed_batches else set()
        self.selected_job = selected_job
        
        self.batch_data = {
            "Batch 1": ["20250418-293111", "20250418-235100"],
            "Batch 2": ["20250418-125894", "20250418-198214"],
            "Batch 3": ["20250418-277660", "20250418-329259"]
        }
        self.setup_ui()

    def setup_ui(self):
        ctk.CTkLabel(self, text=f"JOB: {self.selected_job}", font=("Arial", 16, "bold"), text_color="#38bdf8").pack(pady=(20, 0))
        ctk.CTkLabel(self, text="PILIH BATCH", font=("Franklin Gothic Heavy", 36, "bold"), text_color="#38bdf8").pack(pady=(20, 40))
        
        self.container = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=20)
        self.container.pack(padx=60, pady=20, fill="both", expand=True)

        for batch_name, barcodes in self.batch_data.items():
            is_done = batch_name in self.completed_batches
            frame_color = "#064e3b" if is_done else "#334155"
            frame = ctk.CTkFrame(self.container, fg_color=frame_color, height=100, corner_radius=10)
            frame.pack(fill="x", padx=30, pady=15)
            frame.pack_propagate(False)
            
            status_text = f"{batch_name} - SELESAI SCAN ✓ " if is_done else batch_name
            label_color = "#2dd4bf" if is_done else "white"
            
            ctk.CTkLabel(frame, text=f"{status_text}\nTarget: {barcodes[0]} s/d {barcodes[1]}", 
                         font=("Consolas", 16, "bold"), justify="left", text_color=label_color).pack(side="left", padx=25)
            
            if not is_done:
                btn = ctk.CTkButton(frame, text="START BATCH", fg_color="#22c55e", hover_color="#16a34a",
                                    font=("Arial", 14, "bold"), width=160, height=45,
                                    command=lambda b=batch_name, d=barcodes: self.on_start_callback(b, d))
                btn.pack(side="right", padx=25)
            else:
                ctk.CTkLabel(frame, text="COMPLETED", font=("Arial", 14, "bold"), text_color="#2dd4bf").pack(side="right", padx=25)

class AppScanner(ctk.CTk):
    def __init__(self): 
        super().__init__() 
        self.title("Sistem Scanner Formulasi") 
        self.geometry("1200x800") 
        self.configure(fg_color="#0f172a") 
        
        self.selected_job_no = None 
        self.active_batch = None
        self.target_barcodes = []
        self.is_scanning = False 
        self.completed_batches = set() 
        self.scanned_in_current_batch = set() 
        self._after_id = None
        
        self.show_joblist_selector()

    def show_joblist_selector(self):
        self.is_scanning = False
        for widget in self.winfo_children():
            widget.destroy()
        self.job_selector = JoblistSelector(self, self.select_job_and_proceed)
        self.job_selector.pack(expand=True, fill="both")

    def select_job_and_proceed(self, job_no):
        self.selected_job_no = job_no
        self.show_batch_selector()

    def show_batch_selector(self):
        self.is_scanning = False 
        for widget in self.winfo_children():
            widget.destroy()
        self.selector = BatchSelector(self, self.start_scanning_process, self.completed_batches, self.selected_job_no) 
        self.selector.pack(expand=True, fill="both")

    def start_scanning_process(self, batch_name, barcodes):
        self.active_batch = batch_name
        self.target_barcodes = barcodes
        self.scanned_in_current_batch = set() 
        self.is_scanning = True
        if hasattr(self, 'selector'):
            self.selector.destroy()
        self.setup_scanner_ui()
        self.after(100, self.update_clock)
        self.after(200, self.load_sidebar_history)

    def setup_scanner_ui(self):
        self.limit_sidebar = 30
        self.header = ctk.CTkFrame(self, height=110, corner_radius=0, fg_color="#1e3d59")
        self.header.pack(side="top", fill="x")

        try:
            logo_path = os.path.join(BASE_DIR, "logo2.png") 
            logo_img = Image.open(logo_path)
            self.logo_icon = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(80, 80))
            
            self.logo_label = ctk.CTkLabel(self.header, image=self.logo_icon, text="")
            self.logo_label.place(x=20, y=15)
            
            title_x = 115 
        except Exception as e:
            print(f"Logo tidak ditemukan: {e}")
            title_x = 30

        # --- JUDUL & INFO ---
        ctk.CTkLabel(self.header, text="SISTEM SCANNER FORMULASI", 
                     font=("Franklin Gothic Heavy", 28, "bold"), 
                     text_color="white").place(x=title_x, y=30)

        job_display = f"{self.selected_job_no} | {self.active_batch}"
        self.batch_info_label = ctk.CTkLabel(self.header, text=f"Active: {job_display}", 
                                             font=("Arial", 16, "bold"), text_color="#22c55e",
                                             fg_color="#0f172a", corner_radius=10, padx=15)
        self.batch_info_label.place(x=title_x, y=75)

        # --- JAM & TOMBOL ---
        self.datetime_label = ctk.CTkLabel(self.header, text="", font=("Arial", 14, "bold"), 
                                           text_color="#38bdf8", justify="right")
        self.datetime_label.place(relx=0.97, rely=0.15, anchor="ne")

        self.btn_stop = ctk.CTkButton(self.header, text="STOP BATCH", fg_color="#ef4444", 
                                      hover_color="#b91c1c", font=("Arial", 12, "bold"), 
                                      command=self.konfirmasi_stop)
        self.btn_stop.place(relx=0.85, rely=0.6, anchor="ne") 

        self.btn_full = ctk.CTkButton(self.header, text="HISTORY", fg_color="#20C997", 
                                      font=("Arial", 12, "bold"), command=self.buka_window_history) 
        self.btn_full.place(relx=0.97, rely=0.6, anchor="ne")

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(expand=True, fill="both", padx=20, pady=20)

        self.sidebar = ctk.CTkFrame(self.content, width=300, corner_radius=20, fg_color="#1e293b")
        self.sidebar.pack(side="left", fill="y", padx=(0, 15))
        
        ctk.CTkLabel(self.sidebar, text="DATA MASUK", text_color="#38bdf8", font=("Arial", 16, "bold")).pack(pady=15)
        self.history_display = ctk.CTkTextbox(self.sidebar, fg_color="#0f172a", text_color="#fffbeb", font=("Consolas", 14), corner_radius=10)
        self.history_display.pack(expand=True, fill="both", padx=15, pady=(0, 10)) 

        self.main_area = ctk.CTkFrame(self.content, corner_radius=20, fg_color="#1e293b") 
        self.main_area.pack(side="right", expand=True, fill="both")
        
        ctk.CTkLabel(self.main_area, text="HASIL SCAN :", font=("Arial", 18, "bold"), text_color="#94a3b8").pack(pady=(150, 5))
        self.result_display = ctk.CTkLabel(self.main_area, text="---", font=("Arial", 40, "bold"), text_color="white", wraplength=600)
        self.result_display.pack(pady=10) 

        self.entry_barcode = ctk.CTkEntry(self.main_area, width=450, height=60, justify="center", 
                                          font=("Arial", 22), placeholder_text="Silahkan scan barcode...",
                                          fg_color="#0f172a", text_color="white", border_color="#38bdf8") 
        self.entry_barcode.pack(pady=20)
        self.entry_barcode.focus_set()
        self.entry_barcode.bind('<KeyRelease>', self.handle_auto_scan)

    def handle_auto_scan(self, event=None):
        if event and event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(200, self.loop_check)

    def loop_check(self):
        if not self.is_scanning: return
        val = self.entry_barcode.get().strip()
        if val:
            # Fitur verifikasi barcode
            if val in self.target_barcodes: 
                if val not in self.scanned_in_current_batch:
                    self.scanned_in_current_batch.add(val)
                    # Di sini Anda bisa memanggil cek_formulasi_joblist jika diperlukan
                    self.main_area.configure(fg_color="#1e293b")
                    self.result_display.configure(text="ITEM TERVERIFIKASI", text_color="#22c55e") 
                    self.load_sidebar_history()
                    if len(self.scanned_in_current_batch) >= len(self.target_barcodes):
                        self.result_display.configure(text="BATCH SELESAI!", text_color="#38bdf8")
                        self.after(300, self.show_finish_notification) 
                else:
                    self.result_display.configure(text="ITEM SUDAH TERSCAN!", text_color="#f59e0b")
            else:
                self.main_area.configure(fg_color="#450a0a") 
                self.result_display.configure(text=f"⚠️ ERROR BUKAN BAGIAN {self.active_batch}", text_color="#f87171")
            self.entry_barcode.delete(0, 'end')

    def show_finish_notification(self):
        self.is_scanning = False
        self.completed_batches.add(self.active_batch)
        pop_finish = ctk.CTkToplevel(self)
        pop_finish.title("Status Scan")
        pop_finish.geometry("450x250")
        pop_finish.configure(fg_color="#0f172a")
        pop_finish.attributes("-topmost", True)
        pop_finish.grab_set()
        ctk.CTkLabel(pop_finish, text="✓ BATCH LENGKAP", font=("Arial", 26, "bold"), text_color="#22c55e").pack(pady=(40, 10))
        btn_ok = ctk.CTkButton(pop_finish, text="KEMBALI KE DAFTAR BATCH", 
                               fg_color="#22c55e", hover_color="#16a34a", text_color="white",
                               command=lambda: [pop_finish.destroy(), self.show_batch_selector()])
        btn_ok.pack(pady=20)

    def konfirmasi_stop(self):
        self.pop_stop = ctk.CTkToplevel(self)
        self.pop_stop.title("Konfirmasi Tindakan") 
        self.pop_stop.geometry("400x200") 
        self.pop_stop.configure(fg_color="#1e293b")
        self.pop_stop.attributes("-topmost", True)
        self.pop_stop.grab_set() 

        # Label Peringatan Utama
        ctk.CTkLabel(self.pop_stop, text="SCANNER SEDANG BERJALAN", 
                     font=("Arial", 18, "bold"), text_color="#ef4444").pack(pady=(30, 5))
        ctk.CTkLabel(self.pop_stop, text="APA YANG INGIN ANDA LAKUKAN?", 
                     font=("Arial", 14, "bold"), text_color="white").pack(pady=(0, 20))

        # Tombol Kembali ke Menu Batch
        btn_menu = ctk.CTkButton(self.pop_stop, 
                                 text="KEMBALI KE MENU BATCH", 
                                 fg_color="#FFC107", 
                                 hover_color="#e6ae06",
                                 text_color="black", # Font warna hitam
                                 font=("Arial", 12, "bold"),
                                 command=lambda: [self.pop_stop.destroy(), self.show_batch_selector()])
        btn_menu.pack(fill="x", padx=40, pady=5)

        # Tombol Batal/Lanjut
        btn_lanjut = ctk.CTkButton(self.pop_stop, 
                                   text="BATAL / LANJUT SCAN", 
                                   fg_color="#22c55e", 
                                   hover_color="#16a34a",
                                   text_color="white",
                                   font=("Arial", 12, "bold"),
                                   command=self.pop_stop.destroy)
        btn_lanjut.pack(fill="x", padx=40, pady=5)

    def update_clock(self):
        if not self.is_scanning: return 
        self.datetime_label.configure(text=datetime.now().strftime("%A, %d %B %Y\n%H:%M:%S"))
        self.after(1000, self.update_clock)

    def load_sidebar_history(self):
        try:
            conn = get_connection(); cur = conn.cursor() 
            SCHEMA = os.getenv("DB_SCHEMA", "QC")
            cur.execute(f"SELECT kode_barcode FROM {SCHEMA}.barcode ORDER BY id DESC LIMIT {self.limit_sidebar}")
            rows = cur.fetchall()
            self.history_display.configure(state="normal")
            self.history_display.delete("1.0", "end")
            for idx, row in enumerate(rows, 1): 
                self.history_display.insert("end", f" {idx:02}. {row[0]}\n") 
            self.history_display.configure(state="disabled") 
            cur.close(); conn.close() 
        except: pass

    # --- PERBAIKAN FUNGSI CEK FORMULASI ---
    def cek_formulasi_joblist(self, nomor_job):
        try:
            conn = get_connection()
            cur = conn.cursor()
            SCHEMA = os.getenv("DB_SCHEMA", "qc")
            
            query = f"""
                SELECT 
                    nomor_job, tanggal, bon_rm_ckId, resepId, 
                    target_qty, status, dibuat_oleh, "createdAt", "updatedAt" 
                FROM {SCHEMA}.formulasi_joblist 
                WHERE nomor_job = %s
            """
            
            cur.execute(query, (nomor_job,))
            result = cur.fetchone()
            
            cur.close()
            conn.close()
            return result
        except Exception as e:
            print(f"Error Database: {e}")
            return None

    def buka_window_history(self):
        HistoryWindow(self) 

if __name__ == "__main__":
    start_api_server_in_thread()
    app = AppScanner()
    app.mainloop()