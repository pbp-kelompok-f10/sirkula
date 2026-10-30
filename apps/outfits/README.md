# Mix and Match: hasil, chat, dan riwayat

Referensi halaman awal: Desktop - 4 (1).png. Workspace mengikuti Desktop - 3.png: preview outfit, kolom foto penyusun (1–3 pakaian aktif pada simulasi), panel SirkulaAI, pesan, dan input kirim. Menu riwayat dan Chat Baru mengikuti Desktop - 5.png. Tidak menambahkan UI Outfit Tersimpan, tombol simpan/hapus percakapan, atau kontrol lain.

## Alur pengguna

1. `/outfits/` tetap bisa dilihat sebagai halaman awal publik. Pengguna harus login untuk memulai percakapan; modul login tidak dibuat ulang. Selama accounts belum aktif, pengujian lokal dapat memakai login admin Django.
2. Mengirim input awal atau menekan kartu rekomendasi membuat percakapan milik `request.user`, menyimpan pesan pengguna/balasan simulasi, lalu redirect ke `/outfits/conversations/<uuid>/`.
3. Pesan lanjutan menyimpan satu pasangan pesan dan memperbarui preview terakhir. POST memiliki fallback HTML/redirect; JS memakai respons JSON untuk status kirim/error dan kembali ke GET setelah berhasil.
4. Riwayat halaman awal dan menu chat menampilkan percakapan pengguna sendiri, diurutkan berdasarkan aktivitas terakhir. Semua riwayat tetap tersedia melalui area yang dapat digulir. Tanggal menu memakai bahasa Indonesia dan Asia/Jakarta.
5. Chat Baru kembali ke input awal tanpa membuat percakapan kosong atau menghapus percakapan lama. Klik riwayat membuka seluruh pesan tersimpan dan preview terakhir.
6. Filter kategori asal dipertahankan melalui tautan kembali. UUID, judul, kategori, dan isi dari browser tidak menentukan pemilik record.

## Pembagian kode

- `models.py`, `migrations/0001_initial.py`: Conversation (owner, judul, hasil terakhir, versi, kunci pembuatan) dan Message (role, isi, urutan, kunci request). Model Wardrobe tidak diubah.
- `providers.py`: `DemoStylistProvider` tanpa akses database/network, `StylistReply`, dan factory `get_stylist_provider()` sebagai titik pergantian adapter AI.
- `wardrobe_context.py`: metadata pakaian aktif milik pengguna, whitelist pilihan provider, pemeriksaan ulang versi/foto dalam transaksi, dan resolusi foto privat saat riwayat dibuka.
- `services.py`: validasi respons provider, transaksi penyimpanan, pemilik, urutan, idempotensi, versi, dan daftar riwayat. Provider dipanggil sebelum lock transaksi; versi dicek lagi sebelum menulis agar hasil lama tidak menimpa pesan baru.
- `forms.py`, `views.py`, `urls.py`: input nonkosong/maksimal 500 karakter, UUID request, versi, respons JSON/HTML, CSRF dan owner checks.
- `templates/outfits/`: landing, workspace, hero, kartu rekomendasi/riwayat, serta komponen gambar.
- `static/outfits/js/chat.js`: kirim/status/error, pencegahan submit ganda, scroll pesan, menu riwayat, Escape/klik luar/fokus, dan Chat Baru melalui tautan biasa.
- `static/outfits/css/chat.css`: layout desktop/mobile dan styling komponen sesuai referensi. Header/footer tetap memakai base tim.

## Kontrak provider

Adapter dipanggil melalui `reply(prompt=..., history=..., wardrobe=..., recommendation=...)` dan mengembalikan `StylistReply(text, title, result)`. `history` berisi maksimal 20 pesan terakhir dalam bentuk `role` dan `content`; seluruh pesan tetap tersimpan dalam database.

`wardrobe` merupakan metadata biasa: ID/nama pakaian, kategori (boleh `null`), versi `updated_at`, serta ID/posisi foto yang filenya tersedia. Hanya pakaian aktif milik pengguna yang masuk. Provider tidak menerima ORM object, path storage, URL foto, atau isi file. Draft dan pakaian akun lain tidak dikirim.

Provider mengembalikan `result = {"mode": "demo", "item_ids": [1, 2]}`. Service memeriksa ID terhadap metadata semula, menolak duplikat/ID asing, lalu membentuk hasil kanonis sendiri. Snapshot nama/kategori dan referensi `{"kind": "wardrobe", "item_id": ..., "photo_id": ...}` disimpan pada JSON Conversation; URL foto tidak disimpan. Versi, status, pemilik, relasi foto, dan keberadaan file diperiksa lagi setelah lock sebelum menulis pasangan pesan.

`DemoStylistProvider` memilih maksimal tiga pakaian berfoto, mendukung satu/dua pakaian, dan menyebut nama pilihan aktual dalam balasan. Pilihan berikutnya dirotasi secara deterministik menggunakan panjang konteks; ini simulasi, belum penilaian kecocokan outfit maupun API AI. Preview besar memakai foto pertama pilihan, bukan gambar outfit gabungan hasil AI. Kartu rekomendasi halaman awal tetap memakai fixture desain publik; hasil setelah kartu diklik menggunakan pakaian pengguna saat itu.

Saat riwayat dibuka, referensi foto diverifikasi ulang terhadap pemilik/status aktif dan diubah menjadi URL endpoint privat Wardrobe dalam salinan untuk render. Foto yang hilang/dihapus, pakaian yang tidak lagi aktif, atau referensi yang tidak sesuai menampilkan “Foto tidak tersedia” pada area gambar yang sama. File tidak disalin ke static atau dipertahankan setelah penghapusan. Riwayat lama dengan metadata SVG referensi tetap dapat dibuka tanpa diubah. Pesan lanjutan memakai kondisi Wardrobe terbaru; hanya hasil terbaru diperbarui saat penyimpanan berhasil.

## Keamanan dan kegagalan

- GET/POST percakapan pengguna lain, anonim, atau ID tidak ada menghasilkan 404. Halaman dengan riwayat diberi no-store/private dan Vary: Cookie.
- POST dilindungi CSRF. Teks di-render dengan escaping Django; JavaScript menulis error melalui textContent.
- Creation key unik per pemilik; request key dan role unik per percakapan. Retry dengan key/isi yang sama mengembalikan hasil yang sudah ada tanpa menggandakan pesan. Key yang dipakai untuk isi berbeda ditolak 409.
- Tanpa pakaian aktif berfoto, permintaan ditolak 400 melalui pesan validasi yang ada, tanpa membuat percakapan/pasangan pesan. Pakaian atau foto berubah selama provider berjalan ditolak 409.
- Versi stale ditolak 409 dan pengguna diarahkan lewat pesan error untuk membuka ulang percakapan dari menu riwayat.
- Pasangan pesan dan hasil disimpan dalam satu transaksi. Provider/database gagal tidak meninggalkan percakapan atau setengah pasangan pesan baru.
- Jika respons terputus, browser mempertahankan key yang sama untuk retry. Batas waktu kirim 30 detik tidak dianggap membatalkan proses backend yang mungkin sudah menyimpan.

## Migrasi dan pengujian

Cadangan database lokal dibuat di luar repository sebelum `migrate outfits`. Migrasi awal Outfits sudah diterapkan pada database lokal. Data kategori, pakaian, dan referensi foto Wardrobe dibandingkan sebelum/sesudah dan tetap identik. Tidak ada migrasi yang memindahkan atau mengubah data Wardrobe.

```sh
python manage.py migrate
python manage.py test apps.outfits apps.wardrobe
python manage.py makemigrations --check --dry-run
node --check apps/outfits/static/outfits/js/chat.js
pnpm --dir ui/static_src run build
python manage.py runserver 127.0.0.1:8000
```

196 tes lolos: 42 Outfits dan 154 Wardrobe. Termasuk isolasi pengguna, anonymous/other-user GET/POST, CSRF, escaping, idempotensi, konflik sebelum/sesudah provider, rollback provider/database, provider result tidak valid, history lebih dari 50, context provider dibatasi, dan regresi. Tambahan tes mencakup pilihan 1–3 pakaian/nama aktual, metadata tanpa path/URL, pemisahan draft/akun lain, whitelist ID, foto privat, foto hilang/berubah, kompatibilitas riwayat lama, dan konflik perubahan Wardrobe sebelum simpan.

Integrasi data Wardrobe ini tidak mengubah model atau membutuhkan migrasi baru.

Browser localhost memakai database/foto uji terpisah: input/kartu awal, kirim ikon/Enter, validasi pesan kosong, buka ulang riwayat, Chat Baru tanpa menghapus data, menu/Escape, serta respons gagal sesudah commit lalu retry tanpa duplikasi. Anonim dan akun kedua diuji langsung mendapat 404 untuk URL pemilik; riwayat kedua akun terpisah. Tampilan desktop dan mobile 390/320 px diperiksa. Pengujian integrasi Wardrobe juga memeriksa satu/dua/tiga pakaian, nama balasan, foto privat yang benar-benar termuat, riwayat lama dan lanjutannya, placeholder foto terhapus, validasi saat tidak ada foto aktif, serta akun lain/anonim ditolak saat membuka URL foto. Konten workspace/chat tidak overflow horizontal; masalah global navbar/footer dan warning lama @import Google Fonts tidak diubah.

Bantuan AI: Codex mengimplementasikan backend percakapan, provider simulasi, UI hasil/chat, menu riwayat, tes dan dokumentasi atas permintaan pengguna. Tidak staging/commit, mengubah .gitignore, membuat login baru, atau mengubah fitur app partner. Uji browser tidak menambahkan percakapan ke database asli proyek.
