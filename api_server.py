from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from database import get_connection, simpan_data, cek_master_data
import threading
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Scanner Tracking API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # bebas (dev only)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScanRequest(BaseModel):
    kode_barcode: str

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/history")
def get_history(limit: int = 50, page: int = 1, start: str = None, end: str = None):
    if limit < 1:
        limit = 50
    if page < 1:
        page = 1

    try:
        conn = get_connection()
        cur = conn.cursor()

        if start and end:
            cur.execute("SELECT COUNT(*) FROM latihan.barcode WHERE created_at BETWEEN %s AND %s", (start, end))
        else:
            cur.execute("SELECT COUNT(*) FROM latihan.barcode")

        total = cur.fetchone()[0]
        offset = (page - 1) * limit

        if start and end:
            cur.execute(
                "SELECT id, kode_barcode, created_at FROM latihan.barcode WHERE created_at BETWEEN %s AND %s ORDER BY id DESC LIMIT %s OFFSET %s",
                (start, end, limit, offset),
            )
        else:
            cur.execute(
                "SELECT id, kode_barcode, created_at FROM latihan.barcode ORDER BY id DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "rows": [
                {
                    "id": r[0],
                    "kode_barcode": r[1],
                    "created_at": r[2].isoformat() if r[2] else None,
                }
                for r in rows
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/masterdata/{kode_sap}")
def get_masterdata(kode_sap: str):
    data = cek_master_data(kode_sap)
    if data:
        return {"nama_rawmaterial": data[0], "merk_type": data[1]}
    raise HTTPException(status_code=404, detail="Data tidak ditemukan")

@app.post("/api/scan")
def create_scan(payload: ScanRequest):
    material = cek_master_data(payload.kode_barcode)
    if not material:
        raise HTTPException(status_code=404, detail="Barcode tidak valid")

    saved = simpan_data(payload.kode_barcode)
    if not saved:
        raise HTTPException(status_code=500, detail="Gagal menyimpan data scan")

    return {
        "status": "success",
        "kode_barcode": payload.kode_barcode,
        "nama_rawmaterial": material[0],
        "merk_type": material[1],
    }

def run_api_server():
    uvicorn.run(app, host="127.0.0.1", port=5678, log_level="info")

def start_api_server_in_thread():
    thread = threading.Thread(target=run_api_server, daemon=True)
    thread.start()

if __name__ == "__main__":
    run_api_server()
