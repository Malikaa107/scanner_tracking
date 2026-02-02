import customtkinter as ctk
import psycopg2
import time
from PIL import Image
from datetime import datetime
from tkinter import ttk
try:
    from tkcalendar import Calendar
except ImportError:
    Calendar = None

# KONFIGURASI DATABASE
DB_CONFIG = {
    "host": "localhost",
    "database": "postgres", 
    "user": "postgres",
    "password": "", 
    "port": "5432"
}


class AppScanner(ctk.CTk): #kerangka utama
    def __init__(self):
        super().__init__()
        self.title("Sistem Scanner Formulasi")
        self.geometry("1200x800")
        self.configure(fg_color="#0f172a")
        
        self.last_input_time = time.time()
        self.limit_sidebar = 30 
        self.filter_start = None
        self.filter_end = None

        # 1. HEADER
        self.header = ctk.CTkFrame(self, height=110, corner_radius=0, fg_color="#1e3d59")
        self.header.pack(side="top", fill="x")
    
        try:
            img_hist_header = Image.open("icon_history2.png")
            self.icon_header = ctk.CTkImage(light_image=img_hist_header, dark_image=img_hist_header, size=(20, 20))
        except:
            self.icon_header = None
        
        try:
            img_file = Image.open("Logo2.png") 
            self.logo_img = ctk.CTkImage(light_image=img_file, dark_image=img_file, size=(70, 70))
            ctk.CTkLabel(self.header, text="", image=self.logo_img).place(x=25, y=20)
        except:
            ctk.CTkLabel(self.header, text="LOGO", fg_color="#e11d48", width=70, height=70, text_color="white").place(x=25, y=20)
        
        ctk.CTkLabel(self.header, text="SISTEM SCANNER FORMULASI", font=("Franklin Gothic Heavy", 28, "bold"), text_color="white").place(x=115, y=40)
        
        self.datetime_label = ctk.CTkLabel(self.header, text="", font=("Arial", 14, "bold"), text_color="#38bdf8", justify="right")
        self.datetime_label.place(relx=0.97, rely=0.15, anchor="ne")
        
        self.btn_full = ctk.CTkButton(
            self.header, 
            text=" HISTORY", 
            image=self.icon_header,
            compound="left",
            fg_color="#0ea5e9", 
            font=("Arial", 12, "bold"), 
            command=self.buka_window_history
        )
        self.btn_full.place(relx=0.97, rely=0.6, anchor="ne")

        # 2. MAIN CONTENT AREA
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(expand=True, fill="both", padx=20, pady=20)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self.content, width=300, corner_radius=20, fg_color="#1e293b")
        self.sidebar.pack(side="left", fill="y", padx=(0, 15))
        ctk.CTkLabel(self.sidebar, text="DATA MASUK", text_color="#38bdf8", font=("Arial", 16, "bold")).pack(pady=15)
        self.history_display = ctk.CTkTextbox(self.sidebar, fg_color="#0f172a", text_color="#fffbeb", font=("Consolas", 14), corner_radius=10)
        self.history_display.pack(expand=True, fill="both", padx=15, pady=(0, 10))
        self.btn_load_more = ctk.CTkButton(self.sidebar, text="LIHAT DATA LAINNYA", fg_color="#10b981", text_color="black", font=("Arial", 11, "bold"), hover_color="#059669", command=self.muat_lebih_sidebar)
        self.btn_load_more.pack(pady=15, padx=20, fill="x")

        # Main Area 
        self.main_area = ctk.CTkFrame(self.content, corner_radius=20, fg_color="#1e293b")
        self.main_area.pack(side="right", expand=True, fill="both")
        ctk.CTkLabel(self.main_area, text="HASIL SCAN :", font=("Arial", 18), text_color="#94a3b8").pack(pady=(150, 10))
        self.result_display = ctk.CTkLabel(self.main_area, text="---", font=("Arial", 45, "bold"), text_color="white")
        self.result_display.pack(pady=10)
        self.entry_barcode = ctk.CTkEntry(self.main_area, width=400, height=55, placeholder_text="Silahkan Scan Barcode...", justify="center", font=("Arial", 18), fg_color="#0f172a", text_color="white")
        self.entry_barcode.pack(pady=20)
        self.entry_barcode.focus_set()

        self.update_clock()
        self.load_sidebar_history()
        self.loop_check()

    def update_clock(self): #update jam
        self.datetime_label.configure(text=datetime.now().strftime("%A, %d %B %Y\n%H:%M:%S"))
        self.after(1000, self.update_clock)

    # 3. WINDOW HISTORY LENGKAP
    def buka_window_history(self):
        self.win_hist = ctk.CTkToplevel(self)
        self.win_hist.title("Database History Lengkap")
        self.win_hist.geometry("1150x850")
        self.win_hist.attributes('-topmost', True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#1e293b", foreground="white", fieldbackground="#1e293b", rowheight=35, borderwidth=1)
        style.configure("Treeview.Heading", background="#0f172a", foreground="#38bdf8", font=("Arial", 12, "bold"))
        style.map("Treeview", background=[('selected', '#0ea5e9')])

        self.top_f = ctk.CTkFrame(self.win_hist, fg_color="#1e293b", height=80)
        self.top_f.pack(fill="x", padx=20, pady=10)

        self.btn_cal = ctk.CTkButton(self.top_f, text="📅", width=45, height=45, font=("Arial", 20), fg_color="#0f172a", border_width=1, border_color="#38bdf8", command=self.toggle_picker)
        self.btn_cal.pack(side="left", padx=15)
        
        self.hist_time_lbl = ctk.CTkLabel(self.top_f, text="00:00:00", font=("Consolas", 20, "bold"), text_color="#38bdf8")
        self.hist_time_lbl.pack(side="left", padx=10)

        ctk.CTkButton(self.top_f, text="LIHAT LAPORAN", fg_color="#10b981", text_color="black", font=("Arial", 11, "bold"), command=self.refresh_history).pack(side="right", padx=15)

        self.picker_panel = ctk.CTkFrame(self.win_hist, fg_color="#f1f5f9", height=0)
        self.picker_panel.pack(fill="x", padx=20)
        self.is_picker_open = False
        self.setup_picker_ui()

        table_container = ctk.CTkFrame(self.win_hist, fg_color="transparent")
        table_container.pack(expand=True, fill="both", padx=20, pady=10)

        self.tree = ttk.Treeview(table_container, columns=("ID", "Barcode", "Waktu"), show='headings')
        self.tree.heading("ID", text="NO"); self.tree.heading("Barcode", text="KODE BARCODE"); self.tree.heading("Waktu", text="WAKTU SCAN")
        self.tree.column("ID", width=70, anchor="center"); self.tree.column("Barcode", width=600, anchor="center"); self.tree.column("Waktu", width=300, anchor="center")
        
        self.tree.tag_configure('oddrow', background='#1e293b')
        self.tree.tag_configure('evenrow', background='#334155')
        self.tree.pack(side="left", expand=True, fill="both")
        
        scrolly = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrolly.set)
        scrolly.pack(side="right", fill="y")
        
        self.update_history_clock()
        self.load_full_table(is_initial=True)

    def setup_picker_ui(self): #filter kalender
        self.picker_container = ctk.CTkFrame(self.picker_panel, fg_color="transparent")
        inner_cal = ctk.CTkFrame(self.picker_container, fg_color="transparent")
        inner_cal.pack(pady=10)
        self.c_start = Calendar(inner_cal, selectmode='day', font="Arial 8")
        self.c_start.pack(side="left", padx=20)
        self.c_end = Calendar(inner_cal, selectmode='day', font="Arial 8")
        self.c_end.pack(side="left", padx=20)
        
        time_frame = ctk.CTkFrame(self.picker_container, fg_color="transparent")
        time_frame.pack(pady=10)
        
        ctk.CTkLabel(time_frame, text="Start:", text_color="black", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5)
        self.h_start = ctk.CTkEntry(time_frame, width=45); self.h_start.insert(0, "08"); self.h_start.grid(row=0, column=1)
        self.m_start = ctk.CTkEntry(time_frame, width=45); self.m_start.insert(0, "00"); self.m_start.grid(row=0, column=2, padx=2)
        self.p_start = ctk.CTkOptionMenu(time_frame, values=["AM", "PM"], width=65, fg_color="#1e3d59"); self.p_start.grid(row=0, column=3)

        ctk.CTkLabel(time_frame, text=" s/d ", text_color="black").grid(row=0, column=4, padx=10)

        ctk.CTkLabel(time_frame, text="End:", text_color="black", font=("Arial", 12, "bold")).grid(row=0, column=5, padx=5)
        self.h_end = ctk.CTkEntry(time_frame, width=45); self.h_end.insert(0, "05"); self.h_end.grid(row=0, column=6)
        self.m_end = ctk.CTkEntry(time_frame, width=45); self.m_end.insert(0, "00"); self.m_end.grid(row=0, column=7, padx=2)
        self.p_end = ctk.CTkOptionMenu(time_frame, values=["AM", "PM"], width=65, fg_color="#1e3d59"); self.p_end.set("PM"); self.p_end.grid(row=0, column=8)

        ctk.CTkButton(self.picker_container, text="APPLY RANGE", fg_color="#10b981", text_color="black", font=("Arial", 12, "bold"), command=self.apply_filter).pack(pady=15)

    def toggle_picker(self):
        if not self.is_picker_open:
            self.picker_panel.configure(height=480)
            self.picker_container.pack(fill="both", expand=True)
            self.is_picker_open = True
        else:
            self.picker_container.pack_forget()
            self.picker_panel.configure(height=0)
            self.is_picker_open = False

    def load_full_table(self, is_initial=False):
        try:
            conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
            msg_kosong = "DATABASE KOSONG"
            
            if not is_initial and self.filter_start:
                query = "SELECT id, kode_barcode, created_at FROM latihan.barcode WHERE created_at BETWEEN %s AND %s ORDER BY id DESC"
                cur.execute(query, (self.filter_start, self.filter_end))
                tgl_obj = self.c_start.selection_get()
                tgl_lengkap = tgl_obj.strftime("%d/%m/%Y")
                msg_kosong = f"TIDAK ADA SCAN PADA {tgl_lengkap}"
            else:
                cur.execute("SELECT id, kode_barcode, created_at FROM latihan.barcode ORDER BY id DESC LIMIT 500")
            
            rows = cur.fetchall()
            for i in self.tree.get_children(): self.tree.delete(i)
            
            if not rows:
                self.tree.insert("", "end", values=("X", msg_kosong, "---"))
            else:
                for index, r in enumerate(rows):
                    tag = 'evenrow' if index % 2 == 0 else 'oddrow'
                    self.tree.insert("", "end", values=(r[0], r[1], r[2].strftime("%d/%m/%Y %H:%M:%S")), tags=(tag,))
            cur.close(); conn.close()
        except: pass

    def refresh_history(self):
        self.filter_start = None
        self.filter_end = None
        if self.is_picker_open: self.toggle_picker()
        self.load_full_table(is_initial=True)

    def update_history_clock(self):
        if hasattr(self, 'win_hist') and self.win_hist.winfo_exists():
            self.hist_time_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))
            self.win_hist.after(1000, self.update_history_clock)

    def apply_filter(self):
        t1 = self.convert_to_24h(self.h_start.get(), self.m_start.get(), self.p_start.get())
        t2 = self.convert_to_24h(self.h_end.get(), self.m_end.get(), self.p_end.get())
        self.filter_start = f"{self.c_start.get_date()} {t1}"
        self.filter_end = f"{self.c_end.get_date()} {t2}"
        self.toggle_picker()
        self.load_full_table(is_initial=False)

    def convert_to_24h(self, h, m, p):
        try:
            hour = int(h)
            if p == "PM" and hour < 12: hour += 12
            if p == "AM" and hour == 12: hour = 0
            return f"{hour:02d}:{int(m):02d}:00"
        except: return "00:00:00"

    def muat_lebih_sidebar(self):
        self.limit_sidebar += 30
        self.load_sidebar_history()

    def load_sidebar_history(self):
        try:
            conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
            cur.execute(f"SELECT kode_barcode FROM latihan.barcode ORDER BY id DESC LIMIT {self.limit_sidebar}")
            rows = cur.fetchall()
            self.history_display.configure(state="normal")
            self.history_display.delete("1.0", "end")
            for row in rows: self.history_display.insert("end", f" • {row[0]}\n")
            self.history_display.configure(state="disabled")
            cur.close(); conn.close()
        except: pass

    def simpan_data(self, teks): #penyimpanan data
        try:
            conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
            cur.execute("INSERT INTO latihan.barcode (kode_barcode) VALUES (%s)", (teks,))
            conn.commit(); cur.close(); conn.close()
            return True
        except: return False

    def loop_check(self): #cek input otomatis
        val = self.entry_barcode.get().strip()
        if val and time.time() - self.last_input_time > 0.6:
            if self.simpan_data(val):
                self.result_display.configure(text=val)
                self.load_sidebar_history()
                self.entry_barcode.delete(0, 'end')
        self.after(100, self.loop_check)

if __name__ == "__main__":
    app = AppScanner()
    app.mainloop()