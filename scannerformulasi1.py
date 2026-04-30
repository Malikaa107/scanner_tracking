import customtkinter as ctk 
import time
import os 
from PIL import Image 
from datetime import datetime, timedelta 
import psycopg2 
from tkinter import ttk 
import math 

# Menentukan lokasi folder script picture
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Konfigurasi Database (Host, Nama DB, User, Password)
DB_CONFIG = { 
    "host": "localhost",
    "database": "postgres", 
    "user": "postgres",
    "password": "",
    "port": "5432"
}

# Fungsi untuk membuka koneksi ke database PostgreSQL
def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# Fungsi untuk menyimpan teks barcode yang berhasil di-scan ke tabel database
def simpan_data(teks):
    try:
        conn = get_connection() 
        cur = conn.cursor() 
        cur.execute("INSERT INTO latihan.barcode (kode_barcode) VALUES (%s)", (teks,)) 
        conn.commit() 
        cur.close()
        conn.close() 
        return True 
    except Exception as e:
        print(f"Error simpan_data: {e}") 
        return False 


try:
    from tkcalendar import Calendar
except ImportError:
    Calendar = None 


class HistoryWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent) # Menghubungkan dengan jendela utama 
        self.title("Database History Lengkap") # Memberi judul jendela pop-up
        self.geometry("1150x850") # Mengatur ukuran jendela history
        self.configure(fg_color="#0f172a") # Mengatur warna latar belakang jendela
        self.attributes('-topmost', True) 
        
        self.current_page = 1
        self.rows_per_page = 15 
        self.filter_start = None 
        self.filter_end = None 
        self.page_buttons = [] 

        style = ttk.Style() # Membuat objek style untuk tabel
        style.theme_use("clam") # Menggunakan tema 'clam' agar tabel bisa diwarnai custom
        style.configure("Treeview", background="#1e293b", foreground="white", fieldbackground="#1e293b", rowheight=35, borderwidth=0, font=("Arial", 11)) # Warna body tabel
        style.configure("Treeview.Heading", background="#0f172a", foreground="#38bdf8", font=("Arial", 11, "bold")) # Warna judul kolom tabel
        style.map("Treeview", background=[('selected', '#334155')]) # Warna saat baris tabel diklik

        self.setup_ui() # Memanggil fungsi penyusun tampilan history
        self.update_history_clock() # Memanggil fungsi jam real-time di history
        self.load_full_table(is_initial=True) # Memuat data pertama kali ke tabel

    # Mengatur elemen UI di dalam jendela history
    def setup_ui(self):
        self.top_f = ctk.CTkFrame(self, fg_color="transparent", height=80) # Frame bagian atas untuk tombol filter
        self.top_f.pack(fill="x", padx=20, pady=20)

        self.btn_shift = ctk.CTkButton(self.top_f, text="DATA OPERASIONAL SHIFT", width=180, height=45, font=("Arial", 11, "bold"), fg_color="#0f172a", border_width=2, border_color="#38bdf8", text_color="white", command=self.toggle_shift_panel) # Tombol filter shift
        self.btn_shift.pack(side="left", padx=5)

        self.btn_range = ctk.CTkButton(self.top_f, text="CUSTOM DATE TIME", width=180, height=45, font=("Arial", 11, "bold"), fg_color="#0f172a", border_width=2, border_color="#38bdf8", text_color="white", command=self.toggle_range_panel) # Tombol filter rentang tanggal
        self.btn_range.pack(side="left", padx=5)
        
        self.hist_time_lbl = ctk.CTkLabel(self.top_f, text="00:00:00", font=("Consolas", 24, "bold"), text_color="#38bdf8") # Label jam digital
        self.hist_time_lbl.pack(side="left", padx=25)

        ctk.CTkButton(self.top_f, text="LIHAT SEMUA DATA", fg_color="#0891b2", hover_color="#0e7490", text_color="white", font=("Arial", 11, "bold"), width=160, height=45, command=self.refresh_history).pack(side="right", padx=5) # Tombol reset filter

        self.shift_panel = ctk.CTkFrame(self, fg_color="#f1f5f9", height=0) # Panel tersembunyi untuk pilihan Shift
        self.shift_panel.pack(fill="x", padx=20)
        self.range_panel = ctk.CTkFrame(self, fg_color="#f1f5f9", height=0) # Panel tersembunyi untuk pilihan Kalender
        self.range_panel.pack(fill="x", padx=20)

        self.setup_picker_ui() # Memanggil isi panel filter (kalender & jam)

        self.tree_container = ctk.CTkFrame(self, fg_color="transparent") # Wadah untuk tabel
        self.tree_container.pack(expand=True, fill="both", padx=20, pady=10)
        self.tree = ttk.Treeview(self.tree_container, columns=("ID", "Barcode", "Waktu"), show='headings') # Membuat kolom tabel
        self.tree.heading("ID", text="NO"); self.tree.heading("Barcode", text="KODE BARCODE"); self.tree.heading("Waktu", text="WAKTU SCAN")
        self.tree.column("ID", width=100, anchor="center"); self.tree.column("Barcode", width=650, anchor="center"); self.tree.column("Waktu", width=350, anchor="center")
        self.tree.tag_configure('oddrow', background='#1e293b'); self.tree.tag_configure('evenrow', background='#0f172a'); self.tree.pack(side="left", expand=True, fill="both") # Pengaturan warna baris selang-seling
        
        self.pagination_frame = ctk.CTkFrame(self, fg_color="transparent") # Frame untuk tombol navigasi halaman (paginasi)
        self.pagination_frame.pack(fill="x", padx=20, pady=20)
        self.btn_prev = ctk.CTkButton(self.pagination_frame, text="<", width=40, height=40, fg_color="#1e293b", font=("Arial", 12, "bold"), command=self.prev_page) # Tombol halaman sebelumnya
        self.btn_prev.pack(side="left", padx=5)
        self.page_num_container = ctk.CTkFrame(self.pagination_frame, fg_color="transparent") # Wadah tombol angka halaman
        self.page_num_container.pack(side="left", padx=5)
        self.btn_next = ctk.CTkButton(self.pagination_frame, text=">", width=40, height=40, fg_color="#1e293b", font=("Arial", 12, "bold"), command=self.next_page) # Tombol halaman selanjutnya
        self.btn_next.pack(side="left", padx=5)
        self.result_info = ctk.CTkLabel(self.pagination_frame, text="Results: 0", font=("Arial", 12), text_color="#94a3b8") # Keterangan jumlah data
        self.result_info.pack(side="right", padx=10)

    # Mengatur isi dari filter (Kalender & Pilihan Jam)
    def setup_picker_ui(self):
        self.shift_container = ctk.CTkFrame(self.shift_panel, fg_color="transparent") # Wadah filter shift
        self.shift_cal = Calendar(self.shift_container, selectmode='day', font="Arial 9") # Widget kalender shift
        self.shift_cal.pack(pady=10) 
        btn_f_shift = ctk.CTkFrame(self.shift_container, fg_color="transparent"); btn_f_shift.pack(pady=10)
        ctk.CTkButton(btn_f_shift, text="SHIFT 1\n(07:00-15:00)", fg_color="#38bdf8", text_color="#000000", font=("Arial", 11, "bold"), height=45, command=lambda: self.apply_shift_filter(1)).pack(side="left", padx=5) # Tombol shift 1
        ctk.CTkButton(btn_f_shift, text="SHIFT 2\n(15:00-23:00)", fg_color="#f59e0b", text_color="#000000", font=("Arial", 11, "bold"), height=45, command=lambda: self.apply_shift_filter(2)).pack(side="left", padx=5) # Tombol shift 2
        ctk.CTkButton(btn_f_shift, text="SHIFT 3\n(23:00-07:00)", fg_color="#818cf8", text_color="#000000", font=("Arial", 11, "bold"), height=45, command=lambda: self.apply_shift_filter(3)).pack(side="left", padx=5) # Tombol shift 3
        
        self.range_container = ctk.CTkFrame(self.range_panel, fg_color="transparent") # Wadah filter custom range
        inner_range = ctk.CTkFrame(self.range_container, fg_color="transparent"); inner_range.pack(pady=10)
        f_start = ctk.CTkFrame(inner_range, fg_color="transparent"); f_start.grid(row=0, column=0, padx=25)
        self.cal_start = Calendar(f_start, selectmode='day', font="Arial 8"); self.cal_start.pack(pady=(0, 10)) # Pengaturan Kalender
        t_start_row = ctk.CTkFrame(f_start, fg_color="transparent"); t_start_row.pack()
        ctk.CTkLabel(t_start_row, text="START : ", text_color="#1e293b", font=("Arial", 11, "bold")).pack(side="left")
        self.h_start = ctk.CTkComboBox(t_start_row, values=[f"{i:02d}" for i in range(24)], width=60); self.h_start.set("00"); self.h_start.pack(side="left") # Jam mulai
        self.m_start = ctk.CTkComboBox(t_start_row, values=[f"{i:02d}" for i in range(60)], width=60); self.m_start.set("00"); self.m_start.pack(side="left") # Menit mulai
        f_end = ctk.CTkFrame(inner_range, fg_color="transparent"); f_end.grid(row=0, column=1, padx=25)
        self.cal_end = Calendar(f_end, selectmode='day', font="Arial 8"); self.cal_end.pack(pady=(0, 10)) 
        t_end_row = ctk.CTkFrame(f_end, fg_color="transparent"); t_end_row.pack()
        ctk.CTkLabel(t_end_row, text="END : ", text_color="#e11d48", font=("Arial", 11, "bold")).pack(side="left")
        self.h_end = ctk.CTkComboBox(t_end_row, values=[f"{i:02d}" for i in range(24)], width=60); self.h_end.set("23"); self.h_end.pack(side="left") # Jam selesai
        self.m_end = ctk.CTkComboBox(t_end_row, values=[f"{i:02d}" for i in range(60)], width=60); self.m_end.set("59"); self.m_end.pack(side="left") # Menit selesai
        ctk.CTkButton(self.range_container, text="APPLY FILTER RANGE", fg_color="#0ea5e9", text_color="#000000", font=("Arial", 12, "bold"), height=40, width=200, command=self.apply_range_filter).pack(pady=20) # Tombol eksekusi filter custom

    # open / close panel shift
    def toggle_shift_panel(self): 
        self.range_container.pack_forget(); self.range_panel.configure(height=0) 
        if self.shift_panel.winfo_height() < 10:
            self.shift_panel.configure(height=480); self.shift_container.pack(fill="both", expand=True)
        else:
            self.shift_container.pack_forget(); self.shift_panel.configure(height=0)

    # open / close panel range tanggal
    def toggle_range_panel(self):
        self.shift_container.pack_forget(); self.shift_panel.configure(height=0)
        if self.range_panel.winfo_height() < 10:
            self.range_panel.configure(height=520); self.range_container.pack(fill="both", expand=True)
        else:
            self.range_container.pack_forget(); self.range_panel.configure(height=0)

    # Menerapkan filter berdasarkan pilihan shift jam kerja
    def apply_shift_filter(self, shift_num):
        date_obj = self.shift_cal.selection_get(); date_str = date_obj.strftime("%Y-%m-%d")
        if shift_num == 1: self.filter_start, self.filter_end = f"{date_str} 07:00:00", f"{date_str} 15:00:00"
        elif shift_num == 2: self.filter_start, self.filter_end = f"{date_str} 15:00:00", f"{date_str} 23:00:00"
        elif shift_num == 3: 
            self.filter_start = f"{date_str} 23:00:00"
            self.filter_end = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d") + " 07:00:00"
        self.current_page = 1; self.toggle_shift_panel(); self.load_full_table()

    # Menerapkan filter berdasarkan input kalender dan jam custom 
    def apply_range_filter(self):
        s_date = self.cal_start.selection_get().strftime('%Y-%m-%d')
        e_date = self.cal_end.selection_get().strftime('%Y-%m-%d')
        self.filter_start = f"{s_date} {self.h_start.get()}:{self.m_start.get()}:00"
        self.filter_end = f"{e_date} {self.h_end.get()}:{self.m_end.get()}:59"
        self.current_page = 1; self.toggle_range_panel(); self.load_full_table()

    # Mengambil data dari database dan menampilkannya ke tabel utama (History) 
    def load_full_table(self, is_initial=False):
        try:
            conn = get_connection(); cur = conn.cursor()
            if not is_initial and self.filter_start:
                cur.execute("SELECT COUNT(*) FROM latihan.barcode WHERE created_at BETWEEN %s AND %s", (self.filter_start, self.filter_end)) # Menghitung jumlah data terfilter
            else:
                cur.execute("SELECT COUNT(*) FROM latihan.barcode") # Menghitung semua data
            total_data = cur.fetchone()[0]
            total_pages = math.ceil(total_data / self.rows_per_page) if total_data > 0 else 1
            offset = (self.current_page - 1) * self.rows_per_page # Logika lompatan data per halaman 
            if not is_initial and self.filter_start:
                cur.execute("SELECT id, kode_barcode, created_at FROM latihan.barcode WHERE created_at BETWEEN %s AND %s ORDER BY id DESC LIMIT %s OFFSET %s", (self.filter_start, self.filter_end, self.rows_per_page, offset)) # Ambil data terfilter
            else:
                cur.execute("SELECT id, kode_barcode, created_at FROM latihan.barcode ORDER BY id DESC LIMIT %s OFFSET %s", (self.rows_per_page, offset)) # Ambil semua data
            rows = cur.fetchall()
            for i in self.tree.get_children(): self.tree.delete(i) # Mengosongkan tabel sebelum diisi data baru
            for index, r in enumerate(rows):
                tag = 'evenrow' if index % 2 == 0 else 'oddrow'
                self.tree.insert("", "end", values=(r[0], r[1], r[2].strftime("%d/%m/%Y %H:%M:%S")), tags=(tag,)) # Memasukkan baris data ke tabel
            self.result_info.configure(text=f"Results: {offset+1} - {offset+len(rows)} of {total_data}") # Menampilkan teks info data
            self.update_page_buttons(total_pages) # Memperbarui nomor halaman
            cur.close(); conn.close()
        except: pass

    # Membuat tombol angka halaman dinamis
    def update_page_buttons(self, total_pages):
        for btn in self.page_buttons: btn.destroy() # Menghapus tombol lama
        self.page_buttons = []
        start = max(1, self.current_page - 2); end = min(total_pages, start + 4) # Mengatur tampilan rentang nomor halaman
        for i in range(start, end + 1):
            btn_color = "#0ea5e9" if i == self.current_page else "#1e293b" 
            p_btn = ctk.CTkButton(self.page_num_container, text=str(i), width=40, height=40, fg_color=btn_color, text_color="white" if i != self.current_page else "#000000", font=("Arial", 11, "bold"), command=lambda p=i: self.go_to_page(p)) # Membuat tombol angka
            p_btn.pack(side="left", padx=4); self.page_buttons.append(p_btn)

    def go_to_page(self, page_num): self.current_page = page_num; self.load_full_table() # Pindah ke halaman tertentu
    def next_page(self): self.current_page += 1; self.load_full_table() # Pindah ke halaman depan
    def prev_page(self): 
        if self.current_page > 1: self.current_page -= 1; self.load_full_table() # Pindah ke halaman belakang

    # Mengatur tombol Refresh untuk menghapus filter dan kembali ke halaman 1
    def refresh_history(self):
        self.filter_start = None 
        self.current_page = 1 # halaman kembali
        self.shift_container.pack_forget(); self.shift_panel.configure(height=0)
        self.range_container.pack_forget(); self.range_panel.configure(height=0)
        self.load_full_table(is_initial=True)

    def update_history_clock(self): # update jam realtime di jendela history
        self.hist_time_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self.update_history_clock)

# Jendela utama program scanner 
class AppScanner(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistem Scanner Formulasi")
        self.geometry("1200x800")
        self.configure(fg_color="#0f172a")

        self.last_input_time = time.time()
        self.last_val_length = 0
        self.limit_sidebar = 25

        self.setup_ui()
        self.update_clock()
        self.load_sidebar_history()
        self.loop_check()
    
    def setup_ui(self):
        # HEADER
        self.header = ctk.CTkFrame(self, height=110, corner_radius=0, fg_color="#1e3d59")
        self.header.pack(side="top", fill="x")

        # LOGO
        try:
            logo_path = os.path.join(BASE_DIR, "logo2.png")
            img_logo = Image.open(logo_path)
            self.logo_img = ctk.CTkImage(img_logo, size=(70, 70))
            ctk.CTkLabel(self.header, text="", image=self.logo_img).place(x=25, y=20)
        except:
            ctk.CTkLabel(self.header, text="LOGO", fg_color="#e11d48", text_color="white", width=70, height=70).place(x=25, y=20)

        
        ctk.CTkLabel(self.header, text="SISTEM SCANNER FORMULASI", font=("Franklin Gothic Heavy", 28, "bold"), text_color="white").place(x=115, y=40)

        # JAM
        self.datetime_label = ctk.CTkLabel(self.header, text="", font=("Arial", 14, "bold"), text_color="#38bdf8")
        self.datetime_label.place(relx=0.97, rely=0.15, anchor="ne")

        # TOMBOL HISTORY
        try:
            icon_path = os.path.join(BASE_DIR, "icon_history2.png")
            self.icon_header = ctk.CTkImage(Image.open(icon_path), size=(20, 20))
        except:
            self.icon_header = None

        self.btn_full = ctk.CTkButton(self.header, text="HISTORY", image=self.icon_header, compound="left",
                                    fg_color="#6366f1", hover_color="#4f46e5", font=("Arial", 12, "bold"),
                                    command=self.buka_window_history)
        self.btn_full.place(relx=0.97, rely=0.6, anchor="ne")

        # CONTENT AREA
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(expand=True, fill="both", padx=20, pady=20)

        # SIDEBAR
        self.sidebar = ctk.CTkFrame(self.content, width=300, corner_radius=20, fg_color="#1e293b")
        self.sidebar.pack(side="left", fill="y", padx=(0, 15))
        self.sidebar.pack_propagate(False) # Agar lebar tetap 300

        ctk.CTkLabel(self.sidebar, text="DATA MASUK", text_color="#38bdf8", font=("Arial", 16, "bold")).pack(pady=15)

        self.history_display = ctk.CTkTextbox(self.sidebar, fg_color="#0f172a", text_color="#fffbeb", font=("Consolas", 14), corner_radius=10)
        self.history_display.pack(expand=True, fill="both", padx=15, pady=(0, 10))

        self.btn_more = ctk.CTkButton(self.sidebar, text="LIHAT DATA LAINNYA", fg_color="#0ea5e9", text_color="black",
                                    hover_color="#38bdf8", font=("Arial", 12, "bold"), command=self.tambah_limit_sidebar)
        self.btn_more.pack(pady=15, padx=15, fill="x")

        # MAIN SCAN AREA
        self.main_area = ctk.CTkFrame(self.content, corner_radius=20, fg_color="#1e293b")
        self.main_area.pack(side="right", expand=True, fill="both")

        ctk.CTkLabel(self.main_area, text="HASIL SCAN :", font=("Arial", 18, "bold"), text_color="#94a3b8").pack(pady=(150, 5)) 
        self.result_display = ctk.CTkLabel(self.main_area, text="---", font=("Arial", 40, "bold"), text_color="white", wraplength=600)
        self.result_display.pack(pady=10)

        self.entry_barcode = ctk.CTkEntry(self.main_area, width=450, height=60, justify="center", font=("Arial", 22),
                                        placeholder_text="Silahkan scan barcode...", fg_color="#0f172a",
                                        text_color="white", border_color="#38bdf8")
        self.entry_barcode.pack(pady=20)
        self.entry_barcode.focus_set()

    def tambah_limit_sidebar(self):
        self.limit_sidebar += 50
        self.load_sidebar_history()

    def load_sidebar_history(self):
        try:
            conn = get_connection() 
            cur = conn.cursor()
            cur.execute(f"SELECT kode_barcode FROM latihan.barcode ORDER BY id DESC LIMIT {self.limit_sidebar}")
            rows = cur.fetchall()
            
            self.history_display.configure(state="normal")
            self.history_display.delete("1.0", "end")
            if rows:
                for idx, row in enumerate(rows, 1):
                    self.history_display.insert("end", f" {idx:02d}. {row[0]}\n")
            else:
                self.history_display.insert("end", " (Belum ada data)\n")
            
            self.history_display.configure(state="disabled")
            cur.close(); conn.close()
        except Exception as e:
            print(f"DEBUG DATABASE: {e}") 

    def buka_window_history(self):
        HistoryWindow(self)

    def update_clock(self):
        self.datetime_label.configure(text=datetime.now().strftime("%A, %d %B %Y\n%H:%M:%S"))
        self.after(1000, self.update_clock)

    def loop_check(self):
        val = self.entry_barcode.get().strip()
        if val:
            if len(val) != self.last_val_length:
                self.last_input_time = time.time()
                self.last_val_length = len(val)

            if time.time() - self.last_input_time > 0.3:
                self.result_display.configure(text=val, text_color="#22c55e")
                if simpan_data(val):
                    self.load_sidebar_history()
                self.entry_barcode.delete(0, 'end')
                self.last_val_length = 0

        self.after(100, self.loop_check)

if __name__ == "__main__":
    app = AppScanner()
    app.mainloop()