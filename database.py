import os # Akses sistem 
import logging # Library pencatat log sistem 
from contextlib import contextmanager # Membuat context manager koneksi database
from datetime import datetime # Mengolah format tanggal, waktu 
from typing import Any # Menentukan tipe data dinamis/bebas pada fungsi 
from uuid import UUID # Memvalidasi & mengubah teks menjadi format kode 

import psycopg2 # Library penghubung antara python dan database 
from psycopg2.extras import RealDictCursor # Mengubah hasil query database menjadi format dictionary 
from dotenv import load_dotenv # Membaca kredensial rahasia dari file .env
from app_logging import setup_logging # Mengimpor konfigurasi sistem pencatatan log internal 

load_dotenv() # Ambil konfigurasi database dari file .env secara otomatis 

# Menyusun parameter koneksi database (Host, Nama DB, User, Password, Port)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": os.getenv("DB_PORT", "5432"),
}
SCHEMA = os.getenv("DB_SCHEMA", "qc") # Menentukan target skema tabel database 

setup_logging() #Mengaktifkan pencatatan log di awal aplikasi berjalan 
logger = logging.getLogger(__name__) # Membuat instance pencatat eror khusus file ini 


# Koneksi & Interlock 
def get_connection():
    # Buka koneksi baru ke server PostgreSQL berdasarkan DB_CONFIG.
    return psycopg2.connect(**DB_CONFIG)


@contextmanager
def db_cursor(dict_cursor: bool = False):
    # Context manager cursor + auto commit/rollback. 
    conn = get_connection() # Hubungkan ke database
    cursor_factory = RealDictCursor if dict_cursor else None # Atur apakah output berupa kamus kata / teks murni
    cur = conn.cursor(cursor_factory=cursor_factory) # Buat kursor pengeksekusi perintah SQL 
    try:
        yield conn, cur # Serahkan ke koneksi fungsi pembawa query 
        conn.commit() # Simpan permanen jika query berhasil
    except Exception:
        conn.rollback() # Batalkan semua perubahan jika ada eror
        logger.exception("Database transaction failed and rolled back") #Catat letak kerusakan ke log 
        raise # Lempar eror agar sistem mengetahui kegagalan 
    finally:
        cur.close() #Kursor perintah ditutup kembali
        conn.close() # Server ditutup 


# -----------------------------
# Scanner Formulasi Core
# -----------------------------
#  list_joblist dipakai get_jobs_pending + 
def list_joblist():
    # Ambil joblist aktif (status 0/1) untuk halaman pemilihan job.
    query = f"""
        SELECT
            j.id,
            j.nomor_job,
            j.target_qty, 
            j.status,
            j."resepId"
        FROM {SCHEMA}.formulasi_joblist j
        WHERE j.status IN (0, 1)
        ORDER BY j.status ASC, j.tanggal DESC, j.id DESC
    """ # Untuk menyusun teks perintah sql penarik data joblist aktif 
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(query) #Jalankan pencarian data 
        return cur.fetchall() # Kembalikan baris daftar ke job aktif 


def _get_job_row(cur, joblist_id: int):
    # Ambil 1 baris job dan kembalikan selalu dalam format dictionary 
    query = f"""
        SELECT id, nomor_job, target_qty, status, "resepId"
        FROM {SCHEMA}.formulasi_joblist
        WHERE id = %s
    """ # Penyusun query sql pencarian 1 joblist 
    cur.execute(query, (joblist_id,)) # Untuk mengeksekusi query dengan parameter id joblist
    row = cur.fetchone() # Ambil satu data spesifik 
    if row is None:
        return None # Mengembalikan kosong jika data tidak ditemukan

    # Jika cursor biasa, hasilnya tuple -> normalisasi ke dict.
    if isinstance(row, tuple):
        return {
            "id": row[0], # Untuk memetakan kolom id 
            "nomor_job": row[1],# Memetakan kolom nomor job 
            "target_qty": row[2], # Memetakan kolom target kuantiti 
            "status": row[3], # Memetakan kolom status 
            "resepId": row[4], # Memetakan kolom resepId
        }

    # Jika cursor RealDictCursor, hasil sudah dict-like.
    return row 

# Validasi apakah kode SAP benar ada di master resep
def _is_sap_in_resep(cur, resep_id, sap_rm: str): 
    query = f"""
        SELECT 1
        FROM {SCHEMA}.master_resep_item
        WHERE "resepId" = %s AND sap_rm = %s
        LIMIT 1
    """ # Query pengecekan kecocokan kode SAP dalam resep  
    cur.execute(query, (resep_id, sap_rm)) # Menjalankan verifikasi kode SAP dan ID resep
    return cur.fetchone() is not None # Menghasilkan true jika bahan benar, dan false jika bahan salah 

def _normalize_uuid(value: Any):
    # Normalisasi string UUID; return None jika format tidak valid.
    raw = str(value or "").strip() # Bersihkan spasi diawal dan akhir teks input 
    if not raw:  
        return None # Kembali kosong jika input teks kosong 
    try:
        return str(UUID(raw)) #Ubah bentuk teks menjadi UUID 
    except (ValueError, TypeError, AttributeError): 
        return None # Tolak jika format berantakan  

def _get_usage_scan_target(cur, joblist_id, batch: int, usage_id: str):
    # Ambil row usage berdasarkan id untuk scan mode UUID usage (pakai cursor aktif).
    usage_uuid = _normalize_uuid(usage_id) # Memvalidasi & normalisasi format UUID input 
    if not usage_uuid:
        return None # Batal proses jika UUID tidak valid 

    query = f"""
        SELECT
            id,
            "joblistId",
            "sap_rm",
            "barcode_pallet",
            "batch"
        FROM {SCHEMA}.formulasi_material_usage
        WHERE id = %s
          AND "joblistId" = %s
          AND "batch" = %s
        LIMIT 1
    """ # Menyusun query pencarian data pemakaian material 
    cur.execute(query, (usage_uuid, joblist_id, batch)) # Untuk eksekusi pencarian target data usage 
    row = cur.fetchone() # Ambil 1 baris hasil data usage 
    if row is None:
        return None 
    if isinstance(row, tuple): #Normalisasi data tuple menjadi dictionary 
        return {
            "id": row[0], # Ambil data id usage 
            "joblistId": row[1], # Ambil data id joblist 
            "sap_rm": row[2], # Ambil data kode SAP material 
            "barcode_pallet": row[3], # Ambil data stiker barcode pallet
            "batch": row[4], # Ambil data nomor batch 
        }
    return row # Mengembalikan data dalam format dictionary 

def get_usage_scan_target(joblist_id, batch: int, usage_id: str):
    # Versi publik untuk kebutuhan debug/test di luar transaksi utama.
    with db_cursor(dict_cursor=True) as (_, cur):
        return _get_usage_scan_target(cur, joblist_id, batch, usage_id) # Untuk memanggil fungsi internal scan target 


# Memeriksa apakah seluruh kebutuhan berat bahan dari batch 1 - akhir terpenuhi 
def _is_all_batches_completed(cur, joblist_id: int, resep_id, total_batch: int):
    query = f"""
        WITH usage_per_batch AS (
            SELECT
                u."sap_rm",
                u."batch",
                COALESCE(SUM(u."qty_dipakai"), 0) AS qty_pakai
            FROM {SCHEMA}.formulasi_material_usage u
            WHERE u."joblistId" = %s
            GROUP BY u."sap_rm", u."batch"
        ),
        batch_range AS (
            SELECT generate_series(1, %s) AS batch_ke
        )
        SELECT COUNT(*) AS belum_selesai
        FROM {SCHEMA}.master_resep_item mi
        CROSS JOIN batch_range br
        LEFT JOIN usage_per_batch upb
            ON upb."sap_rm" = mi.sap_rm
           AND upb."batch" = br.batch_ke
        WHERE mi."resepId" = %s
          AND COALESCE(upb.qty_pakai, 0) < mi.qty_standard
    """ # Untuk query kalkulator pengecekan total berat standar vs aktual di semua batch 
    cur.execute(query, (joblist_id, total_batch, resep_id)) # Hitung sisa kekurangan bahan 
    result = cur.fetchone() # Mengambil angka hasil perhitungan 
    if isinstance(result, tuple): 
        not_done = result[0] # Untuk ambil angka index pertama jika berbentuk tuple 
    else:
        not_done = result.get("belum_selesai", 0) # Untuk mengambil key dict jika berbentuk dictionary  
    return not_done == 0 #Mengembalikan true jika semua bahan di batch lunas di timbang 


def running_batch_joblist(joblist_id: int, batch_ke: int):
    # Ambil kebutuhan per item untuk batch tertentu + progress usage batch.
    if batch_ke < 1:
        raise ValueError("batchKe harus >= 1") #Untuk menolak jika operator memasukkan angka batch nol/minus  

    with db_cursor(dict_cursor=True) as (_, cur): # membuka koneksi database dengan output dictionary 
        job = _get_job_row(cur, joblist_id) # Mengambil data ringkasan job aktif 
        if not job:
            raise ValueError("Joblist tidak ditemukan")

        if batch_ke > job["target_qty"]:
            raise ValueError("batchKe melebihi target_qty joblist") # Untuk menolak jika input melebihi target maksimum batch 

        materials_query = f"""
            SELECT
                mi.sap_rm,
                mi.nama_bahan_baku,
                mi.qty_standard,
                mi.no_scan,
                COALESCE(u.qty_pakai, 0) AS qty_terpakai
            FROM {SCHEMA}.master_resep_item mi
            LEFT JOIN (
                SELECT
                    "sap_rm",
                    SUM("qty_dipakai") AS qty_pakai
                FROM {SCHEMA}.formulasi_material_usage
                WHERE "joblistId" = %s AND "batch" = %s
                GROUP BY "sap_rm"
            ) u ON u."sap_rm" = mi.sap_rm
            WHERE mi."resepId" = %s
            ORDER BY mi.sap_rm ASC
        """ # Untuk query penggabungan data item master resep dengan total akumulasi timbangan terpakai 
        cur.execute(materials_query, (joblist_id, batch_ke, job["resepId"])) # Untuk menjalankan query penarikan data resep 
        rows = cur.fetchall() # Menampung seluruh baris data material resep 

    items = [] # 
    for row in rows:
        # Rule UI:
        # - nama material mengandung "AIR" => checklist manual
        # - no_scan = true => checklist manual
        nama_upper = str(row["nama_bahan_baku"] or "").upper() # Ubah nama bahan baku menjadi huruf kapital 
        is_air_material = "AIR" in nama_upper
        is_no_scan = bool(row["no_scan"]) # Otomatis checklist jika master data melarang scan 

        items.append(
            {
                "sap_rm": row["sap_rm"], # Mengsisi kode SAP material 
                "nama_bahan_baku": row["nama_bahan_baku"], # Mengisi nama bahan baku 
                "qty_standard": float(row["qty_standard"] or 0), # Mengisi berat standar resep 
                "qty_terpakai": float(row["qty_terpakai"] or 0), # Mengisi berat aktual 
                "sisa": max(float(row["qty_standard"] or 0) - float(row["qty_terpakai"] or 0), 0.0),
                "is_scan": not (is_air_material or is_no_scan), # izinkan bypass checklist jika bahan bersifat air/no scan 
            }
        )

    return {
        "joblist": {
            "id": job["id"],
            "nomor_job": job["nomor_job"],
            "target_qty": job["target_qty"], 
            "status": job["status"],
            "resepId": job["resepId"],
            "batchKe": batch_ke,
        },
        "items": items,
    }

# Memperbarui berat aktual penimbangan bahan hasil scan ke database, serta memperbarui status pengerjaan formula secara otomatis
def update_material_usage( 
    joblist_id: int,
    barcode_pallet: str,
    sap_rm: str,
    batch: int,
    qty_dipakai: float,
    scan_at: datetime,
    scan_oleh: str,
    usage_id: str = None,
):
    # Update usage material (qty_dipakai + scan_at) dan status job otomatis. 
    if batch < 1:
        raise ValueError("batch wajib >= 1")

    with db_cursor() as (_, cur): #
        job = _get_job_row(cur, joblist_id)
        if not job:
            raise ValueError("joblistId tidak ditemukan")

        if batch > int(job["target_qty"]):
            raise ValueError("batch melebihi target_qty")

        if not _is_sap_in_resep(cur, job["resepId"], sap_rm):
            raise ValueError("sap_rm tidak ada di resep joblist")

        if usage_id:
            # Mode scan by usage.id
            usage_row = _get_usage_scan_target(cur, joblist_id, batch, usage_id)
            if not usage_row:
                raise ValueError("ID usage tidak ditemukan untuk job/batch aktif")
            if usage_row.get("sap_rm") != sap_rm:
                raise ValueError("ID usage tidak sesuai material resep yang discan")

            update_query = f"""
                UPDATE {SCHEMA}.formulasi_material_usage
                SET
                    "qty_dipakai" = %s,
                    "scan_at" = %s
                WHERE id = %s
                  AND "joblistId" = %s
                  AND "batch" = %s
            """  # Untuk query pembaruan data usage berdasarkan ID usage yang sudah terverifikasi kecocokan joblist, batch, dan kode SAP material  
            cur.execute(
                update_query,
                (qty_dipakai, scan_at, usage_id, joblist_id, batch),
            )
        else:
            # Mode lama: update by (joblistId, sap_rm, batch)
            update_query = f"""
                UPDATE {SCHEMA}.formulasi_material_usage
                SET
                    "qty_dipakai" = %s,
                    "scan_at" = %s
                WHERE "joblistId" = %s
                  AND "sap_rm" = %s
                  AND "batch" = %s
            """
            cur.execute(
                update_query,
                (qty_dipakai, scan_at, joblist_id, sap_rm, batch),
            )
        updated_rows = cur.rowcount

        if updated_rows == 0:
            raise ValueError("Data usage tidak ditemukan untuk di-update")

        # status 0 -> 1 saat scan pertama
        if int(job["status"]) == 0:
            cur.execute(
                f"UPDATE {SCHEMA}.formulasi_joblist SET status = 1 WHERE id = %s",
                (joblist_id,),
            )
            job["status"] = 1

        # semua batch selesai -> 2
        if _is_all_batches_completed(cur, joblist_id, job["resepId"], int(job["target_qty"])):
            cur.execute(
                f"UPDATE {SCHEMA}.formulasi_joblist SET status = 2 WHERE id = %s",
                (joblist_id,),
            )
            job["status"] = 2

        return {
            "saved": updated_rows > 0,
            "job_status": int(job["status"]),
            "joblist_id": joblist_id,
            "batch": batch,
            "sap_rm": sap_rm,
            "usage_id": usage_id,
            "scan_at": scan_at.isoformat(),
            "qty_dipakai": qty_dipakai,
        }


# -----------------------------
# Compatibility helpers for UI lama
# -----------------------------
def get_jobs_pending():
    # Wrapper kompatibilitas untuk kode lama. 
    try:
        return list_joblist() # Memanggil fungsi utama pembaca daftar joblist 
    except Exception as exc:
        logger.exception("Error get_jobs_pending") # Catat log error
        return [] 


def get_all_jobs():
    # Wrapper kompatibilitas penarikan data menyeluruh untuk kode lama.
    try:
        return list_joblist()
    except Exception as exc:
        logger.exception("Error get_all_jobs")
        return []


def get_job_materials(job_id: int):
    # Wrapper kompatibilitas: mapping struktur data lama dari running_batch_joblist.
    try:
        data = running_batch_joblist(job_id, 1) #Mengambil data kebutuhan resep pada batch pertama 
        result = []
        for item in data["items"]: 
            result.append(
                {
                    "kode_sap": item["sap_rm"], #Konversi nama variabel dari sap_rm ke kode_sap
                    "nama": item["nama_bahan_baku"], # Konversi nama variabel dari nama_bahan_baku ke nama 
                    "target_qty": item["qty_standard"],  # kebutuhan per batch 
                    "satuan": "Kg", # satuan berat bahan baku 
                    "is_scan": item["is_scan"], # #Menyalin status wajib scan/manual 
                }
            )
        return result 
    except Exception as exc:
        logger.exception("Error get_job_materials for job_id=%s", job_id) #Mencatat log detail kesalahan sistem 
        return []


# -----------------------------
# Existing API features (tetap)
# -----------------------------
# Untuk memfasilitasi admin/sistem merubah status pengerjaan perintah job secara manual 
def update_job_status(job_id: int, status_code: int):
    query = f"""
        UPDATE {SCHEMA}.formulasi_joblist
        SET status = %s
        WHERE id = %s
    """ # Untuk query pembaruan manual status baris joblist
    try:
        with db_cursor() as (_, cur): # Membuka koneksi database untuk mengeksekusi query pembaruan status joblist 
            cur.execute(query, (status_code, job_id)) # Pembaruan status job ke postgresql 
        return True #Mengirimkan sinyal menandakan proses update berhasil 
    except Exception as exc:
        logger.exception("Error update_job_status job_id=%s status=%s", job_id, status_code)
        return False

# Menarik data riwayat aktivitas lama untuk komponen tabel halaman (pagination)
def get_history(limit: int, offset: int):
    rows_query = f"""
        SELECT
            b.id,
            b.kode_barcode,
            b.waktu,
            m.nama_rawmaterial,
            m."Target_menit"
        FROM {SCHEMA}.barcode b
        LEFT JOIN {SCHEMA}.master_data m ON b.kode_barcode = m.kode_sap
        ORDER BY b.id DESC
        LIMIT %s OFFSET %s
    """ #Untuk query penarik data log baris riwayat dgn limit pembatas jumlah data per halaman 
    total_query = f"SELECT COUNT(*) FROM {SCHEMA}.barcode"

    with db_cursor() as (_, cur):
        cur.execute(rows_query, (limit, offset)) # Untuk eksekusi penarikan potongan lembar data riwayat
        rows = cur.fetchall() # Untuk menampung seluruh baris data riwayat hasil query 
        cur.execute(total_query) # Eksekusi hitung total baris tabel log 
        total = cur.fetchone()[0] # Untuk ambil int hasil total hitungan baris riwayat 
    return rows, total

# Memeriksa nama material & target menit operasional yg terdaftar berdasarkan kode SAP 
def cek_master_data(kode_sap: str):
    query = f"SELECT nama_rawmaterial, COALESCE(\"Target_menit\", 0) FROM {SCHEMA}.master_data WHERE kode_sap = %s" #Pengecekan master data material 
    try:
        with db_cursor() as (_, cur): 
            cur.execute(query, (kode_sap,)) #Untuk pencarian spesifikasi material berdasarkan kode SAP 
            return cur.fetchone()
    except Exception as exc:
        logger.exception("Error cek_master_data kode_sap=%s", kode_sap)
        return None

# Untuk memasukkan data raw material baru ke tabel / memperbarui nama jika kode SAP sudah ada (upsert)
def tambah_master_data(kode_sap: str, nama_rawmaterial: str, target_menit: int = 0):
    query = f"""
        INSERT INTO {SCHEMA}.master_data (kode_sap, nama_rawmaterial, "Target_menit")
        VALUES (%s, %s, %s)
        ON CONFLICT (kode_sap)
        DO UPDATE SET
            nama_rawmaterial = EXCLUDED.nama_rawmaterial,
            "Target_menit" = EXCLUDED."Target_menit"
    """ # Untuk query simpan data master baru 
    try:
        with db_cursor() as (_, cur): 
            cur.execute(query, (kode_sap, nama_rawmaterial, target_menit)) # Untuk mengeksekusi perintah upsert data master material 
        return True # Mengirimkan sinyal true tanda master data sukses diamankan di database 
    except Exception as exc:
        logger.exception("Error tambah_master_data kode_sap=%s", kode_sap)
        return False

# Mencatat log data scan 
def simpan_data(kode_barcode: str):
    query = f"INSERT INTO {SCHEMA}.barcode (kode_barcode, waktu) VALUES (%s, NOW())"
    try:
        with db_cursor() as (_, cur): # Membuka koneksi database untuk menyimpan data log scan 
            cur.execute(query, (kode_barcode,)) # Penyimpanan teks barcode dalam database log 
        return True # Mengirimkan status true tanda log scan sukses tertulis permanen 
    except Exception as exc: 
        logger.exception("Error simpan_data kode_barcode=%s", kode_barcode)
        return False # untuk mengirimkan status false tanda log gagal terarsip di database

# Untuk validasi data yang di scan apakah sesuai dengan kebutuhan resep dan kondisi stok pallet di gudang 
def validate_pallet(barcode_id, kode_sap_resep):
    query = f"""
        SELECT id, kode_sap, nama_raw_material, kg
        FROM {SCHEMA}.masterlist_rm
        WHERE id = %s
    """ # untuk query pengecekan data spesifikasi muatan pallet logistik gudang
    try:
        with db_cursor(dict_cursor=True) as (_, cur):
            cur.execute(query, (barcode_id,)) # Eksekusi pencarian detail pallet berdasarkan nomor id barcode 
            pallet = cur.fetchone() 
# Jika pallet tidak ditemukan, maka akan mengembalikan status false
        if not pallet:
            return {"status": False, "message": "Barcode tidak terdaftar!"}
# Jika kode SAP pada pallet tidak sesuai dengan kode SAP resep, maka akan mengembalikan status false 
        if pallet["kode_sap"] != kode_sap_resep:
            return {
                "status": False,
                "message": f"SALAH BAHAN!\\nResep: {kode_sap_resep}\\nScan: {pallet['kode_sap']}",
            }

        if pallet["kg"] <= 0:
            return {"status": False, "message": "Stok Pallet Kosong (0 kg)!"}

        return {"status": True, "data": pallet}
    except Exception as exc:
        logger.exception("Error validate_pallet barcode_id=%s kode_sap_resep=%s", barcode_id, kode_sap_resep) 
        return {"status": False, "message": str(exc)}

# Mencatat pemakaian bahan hasil scan ke tabel usage sekaligus mengurangi stok aktual pallet di masterlist_rm
def catat_usage_masterlist(job_id, barcode_id, qty_pakai, kode_sap):
    insert_query = f"""
        INSERT INTO {SCHEMA}.formulasi_material_usage (job_id, kode_sap, barcode_pallet, qty_pakai, waktu)
        VALUES (%s, %s, %s, %s, NOW())
    """ 
    update_query = f"UPDATE {SCHEMA}.masterlist_rm SET kg = kg - %s WHERE id = %s" # Untuk query pengurangan stok aktual pallet di masterlist_rm sesuai jumlah berat bahan dipakai 

    try: 
        with db_cursor() as (_, cur):
            cur.execute(insert_query, (job_id, kode_sap, str(barcode_id), qty_pakai)) # catat pemakaian bahan hasil scan ke tabel usage untuk keperluan monitoring & histori 
            cur.execute(update_query, (qty_pakai, barcode_id)) # kurangi stok aktual pallet di masterlist_rm sesuai jumlah berat bahan yang dipakai 
        return True
    except Exception as exc: 
        logger.exception(
            "Error catat_usage_masterlist job_id=%s barcode_id=%s kode_sap=%s",
            job_id,
            barcode_id,
            kode_sap,
        )
        return False # Mengirimkan status false tanda pencatatan pemakaian bahan gagal di database 
