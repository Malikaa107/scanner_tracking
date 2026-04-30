# Scanner Tracking

Aplikasi desktop Python untuk scan barcode dan menyimpan historinya ke PostgreSQL, dengan tambahan API FastAPI agar data dapat diakses dari frontend web.

## Requirements

- Python 3.10+ / 3.11+
- PostgreSQL database dengan schema `latihan`
- Tabel `latihan.barcode` yang memiliki setidaknya kolom:
  - `id`
  - `kode_barcode`
  - `created_at`
- Tabel `latihan.master_data` dengan kolom `kode_sap`, `nama_rawmaterial`, dan `merk_type`

## Install

1. Buka terminal di folder proyek:

```powershell
cd D:\Something\Mayora\scanner_tracking
```

2. Install dependency:

```powershell
py -3 -m pip install -r requirement.txt
```

Jika `py` tidak berfungsi, gunakan:

```powershell
python -m pip install -r requirement.txt
```

## Menjalankan aplikasi

### GUI + API bersamaan

```powershell
py App_scanner.py
```

Aplikasi desktop akan terbuka dan server API akan berjalan di `http://127.0.0.1:5678`.

### Hanya API saja

```powershell
py api_server.py
```

## Endpoint API

1. `GET /api/health`
   - Cek apakah server API hidup.

2. `POST /api/scan`
   - Body JSON:
     ```json
     {
       "kode_barcode": "123456"
     }
     ```
   - Fungsi: validasi barcode, simpan ke tabel `latihan.barcode`, dan kembalikan data master material.

3. `GET /api/masterdata/{kode_sap}`
   - Contoh: `/api/masterdata/123456`
   - Fungsi: ambil `nama_rawmaterial` dan `merk_type` dari `latihan.master_data`.

4. `GET /api/history`
   - Contoh tanpa filter: `/api/history?limit=50&page=1`
   - Contoh dengan rentang waktu:
     `/api/history?start=2026-04-01%2000:00:00&end=2026-04-30%2023:59:59&limit=15&page=1`
   - contoh payload
      {
        "total": 3,
        "page": 1,
        "limit": 10,
        "rows": [
          {
              "id": 3,
              "kode_barcode": "12345678",
              "created_at": "2026-04-30T11:47:51.027179"
          },
        ]
      }
   - Fungsi: ambil histori scan, mendukung paging dan filter tanggal.

## Catatan integrasi frontend

- Jalankan `App_scanner.py` jika ingin tetap menggunakan GUI dan API bersama-sama.
- Frontend web bisa memanggil endpoint API di `http://127.0.0.1:5678`.
- Pastikan konfigurasi database di `database.py` sudah benar.

Saat ini `api_server.py` sudah menyediakan:

- `create_scan` untuk menambahkan scan baru
- `get_masterdata` untuk mengambil data master material
- `get_history` untuk mengambil histori scan

fitur yang belum sama dengan GUI untuk API:

- Sudah:
  - scan/create data baru
  - mengambil detail master data
  - mengambil histori terbaru
  - paging dan filter rentang tanggal di endpoint history

- Belum sepenuhnya sama dengan GUI:
  - fitur "shift" GUI belum otomatis disediakan sebagai endpoint khusus
  - filter katakanlah berdasarkan jenis shift dapat diimplementasikan dengan query tanggal

Jadi, `api_server.py` sudah cukup untuk integrasi create/get ke frontend web, tetapi jika ingin fitur history berbasis shift otomatis, bisa ditambahkan endpoint khusus lagi.
