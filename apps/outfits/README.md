# Outfits: integrasi Sirkula API v2

Kontrak sumber yang dibaca: `sirkula-ai-contract/auth.py`, `app.py`, `core.py`, `previews.py`, dan contoh bridge Django. API mencocokkan gambar pakaian; API ini **bukan chatbot**. Tidak ada layanan chat/LLM tambahan atau fallback AI palsu.

## Konfigurasi dan alur

- `WARDROBE_API_URL` dan `WARDROBE_SECRET` dibaca server dari environment/.env. .env diabaikan Git; .env.example hanya placeholder. URL harus origin HTTPS tanpa userinfo/query/path; secret minimal 32 karakter sesuai kontrak. Redirect upstream ditolak.
- `OUTFITS_PROVIDER=api` adalah default. `demo` hanya untuk simulasi eksplisit/regresi; kegagalan API tidak berubah menjadi jawaban demo.
- HMAC-SHA256 menandatangani `METHOD\nPATH\nOWNER\nTIMESTAMP\nNONCE\nSHA256(BODY)`. Empat header X-Wardrobe dikirim hanya oleh Django. Nonce baru pada setiap request; body yang ditandatangani persis body yang dikirim. Owner API menggunakan UUID namespace permanen per pengguna, bukan input browser.
- Kaos/Kemeja/Outer → `baju`; Celana → `celana`, tanpa membedakan kapital. Sepatu, kategori khusus yang tidak terdaftar, kategori kosong, draft, dan pakaian pengguna lain tidak disinkronkan. Tidak ada kategori fallback menjadi baju.
- API memiliki satu foto per item: sinkronisasi memakai foto utama pertama yang tersedia. Maksimal lima foto asli tetap disimpan privat di Wardrobe; foto lainnya tidak diunggah.
- Sebelum pencocokan, GET katalog memeriksa pemetaan. Item baru diunggah sebagai bytes melalui POST; foto/kategori berubah memakai PUT dengan ID API yang sama. Item yang sudah dihapus/nonaktif/tidak didukung dihapus dari katalog saat sinkronisasi berikutnya. Membuka halaman saja tidak melakukan upload atau generate.
- Kartu rekomendasi yang sudah ada menjadi pintasan Best/Random dengan foto privat pengguna. Ketik `acak`, `random`, atau `acak outfit` untuk random; input lain menggunakan best. Teks bebas tidak ditafsirkan oleh chatbot. Random memakai seed dari UUID request agar retry tetap konsisten.
- Hasil API wajib memetakan satu baju dan satu celana yang benar-benar dimiliki pengguna; skor harus finite dan dalam rentang kontrak. Foto/path upstream tidak diteruskan mentah ke browser. Area percakapan menyimpan input dan **status aplikasi** (role status); pesan dan riwayat lama tetap dibaca.

## Retry dan kegagalan

- Timeout HTTP dibatasi 25 detik; tidak ada retry POST otomatis. Respons dibatasi ukurannya, pesan error upstream tidak dicetak, dan log hanya berisi kode error terkontrol.
- Lease per pengguna mencegah dua sinkronisasi bersamaan. Pemetaan dan status upload pending disimpan sebelum POST. Jika respons upload hilang, request berikutnya mencari satu item remote yang kategori dan hash JPEG normalisasinya cocok, lalu memulihkan ID tanpa POST ulang.
- Kontrak upload belum mempunyai idempotency key. Bila upload tidak pernah diterima atau tidak bisa dibuktikan secara unik, retry diblokir dengan upload_unknown, tanpa menciptakan duplikat. Administrator perlu memastikan request lama selesai dan merekonsiliasi katalog sebelum memperbaiki record pending; jangan menghapus pending secara buta. Perbedaan encoder JPEG antarserver dapat menyebabkan rekonsiliasi hash ditolak secara aman.
- Transaksi percakapan, versi, dan request key lama tetap dipakai. Gagal API/validasi tidak menambah percakapan/pesan. Retry hasil yang sudah disimpan tidak memanggil API lagi. Sebelum menyimpan, item/foto/versi diperiksa ulang.
- Jika hanya ada satu kategori pakaian, layanan meminta minimal satu baju dan satu celana; tidak mengarang pasangan.

## Preview dan kuota per pengguna

Preview telah diizinkan: `OUTFITS_PREVIEW_ENABLED=True` dan `OUTFITS_PREVIEW_MAX_REQUESTS=20`. Backend membatasi maksimal 20 **percobaan** per pengguna, termasuk hasil timeout yang belum pasti. Counter baru `OutfitUserPreviewBudget` mengikuti pengguna Django; namespace API tetap unik per pengguna. Counter global lama dipertahankan untuk audit dan tidak lagi digunakan untuk membatasi request baru.

Setelah pencocokan API baru berhasil disimpan, backend memulai preview satu kali. Request key yang diputar ulang, GET halaman, refresh, dan GET status tidak memanggil enqueue baru. Pasangan/revisi yang sudah mempunyai attempt hanya diperiksa statusnya. Tidak ada UI/tombol baru atau layanan tambahan.

- GET `/outfits/conversations/<uuid>/preview/`: status saja. Job dari request timeout dicari melalui pencocokan manual yang tidak generate.
- POST endpoint yang sama: tetap dibatasi session pemilik, CSRF, flag host, kuota, lease, dan attempt per pasangan/revisi. Timeout tidak mengembalikan kuota atau memicu POST ulang otomatis.
- GET `.../preview/image/`: proxy privat yang memeriksa pemilik, status aktif, versi/foto/revisi pasangan, dan status ready. Cache private/no-store, Vary Cookie, nosniff dan same-origin.
- Polling status queued/running setiap sekitar 3 detik, maksimal 100 kali. Ready memakai area preview existing dan label ilustrasi. Stale, gagal/unknown, disabled, quota habis, HTTP error, serta gambar gagal dimuat menampilkan status aplikasi dan mempertahankan foto pakaian. Halaman ditutup atau input baru dikirim menghentikan update preview lama.
- Kontrak lokal `sirkula-ai-contract/previews.py` masih menggunakan counter global `settings.preview_attempts`. Health server tidak memuat kuota; konfirmasi kuota server 20 per pengguna belum dapat diverifikasi dari kontrak yang diberikan. Counter lokal tidak dapat mengubah pembatasan host.

## Migrasi dan verifikasi

Migrasi `outfits.0003` menambah counter per pengguna dan mengisi jumlah attempt lama berdasarkan pemilik tanpa mereset konsumsi. Counter global tetap disimpan. Migrasi `outfits.0002` menambah namespace/pemetaan, lease, kuota/attempt preview, dan role status. Database lokal dicadangkan sebelum migrate; fingerprint kategori, pakaian, foto, percakapan, dan pesan lama identik sesudahnya. Tidak ada perubahan model Wardrobe atau UI baru.

```sh
python manage.py migrate
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

245 tes Python dan 11 unit test JavaScript lolos. Coverage kode aplikasi (statement + branch) 90,36%; app Outfits 93,13%; JavaScript chat/polling 100% baris, 92,31% cabang, 90% fungsi. File tes dan migrasi tidak dihitung untuk menaikkan metrik. Unit test migrasi tetap memeriksa backfill counter. Konfigurasi `.coveragerc` menetapkan fail_under=80.

```sh
pip install -r requirements-dev.txt
python -m coverage run manage.py test
python -m coverage report --fail-under=80
node --test --experimental-test-coverage --test-coverage-include='apps/outfits/static/outfits/js/chat.js' --test-coverage-lines=80 --test-coverage-branches=80 apps/outfits/js_tests/preview.test.cjs
```

Pengujian end-to-end telah dihentikan atas instruksi pengguna. Sebelum penghentian, satu request generate dilakukan melalui akun/foto sintetis dengan guard persisten maksimal satu panggilan; job belum terdeteksi dan status lokal failed_or_unknown. Tidak ada generate kedua. Alur ready dan gambar privat dibuktikan dengan unit test/fake API, bukan klaim keberhasilan generate nyata. Kesiapan/kecocokan konfigurasi server tetap perlu dikonfirmasi partner.

Tidak staging/commit/push/merge; .env diabaikan Git, nilai secret tidak ada pada file perubahan, .env.example hanya placeholder.
