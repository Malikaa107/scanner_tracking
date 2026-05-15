import logging # library untuk mencatat log (pesan sistem)
import os #library untuk interaksi sistem (buat folder, file)
from logging.handlers import RotatingFileHandler # library mengelola file log agar tdk terlalu besar, membuat file baru saat ukuran tercapai batas


def setup_logging() -> None: # fungsi untuk mengatur logging
    """Configure root logger once for console + file output.""" 
    root_logger = logging.getLogger()  # mengambil logger utama (root logger) untuk mencatat log diseluruh aplikasi
    if getattr(root_logger, "_scanner_logging_configured", False): # cek apakah logger sudah dikonfigurasi sebelumnya, agar tidak duplikasi log
        return

    # mengambil level log dari environment
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper() 
    log_level = getattr(logging, log_level_name, logging.INFO) 

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs") 
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s") # format log yg mencakup waktu, level log, nama dan pesan 

    # Handler 1 : menampilkan log ke terminal 
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    # Handler 2: menyimpan log ke dalam file teks 
    file_handler = RotatingFileHandler( 
        log_file,
        maxBytes=2 * 1024 * 1024, # jika ukuran melebihi 2MB, buat file baru
        backupCount=5, # simpan maksimal 5 file log lama 
        encoding="utf-8", 
    )
    file_handler.setFormatter(formatter)

    # Terapkan konfigurasi ke root logger 
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    root_logger._scanner_logging_configured = True

