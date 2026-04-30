import customtkinter as ctk #library utama membuat tampilan UI
import psycopg2 #library untuk menghubungkan database - postgreSQL
import time #untuk mengatur jeda waktu (delay)
import math #untuk perhitungan digunakan pada bagian halaman/pagination
from PIL import Image #memproses gambar
from datetime import datetime, timedelta #digunakan untuk waktu tanggal durasi
from tkinter import ttk #untuk tabel treeview 
try:
    from tkcalendar import Calendar #untuk memunculkan kalender 
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

class AppScanner(ctk.CTk): 
    def __init__(self):
        super().__init__()
        self.title("Sistem Scanner Formulasi") #judul pada jendela aplikasi
        self.geometry("1200x800") #ukuran  jendela aplikasi
        self.configure(fg_color="#0f172a") #mengatur warna latar belakang
        
        #Variabel Logika
        self.last_input_time = time.time() #memcatat waktu terakhir scan
        self.limit_sidebar = 30 #jumlah data awal di sidebar kiri 
        self.filter_start = None #halaman data yg sedang dibuka
        self.filter_end = None #jumlah baris per halaman di tabel 
        
        self.current_page = 1 #halaman tabel yang sedang dibuka 
        self.rows_per_page = 15 #jumlah baris per halaman di tabel history
        self.page_buttons = []

        # 1. HEADER (bagian atas)
        self.header = ctk.CTkFrame(self, height=110, corner_radius=0, fg_color="#1e3d59")
        self.header.pack(side="top", fill="x") #background 
    
        #Load logo & icon 
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
        
        # KOMPONEN DI HEADER
        #menampilkan teks judul
        ctk.CTkLabel(self.header, text="SISTEM SCANNER FORMULASI", font=("Franklin Gothic Heavy", 28, "bold"), text_color="white").place(x=115, y=40)
        
        #Label untuk menampilkan jam berjalan
        self.datetime_label = ctk.CTkLabel(self.header, text="", font=("Arial", 14, "bold"), text_color="#38bdf8", justify="right")
        self.datetime_label.place(relx=0.97, rely=0.15, anchor="ne")
        #Tombol untuk membuka jendela database lengkap
        self.btn_full = ctk.CTkButton(self.header, text=" HISTORY", image=self.icon_header, compound="left", fg_color="#0ea5e9", font=("Arial", 12, "bold"), command=self.buka_window_history)
        self.btn_full.place(relx=0.97, rely=0.6, anchor="ne")

        # 2. MAIN CONTENT AREA
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(expand=True, fill="both", padx=20, pady=20)
        #Sidebar kiri
        self.sidebar = ctk.CTkFrame(self.content, width=300, corner_radius=20, fg_color="#1e293b") #data scan terakhir
        self.sidebar.pack(side="left", fill="y", padx=(0, 15))
        ctk.CTkLabel(self.sidebar, text="DATA MASUK", text_color="#38bdf8", font=("Arial", 16, "bold")).pack(pady=15)
        self.history_display = ctk.CTkTextbox(self.sidebar, fg_color="#0f172a", text_color="#fffbeb", font=("Consolas", 14), corner_radius=10) #tempat data daftar barcode muncul
        self.history_display.pack(expand=True, fill="both", padx=15, pady=(0, 10))
        #tombol lihat data 
        self.btn_load_more = ctk.CTkButton(self.sidebar, text="LIHAT DATA LAINNYA", fg_color="#10b981", text_color="black", font=("Arial", 11, "bold"), hover_color="#059669", command=self.muat_lebih_sidebar)
        self.btn_load_more.pack(pady=15, padx=20, fill="x")
        #MAIN AREA (TENGAH)
        self.main_area = ctk.CTkFrame(self.content, corner_radius=20, fg_color="#1e293b") #utama area scan 
        self.main_area.pack(side="right", expand=True, fill="both")
        ctk.CTkLabel(self.main_area, text="HASIL SCAN :", font=("Arial", 18), text_color="#94a3b8").pack(pady=(150, 10)) #menampilkan teks barcode yg baru di scan
        self.result_display = ctk.CTkLabel(self.main_area, text="---", font=("Arial", 45, "bold"), text_color="white")
        self.result_display.pack(pady=10)
        #Kotak input tempat barcode masuk secara otomatis dari alat scanner
        self.entry_barcode = ctk.CTkEntry(self.main_area, width=400, height=55, placeholder_text="Silahkan Scan Barcode...", justify="center", font=("Arial", 18), fg_color="#0f172a", text_color="white") #
        self.entry_barcode.pack(pady=20)
        self.entry_barcode.focus_set() #memastikan kursor aktif

        self.update_clock() 
        self.load_sidebar_history() 
        self.loop_check() 

    def update_clock(self):
        #mengupdate teks jam setiap 1 detik agar waktu terus berjalan 
        self.datetime_label.configure(text=datetime.now().strftime("%A, %d %B %Y\n%H:%M:%S"))
        self.after(1000, self.update_clock)

    # 3. WINDOW HISTORY LENGKAP
    def buka_window_history(self):
        self.win_hist = ctk.CTkToplevel(self)
        self.win_hist.title("Database History Lengkap")
        self.win_hist.geometry("1150x850")
        self.win_hist.attributes('-topmost', True)
        self.current_page = 1
       #Pengaturan gaya tabel (Treeview) 
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#1e293b", foreground="white", fieldbackground="#1e293b", rowheight=35, borderwidth=1)
        style.configure("Treeview.Heading", background="#0f172a", foreground="#38bdf8", font=("Arial", 12, "bold"))
        style.map("Treeview", background=[('selected', '#0ea5e9')])

        self.top_f = ctk.CTkFrame(self.win_hist, fg_color="#1e293b", height=80)
        self.top_f.pack(fill="x", padx=20, pady=10)

        # PENAMAAN TOMBOL 
        self.btn_shift = ctk.CTkButton(self.top_f, text="DATA OPERASIONAL SHIFT", width=150, height=45, font=("Arial", 12, "bold"), fg_color="#0f172a", border_width=1, border_color="#38bdf8", command=self.toggle_shift_panel)
        self.btn_shift.pack(side="left", padx=5)

        self.btn_range = ctk.CTkButton(self.top_f, text="CUSTOM DATE TIME", width=150, height=45, font=("Arial", 12, "bold"), fg_color="#0f172a", border_width=1, border_color="#38bdf8", command=self.toggle_range_panel)
        self.btn_range.pack(side="left", padx=5)
        
        self.hist_time_lbl = ctk.CTkLabel(self.top_f, text="00:00:00", font=("Consolas", 20, "bold"), text_color="#38bdf8")
        self.hist_time_lbl.pack(side="left", padx=15)

        ctk.CTkButton(self.top_f, text="LIHAT SEMUA DATA", fg_color="#10b981", text_color="black", font=("Arial", 11, "bold"), command=self.refresh_history).pack(side="right", padx=15)

        self.shift_panel = ctk.CTkFrame(self.win_hist, fg_color="#f1f5f9", height=0)
        self.shift_panel.pack(fill="x", padx=20)
        
        self.range_panel = ctk.CTkFrame(self.win_hist, fg_color="#f1f5f9", height=0)
        self.range_panel.pack(fill="x", padx=20)

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

        self.pagination_frame = ctk.CTkFrame(self.win_hist, fg_color="transparent")
        self.pagination_frame.pack(fill="x", padx=20, pady=10)
        self.btn_prev = ctk.CTkButton(self.pagination_frame, text="<", width=40, height=40, fg_color="#1e293b", command=self.prev_page)
        self.btn_prev.pack(side="left", padx=5)
        self.page_num_container = ctk.CTkFrame(self.pagination_frame, fg_color="transparent")
        self.page_num_container.pack(side="left", padx=5)
        self.btn_next = ctk.CTkButton(self.pagination_frame, text=">", width=40, height=40, fg_color="#1e293b", command=self.next_page)
        self.btn_next.pack(side="left", padx=5)
        self.result_info = ctk.CTkLabel(self.pagination_frame, text="Results: 0", font=("Arial", 12), text_color="#94a3b8")
        self.result_info.pack(side="right", padx=10) 
        
        self.update_history_clock()
        self.load_full_table(is_initial=True) 

    def setup_picker_ui(self):
        # 1. KONTEN SHIFT
        self.shift_container = ctk.CTkFrame(self.shift_panel, fg_color="transparent")
        inner_cal_shift = ctk.CTkFrame(self.shift_container, fg_color="transparent")
        inner_cal_shift.pack(pady=10)
        self.shift_cal = Calendar(inner_cal_shift, selectmode='day', font="Arial 9", background="#1e3d59", foreground="white")
        self.shift_cal.pack(padx=20)

        btn_f_shift = ctk.CTkFrame(self.shift_container, fg_color="transparent")
        btn_f_shift.pack(pady=10)
        ctk.CTkButton(btn_f_shift, text="SHIFT 1\n(07:00-15:00)", fg_color="#0ea5e9", height=45, command=lambda: self.apply_shift_filter(1)).pack(side="left", padx=5)
        ctk.CTkButton(btn_f_shift, text="SHIFT 2\n(15:00-23:00)", fg_color="#f59e0b", height=45, command=lambda: self.apply_shift_filter(2)).pack(side="left", padx=5)
        ctk.CTkButton(btn_f_shift, text="SHIFT 3\n(23:00-07:00)", fg_color="#6366f1", height=45, command=lambda: self.apply_shift_filter(3)).pack(side="left", padx=5)

        # 2. KONTEN CUSTOM DATE TIME
        self.range_container = ctk.CTkFrame(self.range_panel, fg_color="transparent")
        inner_range = ctk.CTkFrame(self.range_container, fg_color="transparent")
        inner_range.pack(pady=10)
        
        # BLOK START 
        f_start = ctk.CTkFrame(inner_range, fg_color="transparent")
        f_start.grid(row=0, column=0, padx=25)
        
        self.cal_start = Calendar(f_start, selectmode='day', font="Arial 8")
        self.cal_start.pack(pady=(0, 10))
        
        t_start_row = ctk.CTkFrame(f_start, fg_color="transparent")
        t_start_row.pack()
        ctk.CTkLabel(t_start_row, text="START : ", text_color="#1e3d59", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 5))
        self.h_start = ctk.CTkComboBox(t_start_row, values=[f"{i:02d}" for i in range(24)], width=65)
        self.h_start.set("00")
        self.h_start.pack(side="left")
        ctk.CTkLabel(t_start_row, text=":", text_color="black", font=("Arial", 12, "bold")).pack(side="left", padx=2)
        self.m_start = ctk.CTkComboBox(t_start_row, values=[f"{i:02d}" for i in range(60)], width=65)
        self.m_start.set("00")
        self.m_start.pack(side="left")

        # BLOK END
        f_end = ctk.CTkFrame(inner_range, fg_color="transparent")
        f_end.grid(row=0, column=1, padx=25)
        
        self.cal_end = Calendar(f_end, selectmode='day', font="Arial 8")
        self.cal_end.pack(pady=(0, 10))
        
        t_end_row = ctk.CTkFrame(f_end, fg_color="transparent")
        t_end_row.pack()
        # Label diletakkan di samping combo box
        ctk.CTkLabel(t_end_row, text="END : ", text_color="#e11d48", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 5))
        self.h_end = ctk.CTkComboBox(t_end_row, values=[f"{i:02d}" for i in range(24)], width=65)
        self.h_end.set("23")
        self.h_end.pack(side="left")
        ctk.CTkLabel(t_end_row, text=":", text_color="black", font=("Arial", 12, "bold")).pack(side="left", padx=2)
        self.m_end = ctk.CTkComboBox(t_end_row, values=[f"{i:02d}" for i in range(60)], width=65)
        self.m_end.set("59")
        self.m_end.pack(side="left")

        ctk.CTkButton(self.range_container, text="APPLY RANGE", fg_color="#10b981", text_color="black", font=("Arial", 12, "bold"), height=40, command=self.apply_range_filter).pack(pady=20)

    def toggle_shift_panel(self):
        self.range_container.pack_forget()
        self.range_panel.configure(height=0)
        if self.shift_panel.winfo_height() < 10:
            self.shift_panel.configure(height=480)
            self.shift_container.pack(fill="both", expand=True)
        else:
            self.shift_container.pack_forget()
            self.shift_panel.configure(height=0)

    def toggle_range_panel(self):
        self.shift_container.pack_forget()
        self.shift_panel.configure(height=0)
        if self.range_panel.winfo_height() < 10:
            self.range_panel.configure(height=520) 
            self.range_container.pack(fill="both", expand=True)
        else:
            self.range_container.pack_forget()
            self.range_panel.configure(height=0)

    def apply_shift_filter(self, shift_num):
        date_obj = self.shift_cal.selection_get()
        date_str = date_obj.strftime("%Y-%m-%d")
        if shift_num == 1:
            self.filter_start, self.filter_end = f"{date_str} 07:00:00", f"{date_str} 15:00:00"
        elif shift_num == 2:
            self.filter_start, self.filter_end = f"{date_str} 15:00:00", f"{date_str} 23:00:00"
        elif shift_num == 3:
            self.filter_start = f"{date_str} 23:00:00"
            self.filter_end = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d") + " 07:00:00"
        
        self.current_page = 1
        self.toggle_shift_panel()
        self.load_full_table(is_initial=False)

    def apply_range_filter(self):
        s_date = self.cal_start.selection_get().strftime('%Y-%m-%d')
        e_date = self.cal_end.selection_get().strftime('%Y-%m-%d')
        self.filter_start = f"{s_date} {self.h_start.get()}:{self.m_start.get()}:00"
        self.filter_end = f"{e_date} {self.h_end.get()}:{self.m_end.get()}:59"
        self.current_page = 1
        self.toggle_range_panel()
        self.load_full_table(is_initial=False)

    def load_full_table(self, is_initial=False):
        try:
            conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
            if not is_initial and self.filter_start:
                cur.execute("SELECT COUNT(*) FROM latihan.barcode WHERE created_at BETWEEN %s AND %s", (self.filter_start, self.filter_end))
            else:
                cur.execute("SELECT COUNT(*) FROM latihan.barcode")
            total_data = cur.fetchone()[0]
            total_pages = math.ceil(total_data / self.rows_per_page) if total_data > 0 else 1
            offset = (self.current_page - 1) * self.rows_per_page
            if not is_initial and self.filter_start:
                cur.execute("SELECT id, kode_barcode, created_at FROM latihan.barcode WHERE created_at BETWEEN %s AND %s ORDER BY id DESC LIMIT %s OFFSET %s", (self.filter_start, self.filter_end, self.rows_per_page, offset))
            else:
                cur.execute("SELECT id, kode_barcode, created_at FROM latihan.barcode ORDER BY id DESC LIMIT %s OFFSET %s", (self.rows_per_page, offset))
            rows = cur.fetchall()
            for i in self.tree.get_children(): self.tree.delete(i)
            if not rows:
                self.tree.insert("", "end", values=("X", "TIDAK ADA DATA SCAN", "---"))
            else:
                for index, r in enumerate(rows):
                    tag = 'evenrow' if index % 2 == 0 else 'oddrow'
                    self.tree.insert("", "end", values=(r[0], r[1], r[2].strftime("%d/%m/%Y %H:%M:%S")), tags=(tag,))
            end_res = offset + len(rows)
            self.result_info.configure(text=f"Results: {offset+1 if total_data>0 else 0} - {end_res} of {total_data}")
            self.btn_prev.configure(state="normal" if self.current_page > 1 else "disabled")
            self.btn_next.configure(state="normal" if end_res < total_data else "disabled")
            self.update_page_buttons(total_pages)
            cur.close(); conn.close()
        except: pass

    def update_page_buttons(self, total_pages):
        for btn in self.page_buttons: btn.destroy()
        self.page_buttons = []
        start = max(1, self.current_page - 2)
        end = min(total_pages, start + 4)
        if end - start < 4: start = max(1, end - 4)
        for i in range(start, end + 1):
            btn_color = "#0ea5e9" if i == self.current_page else "#1e293b"
            p_btn = ctk.CTkButton(self.page_num_container, text=str(i), width=40, height=40, fg_color=btn_color, command=lambda p=i: self.go_to_page(p))
            p_btn.pack(side="left", padx=2)
            self.page_buttons.append(p_btn)

    def go_to_page(self, page_num):
        self.current_page = page_num; self.load_full_table()

    def next_page(self):
        self.current_page += 1; self.load_full_table()

    def prev_page(self):
        if self.current_page > 1: self.current_page -= 1; self.load_full_table()

    def refresh_history(self):
        self.filter_start = None; self.filter_end = None
        self.current_page = 1
        self.shift_container.pack_forget(); self.shift_panel.configure(height=0)
        self.range_container.pack_forget(); self.range_panel.configure(height=0)
        self.load_full_table(is_initial=True)

    def update_history_clock(self):
        if hasattr(self, 'win_hist') and self.win_hist.winfo_exists():
            self.hist_time_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))
            self.win_hist.after(1000, self.update_history_clock)

    def muat_lebih_sidebar(self):
        self.limit_sidebar += 30; self.load_sidebar_history()

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

    def simpan_data(self, teks):
        try:
            conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
            cur.execute("INSERT INTO latihan.barcode (kode_barcode) VALUES (%s)", (teks,))
            conn.commit(); cur.close(); conn.close()
            return True
        except: return False

    def loop_check(self):
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