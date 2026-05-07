import psycopg2
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
    return psycopg2.connect(**DB_CONFIG)

# FUNGSI CEK FORMULASI JOBLIST
def cek_formulasi_joblist(nomor_job):
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        query = f"""
            SELECT 
                nomor_job, 
                tanggal, 
                bon_rm_ckId, 
                resepId, 
                target_qty, 
                status, 
                dibuat_oleh, 
                "createdAt", 
                "updatedAt" 
            FROM {SCHEMA}.formulasi_joblist 
            WHERE nomor_job = %s
        """
        
        cur.execute(query, (nomor_job,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        return result 
    except Exception as e:
        print(f"Error cek_formulasi_joblist: {e}")
        return None