# Menjalankan Sirkula lokal

Setup awal:
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
npm run build:css
.venv/bin/python manage.py migrate
```

Buat `.env` lokal dengan `DEBUG=True` dan `PRODUCTION=False` (satu baris masing-masing). Jangan menyalin seluruh `.env.example` karena contoh tersebut memuat bagian development dan production sekaligus.

Jalankan Django dan biarkan terminalnya terbuka:
```sh
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Buka http://127.0.0.1:8000/ . Pada tahap 0, halaman bawaan Django dapat muncul karena belum ada route aplikasi. Login admin tersedia di /admin/login/; akun admin belum dibuat.

Saat mengedit CSS/template, jalankan di terminal kedua:
```sh
npm run watch:css
```

Tailwind CSS dihasilkan lokal dari static/css/input.css. Sebelum deployment, jalankan npm ci dan npm run build:css sebelum collectstatic. Database SQLite dan environment lokal tidak masuk Git. Strategi media upload akan disiapkan pada fitur pakaian.

## Catatan bantuan AI

Tahap 0: Codex membantu menyiapkan environment, konfigurasi build Tailwind, penemuan static files Django, dokumentasi lokal, dan aturan kerja. Tidak membuat fitur Wardrobe atau melakukan commit. Pengguna melakukan review dan commit sendiri.
