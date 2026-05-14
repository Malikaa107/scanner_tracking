import customtkinter as ctk
from tkcalendar import Calendar
from datetime import datetime
import os
import logging
from app_logging import setup_logging
from database import get_connection

setup_logging()
logger = logging.getLogger(__name__)

class HistoryWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Database History Lengkap")
        self.geometry("1100x750")
        self.configure(fg_color="#0f172a")
        
        self.after(200, lambda: self.focus_force())
        self.transient(parent)
        
        # State Management
        self.current_page = 1
        self.rows_per_page = 15
        self.total_data = 0
        self.active_filter_panel = None 
        
        self.setup_ui()
        self.after(500, self.load_data) # Jeda
        self.update_clock()

    def setup_ui(self):
        #  HEADER AREA
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=30, pady=20)

        self.btn_shift = ctk.CTkButton(self.header_frame, text="DATA OPERASIONAL SHIFT", 
                                       fg_color="transparent", border_width=2, border_color="#38bdf8",
                                       text_color="white", font=("Arial", 12, "bold"), width=180, height=40,
                                       command=self.toggle_shift_panel)
        self.btn_shift.pack(side="left", padx=5)

        self.btn_custom = ctk.CTkButton(self.header_frame, text="CUSTOM DATE TIME", 
                                        fg_color="transparent", border_width=2, border_color="#38bdf8",
                                        text_color="white", font=("Arial", 12, "bold"), width=180, height=40,
                                        command=self.toggle_custom_panel)
        self.btn_custom.pack(side="left", padx=5)

        self.clock_label = ctk.CTkLabel(self.header_frame, text="00:00:00", 
                                        font=("Consolas", 32, "bold"), text_color="#38bdf8")
        self.clock_label.pack(side="left", padx=40)

        self.btn_all = ctk.CTkButton(self.header_frame, text="LIHAT SEMUA DATA", 
                                     fg_color="#0ea5e9", hover_color="#0284c7",
                                     text_color="white", font=("Arial", 12, "bold"), width=150, height=40,
                                     command=self.reset_filter)
        self.btn_all.pack(side="right")

        # DYNAMIC FILTER PANEL 
        self.filter_container = ctk.CTkFrame(self, fg_color="#f1f5f9", height=0)
        self.filter_container.pack(fill="x", padx=30, pady=(0, 10))
        self.filter_container.pack_propagate(False)

        #  TABLE HEADER 
        self.columns = [
            ("NO", 60), ("BATCH ID", 110), ("NAMA BAHAN", 310), 
            ("KODE BARCODE", 220), ("WAKTU SCAN", 220), ("MENIT KE-", 110)
        ]
        
        self.table_header_container = ctk.CTkFrame(self, fg_color="transparent")
        self.table_header_container.pack(fill="x", padx=30)
        
        for text, width in self.columns:
            f = ctk.CTkFrame(self.table_header_container, width=width, height=40, 
                             fg_color="transparent", border_width=1, border_color="#38bdf8")
            f.pack(side="left", padx=1)
            f.pack_propagate(False)
            ctk.CTkLabel(f, text=text, font=("Arial", 11, "bold"), text_color="#38bdf8").pack(expand=True)

        line = ctk.CTkFrame(self, height=2, fg_color="#38bdf8")
        line.pack(fill="x", padx=30, pady=(2, 5))

        #  TABLE BODY
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll_frame.pack(expand=True, fill="both", padx=30)

        # Footer
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(fill="x", padx=30, pady=15)
        self.pagination_frame = ctk.CTkFrame(self.footer_frame, fg_color="transparent")
        self.pagination_frame.pack(side="left")
        self.total_label = ctk.CTkLabel(self.footer_frame, text="Total: 0 Data", font=("Arial", 12), text_color="#94a3b8")
        self.total_label.pack(side="right")

    def clear_filter_container(self):
        for widget in self.filter_container.winfo_children():
            widget.destroy()

    def toggle_shift_panel(self):
        if self.active_filter_panel == "shift":
            self.filter_container.configure(height=0)
            self.clear_filter_container()
            self.active_filter_panel = None
        else:
            self.active_filter_panel = "shift"
            self.filter_container.configure(height=340) 
            self.clear_filter_container()
            
            # Kalender
            self.cal_shift = Calendar(self.filter_container, selectmode='day', font="Arial 8")
            self.cal_shift.pack(pady=8)

            shift_btn_frame = ctk.CTkFrame(self.filter_container, fg_color="transparent")
            shift_btn_frame.pack(pady=5)
            shifts = [("SHIFT 1\n(07:00-15:00)", "#38bdf8"), ("SHIFT 2\n(15:00-23:00)", "#f59e0b"), ("SHIFT 3\n(23:00-07:00)", "#818cf8")]
            for txt, color in shifts:
                ctk.CTkButton(shift_btn_frame, text=txt, fg_color=color, text_color="black",
                              font=("Arial", 10, "bold"), width=120, height=40).pack(side="left", padx=10)

    def toggle_custom_panel(self):
        if self.active_filter_panel == "custom":
            self.filter_container.configure(height=0)
            self.clear_filter_container()
            self.active_filter_panel = None
        else:
            self.active_filter_panel = "custom"
            self.filter_container.configure(height=300) 
            self.clear_filter_container()

            cal_wrapper = ctk.CTkFrame(self.filter_container, fg_color="transparent")
            cal_wrapper.pack(pady=8)

            for label_text in ["START", "END"]:
                f_side = ctk.CTkFrame(cal_wrapper, fg_color="transparent")
                f_side.pack(side="left", padx=15)
                
                # Kalender custom
                cal = Calendar(f_side, selectmode='day', font="Arial 8", borderwidth=1)
                cal.pack(pady=8)
                
                # Frame untuk baris jam
                time_row = ctk.CTkFrame(f_side, fg_color="transparent")
                time_row.pack(pady=5, fill="x")
                
                # Label diletakkan di kiri
                ctk.CTkLabel(time_row, text=f"{label_text} : ", font=("Arial", 11, "bold"), 
                             text_color="black").pack(side="left", padx=(0, 5))
                
                # Jam 
                ctk.CTkComboBox(time_row, values=[f"{i:02d}" for i in range(24)], 
                                width=60, height=25).pack(side="left", padx=2)
                
                # Menit
                ctk.CTkComboBox(time_row, values=[f"{i:02d}" for i in range(60)], 
                                width=60, height=25).pack(side="left", padx=2)

            ctk.CTkButton(self.filter_container, text="APPLY FILTER RANGE", 
                          fg_color="#0ea5e9", width=200, height=35, 
                          font=("Arial", 11, "bold")).pack(pady=5)

    def reset_filter(self):
        self.filter_container.configure(height=0)
        self.clear_filter_container()
        self.active_filter_panel = None
        self.current_page = 1
        self.load_data()

    def update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.clock_label.configure(text=now)
        self.after(1000, self.update_clock)

    def create_pagination_buttons(self):
        for widget in self.pagination_frame.winfo_children(): widget.destroy()
        num_pages = max(1, (self.total_data // self.rows_per_page) + (1 if self.total_data % self.rows_per_page > 0 else 0))
        ctk.CTkButton(self.pagination_frame, text="<", width=35, command=lambda: self.change_page(self.current_page - 1)).pack(side="left", padx=2)
        start_p = max(1, self.current_page - 1)
        end_p = min(num_pages, start_p + 2)
        for i in range(start_p, end_p + 1):
            bg = "#38bdf8" if i == self.current_page else "#1e293b"
            ctk.CTkButton(self.pagination_frame, text=str(i), width=35, fg_color=bg, command=lambda p=i: self.change_page(p)).pack(side="left", padx=2)
        ctk.CTkButton(self.pagination_frame, text=">", width=35, command=lambda: self.change_page(self.current_page + 1)).pack(side="left", padx=2)

    def change_page(self, page):
        if page > 0:
            self.current_page = page
            self.load_data()

    def load_data(self):
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        try:
            conn = get_connection(); cur = conn.cursor()
            schema = os.getenv("DB_SCHEMA", "latihan")
            cur.execute(f"SELECT COUNT(*) FROM {schema}.barcode")
            self.total_data = cur.fetchone()[0]
            offset = (self.current_page - 1) * self.rows_per_page
            query = f"SELECT b.id, 'BATCH-001', m.nama_rawmaterial, b.kode_barcode, b.waktu_scan FROM {schema}.barcode b LEFT JOIN {schema}.master_data m ON b.kode_barcode = m.kode_sap ORDER BY b.id DESC LIMIT %s OFFSET %s"
            cur.execute(query, (self.rows_per_page, offset))
            rows = cur.fetchall()
            for row in rows:
                r_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
                r_frame.pack(fill="x", pady=1)
                vals = [str(row[0]), str(row[1]), str(row[2])[:35], str(row[3]), row[4].strftime("%Y-%m-%d %H:%M:%S") if row[4] else "-", "12"]
                for i, val in enumerate(vals):
                    f = ctk.CTkFrame(r_frame, width=self.columns[i][1], height=35, fg_color="transparent", border_width=1, border_color="#334155")
                    f.pack(side="left", padx=1)
                    f.pack_propagate(False)
                    ctk.CTkLabel(f, text=val, font=("Arial", 10), text_color="white").pack(expand=True)
            self.total_label.configure(text=f"Total: {self.total_data} Data")
            self.create_pagination_buttons()
            cur.close(); conn.close()
        except Exception as e:
            logger.exception("Error loading data history")
