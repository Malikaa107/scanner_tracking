from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from database import get_connection
import uvicorn
import os
from fastapi.middleware.cors import CORSMiddleware
import threading

app = FastAPI(title="Scanner Tracking API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model data disesuaikan dengan database terbaru (Target Menit)
class ScanRequest(BaseModel):
    kode_barcode: str 

class MasterDataRequest(BaseModel):
    kode_sap: str
    nama_rawmaterial: str
    target_menit: int = 0

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/history")
def get_history(limit: int = 10, page: int = 1):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        offset = (page - 1) * limit
        SCHEMA = os.getenv("DB_SCHEMA", "latihan")
        
        # Gunakan petik dua "Target_menit" jika di Postgres namanya ada huruf kapital 
        query = f"""
            SELECT 
                b.id, 
                b.kode_barcode, 
                b.waktu,
                m.nama_rawmaterial,
                m."Target_menit"
            FROM {SCHEMA}.barcode b 
            LEFT JOIN {SCHEMA}.master_data m ON b.kode_barcode = m.kode_sap
            ORDER BY b.id DESC LIMIT %s OFFSET %s
        """
        cur.execute(query, (limit, offset))
        rows = cur.fetchall()
        
        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.barcode")
        total = cur.fetchone()[0]


        
        
        cur.close()
        conn.close()

        return {
            "total": total,
            "page": page,
            "total_pages": (total + limit - 1) // limit,
            "rows": [
                {
                    "id": r[0],
                    "kode_barcode": r[1],
                    "created_at": r[2].isoformat() if r[2] else None,
                    "nama_rawmaterial": r[3] if r[3] else "-",
                    "target_menit": r[4] if r[4] is not None else 0
                } for r in rows
            ]
        } 
    except Exception as exc:
        if conn: conn.close()
        print(f"❌ DATABASE ERROR: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/masterdata/{kode_sap}")
def get_masterdata(kode_sap: str):
    data = cek_master_data(kode_sap)
    if data:
        # data[0] = nama, data[1] = target_menit 
        return {"nama_rawmaterial": data[0], "target_menit": data[1]}
    raise HTTPException(status_code=404, detail="Data tidak ditemukan")

@app.post("/api/scan")
def create_scan(payload: ScanRequest):
    material = cek_master_data(payload.kode_barcode)
    if not material:
        raise HTTPException(status_code=404, detail="Barcode belum ada di Master Data")

    saved = simpan_data(payload.kode_barcode)
    if not saved:
        raise HTTPException(status_code=500, detail="Gagal menyimpan data scan")

    return {
        "status": "success",
        "kode_barcode": payload.kode_barcode,
        "nama_rawmaterial": material[0],
        "target_menit": material[1]
    }

@app.post("/api/masterdata")
def create_masterdata(payload: MasterDataRequest):
    success = tambah_master_data(
        payload.kode_sap, 
        payload.nama_rawmaterial,
        payload.target_menit
    )

    if not success:
        raise HTTPException(status_code=500, detail="Gagal menyimpan ke database master") 
            
    return {"status": "success", "message": "Data master berhasil ditambahkan!"}

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=5678, log_level="info")

def start_api_server_in_thread():
    api_thread = threading.Thread(target=run_server, daemon=True)
    api_thread.start()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5678, log_level="info")