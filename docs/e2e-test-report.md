# Laporan Pengujian End-to-End Sirkula

Tanggal pengujian: 30 Oktober 2026

## Environment

- Django development server: `http://127.0.0.1:8000/`
- Browser: Codex in-app browser
- Akun demo lokal: `e2e_admin` dan `e2e_seller`
- Data demo: `E2E Thrift Jacket` dan `E2E Barter Bag`

## Hasil pengujian browser

| Modul | Alur | Hasil |
|---|---|---|
| Home | Membuka halaman beranda | Lulus |
| Shop | Membuka daftar produk | Lulus |
| Shop | Search produk `Ayam` | Lulus |
| Shop | Filter harga `10000` sampai `60000` | Lulus |
| Detail produk | Membuka detail produk | Lulus |
| Galeri | Mengganti thumbnail foto utama | Lulus |
| Cart | Menambahkan produk thrift | Lulus |
| Cart | Melihat subtotal dan total | Lulus |
| CRUD seller | Membuka daftar produk milik seller | Lulus |
| Transaksi | Membuka daftar pesanan pembeli | Lulus |
| Transaksi | Membuka daftar pesanan masuk seller | Lulus |
| Transaksi | Membuka detail transaksi | Lulus |
| Transaksi | Seller mengonfirmasi pesanan | Lulus |
| Timeline | Status berubah menjadi dikonfirmasi dan tercatat di timeline | Lulus |
| Barter | Membuka tawaran barter masuk | Lulus |
| Barter | Membuka daftar transaksi barter | Lulus |
| Login required | Mengakses cart tanpa login | Mengarah ke `/accounts/login/`, tetapi URL login belum tersedia sehingga tampil 404 |

## Pengujian otomatis

Perintah:

```powershell
python manage.py check
python manage.py migrate --noinput
python manage.py test apps.transactions.tests apps.bartering.tests --verbosity 2
```

Hasil:

- System check: lulus.
- Migration: lulus.
- Test transaksi dan barter: 9 test lulus.

## QRIS

Pengujian QRIS sandbox dilakukan melalui browser pada 30 Oktober 2026.

| Langkah | Hasil |
|---|---|
| Membuka checkout thrift | Lulus; total tampil `Rp 53.500` |
| Mengisi alamat dan nomor handphone demo | Lulus |
| Submit checkout ke endpoint QRIS sandbox | Request dijalankan, tetapi QR tidak terbentuk |
| Respons UI | Menampilkan `QRIS belum dapat dibuat. Periksa konfigurasi Midtrans.` |
| Rollback order ketika request gagal | Lulus; order QRIS gagal dihapus |
| Rollback ketersediaan produk | Lulus; produk kembali `is_available=True` |

Kesimpulan: alur error handling QRIS bekerja, tetapi integrasi belum menghasilkan QR sandbox. Konfigurasi saat ini terbaca sebagai sandbox (`MIDTRANS_IS_PRODUCTION=False`) dan server key terisi, namun request Midtrans tetap gagal. Periksa kembali server key sandbox dan akses QRIS pada akun Midtrans; setelah itu ulangi checkout sandbox.

## Pengujian pengguna ulang

Pengujian ulang dilakukan melalui browser pada 30 Oktober 2026 menggunakan akun demo pembeli dan penjual.

| Area | Alur yang diuji | Hasil |
|---|---|---|
| Home | Membuka beranda dan memeriksa navigasi Home, Shop, Wardrobe, Map | Lulus |
| Shop | Membuka daftar produk, search, dan filter harga | Lulus |
| Detail | Membuka detail produk barter/thrift | Lulus |
| Galeri | Klik thumbnail dan memastikan foto utama berubah | Lulus |
| Cart | Membuka cart dan memeriksa produk/total | Lulus |
| Checkout | Membuka checkout thrift dan memeriksa form, pengiriman, metode pembelian, total | Lulus |
| Pembeli | Daftar pesanan dan detail transaksi | Lulus |
| Penjual | Daftar pesanan masuk dan halaman produk milik penjual | Lulus |
| Status | Status `Dikonfirmasi` dan timeline transaksi | Lulus |
| Barter | Tawaran masuk, tawaran keluar, dan transaksi barter | Lulus |
| Barter | Membuka chat checkout dan form ajukan tawaran | Lulus; form tidak dikirim |
| CRUD produk | Membuka form tambah dan edit produk penjual | Lulus; form tidak disimpan |
| Admin | Dashboard dan model Bartering, Marketplace, Transactions | Lulus |
| Login required | Cart tanpa login | Redirect bekerja, tetapi `/accounts/login/` masih 404 karena URL login belum dibuat |

Tidak ada perubahan data produksi. Pengujian memakai akun, produk, dan order demo lokal.
