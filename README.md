<p align="center">
<!-- mau domain pbp :( -->
  <a href="https://sirkula.pbp.cs.ui.ac.id">  
    <picture>
      <img src="static/img/sirkula-logo.png" alt="Sirkula Logo">
    </picture>
  </a>
</p>

<p align="center" style="color: #c3e3d6"><b>PBP Midterm Project - Kelompok F10</b></p>
<p align="center">
  <a href="https://www.djangoproject.com/"><img alt="django" src="https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="html" src="https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="css" src="https://img.shields.io/badge/-CSS-1572B6?style=flat-square&logo=css&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="django" src="https://shields.io/badge/JavaScript-F7DF1E?logo=JavaScript&logoColor=white&style=flat" /></a>
  <a href="https://sqlite.org"><img alt="postgresql" src="https://img.shields.io/badge/postgresql-4169e1?style=flat&logo=postgresql&logoColor=white" /></a>
</p>

<pre align="center">
ANGGOTA KELOMPOK:
ZAYYAN RAMADZAKI FIRDAUS (2506550955)
RAYYAN RADITIA PRAMANA (2506598955)
ILMAN GHANI AWLIYA (2506656803)
FAREL BOSTON CORINTHIANS NADEAK (2506548490)
MARWA MUHLASHON (2506552714)
</pre>

## ♻️ Tentang Sirkula 
Sirkula membantu pengguna menemukan barang layak pakai di sekitar mereka dan memanfaatkan kembali barang yang sudah dimiliki. Pengguna dapat mencari barang preloved, menawarkan barang untuk dijual atau ditukar, serta mendata koleksi pakaian dalam lemari digital.

Fashion menjadi fokus utama Sirkula. Melalui pengembangan AI Stylist, kami ingin membantu pengguna menemukan kombinasi outfit dari koleksi pribadi sebelum memutuskan membeli pakaian baru. Marketplace Sirkula juga mencakup kategori barang lain untuk mendukung pertukaran barang di lingkungan terdekat.

Proyek ini dikembangkan oleh Kelompok F10 untuk Proyek Tengah Semester mata kuliah Pemrograman Berbasis Platform di Fakultas Ilmu Komputer, Universitas Indonesia.

## 🎨 Features
Sirkula masih dalam pengembangan. Berikut cakupan fitur yang menjadi fokus proyek.

| Modul | Cakupan |
| --- | --- |
| **Marketplace** | Katalog dan detail barang yang ditawarkan pengguna. |
| **Discovery Map** | Pencarian produk dan toko berdasarkan lokasi, radius, dan kata kunci. |
| **Transaksi dan barter** | Alur pembelian dan pertukaran barang, termasuk status serta riwayat transaksi. |
| **Personal Wardrobe** | Pengelolaan koleksi pakaian pribadi dalam lemari digital. |
| **AI Stylist** | Pengembangan rekomendasi dan visualisasi outfit berdasarkan koleksi pakaian pengguna. |
| **Akun dan profil** | Autentikasi dan pengelolaan profil pengguna. |

## 💻 Tech Stack
- **Backend:** Python dan Django
- **Antarmuka:** Django Templates, HTML, dan JavaScript
- **Styling:** Tailwind CSS
- **Database:** SQLite untuk pengembangan lokal dan PostgreSQL untuk produksi
- **Peta:** MapLibre GL dengan style OpenFreeMap Liberty
- **Geocoding:** Provider yang kompatibel dengan Nominatim

## ⬇️ Instalasi dan menjalankan secara lokal

### Prasyarat

Siapkan Git, Python, Node.js, dan pnpm.

### 1. Clone repositori

```bash
git clone https://github.com/pbp-kelompok-f10/sirkula.git
cd sirkula
```

### 2. Siapkan virtual environment

```bash
python -m venv env
```

Aktifkan virtual environment sesuai sistem operasi.

**macOS / Linux**

```bash
source env/bin/activate
```

**Windows PowerShell**

```powershell
.\env\Scripts\Activate.ps1
```

### 3. Instal dependensi

```bash
python -m pip install -r requirements.txt
```

### 4. Atur environment

Salin `.env.example` menjadi `.env`.

**macOS / Linux**

```bash
cp .env.example .env
```

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

Untuk pengembangan lokal, gunakan:

```dotenv
DEBUG=True
PRODUCTION=False
```

Berkas contoh memuat konfigurasi development dan production. Pastikan `DEBUG` dan `PRODUCTION` hanya didefinisikan satu kali dengan nilai yang sesuai.

Sesuaikan `NPM_BIN_PATH` dengan lokasi pnpm pada perangkat. Isi konfigurasi layanan eksternal jika fitur terkait akan digunakan. Simpan kredensial di `.env` dan jangan sertakan dalam commit.

### 5. Build stylesheet

```bash
cd ui/static_src
pnpm install
pnpm run build
cd ../..
```

Jalankan kembali `pnpm run build` setelah mengubah komponen atau stylesheet yang memerlukan kompilasi Tailwind.

### 6. Jalankan aplikasi

```bash
python manage.py migrate
python manage.py runserver
```

Aplikasi dapat diakses di [localhost:8000](http://localhost:8000/).

## 🗂️ Struktur proyek

```text
.
├── apps/               # Modul fitur aplikasi
├── main/               # Modul halaman utama
├── sirkula/            # Konfigurasi proyek Django
├── static/             # Aset statis bersama
├── templates/          # Template bersama
├── ui/                 # Sumber styling dan konfigurasi build
├── .env.example        # Contoh konfigurasi environment
├── manage.py
└── requirements.txt
```

## 🌎 Discovery Map

Discovery Map tersedia di `/marketplace/map/`. Pengguna dapat mencari produk dan toko di sekitar koordinat atau area yang dipilih.

Koordinat disimpan sebagai nilai desimal. Jarak dihitung di backend menggunakan rumus Haversine, sehingga fitur ini dapat berjalan di SQLite maupun PostgreSQL tanpa PostGIS atau ekstensi database spasial.

### Provider peta dan lokasi

Peta menggunakan MapLibre GL dengan style OpenFreeMap Liberty. Data peta bersumber dari OpenStreetMap, dengan atribusi yang ditampilkan melalui kontrol peta.

Forward dan reverse geocoding diteruskan melalui backend ke provider yang kompatibel dengan Nominatim. Request menggunakan identitas aplikasi, timeout, dan cache. Pencarian di antarmuka menggunakan debounce untuk membatasi request berulang.

Geolokasi IP ditangani oleh provider terpisah. Saat aplikasi berjalan dengan IP lokal atau privat, lokasi default diarahkan ke Jakarta Pusat tanpa request geolokasi eksternal.

### Konfigurasi

| Environment variable | Kegunaan |
| --- | --- |
| `NOMINATIM_BASE_URL` | Alamat provider geocoding yang kompatibel dengan Nominatim. |
| `IP_GEOLOCATION_URL` | Alamat provider geolokasi IP dengan dukungan placeholder `{ip}`. |
| `LOCATION_USER_AGENT` | Identitas aplikasi dan kontak pengelola untuk request geocoding. |
| `LOCATION_REQUEST_TIMEOUT` | Batas waktu request provider dalam detik. |
| `LOCATION_CACHE_SECONDS` | Durasi cache hasil geocoding dan pencarian lokasi IP. |

Untuk deployment dengan trafik tinggi, gunakan instance Nominatim mandiri atau provider komersial melalui `NOMINATIM_BASE_URL`.

### Endpoint

| Method | Endpoint | Keterangan |
| --- | --- | --- |
| `GET` | `/marketplace/api/locations/` | Daftar lokasi yang tersedia di Jabodetabek. Mendukung pencarian melalui `q`. |
| `GET` | `/marketplace/api/nearby/` | Produk dan toko terdekat. Mendukung `lat`, `lon`, `location`, `radius`, dan `q`. |
| `GET` | `/marketplace/api/geocode/` | Pencarian koordinat menggunakan `q`, minimal tiga karakter. |
| `GET` | `/marketplace/api/reverse-geocode/` | Pencarian informasi lokasi menggunakan `lat` dan `lon`. |

Pada endpoint `nearby`, lokasi ditentukan melalui pasangan `lat` dan `lon` atau slug `location`. Jika lokasi tidak diberikan, aplikasi menggunakan fallback berbasis IP.

## ⛑️ Pemeriksaan dan pengujian

Jalankan pemeriksaan konfigurasi dan konsistensi migrasi:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

Jalankan pengujian Discovery Map:

```bash
python manage.py test apps.marketplace.tests
```

Periksa sintaks JavaScript:

```bash
node --check apps/marketplace/static/marketplace/js/discovery-map.js
```

Periksa build stylesheet:

```bash
cd ui/static_src
pnpm run build
```

## ✒️ Kontribusi

Kontribusi dapat berupa perbaikan bug, pembaruan dokumentasi, atau usulan fitur.

Untuk melaporkan masalah, buka [issue](https://github.com/pbp-kelompok-f10/sirkula/issues) dan sertakan:

- Langkah untuk mereproduksi masalah.
- Perilaku yang diharapkan dan hasil yang terjadi.
- Informasi lingkungan atau tangkapan layar jika relevan.

Untuk mengajukan perubahan:

1. Fork repositori dan buat branch untuk perubahan Anda.
2. Kerjakan satu perubahan dengan ruang lingkup yang jelas.
3. Jalankan pemeriksaan yang relevan.
4. Ajukan pull request dengan penjelasan perubahan dan cara memverifikasinya.

Untuk perubahan besar, buka issue terlebih dahulu agar pendekatan dan ruang lingkupnya dapat didiskusikan.

## 👥 Tim pengembang

| Nama | NPM | Tanggung jawab |
| --- | --- | --- |
| Zayyan Ramadzaki Firdaus | 2506550955 | Discovery Map dan integrasi layanan lokasi |
| Rayyan Raditia Pramana | 2506598955 | Homepage, dataset fashion, dan integrasi AI |
| Ilman Ghani Awliya | 2506656803 | Marketplace, transaksi, barter, dan desain antarmuka |
| Farel Boston Corinthians Nadeak | 2506548490 | Personal Wardrobe dan integrasi rekomendasi outfit |
| Marwa Muhlashon | 2506552714 | Profil pengguna dan desain UI/UX |

## 🎯 Target Pengguna
Target utama dari platform ini adalah mahasiswa dan generasi Z yang tertarik pada bidang fashion, namun ingin memanfaatkan pakaian yang sudah mereka miliki sekaligus mencari pilihan fashion yang terjangkau. Platform ini ditujukan bagi pengguna yang ingin mengeksplorasi gaya berpakaian dan mendapatkan inspirasi outfit untuk berbagai aktivitas, seperti kuliah, berkumpul bersama teman, maupun menghadiri acara tertentu, tanpa harus selalu membeli pakaian baru.

## 📎 Tautan
Sejauh ini kami masih melakukan eksplorasi design system seperti warna, tone, dan project branding. [Tautan Figma dapat diakses disini.](https://www.figma.com/design/TyoL1i8RIAmSWF3XUgPpNu/PBP-ZBMRI?node-id=0-1&p=f&t=d6ULHADOhbWBseQy-0)

## AI Disclosure 
Kami menggunakan AI sebagai alat yang membantu dan menjadi partner dalam melakukan pengerjaan proyek sirkula (PBP) ini. Dalam penggunannya kami melakukan diskusi, brainstorming, bantuan kode untuk sintaks dan copy paste dalam hal yang kompleks, serta harness hanya untuk bagian kompleks dan memakan banyak waktu.

Dalam penggunannya kami melakukan strategi dengan memberikan konteks dan prompting sedetail, selengkap, dan setepat mungkin untuk menghasilkan hasil yang tepat sesuai yang diinginkan. Setiap hasil/output kami periksa/review terlebih dahulu dan memahami baru melakukan implementasinya. Setiap implementasi pun di cek dan verfikasi oleh setiap individu.

Link chat:
- Marwa : Claude Sonnet 5.5 - https://claude.ai/share/c81abc6e-ff14-4b57-a8e6-917105a7d5ed 
- Boston : Sol 6.1 - https://chatgpt.com/s/cx_6ae4c86f25c48191952bb042a7339e39
- Zayyan : Deepseek V4.1 Flash (Tidak dapat di share link chat harness nya)
- Rayyan : Astra 6 - https://chatgpt.com/s/cx_6ae4c829d7dc8191b276f60590970575
- Ilman : 5.6 Luna -  https://chatgpt.com/s/cx_6ae4c9690ebc819194558629906b01bc

<!-- trigger pws -->