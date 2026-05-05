import psycopg2

# 1. Konfigurasi Database
DB_CONFIG = { 
    "host": "localhost",
    "database": "postgres", 
    "user": "postgres",
    "password": "",
    "port": "5432"
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


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

# Pengecekan ke Master Data
def cek_master_data(barcode):
   # Mengambil data material dari tabel master_data berdasarkan kode_sap.
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Mencari nama material dan merk di tabel master_data
        query = "SELECT nama_rawmaterial, merk_type FROM latihan.master_data WHERE kode_sap = %s"
        cur.execute(query, (barcode,))
        
        result = cur.fetchone() # Mengambil 1 baris data
        
        cur.close()
        conn.close()
        
        return result # Mengembalikan (nama, merk) jika ada, atau None jika tidak ada
    except Exception as e:
        print(f"Error cek_master_data: {e}")
        return None

def tambah_master_data(kode_sap, nama, target_menit):
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Query disesuaikan dengan database master data 
        query = """
            INSERT INTO latihan.master_data (kode_sap, nama_rawmaterial, "Target_menit") 
            VALUES (%s, %s, %s)
        """
        cur.execute(query, (kode_sap, nama, target_menit))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

# Tambah Fungsi Untuk Menampilkan History Dengan Nama Barang
def get_all_history(limit=50, offset=0):
    try:
        conn = get_connection()
        cur = conn.cursor()
        query = """
            SELECT 
                b.id, 
                b.kode_barcode, 
                m.nama_rawmaterial, 
                m.merk_type, 
                b.created_at 
            FROM latihan.barcode b
            LEFT JOIN latihan.master_data m ON b.kode_barcode = m.kode_sap
            ORDER BY b.created_at DESC 
            LIMIT %s OFFSET %s
        """
        cur.execute(query, (limit, offset))
        result = cur.fetchall()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Error get_all_history: {e}")
        return []