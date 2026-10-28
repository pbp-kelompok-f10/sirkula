# Wardrobe: Tambah Pakaian

Modal Tambah Pakaian mengikuti referensi pengguna: latar krem, judul hijau, nama dan kategori sejajar di desktop, area upload bergaris putus-putus, serta tombol Simpan. Pada layar kecil field ditumpuk dan isi dialog dapat digulir. Draft belum tersedia pada tahap ini.

## Alur

1. Login melalui modul accounts bila sudah tersedia, atau login admin Django lokal.
2. Buka /wardrobe/ lalu Tambah Baju. Pengunjung anonim tidak dapat membuka modal.
3. Pilih kategori milik pengguna. Jika belum ada kategori, dialog menjelaskan cara menambahkannya dan menonaktifkan Simpan.
4. Pilih/seret 1–5 foto JPEG, PNG atau WebP, masing-masing maksimal 5.000.000 byte. JS memeriksa ekstensi, MIME yang tersedia, ukuran dan kemampuan browser membaca gambar. Backend tetap menjadi validator utama.
5. Foto baru ditambahkan ke pilihan sebelumnya. Jika satu batch melanggar batas atau memuat file tidak valid, batch tersebut ditolak tanpa menghapus pilihan yang sudah valid. Hapus mengubah preview sekaligus FileList yang akan dikirim. Blob preview dilepas saat foto dihapus atau batch gagal dibaca.
6. Simpan mengirim multipart POST dengan CSRF ke wardrobe:create_item. Tombol menampilkan Menyimpan… dan mencegah submit berulang selama navigasi.
7. Jika backend menolak, modal dibuka kembali; nama/kategori yang masih valid dipertahankan, error field/non-field ditampilkan, fokus menuju error. Foto harus dipilih ulang karena browser tidak mengisi file input setelah respons halaman baru.
8. Setelah berhasil, kartu memakai endpoint foto privat yang sudah ada. Modal kategori tetap berfungsi; Escape/tombol tutup/backdrop mengembalikan fokus ke tombol pembuka. Menutup dan membuka dialog pada halaman yang sama mempertahankan isian/pilihan.

## File

- templates/wardrobe/index.html: tombol, modal multipart, pesan server dan hook preview.
- static/wardrobe/js/wardrobe.js: pengelolaan dua dialog, validasi client, DataTransfer/FileList, preview, hapus, dan status submit.
- static/wardrobe/css/wardrobe.css: backdrop, fokus, status invalid dan kartu preview.
- tests/test_item_modal.py: tes render dan validasi endpoint yang dipakai modal.

## Menjalankan dan memeriksa

Dari root repository:

```sh
python manage.py check
python manage.py test apps.wardrobe
python manage.py makemigrations --check --dry-run
node --check apps/wardrobe/static/wardrobe/js/wardrobe.js
pnpm --dir ui/static_src run build
python manage.py runserver 127.0.0.1:8000
```

Verifikasi tahap ini: 35 tes lolos, check/missing migrations/sintaks JS/diff whitespace lolos. Browser diuji memakai kode checkout asli dengan database dan folder privat sementara: isian wajib, preview lima foto, penolakan foto keenam, hapus/ganti foto, penolakan ukuran >5 MB dan gambar rusak, simpan/kartu privat, error kategori yang dihapus sebelum submit, serta regresi buka/tutup modal kategori. Hash lima foto tersimpan cocok dengan pilihan terakhir dan tidak menyertakan foto yang dihapus.

Modal diperiksa pada desktop dan breakpoint ponsel: field bertumpuk, dialog muat dan tidak overflow horizontal di dalam dialog. Ada overflow horizontal pada navbar bersama dari main; navbar tidak diubah. Build UI juga masih memberi warning upstream tentang urutan @import Google Fonts di tokens.css. Perbaikan kedua hal ini berada di luar tahap modal.

Bantuan AI: Codex menambahkan modal, JS/CSS scoped, tes integrasi modal, dan dokumentasi ini setelah backend pengguna lolos review. Backend, model, migrasi, .gitignore, dan dependency tidak diubah pada tahap ini. Pengujian browser tidak menambahkan data/foto ke database atau storage asli. Tidak ada staging atau commit oleh Codex.
