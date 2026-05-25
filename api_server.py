import threading # Untuk membelah jalur kerja (multi threading) agar ui dan server berjalan bersamaan 
import logging # Untuk mencatat log aktivitas jika ada error pada API 
from datetime import datetime # Untuk memproses data tanggal, waktu, transaksi scan dari operator 

import uvicorn # Library server utama menjalankan aplikasi fastAPI pada port tertentu
from fastapi import FastAPI, HTTPException # Framework inti untuk API dan handling status eror http
from fastapi.middleware.cors import CORSMiddleware # Sistem keamanan untuk memberi izin akses aplikasi luar ke server ini 
from pydantic import BaseModel # Library untuk mengunci & memvalidasi format struktur data dari luar 

from app_logging import setup_logging #Mengimpor konfigurasi sistem pencatatan log 
from database import (  # Mengimpor fungsi komunikasi dari (database.py)
    cek_master_data,
    get_history as db_get_history,
    list_joblist,
    running_batch_joblist,
    simpan_data,
    tambah_master_data,
    update_material_usage,
)

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Scanner Tracking API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    kode_barcode: str


class MasterDataRequest(BaseModel):
    kode_sap: str
    nama_rawmaterial: str
    target_menit: int = 0

class UpdateMaterialUsageRequest(BaseModel):
    # Payload update usage scanner sesuai rule batch + scan_at wajib.
    joblistId: int
    barcode_pallet: str
    sap_rm: str
    batch: int
    qty_dipakai: float 
    scan_at: datetime
    scan_oleh: str = "Admin"


@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/jobs")
def api_list_joblist():
    # List joblist aktif (status 0 atau 1).
    try:
        jobs = list_joblist()
        return {"jobs": jobs}
    except Exception as exc:
        logger.exception("Database error /api/jobs")
        raise HTTPException(status_code=500, detail="Gagal mengambil joblist")

@app.get("/api/listJoblist")
def api_list_joblist_alias():
    return api_list_joblist()

@app.get("/api/jobs/{joblist_id}/running-batch")
def api_running_batch_joblist(joblist_id: int, batchKe: int):
    """Detail kebutuhan + progress material untuk 1 batch joblist."""
    try:
        return running_batch_joblist(joblist_id, batchKe)
    except ValueError as exc:
        logger.warning("Validation error /api/jobs/%s/running-batch: %s", joblist_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Database error /api/jobs/%s/running-batch", joblist_id)
        raise HTTPException(status_code=500, detail="Gagal mengambil data running batch")

@app.get("/api/runningBatchJoblist")
def api_running_batch_joblist_alias(joblistId: int, batchKe: int):
    return api_running_batch_joblist(joblistId, batchKe)

@app.post("/api/material-usage")
def api_update_material_usage(payload: UpdateMaterialUsageRequest):
    """Simpan usage scan, validasi resep, dan update status job otomatis."""
    try:
        result = update_material_usage(
            joblist_id=payload.joblistId,
            barcode_pallet=payload.barcode_pallet,
            sap_rm=payload.sap_rm,
            batch=payload.batch,
            qty_dipakai=payload.qty_dipakai,
            scan_at=payload.scan_at,
            scan_oleh=payload.scan_oleh,
        )
        return {"status": "success", "data": result}
    except ValueError as exc:
        logger.warning("Validation error /api/material-usage: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Database error /api/material-usage")
        raise HTTPException(status_code=500, detail="Gagal update material usage")

@app.post("/api/updateMaterialUsage")
def api_update_material_usage_alias(payload: UpdateMaterialUsageRequest):
    return api_update_material_usage(payload)


@app.get("/api/history")
def get_history(limit: int = 10, page: int = 1): 
    if limit < 1 or page < 1:
        raise HTTPException(status_code=400, detail="limit dan page harus >= 1")

    try:
        offset = (page - 1) * limit
        rows, total = db_get_history(limit=limit, offset=offset)

        return {
            "total": total,
            "page": page,
            "total_pages": (total + limit - 1) // limit,
            "rows": [
                {
                    "id": row[0],
                    "kode_barcode": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "nama_rawmaterial": row[3] if row[3] else "-",
                    "target_menit": row[4] if row[4] is not None else 0,
                }
                for row in rows
            ],
        }
    except Exception as exc:
        logger.exception("Database error /api/history")
        raise HTTPException(status_code=500, detail="Gagal mengambil history")


@app.get("/api/masterdata/{kode_sap}")
def get_masterdata(kode_sap: str):
    data = cek_master_data(kode_sap)
    if data:
        return {"nama_rawmaterial": data[0], "target_menit": data[1]}
    raise HTTPException(status_code=404, detail="Data tidak ditemukan")


@app.post("/api/scan")
def create_scan(payload: ScanRequest):
    material = cek_master_data(payload.kode_barcode)
    if not material:
        raise HTTPException(status_code=404, detail="Barcode belum ada di Master Data")

    if not simpan_data(payload.kode_barcode):
        raise HTTPException(status_code=500, detail="Gagal menyimpan data scan")

    return {
        "status": "success",
        "kode_barcode": payload.kode_barcode,
        "nama_rawmaterial": material[0],
        "target_menit": material[1],
    }


@app.post("/api/masterdata")
def create_masterdata(payload: MasterDataRequest):
    if not tambah_master_data(
        payload.kode_sap,
        payload.nama_rawmaterial,
        payload.target_menit,
    ):
        raise HTTPException(status_code=500, detail="Gagal menyimpan ke database master")

    return {"status": "success", "message": "Data master berhasil ditambahkan"}


def run_server():
    uvicorn.run(app, host="127.0.0.1", port=5678, log_level="info")


def start_api_server_in_thread():
    api_thread = threading.Thread(target=run_server, daemon=True)
    api_thread.start()


if __name__ == "__main__":
    run_server()
