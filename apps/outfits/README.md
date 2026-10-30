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

## Preview berbayar

Default `OUTFITS_PREVIEW_ENABLED=False` dan `OUTFITS_PREVIEW_MAX_REQUESTS=0`. Tetap nonaktif sampai operator menerima persetujuan batas/kuota. Tidak ada tombol baru atau trigger generate otomatis dari kartu/input/polling.

- GET `/outfits/conversations/<uuid>/preview/`: status saja, tidak enqueue. Jika request enqueue sebelumnya timeout, pencocokan manual (tanpa generate) digunakan untuk mencari job yang mungkin sudah ada.
- POST endpoint yang sama: hanya setelah login pemilik, CSRF, flag host, dan kuota persisten instalasi mengizinkan. Satu attempt per pasangan/revisi; timeout tetap mengonsumsi attempt. Pemanggilan ulang hanya memeriksa status, bukan POST enqueue baru.
- GET `.../preview/image/`: proxy privat setelah memeriksa owner, pakaian aktif, versi/foto/revisi pasangan, dan status ready. Tidak menyediakan URL langsung API. Cache private/no-store, Vary Cookie, nosniff dan same-origin.
- Browser hanya membaca status, polling setiap sekitar 3 detik selama queued/running (maksimal 40 kali); ready mengganti area preview existing dan menampilkan label ilustrasi. Polling dihentikan saat berpindah halaman/mengirim input. Request preview terikat versi percakapan agar gambar pasangan lama tidak tercampur.

## Migrasi dan verifikasi

Migrasi `outfits.0002` menambah namespace/pemetaan, lease, kuota/attempt preview, dan role status. Database lokal dicadangkan sebelum migrate; fingerprint kategori, pakaian, foto, percakapan, dan pesan lama identik sesudahnya. Tidak ada perubahan model Wardrobe atau UI baru.

```sh
python manage.py migrate
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

235 tes lolos (termasuk 27 tes kontrak/integrasi API baru). Endpoint health HMAC, sinkronisasi dua foto sintetis, best, dan random telah diuji dengan API nyata melalui localhost memakai database/foto uji terpisah. Generate berbayar tidak pernah dipanggil. Foto sintetis remote dibersihkan setelah pengujian. Desktop 1440 px dan mobile 390 px diperiksa; overflow navbar/footer tim yang sudah ada tetap di luar perubahan ini.

File utama: api_client.py, sync.py, api_provider.py, preview_service.py, preview_views.py, models.py/migration0002, services/providers/views/urls.py, template dan JS/CSS existing, test_api.py dan tes regresi. Tidak staging/commit/push/merge; .gitignore dan .env tidak diubah.
