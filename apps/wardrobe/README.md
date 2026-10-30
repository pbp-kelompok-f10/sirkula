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


## Detail pakaian dan galeri

Klik kartu (atau Enter pada tautan kartu) membuka dialog Detail Pakaian. Nama, kategori dan daftar foto diambil dari wardrobe:item_detail; setiap gambar memakai wardrobe:item_photo. Data pengguna dimasukkan ke DOM lewat textContent/atribut DOM, bukan HTML mentah. Edit tersedia melalui tombol Edit Pakaian; hapus permanen tersedia melalui konfirmasi Hapus Pakaian.

File tahap ini: templates/wardrobe/index.html untuk tautan kartu dan dialog; static/wardrobe/js/item-detail.js untuk fetch/galeri; static/wardrobe/css/wardrobe.css untuk foto/thumbnail; tests/test_item_detail.py untuk akses detail. JS upload dan backend pengguna tidak diubah.

Detail memiliki loading, error 404/gangguan server, tombol Coba lagi, batas waktu request 15 detik, AbortController dan penanda versi request agar respons lama tidak mengganti item baru. Modal ditutup lewat tombol, Escape atau backdrop; fokus kembali ke kartu. Foto dapat dipilih lewat thumbnail, tombol Sebelumnya/Berikutnya, atau panah keyboard. Foto pertama/terakhir membatasi tombol navigasi. Satu foto tetap menampilkan penghitung tanpa kontrol tambahan; tanpa foto menampilkan pesan; kategori null menjadi Tanpa kategori; file yang gagal dimuat memberi pesan tanpa menutup detail lainnya.

Validasi: 45 tes lolos, termasuk 10 tes akses detail baru (owner, non-owner/anonim 404, GET/HEAD, penolakan metode tulis, foto berurutan, kategori dihapus, foto kosong, header cache privat, tidak membocorkan path storage, dan URL foto tetap menolak pengguna lain). System check, missing migrations, sintaks JS dan diff whitespace lolos.

Browser localhost diuji dengan kode checkout asli, database/foto baru dan middleware skenario yang hanya ada di workspace sementara. Loading sengaja diperlambat untuk memeriksa pembatalan; HTTP 503 sementara untuk uji error/retry; record dihapus hanya pada database uji untuk memeriksa 404 dari kartu lama. Galeri lima foto, thumbnail, panah keyboard, batas tombol, foto tunggal, tanpa kategori/foto, file hilang, retry berhasil dan fokus saat Escape terverifikasi. Modal juga muat pada viewport CSS 390 px (lebar dialog 358 px, clientWidth sama dengan scrollWidth). Tidak ada data asli yang diubah.

Build UI berhasil; warning urutan @import Google Fonts dari main dan overflow navbar bersama pada mobile yang sebelumnya dicatat tidak ditangani pada fitur ini. Bantuan AI: Codex menambahkan modal/galeri, tes akses detail dan dokumentasi setelah backend pengguna disiapkan. Tidak ada staging/commit.


## Edit pakaian

Tombol Edit Pakaian dalam detail membuka dialog dengan gaya Tambah Pakaian. Nama dan kategori terisi dari detail; foto lama memakai endpoint privat. Hapus pada foto lama hanya menandai penghapusan dan dapat dibatalkan. Foto baru dapat dipilih/ditambahkan, dipreview, atau dihapus dari pilihan. Jumlah akhir harus 1–5, masing-masing unggahan baru maksimal 5.000.000 byte. Kategori wajib dipilih saat simpan, termasuk ketika kategori sebelumnya sudah dihapus.

Batal, Escape, atau klik backdrop menutup edit, melepas URL preview, dan membuang perubahan lokal tanpa POST. Detail sebelumnya tetap terbuka dan mendapat kembali fokus. Selama POST berjalan, kontrol dinonaktifkan untuk mencegah pengiriman ganda atau penutupan yang memberi kesan pembatalan. Respons validasi ditampilkan dekat field; error umum di bagian atas. Jika hasil request tidak dapat dipastikan, pengiriman ulang untuk item tersebut diblokir sampai halaman dimuat ulang.

Simpan mengirim multipart ke wardrobe:update_item dengan token CSRF, nama, kategori, file baru, dan ID foto lama yang ditandai. Backend pengguna menjalankan transaksi, membersihkan unggahan baru saat rollback, dan menghapus file lama hanya melalui on_commit setelah sukses. Kegagalan penghapusan file setelah commit dicatat ke log dan dapat meninggalkan file sisa. Setelah sukses, browser memuat ulang URL saat ini sehingga filter kategori tetap aktif; pakaian yang dipindah kategori tidak lagi muncul pada filter sebelumnya.

File baru: templates/wardrobe/_item_edit_modal.html, static/wardrobe/js/item-edit.js, tests/test_item_edit.py. Index, JS detail, dan CSS scoped menghubungkan tombol, data URL, modal dan penanda foto yang akan dihapus. Tidak memerlukan migrasi atau perubahan app lain.

Tes permanen: `python manage.py test apps.wardrobe.tests.test_item_edit` (17 tes), atau `python manage.py test apps.wardrobe.tests` (62 tes). Tes mencakup kepemilikan, CSRF, kategori wajib/privat, foto milik pakaian lain, jumlah/ukuran/file rusak, posisi dan ID foto, rollback database/storage, penghapusan setelah commit, serta kegagalan cleanup. Browser localhost diuji pada desktop dan 390 px menggunakan database/foto uji terpisah: buka dari detail, batal dan fokus kembali, preview/hapus foto baru, penolakan foto keenam, penggantian foto, nama tersimpan, kategori kosong, pergantian kategori, dan filter tetap aktif.

Bantuan AI: Codex menambahkan modal edit, penghubung JS/CSS, tes permanen dan dokumentasi setelah form/view/URL dipasang pengguna. Data asli, .gitignore, dan app lain tidak diubah. Build CSS berhasil dengan warning urutan @import Google Fonts yang sudah ada. Tidak ada staging atau commit.


## Hapus permanen dan retry cleanup

Dari detail, tombol Hapus Pakaian membuka dialog krem/hijau sesuai gaya modal yang ada. Dialog menyebut nama pakaian dan sifat permanen penghapusan. Nama dimasukkan melalui textContent. Fokus awal berada di Batal. Batal, Escape, tombol tutup, dan backdrop hanya menutup konfirmasi; detail tetap terbuka dan mendapat kembali fokus. Tidak ada Sampah atau restore.

Ya, Hapus Permanen mengirim POST multipart dengan CSRF ke wardrobe:delete_item. Selama request berlangsung, tombol dinonaktifkan dan dialog tidak dapat ditutup agar penutupan tidak dianggap membatalkan proses server. Error database tampil di dialog dan dapat dicoba ulang. Hasil request yang tidak pasti atau perubahan sesi mengharuskan reload sebelum pengiriman ulang. Sukses memuat ulang URL saat ini sehingga filter kategori tetap aktif, termasuk ketika hasil filter menjadi kosong.

View dan model antrean dipasang pengguna. Command hanya memproses referensi pada WardrobePhotoCleanup; file lain tidak disentuh. File yang gagal dibersihkan tetap di antrean. Jalankan dari root repository:

```sh
python manage.py cleanup_wardrobe_photos
python manage.py cleanup_wardrobe_photos --batch-size 100
```

Antrean diproses berdasarkan ID per batch; setiap ID hanya dicoba satu kali per pemanggilan. Antrean baru setelah command dimulai diproses pada pemanggilan berikutnya. Command menampilkan jumlah diproses/selesai/tertunda, dan keluar dengan status gagal (CommandError) jika antrean yang dicoba masih tertunda. Periksa log/storage lalu jalankan ulang. File yang sudah tidak ada dianggap selesai. Command ini belum dijadwalkan otomatis.

File tambahan: management/commands/cleanup_wardrobe_photos.py, templates/wardrobe/_item_delete_modal.html, static/wardrobe/js/item-delete.js, tests/test_cleanup_command.py, tests/test_item_delete_modal.py. Index, JS detail, dan CSS scoped menghubungkan tombol dan modal. Tidak ada perubahan app lain atau .gitignore.

Validasi: 77 tes Wardrobe lolos, termasuk 6 tes command dan 2 tes render modal baru. Command diuji untuk antrean kosong, batch kecil, file tanpa antrean tidak tersentuh, kegagalan sebagian tanpa menghambat batch berikutnya, retry, file hilang, pemanggilan ulang, input batch tidak valid, dan antrean baru yang ditunda ke run berikutnya. System check, tidak ada migrasi tertinggal, sintaks JS dan diff whitespace lolos. Build CSS berhasil dengan warning urutan @import Google Fonts yang sudah ada.

Browser localhost memakai kode proyek asli dengan database/foto dan middleware simulasi terpisah di workspace uji: Batal/Escape menjaga record dan file, fokus kembali ke Hapus, error database tidak menghapus data, kegagalan storage menyisakan referensi, command retry membersihkan file sisa, penghapusan normal berhasil, dan filter Atasan tetap aktif hingga hasil kosong. Modal diperiksa pada desktop dan 390 px (lebar dan scrollWidth dialog 358 px). Seluruh simulasi hanya memengaruhi data uji.

Bantuan AI: Codex menambahkan command, modal/JS, tes permanen dan dokumentasi setelah backend pengguna lolos review. Tidak ada staging atau commit.


## Cleanup persisten untuk edit dan rollback unggahan

Foto lama yang dilepas saat edit sekarang dicatat ke WardrobePhotoCleanup dalam transaksi yang sama dengan perubahan item. File hanya diproses setelah commit. Jika callback tidak sempat berjalan atau storage gagal, referensi tetap tersedia bagi cleanup_wardrobe_photos. Jika transaksi edit gagal, antrean foto lama ikut dibatalkan sehingga foto yang dipulihkan tidak ikut dibersihkan.

Setelah rollback tambah/edit, nama unggahan baru yang sudah berhasil disimpan dicatat ke antrean sebelum cleanup dicoba. Kegagalan storage tidak lagi meninggalkan file tanpa referensi retry. Bila pencatatan database sendiri gagal, cleanup tidak dilanjutkan dan kegagalan beserta nama file dicatat ke log untuk penanganan operasional.

Worker memeriksa WardrobeItemImage untuk seluruh pengguna sebelum menghapus file. Jika nama file masih direferensikan, file dan antreannya dipertahankan, warning dicatat, dan command melaporkan pekerjaan tertunda. Antrean tersebut bisa diproses setelah file tidak lagi direferensikan. File yang tidak ada tetap aman diproses ulang.

Tes permanen tambahan ada pada tests/test_persistent_cleanup.py: edit cleanup gagal lalu retry, callback tidak berjalan, rollback edit/tambah dengan cleanup gagal, kegagalan unggahan kedua, perlindungan foto aktif lintas pengguna, retry setelah referensi dilepas, deduplikasi antrean, kegagalan penghapusan record antrean, dan kegagalan insert antrean. Pemeriksaan membandingkan isi file foto aktif sebelum/sesudah retry. Tidak ada perubahan model/migrasi atau tampilan pada tahap ini.


## Kategori default pengguna

Saat pengguna baru dibuat melalui `create_user`, `create_superuser`, atau penyimpanan model biasa, signal `post_save` membuat kategori milik pengguna: Kaos, Celana, Kemeja, Outer, dan Sepatu. Signal terdaftar dari `WardrobeConfig.ready()` dan hanya berjalan pada `created=True`, bukan saat login, update pengguna, atau membuka Wardrobe. Import fixture mentah (`raw=True`) dilewati.

`defaults.ensure_default_categories()` dipakai signal dan command. Pencarian memakai `name__iexact` serta pemilik, sehingga `kaos` yang sudah ada digunakan kembali tanpa mengganti nama, ID, atau relasinya. Unique constraint database tetap melindungi nama per pemilik. Helper menjalankan satu transaksi per pengguna dan mengunci pengguna selama pengisian kategori; kegagalan tidak meninggalkan sebagian kategori baru milik pengguna tersebut.

Untuk melengkapi kategori pengguna yang sudah ada, jalankan secara eksplisit:

```sh
python manage.py seed_wardrobe_categories
# Jika memakai alias database lain:
python manage.py seed_wardrobe_categories --database default
```

Command memproses semua pengguna, hanya menambahkan nama default yang belum ada, dan menampilkan jumlah pengguna/kategori. Pemanggilan ulang tanpa perubahan tidak menambah duplikat. Kategori khusus, ID kategori lama, pakaian, dan foto tetap dipertahankan. Command yang dijalankan secara sengaja akan membuat kembali nama default yang pernah dihapus atau diganti; kunjungan Wardrobe/login tidak melakukannya. Pengguna yang dibuat dengan `bulk_create` (yang tidak mengirim signal Django) juga dapat dilengkapi melalui command ini.

Tidak membutuhkan migrasi schema dan tidak ada backfill otomatis saat startup/migrate. Command belum dijalankan pada database asli oleh Codex.

Tes fitur ada di `tests/test_default_categories.py`: pengguna baru/superuser, isolasi pemilik, tidak dibuat ulang setelah hapus/ganti nama/login/kunjungan Wardrobe, fixture raw, registrasi signal tunggal, kapitalisasi, constraint database, rollback dan retry, command kosong, pengisian pengguna lama, idempotensi, serta perlindungan relasi pakaian/foto.
