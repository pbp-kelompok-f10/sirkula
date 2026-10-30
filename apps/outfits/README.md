# Mix and Match: hasil, chat, dan riwayat

Referensi halaman awal: Desktop - 4 (1).png. Workspace mengikuti Desktop - 3.png: preview outfit, tiga foto penyusun, panel SirkulaAI, pesan, dan input kirim. Menu riwayat dan Chat Baru mengikuti Desktop - 5.png. Tidak menambahkan UI Outfit Tersimpan, tombol simpan/hapus percakapan, atau kontrol lain.

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
- `services.py`: validasi respons provider, transaksi penyimpanan, pemilik, urutan, idempotensi, versi, dan daftar riwayat. Provider dipanggil sebelum lock transaksi; versi dicek lagi sebelum menulis agar hasil lama tidak menimpa pesan baru.
- `forms.py`, `views.py`, `urls.py`: input nonkosong/maksimal 500 karakter, UUID request, versi, respons JSON/HTML, CSRF dan owner checks.
- `templates/outfits/`: landing, workspace, hero, kartu rekomendasi/riwayat, serta komponen gambar.
- `static/outfits/js/chat.js`: kirim/status/error, pencegahan submit ganda, scroll pesan, menu riwayat, Escape/klik luar/fokus, dan Chat Baru melalui tautan biasa.
- `static/outfits/css/chat.css`: layout desktop/mobile dan styling komponen sesuai referensi. Header/footer tetap memakai base tim.

## Kontrak provider

Adapter dipanggil melalui `reply(prompt=..., history=..., recommendation=...)` dan mengembalikan `StylistReply(text, title, result)`. `history` berisi maksimal 20 pesan terakhir dalam bentuk `role` dan `content`; seluruh pesan tetap tersimpan dalam database.

`result` memiliki `mode`, `preview`, dan `pieces` (nama serta gambar penyusun). Gambar demo memakai metadata viewport SVG dari salinan referensi pengguna. Format gambar juga menyediakan representasi URL lokal privat untuk adapter AI kelak; endpoint penyajian/penyimpanan gambar AI harus dibuat saat integrasi tersebut, tidak memakai URL eksternal mentah dari model. Tidak ada API AI yang dipanggil pada tahap ini.

`DemoStylistProvider` mengembalikan contoh kombinasi kaos putih, kemeja biru, dan celana krem untuk semua prompt. Ini fixture UI, bukan penilaian kecocokan outfit. Data pakaian/foto privat Wardrobe tidak dibaca atau disalin menjadi static.

## Keamanan dan kegagalan

- GET/POST percakapan pengguna lain, anonim, atau ID tidak ada menghasilkan 404. Halaman dengan riwayat diberi no-store/private dan Vary: Cookie.
- POST dilindungi CSRF. Teks di-render dengan escaping Django; JavaScript menulis error melalui textContent.
- Creation key unik per pemilik; request key dan role unik per percakapan. Retry dengan key/isi yang sama mengembalikan hasil yang sudah ada tanpa menggandakan pesan. Key yang dipakai untuk isi berbeda ditolak 409.
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

182 tes lolos: 28 Outfits dan 154 Wardrobe. Termasuk isolasi pengguna, anonymous/other-user GET/POST, CSRF, escaping, idempotensi, konflik sebelum/sesudah provider, rollback provider/database, provider result tidak valid, history lebih dari 50, context provider dibatasi, dan regresi.

Browser localhost memakai database/foto uji terpisah: input/kartu awal, kirim ikon/Enter, validasi pesan kosong, buka ulang riwayat, Chat Baru tanpa menghapus data, menu/Escape, serta respons gagal sesudah commit lalu retry tanpa duplikasi. Anonim dan akun kedua diuji langsung mendapat 404 untuk URL pemilik; riwayat kedua akun terpisah. Tampilan desktop dan mobile 390/320 px diperiksa. Konten workspace/chat tidak overflow horizontal; masalah global navbar/footer dan warning lama @import Google Fonts tidak diubah.

Bantuan AI: Codex mengimplementasikan backend percakapan, provider simulasi, UI hasil/chat, menu riwayat, tes dan dokumentasi atas permintaan pengguna. Tidak staging/commit, mengubah .gitignore, membuat login baru, atau mengubah fitur app partner. Uji browser tidak menambahkan percakapan ke database asli proyek.
