import customtkinter as ctk # Library UI / tampilan utama
from tkcalendar import Calendar # Library widget kalender visual 
from datetime import datetime, timedelta # Modul manipulasi tanggal & kalkulasi shift kerja 
import logging # Library pencatat aktivitas sistem 
from app_logging import setup_logging # Ambil fungsi pengaturan awal sistem log
from database import SCHEMA, get_connection # Ambil konfigurasi schema & fungsi koneksi database 

# Menjalankan konfigurasi logging di awal aplikasi
setup_logging()
logger = logging.getLogger(__name__)

class HistoryWindow(ctk.CTkToplevel): 
    def __init__(self, parent): # Inisialisasi jendela riwayat dan pengaturan state
        super().__init__(parent) 
        self.title("Database History")
        self.geometry("1100x750")
        self.configure(fg_color="#0f172a")

        self.resizable(True, True)
        # Memaksa jendela pop-up naik ke fokus layar paling depan
        self.after(200, lambda: self.focus_force())
        
        # Pengelolaan State Management (Variabel Kontrol)
        self.current_page = 1 # Menandai posisi halaman aktif 
        self.rows_per_page = 15 # Membatasi jumlah baris data maksimal per halaman
        self.total_data = 0 # Variabel penampung hitungan total baris data dari database
        self.active_filter_panel = None # Melacak laci filter yang sedang dibuka oleh operator 

        self.filter_start_time = None # Menyimpan batas awal timestamp filter
        self.filter_end_time = None # Menyimpan batas akhir timestamp filter
        
        self.setup_ui() 
        self.after(500, self.load_data) # Jeda aman sebelum mulai menarik data dari database
        self.update_clock() # Menjalankan jam digital real-time di header

    def setup_ui(self):
        # Membangun tata letak visual utama antarmuka window.
        # AREA HEADER ATAS (Tombol Filter & Jam)
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=30, pady=20)
        
        # Tombol pembuka laci filter shift kerja pabrik
        self.btn_shift = ctk.CTkButton( 
            self.header_frame, text="DATA OPERASIONAL SHIFT", 
            fg_color="transparent", border_width=2, border_color="#38bdf8",
            text_color="white", font=("Arial", 12, "bold"), width=180, height=40,
            command=self.toggle_shift_panel
        )
        self.btn_shift.pack(side="left", padx=5)
        
        # Tombol pembuka laci filter rentang tanggal jam kustom
        self.btn_custom = ctk.CTkButton(
            self.header_frame, text="CUSTOM DATE TIME", 
            fg_color="transparent", border_width=2, border_color="#38bdf8",
            text_color="white", font=("Arial", 12, "bold"), width=180, height=40,
            command=self.toggle_custom_panel
        )
        self.btn_custom.pack(side="left", padx=5)

        # Jam digital besar di area tengah header 
        self.clock_label = ctk.CTkLabel(
            self.header_frame, text="00:00:00", 
            font=("Consolas", 32, "bold"), text_color="#38bdf8"
        ) 
        self.clock_label.pack(side="left", padx=40)

        # Tombol reset filter (Lihat semua data)
        self.btn_all = ctk.CTkButton(
            self.header_frame, text="LIHAT SEMUA DATA", 
            fg_color="#0ea5e9", hover_color="#0284c7",
            text_color="white", font=("Arial", 12, "bold"), width=150, height=40,
            command=self.reset_filter
        )
        self.btn_all.pack(side="right")

        # DYNAMIC FILTER PANEL
        self.filter_container = ctk.CTkFrame(self, fg_color="#f1f5f9", height=0)
        self.filter_container.pack(fill="x", padx=30, pady=(0, 10))
        self.filter_container.pack_propagate(False) # Kunci ukuran kontainer agar tidak mengecil

        # TABLE HEADER (Judul Kolom Tabel)
        self.columns = [
            ("NO", 50), ("JOB", 170), ("BATCH", 70), ("SAP RM", 120),
            ("NAMA BAHAN", 230), ("QTY", 80), ("BARCODE/USAGE", 180),
            ("SCAN AT", 170), ("OPERATOR", 100),
        ]
        
        self.table_header_container = ctk.CTkFrame(self, fg_color="transparent")
        self.table_header_container.pack(fill="x", padx=30)
        
        for text, width in self.columns:
            f = ctk.CTkFrame(
                self.table_header_container, width=width, height=40, 
                fg_color="transparent", border_width=1, border_color="#38bdf8"
            )
            f.pack(side="left", padx=1)
            f.pack_propagate(False)
            ctk.CTkLabel(f, text=text, font=("Arial", 11, "bold"), text_color="#38bdf8").pack(expand=True)

        line = ctk.CTkFrame(self, height=2, fg_color="#38bdf8")
        line.pack(fill="x", padx=30, pady=(2, 5))

        # TABLE BODY (Area Scroll Data)
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll_frame.pack(expand=True, fill="both", padx=30)

        # AREA FOOTER BAWAH (Navigasi & Indikator Total)
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(fill="x", padx=30, pady=15)
        
        self.pagination_frame = ctk.CTkFrame(self.footer_frame, fg_color="transparent")
        self.pagination_frame.pack(side="left")
        
        self.total_label = ctk.CTkLabel(self.footer_frame, text="Total: 0 Data", font=("Arial", 12), text_color="#94a3b8")
        self.total_label.pack(side="right")

    def clear_filter_container(self): 
        # Membersihkan widget lama di dalam laci filter
        for widget in self.filter_container.winfo_children():
            widget.destroy()

    def toggle_shift_panel(self):
        # Membuka atau menutup laci panel filter berdasarkan Shift Operasional Kerja.
        if self.active_filter_panel == "shift":
            self.filter_container.configure(height=0)
            self.clear_filter_container()
            self.active_filter_panel = None
        else: 
            self.active_filter_panel = "shift"
            self.filter_container.configure(height=340) 
            self.clear_filter_container()
            
            # Membuat kalender tunggal untuk filter data shift
            self.cal_shift = Calendar(self.filter_container, selectmode='day', font="Arial 8")
            self.cal_shift.pack(pady=8)

            shift_btn_frame = ctk.CTkFrame(self.filter_container, fg_color="transparent")
            shift_btn_frame.pack(pady=5)
            
            # Array data shift berisi: (Teks Tombol, Warna UI, Parameter Nomor Shift)
            shifts = [
                ("SHIFT 1\n(07:00-15:00)", "#38bdf8", 1), 
                ("SHIFT 2\n(15:00-23:00)", "#f59e0b", 2), 
                ("SHIFT 3\n(23:00-07:00)", "#818cf8", 3)
            ]

            # Membuat tombol secara looping dan menyambungkan fungsinya dengan benar lewat command=lambda
            for txt, color, s_num in shifts: 
                ctk.CTkButton(
                    shift_btn_frame, text=txt, fg_color=color, text_color="black",
                    font=("Arial", 10, "bold"), width=120, height=40,
                    command=lambda sn=s_num: self.apply_shift_filter(sn)
                ).pack(side="left", padx=10)

    def apply_shift_filter(self, shift_num):
        # Menghitung konversi tanggal kalender dan batas jam shift menjadi Timestamp Database.
        try:
            selected_date = self.cal_shift.selection_get()
            
            if shift_num == 1:
                start_dt = datetime.combine(selected_date, datetime.min.time()).replace(hour=7, minute=0, second=0)
                end_dt = datetime.combine(selected_date, datetime.min.time()).replace(hour=15, minute=0, second=0)
            elif shift_num == 2:
                start_dt = datetime.combine(selected_date, datetime.min.time()).replace(hour=15, minute=0, second=0)
                end_dt = datetime.combine(selected_date, datetime.min.time()).replace(hour=23, minute=0, second=0)
            elif shift_num == 3:
                start_dt = datetime.combine(selected_date, datetime.min.time()).replace(hour=23, minute=0, second=0)
                end_dt = datetime.combine(selected_date + timedelta(days=1), datetime.min.time()).replace(hour=7, minute=0, second=0)
                
            self.filter_start_time = start_dt  
            self.filter_end_time = end_dt  
            self.current_page = 1  # Reset ke halaman pertama setelah filter berubah
            self.load_data()  
        except Exception:
            logger.exception("Gagal menerapkan filter data operasional shift.")

    def toggle_custom_panel(self):
        # Membuka atau menutup laci panel filter kustom tanggal dan jam secara manual.
        if self.active_filter_panel == "custom":
            self.filter_container.configure(height=0)
            self.clear_filter_container()
            self.active_filter_panel = None
        else:
            self.active_filter_panel = "custom"
            self.filter_container.configure(height=320) # Ditambah sedikit tingginya agar muat rapi
            self.clear_filter_container()

            cal_wrapper = ctk.CTkFrame(self.filter_container, fg_color="transparent")
            cal_wrapper.pack(pady=8)

            #  SISI KIRI (START FILTER)
            f_start = ctk.CTkFrame(cal_wrapper, fg_color="transparent")
            f_start.pack(side="left", padx=15)
            self.cal_custom_start = Calendar(f_start, selectmode='day', font="Arial 8", borderwidth=1)
            self.cal_custom_start.pack(pady=5)
            
            time_row_start = ctk.CTkFrame(f_start, fg_color="transparent")
            time_row_start.pack(pady=2, fill="x")
            ctk.CTkLabel(time_row_start, text="START : ", font=("Arial", 11, "bold"), text_color="black").pack(side="left")
            self.combo_start_hour = ctk.CTkComboBox(time_row_start, values=[f"{i:02d}" for i in range(24)], width=65, height=25)
            self.combo_start_hour.pack(side="left", padx=2)
            self.combo_start_hour.set("00")
            self.combo_start_min = ctk.CTkComboBox(time_row_start, values=[f"{i:02d}" for i in range(60)], width=65, height=25)
            self.combo_start_min.pack(side="left", padx=2)
            self.combo_start_min.set("00")

            # SISI KANAN (END FILTER)
            f_end = ctk.CTkFrame(cal_wrapper, fg_color="transparent")
            f_end.pack(side="left", padx=15)
            self.cal_custom_end = Calendar(f_end, selectmode='day', font="Arial 8", borderwidth=1)
            self.cal_custom_end.pack(pady=5)
            
            time_row_end = ctk.CTkFrame(f_end, fg_color="transparent")
            time_row_end.pack(pady=2, fill="x")
            ctk.CTkLabel(time_row_end, text="END : ", font=("Arial", 11, "bold"), text_color="black").pack(side="left")
            self.combo_end_hour = ctk.CTkComboBox(time_row_end, values=[f"{i:02d}" for i in range(24)], width=65, height=25)
            self.combo_end_hour.pack(side="left", padx=2)
            self.combo_end_hour.set("23")
            self.combo_end_min = ctk.CTkComboBox(time_row_end, values=[f"{i:02d}" for i in range(60)], width=65, height=25)
            self.combo_end_min.pack(side="left", padx=2)
            self.combo_end_min.set("59")
            
            # Tombol eksekusi dengan fungsi yang sudah terhubung
            ctk.CTkButton(
                self.filter_container, text="APPLY FILTER RANGE", 
                fg_color="#0ea5e9", hover_color="#0284c7", width=200, height=35, 
                font=("Arial", 11, "bold"), command=self.apply_custom_range_filter
            ).pack(pady=10)

    def apply_custom_range_filter(self):
        # Menggabungkan teks tanggal kalender kustom beserta jam pilihan ComboBox
        try:
            date_start = self.cal_custom_start.selection_get()
            h_start = int(self.combo_start_hour.get())
            m_start = int(self.combo_start_min.get())
            dt_start = datetime.combine(date_start, datetime.min.time()).replace(hour=h_start, minute=m_start, second=0)

            # Menggunakan selection_get() untuk kalender akhir
            date_end = self.cal_custom_end.selection_get()
            h_end = int(self.combo_end_hour.get())
            m_end = int(self.combo_end_min.get())
            dt_end = datetime.combine(date_end, datetime.min.time()).replace(hour=h_end, minute=m_end, second=59)

            # Sistem Interlock Proteksi terbalik input tanggal
            if dt_start > dt_end:
                dt_start, dt_end = dt_end, dt_start

            self.filter_start_time = dt_start  
            self.filter_end_time = dt_end  
            self.current_page = 1  
            self.load_data()  
        except Exception:
            logger.exception("Gagal menerapkan filter kustom tanggal dan jam.") # catat eror 
    
    def reset_filter(self):
        # Menghapus seluruh filter aktif & kembali menampilkan semua data semula.
        self.filter_container.configure(height=0)
        self.clear_filter_container() 
        self.active_filter_panel = None 
        self.filter_start_time = None  
        self.filter_end_time = None
        self.current_page = 1
        self.load_data()

    def update_clock(self):
        # Fungsi rekursif jam digital pada header window.
        now = datetime.now().strftime("%H:%M:%S") 
        self.clock_label.configure(text=now) 
        self.after(1000, self.update_clock) 

    def create_pagination_buttons(self): 
        # Membangun susunan tombol nomor halaman dinamis (footer kiri).
        for widget in self.pagination_frame.winfo_children(): 
            widget.destroy()
            
        num_pages = max(1, (self.total_data // self.rows_per_page) + (1 if self.total_data % self.rows_per_page > 0 else 0)) 
        
        # Tombol Navigasi Mundur
        ctk.CTkButton(self.pagination_frame, text="<", width=35, command=lambda: self.change_page(self.current_page - 1)).pack(side="left", padx=2) 
        
        start_p = max(1, self.current_page - 1) 
        end_p = min(num_pages, start_p + 2)
        
        for i in range(start_p, end_p + 1):
            bg = "#38bdf8" if i == self.current_page else "#1e293b"
            text_color = "black" if i == self.current_page else "white"
            ctk.CTkButton(
                self.pagination_frame, text=str(i), width=35, fg_color=bg, text_color=text_color,
                font=("Arial", 11, "bold"), command=lambda p=i: self.change_page(p)
            ).pack(side="left", padx=2)
            
        # Tombol Navigasi Maju 
        ctk.CTkButton(self.pagination_frame, text=">", width=35, command=lambda: self.change_page(self.current_page + 1)).pack(side="left", padx=2) 

    def change_page(self, page):
        # Pindah target halaman tabel ke nomor halaman baru.
        num_pages = max(1, (self.total_data // self.rows_per_page) + (1 if self.total_data % self.rows_per_page > 0 else 0))
        if 0 < page <= num_pages:
            self.current_page = page
            self.load_data()
    
    def load_data(self):
        # Menarik record data penggunaan material dari database PostgreSQL secara dinamis.
        for widget in self.scroll_frame.winfo_children(): 
            widget.destroy()
            
        conn = None
        cur = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            # KONSTRUKSI WHERE CLAUSE DINAMIS 
            where_clauses = ["u.\"scan_at\" IS NOT NULL"]
            query_params = []
            
            # Parameter filter waktu jika operator sedang menyaring data
            if self.filter_start_time and self.filter_end_time:
                where_clauses.append("u.\"scan_at\" BETWEEN %s AND %s")
                query_params.extend([self.filter_start_time, self.filter_end_time])
                
            where_stmt = " WHERE " + " AND ".join(where_clauses)
            
            # Hitung total data berdasarkan filter aktif
            count_query = f"SELECT COUNT(*) FROM {SCHEMA}.formulasi_material_usage u {where_stmt}"
            cur.execute(count_query, query_params)
            self.total_data = cur.fetchone()[0]
            
            offset = (self.current_page - 1) * self.rows_per_page 

            # Ambil data halaman aktif sesuai limit dan offset halaman
            query = f"""
                SELECT
                    u.id,
                    COALESCE(j.nomor_job, '-') AS nomor_job,
                    u."batch",
                    u."sap_rm",
                    COALESCE(mi.nama_bahan_baku, '-') AS nama_bahan_baku,
                    COALESCE(u."qty_dipakai", 0) AS qty_dipakai,
                    COALESCE(u."barcode_pallet", '-') AS barcode_pallet,
                    u."scan_at",
                    COALESCE(u."scan_oleh", '-') AS scan_oleh
                FROM {SCHEMA}.formulasi_material_usage u
                LEFT JOIN {SCHEMA}.formulasi_joblist j ON j.id = u."joblistId"
                LEFT JOIN {SCHEMA}.master_resep_item mi ON mi."resepId" = j."resepId" AND mi.sap_rm = u."sap_rm"
                {where_stmt}
                ORDER BY u."scan_at" DESC NULLS LAST, u.id DESC
                LIMIT %s OFFSET %s
            """
            exec_params = query_params + [self.rows_per_page, offset]
            cur.execute(query, exec_params)
            rows = cur.fetchall()

            base_no = offset + 1 
            for idx, row in enumerate(rows):
                r_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
                r_frame.pack(fill="x", pady=1)

                usage_id = str(row[0]) if row[0] else "-"
                barcode_or_usage = str(row[6]) if row[6] and str(row[6]).strip() else usage_id
                vals = [
                    str(base_no + idx), # Kolom no baris data 
                    str(row[1]), # Kolom nomor job SAP
                    str(row[2]), # Kolom no batch produksi 
                    str(row[3]), # Kolom kode SAP materialRM 
                    str(row[4])[:32], # kolom nama bahan baku 
                    f"{float(row[5]):g}", # Kolom qty 
                    barcode_or_usage[:24], 
                    row[7].strftime("%Y-%m-%d %H:%M:%S") if row[7] else "-", 
                    str(row[8]), 
                ] 
                for i, val in enumerate(vals):
                    f = ctk.CTkFrame(r_frame, width=self.columns[i][1], height=35, fg_color="transparent", border_width=1, border_color="#334155")
                    f.pack(side="left", padx=1)
                    f.pack_propagate(False)
                    ctk.CTkLabel(f, text=val, font=("Arial", 10), text_color="white").pack(expand=True)

            self.total_label.configure(text=f"Total: {self.total_data} Data")
            self.create_pagination_buttons() 
            
        except Exception:
            logger.exception("Error loading data history")
        finally:
            # BLOK INTERLOCK KEAMANAN:
            if cur: cur.close()
            if conn: conn.close()