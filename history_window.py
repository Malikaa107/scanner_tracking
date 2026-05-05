import customtkinter as ctk
from tkinter import ttk
import math
import os
from datetime import datetime, timedelta
from database import get_connection

try:
    from tkcalendar import Calendar
except ImportError:
    Calendar = None 

class HistoryWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Database History Lengkap")
        self.geometry("1150x850")
        self.attributes('-topmost', True)
        
        self.current_page = 1
        self.rows_per_page = 15
        self.filter_start = None
        self.filter_end = None
        self.page_buttons = []

        # STYLE TABEL ASLI
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#1e293b", foreground="white", fieldbackground="#1e293b", rowheight=35, borderwidth=1)
        style.configure("Treeview.Heading", background="#0f172a", foreground="#94a3b8", font=("Arial", 12, "bold"))
        style.map("Treeview", background=[('selected', '#0ea5e9')])

        self.setup_ui()
        self.update_history_clock()
        self.load_full_table(is_initial=True)

    def setup_ui(self):
        self.top_f = ctk.CTkFrame(self, fg_color="#1e293b", height=80)
        self.top_f.pack(fill="x", padx=20, pady=10)

        self.btn_shift = ctk.CTkButton(self.top_f, text="DATA OPERASIONAL SHIFT", width=150, height=45, font=("Arial", 12, "bold"), fg_color="#0f172a", border_width=1, border_color="#38bdf8", command=self.toggle_shift_panel)
        self.btn_shift.pack(side="left", padx=5)

        self.btn_range = ctk.CTkButton(self.top_f, text="CUSTOM DATE TIME", width=150, height=45, font=("Arial", 12, "bold"), fg_color="#0f172a", border_width=1, border_color="#38bdf8", command=self.toggle_range_panel)
        self.btn_range.pack(side="left", padx=5)
        
        self.hist_time_lbl = ctk.CTkLabel(self.top_f, text="00:00:00", font=("Consolas", 20, "bold"), text_color="#38bdf8")
        self.hist_time_lbl.pack(side="left", padx=15)

        ctk.CTkButton(self.top_f, text="LIHAT SEMUA DATA", fg_color="#10b981", hover_color="#059669", text_color="white", font=("Arial", 11, "bold"), command=self.refresh_history).pack(side="right", padx=15)

        self.shift_panel = ctk.CTkFrame(self, fg_color="#0f172a", height=0) 
        self.shift_panel.pack(fill="x", padx=20)
        
        self.range_panel = ctk.CTkFrame(self, fg_color="#f1f5f9", height=0)
        self.range_panel.pack(fill="x", padx=20)

        self.setup_picker_ui()

        # TABEL
        table_container = ctk.CTkFrame(self, fg_color="transparent")
        table_container.pack(expand=True, fill="both", padx=20, pady=10)

        self.tree = ttk.Treeview(table_container, columns=("ID", "Barcode", "Waktu"), show='headings')
        self.tree.heading("ID", text="NO"); self.tree.heading("Barcode", text="KODE BARCODE"); self.tree.heading("Waktu", text="WAKTU SCAN")
        self.tree.column("ID", width=70, anchor="center"); self.tree.column("Barcode", width=600, anchor="center"); self.tree.column("Waktu", width=300, anchor="center")
        self.tree.tag_configure('oddrow', background='#1e293b')
        self.tree.tag_configure('evenrow', background='#334155')
        self.tree.pack(side="left", expand=True, fill="both")
        
        # PAGINATION NO DI BAWAH
        self.pagination_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.pagination_frame.pack(fill="x", padx=20, pady=10)
        self.btn_prev = ctk.CTkButton(self.pagination_frame, text="<", width=40, height=40, fg_color="#1e293b", command=self.prev_page)
        self.btn_prev.pack(side="left", padx=5)
        self.page_num_container = ctk.CTkFrame(self.pagination_frame, fg_color="transparent")
        self.page_num_container.pack(side="left", padx=5)
        self.btn_next = ctk.CTkButton(self.pagination_frame, text=">", width=40, height=40, fg_color="#1e293b", command=self.next_page)
        self.btn_next.pack(side="left", padx=5)
        self.result_info = ctk.CTkLabel(self.pagination_frame, text="Results: 0", font=("Arial", 12), text_color="#94a3b8")
        self.result_info.pack(side="right", padx=10) 

    def setup_picker_ui(self):
        # SHIFT PANEL
        self.shift_container = ctk.CTkFrame(self.shift_panel, fg_color="transparent")
        self.shift_cal = Calendar(self.shift_container, selectmode='day', font="Arial 9", background="#1e3d59", foreground="white")
        self.shift_cal.pack(pady=10)

        btn_f_shift = ctk.CTkFrame(self.shift_container, fg_color="transparent")
        btn_f_shift.pack(pady=10)
        ctk.CTkButton(btn_f_shift, text="SHIFT 1\n(07:00-15:00)", fg_color="#059669", hover_color="#10b981", height=45, command=lambda: self.apply_shift_filter(1)).pack(side="left", padx=5)
        ctk.CTkButton(btn_f_shift, text="SHIFT 2\n(15:00-23:00)", fg_color="#d97706", hover_color="#6366f1", height=45, command=lambda: self.apply_shift_filter(2)).pack(side="left", padx=5)
        ctk.CTkButton(btn_f_shift, text="SHIFT 3\n(23:00-07:00)", fg_color="#4f46e5", hover_color="#6366f1", height=45, command=lambda: self.apply_shift_filter(3)).pack(side="left", padx=5)

        # RANGE PANEL (KALENDER START & END)
        self.range_container = ctk.CTkFrame(self.range_panel, fg_color="transparent")
        inner_range = ctk.CTkFrame(self.range_container, fg_color="transparent")
        inner_range.pack(pady=10)
        
        # START
        f_start = ctk.CTkFrame(inner_range, fg_color="transparent"); f_start.grid(row=0, column=0, padx=25)
        self.cal_start = Calendar(f_start, selectmode='day', font="Arial 8"); self.cal_start.pack(pady=(0, 10))
        t_start_row = ctk.CTkFrame(f_start, fg_color="transparent"); t_start_row.pack()
        ctk.CTkLabel(t_start_row, text="START : ", text_color="#1e3d59", font=("Arial", 12, "bold")).pack(side="left")
        self.h_start = ctk.CTkComboBox(t_start_row, values=[f"{i:02d}" for i in range(24)], width=65); self.h_start.set("00"); self.h_start.pack(side="left")
        self.m_start = ctk.CTkComboBox(t_start_row, values=[f"{i:02d}" for i in range(60)], width=65); self.m_start.set("00"); self.m_start.pack(side="left")

        # END
        f_end = ctk.CTkFrame(inner_range, fg_color="transparent"); f_end.grid(row=0, column=1, padx=25)
        self.cal_end = Calendar(f_end, selectmode='day', font="Arial 8"); self.cal_end.pack(pady=(0, 10))
        t_end_row = ctk.CTkFrame(f_end, fg_color="transparent"); t_end_row.pack()
        ctk.CTkLabel(t_end_row, text="END : ", text_color="#f43f5e", font=("Arial", 12, "bold")).pack(side="left")
        self.h_end = ctk.CTkComboBox(t_end_row, values=[f"{i:02d}" for i in range(24)], width=65); self.h_end.set("23"); self.h_end.pack(side="left")
        self.m_end = ctk.CTkComboBox(t_end_row, values=[f"{i:02d}" for i in range(60)], width=65); self.m_end.set("59"); self.m_end.pack(side="left")

        ctk.CTkButton(self.range_container, text="APPLY RANGE", fg_color="#10b981", text_color="black", font=("Arial", 12, "bold"), height=40, command=self.apply_range_filter).pack(pady=20)

    def toggle_shift_panel(self):
        self.range_container.pack_forget(); self.range_panel.configure(height=0) 
        if self.shift_panel.winfo_height() < 10:
            self.shift_panel.configure(height=480); self.shift_container.pack(fill="both", expand=True)
        else:
            self.shift_container.pack_forget(); self.shift_panel.configure(height=0)

    def toggle_range_panel(self):
        self.shift_container.pack_forget(); self.shift_panel.configure(height=0)
        if self.range_panel.winfo_height() < 10:
            self.range_panel.configure(height=520); self.range_container.pack(fill="both", expand=True)
        else:
            self.range_container.pack_forget(); self.range_panel.configure(height=0)

    def apply_shift_filter(self, shift_num):
        date_obj = self.shift_cal.selection_get(); date_str = date_obj.strftime("%Y-%m-%d")
        if shift_num == 1: self.filter_start, self.filter_end = f"{date_str} 07:00:00", f"{date_str} 15:00:00"
        elif shift_num == 2: self.filter_start, self.filter_end = f"{date_str} 15:00:00", f"{date_str} 23:00:00"
        elif shift_num == 3: 
            self.filter_start = f"{date_str} 23:00:00"
            self.filter_end = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d") + " 07:00:00"
        self.current_page = 1; self.toggle_shift_panel(); self.load_full_table()

    def apply_range_filter(self):
        s_date = self.cal_start.selection_get().strftime('%Y-%m-%d')
        e_date = self.cal_end.selection_get().strftime('%Y-%m-%d')
        self.filter_start = f"{s_date} {self.h_start.get()}:{self.m_start.get()}:00"
        self.filter_end = f"{e_date} {self.h_end.get()}:{self.m_end.get()}:59"
        self.current_page = 1; self.toggle_range_panel(); self.load_full_table()

    def load_full_table(self, is_initial=False):
        try:
            conn = get_connection(); cur = conn.cursor()
            SCHEMA = os.getenv("DB_SCHEMA", "latihan")
            if not is_initial and self.filter_start:
                cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.barcode WHERE created_at BETWEEN %s AND %s", (self.filter_start, self.filter_end))
            else:
                cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.barcode")
            total_data = cur.fetchone()[0]
            total_pages = math.ceil(total_data / self.rows_per_page) if total_data > 0 else 1
            offset = (self.current_page - 1) * self.rows_per_page
            if not is_initial and self.filter_start:
                cur.execute(f"SELECT id, kode_barcode, created_at FROM {SCHEMA}.barcode WHERE created_at BETWEEN %s AND %s ORDER BY id DESC LIMIT %s OFFSET %s", (self.filter_start, self.filter_end, self.rows_per_page, offset))
            else:
                cur.execute(f"SELECT id, kode_barcode, created_at FROM {SCHEMA}.barcode ORDER BY id DESC LIMIT %s OFFSET %s", (self.rows_per_page, offset))
            rows = cur.fetchall()
            for i in self.tree.get_children(): self.tree.delete(i)
            for index, r in enumerate(rows):
                tag = 'evenrow' if index % 2 == 0 else 'oddrow'
                self.tree.insert("", "end", values=(r[0], r[1], r[2].strftime("%d/%m/%Y %H:%M:%S")), tags=(tag,))
            self.result_info.configure(text=f"Results: {offset+1} - {offset+len(rows)} of {total_data}")
            self.update_page_buttons(total_pages)
            cur.close(); conn.close()
        except: pass

    def update_page_buttons(self, total_pages):
        for btn in self.page_buttons: btn.destroy()
        self.page_buttons = []
        start = max(1, self.current_page - 2); end = min(total_pages, start + 4)
        for i in range(start, end + 1):
            btn_color = "#10b981" if i == self.current_page else "#1e293b"
            p_btn = ctk.CTkButton(self.page_num_container, text=str(i), width=40, height=40, fg_color=btn_color, command=lambda p=i: self.go_to_page(p))
            p_btn.pack(side="left", padx=2); self.page_buttons.append(p_btn)

    def go_to_page(self, page_num): self.current_page = page_num; self.load_full_table()
    def next_page(self): self.current_page += 1; self.load_full_table()
    def prev_page(self): 
        if self.current_page > 1: self.current_page -= 1; self.load_full_table()
    def refresh_history(self): self.filter_start = None; self.current_page = 1; self.load_full_table(is_initial=True)
    def update_history_clock(self):
        self.hist_time_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self.update_history_clock)
