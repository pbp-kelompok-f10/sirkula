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

## Tambah Kategori

Bantuan AI: Codex menyiapkan modal, JavaScript, dan tes kategori. Modal mengikuti referensi Tambah Kategori Baru, memakai dialog native untuk fokus keyboard dan Escape. Penyimpanan tetap POST Django dengan CSRF; owner diambil view dari request.user. Error server dirender pada field yang terkait dan modal dibuka kembali.

Jalankan `python manage.py test main`, `python manage.py check`, `node --check static/js/wardrobe.js`, dan `npm run build:css`.

Pengujian browser lokal memakai akun staf uji melalui `/admin/login/`, kemudian `/wardrobe/`. Jangan menyimpan kredensial dalam Git. Buat akun lokal sendiri dengan `python manage.py createsuperuser` jika diperlukan.

Periksa: buka modal, fokus input, Tab/Shift+Tab tetap dalam dialog, tutup dengan tombol/Escape/backdrop, fokus kembali ke Tambah Kategori, simpan nama baru, lalu coba nama duplikat (termasuk perbedaan kapital), input kosong dan nama panjang. Pada error server, nilai harus tetap terlihat dengan pesan validasi. Ulangi dengan akun kedua untuk memastikan kategori akun pertama tidak tampil. Pengunjung anonim tidak dapat membuka modal atau menyimpan kategori. Periksa desktop dan lebar ponsel; dialog harus muat dan bisa digulir pada layar pendek.

Validasi pada salinan kerja Codex: 11 tes backend lulus; Django check, pemeriksaan migrasi, sintaks JS dan build CSS lulus. Tampilan/interaksi browser belum terverifikasi karena sandbox menolak pembukaan port localhost. Perubahan perlu diterapkan dan diperiksa pada checkout asli sebelum dinyatakan selesai.
