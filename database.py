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
