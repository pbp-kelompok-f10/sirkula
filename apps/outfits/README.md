# Mix and Match — halaman awal

Halaman `/outfits/` mengikuti referensi `Desktop - 4 (1).png`: hero gradasi dengan tombol kembali, input kebutuhan berikon kirim, empat kartu Rekomendasi Outfit, dan empat kartu Riwayat. Header/footer memakai base tim. Tidak menambahkan bagian Outfit Tersimpan, tombol baru, atau workspace hasil/chat.

## Data dan alur

- `demo_data.py` berisi fixture publik. Ini bukan riwayat atau pakaian asli pengguna.
- `services.py` menyediakan `get_landing_content(prompt)` yang mengembalikan data baru setiap pemanggilan. View/template bergantung pada kontrak ini, bukan endpoint AI. Tidak ada koneksi AI pada tahap ini.
- `forms.py` memvalidasi kebutuhan nonkosong setelah trim dan maksimal 500 karakter.
- GET/HEAD menampilkan halaman. POST dengan CSRF memvalidasi kebutuhan dan hanya merotasi contoh rekomendasi secara deterministik. Tidak menyimpan riwayat, percakapan, atau pakaian. Input valid tetap tampil setelah submit; error tampil dekat input dan mendapat fokus.
- Kartu merupakan preview statis; pembukaan hasil/percakapan dikerjakan pada tahap berikutnya.
- Tautan Mix and Match Outfit dan Chat AI Stylist dari Wardrobe mengarah ke halaman ini. Chat AI Stylist menargetkan input melalui anchor. Parameter kategori numerik dipertahankan saat kembali ke Wardrobe; tidak menerima URL tujuan dari pengguna.
- Referensi chat tambahan `Desktop - 5.png` memperlihatkan input pesan, menu riwayat, dan Chat Baru. Komponen tersebut dicatat untuk tahap chat, tidak ditambahkan ke halaman awal.

## Aset contoh dan styling

`static/outfits/img/landing-reference.png` adalah salinan referensi pengguna, tidak mengubah berkas asli. Komponen `_card.html` memakai viewport SVG untuk menampilkan hanya bagian foto blouse dari referensi; gambar utuh diunduh sekali dan dipakai semua kartu. Metadata viewport berada pada data demo. Saat aset thumbnail asli/API tersedia, ganti representasi gambar melalui batas data/komponen kartu. Tidak memakai foto Wardrobe privat sebagai aset publik.

CSS pada `static/outfits/css/landing.css` hanya berlaku di dalam `.mix-landing`. Desktop menggunakan empat kolom, tablet/mobile dua kolom, dan layar di bawah 360 px satu kolom. Tombol kirim 44×44 px, focus ring, label screen reader, dan rasio gambar disediakan. Nama kartu memakai contoh pakaian menggantikan teks dummy Telur Ayam Kampung pada mockup.

## Verifikasi

```sh
python manage.py test apps.outfits apps.wardrobe
python manage.py makemigrations --check --dry-run
pnpm --dir ui/static_src run build
python manage.py runserver 127.0.0.1:8000
```

164 tes lolos: 154 regresi Wardrobe dan 10 tes landing. Tes mencakup render tanpa UI tambahan, submit simulasi tanpa penulisan data, validasi, escaping, CSRF/metode HTTP, tautan balik yang aman, isolasi dari data Wardrobe pengguna, fixture tidak termutasi antar-request, tautan masuk, dan penemuan aset statis. Tidak membutuhkan perubahan model/migrasi.

Browser localhost memakai database/foto uji terpisah: navigasi masuk/kembali, filter kategori, anchor Chat AI Stylist, input kosong/spasi, kirim lewat ikon dan Enter, serta tampilan desktop 1440×1024 dan mobile 390×844/320×740. Konten Mix and Match tidak overflow horizontal pada kedua ukuran mobile. Halaman global masih memiliki overflow navbar/footer dari base tim yang sudah ada; tidak diubah di tahap ini. Build berhasil dengan warning lama urutan @import Google Fonts.

Bantuan AI: Codex menambahkan halaman awal, data simulasi, form/service, CSS scoped, penghubung Wardrobe, dan tes atas permintaan pengguna. Tidak membuat halaman hasil/chat, tidak memakai API AI, tidak staging/commit, dan tidak mengubah .gitignore atau fitur app partner. Database serta foto asli tidak digunakan untuk mutasi pengujian.
