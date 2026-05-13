import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# 1. Konfigurasi Database
DB_CONFIG = { 
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "postgres"), 
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": os.getenv("DB_PORT", "5432")
}

SCHEMA = os.getenv("DB_SCHEMA", "qc")

def get_connection():
    # Membuka koneksi ke PostgreSQL
    return psycopg2.connect(**DB_CONFIG)

# Alur 1 : ambil daftar job
def get_jobs_pending():
    # Mengambil daftar job aktif (Pending=0 / Progress=1)
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = f"""
            SELECT j.id, j.nomor_job, j.tanggal, j."resepId", j.target_qty, j.status, r.nama_resep
            FROM {SCHEMA}.formulasi_joblist j
            LEFT JOIN {SCHEMA}.master_resep r ON j."resepId" = r.id
            WHERE j.status IN (0, 1)
            ORDER BY j.tanggal DESC
        """
        cur.execute(query)
        result = cur.fetchall()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Error get_jobs_pending: {e}")
        return []

# alur 2 & 3 : ambil bahan baku dan hitung kebutuhan 
def get_job_materials(job_id):
    # Mengambil detail material dan menghitung total_kebutuhan (qty_std * target_qty)
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = f"""
            SELECT 
                d.id,
                d.kode_sap,
                m.nama_rawmaterial,
                d.qty_standard,
                d.is_scan,
                (d.qty_standard * j.target_qty) AS total_kebutuhan
            FROM {SCHEMA}.master_resep_detail d
            JOIN {SCHEMA}.master_data m ON d.kode_sap = m.kode_sap
            JOIN {SCHEMA}.formulasi_joblist j ON j."resepId" = d."resepId"
            WHERE j.id = %s
        """
        cur.execute(query, (job_id,))
        result = cur.fetchall()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Error get_job_materials: {e}")
        return []

# ALUR 5: Validasi pallet  dari (masterlist_rm)
def validate_pallet(barcode_id, kode_sap_resep): 
    # Validasi pallet berdasarkan ID di tabel masterlist_rm
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = f"""
            SELECT id, kode_sap, nama_raw_material, kg 
            FROM {SCHEMA}.masterlist_rm 
            WHERE id = %s
        """
        cur.execute(query, (barcode_id,))
        pallet = cur.fetchone()
        conn.close()

        if not pallet:
            return {"status": False, "message": "Barcode tidak terdaftar!"}
        
        if pallet['kode_sap'] != kode_sap_resep:
            return {
                "status": False, 
                "message": f"SALAH BAHAN!\nResep: {kode_sap_resep}\nScan: {pallet['kode_sap']}"
            }
        
        if pallet['kg'] <= 0:
            return {"status": False, "message": "Stok Pallet Kosong (0 kg)!"}
            
        return {"status": True, "data": pallet}
    except Exception as e:
        return {"status": False, "message": str(e)}

# ALUR 6: Catat pemakaian dan kurangi stok (kg) 
def catat_usage_masterlist(job_id, barcode_id, qty_pakai, kode_sap):
    # Update tabel usage dan kurangi kolom KG di masterlist_rm 
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1. Catat History
        query_ins = f"""
            INSERT INTO {SCHEMA}.formulasi_material_usage (job_id, kode_sap, barcode_pallet, qty_pakai, waktu)
            VALUES (%s, %s, %s, %s, NOW())
        """
        cur.execute(query_ins, (job_id, kode_sap, str(barcode_id), qty_pakai))

        # 2. Potong kg di masterlist_rm
        query_upd = f"UPDATE {SCHEMA}.masterlist_rm SET kg = kg - %s WHERE id = %s"
        cur.execute(query_upd, (qty_pakai, barcode_id))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error catat_usage: {e}")
        return False
    finally:
        cur.close()
        conn.close()

# ALUR 7: Update status job
def update_job_status(job_id, status_code):
    # Mengubah status job (0:Pending, 1:Progress, 2:Selesai)
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {SCHEMA}.formulasi_joblist 
            SET status = %s, "updatedAt" = NOW() 
            WHERE id = %s
        """, (status_code, job_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error update_job_status: {e}")
        return False