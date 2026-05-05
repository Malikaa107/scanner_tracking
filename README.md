# Scanner Tracking

Aplikasi desktop Python untuk scan barcode dan menyimpan historinya ke PostgreSQL, dengan tambahan API FastAPI agar data dapat diakses dari frontend web secara bersamaan.

## Requirements

- Python 3.10+ / 3.11+
- PostgreSQL database dengan schema `latihan`
- Tabel `latihan.barcode` yang memiliki setidaknya kolom:
  - `id`
  - `kode_barcode`
  - `created_at`
- Tabel `latihan.master_data` dengan kolom `kode_sap`, `nama_rawmaterial`, dan `merk_type`

## Instalasi

1. Buka terminal di folder proyek ini.

2. Install dependency yang dibutuhkan:

```powershell
pip install -r requirement.txt
```

*(Jika perintah `pip` tidak dikenali, pastikan Python sudah ter-install dan terdaftar di dalam PATH environment variabel, atau gunakan perintah `py -m pip install -r requirement.txt` / `python -m pip install -r requirement.txt`)*

## Menjalankan Aplikasi

Aplikasi telah diperbarui sehingga ketika antarmuka GUI (Desktop) dijalankan, server API (FastAPI) juga otomatis berjalan di latar belakang (thread terpisah).

### Opsi 1: Menjalankan GUI + API Bersamaan (Utama)

```powershell
python App_scanner.py
```
*(Bisa juga dengan `py App_scanner.py`)*

Aplikasi desktop (Sistem Scanner Formulasi) akan terbuka dan secara bersamaan server API akan siap menerima *request* di `http://127.0.0.1:5678`.

### Opsi 2: Hanya Menjalankan API Saja (Tanpa Layar)

Jika Anda hanya membutuhkan backend API untuk diakses web frontend tanpa membuka jendela aplikasi Desktop:
```powershell
python api_server.py
```

## Endpoint API (Base URL: http://127.0.0.1:5678)

1. `GET /api/health`
   - Berfungsi untuk mengecek apakah server API hidup.

2. `POST /api/scan`
   - **Body JSON:**
     ```json
     {
       "kode_barcode": "123456"
     }
     ```
   - **Fungsi:** Validasi barcode, menyimpannya ke tabel `latihan.barcode` di database, dan mengembalikan data master material. Dapat digunakan untuk mensimulasikan proses scan dari alat eksternal atau *frontend*.

3. `GET /api/masterdata/{kode_sap}`
   - **Contoh:** `/api/masterdata/123456`
   - **Fungsi:** Mengambil detail informasi raw material (contohnya `nama_rawmaterial` dan `merk_type`) dari tabel `latihan.master_data`.

4. `GET /api/history`
   - **Contoh tanpa filter:** `/api/history?limit=50&page=1`
   - **Contoh dengan rentang waktu:**
     `/api/history?start=2026-04-01%2000:00:00&end=2026-04-30%2023:59:59&limit=15&page=1`
   - **Contoh Response Payload:**
     ```json
     {
       "total": 3,
       "page": 1,
       "limit": 10,
       "rows": [
         {
             "id": 3,
             "kode_barcode": "12345678",
             "created_at": "2026-04-30T11:47:51.027179"
         }
       ]
     }
     ```
   - **Fungsi:** Mengambil histori scan barcode dari database. Telah mendukung *pagination* (halaman) dan *filtering* berdasarkan rentang tanggal-waktu.

## Catatan Integrasi Frontend

- Saat ini, cukup jalankan `App_scanner.py` untuk mengaktifkan UI Scanner yang akan dipakai oleh operator dan sekaligus menghidupkan server API untuk web frontend.
- Aplikasi web (React.js, Vue, dll) bisa mengkonsumsi endpoint-endpoint yang berjalan lokal di alamat `http://127.0.0.1:5678`.
- Pastikan konfigurasi *host*, *user*, dan *password* database di file `database.py` sudah sesuai dengan pengaturan server database aktif Anda.

### Status Fungsionalitas API:
- ✅ Menambah/Simpan data pemindaian baru (`POST /api/scan`).
- ✅ Mengambil detail material / Master Data (`GET /api/masterdata/...`).
- ✅ Mengambil riwayat terbaru (`GET /api/history`).
- ✅ Paging dan filter waktu pada riwayat.
- 🚧 **Belum tersedia Endpoint Khusus Shift**: Saat ini logika pemilihan shift yang ada pada aplikasi lama belum dibuatkan endpoint spesifik di API. Namun, frontend dapat mengakali hal ini dengan mengirimkan parameter query tanggal dan jam kerja (`start` & `end`) ke dalam endpoint riwayat biasa.
