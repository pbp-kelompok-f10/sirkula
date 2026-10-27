# Aturan kerja Sirkula — Wardrobe

- Kerjakan pada branch feat/wardrobe; periksa status Git sebelum setiap tahap.
- Jangan staging, commit, amend, push, merge, rebase, reset, atau pindah branch tanpa instruksi eksplisit pengguna. Commit dilakukan pengguna sendiri.
- Kerjakan satu fitur yang disepakati per tahap. Jangan menimpa perubahan pengguna.
- Setiap fitur wajib menjalani tes relevan dan pemeriksaan tampilan/alur di localhost sebelum dinyatakan selesai.
- Laporkan hasil tes yang benar-benar dilakukan, keterbatasan, file yang berubah, cara mencoba, dan usulan pesan commit.
- Setelah satu fitur selesai, berhenti untuk review pengguna. Lanjut hanya ketika pengguna menyatakan siap.
- Perubahan file bersama harus minimal. Jangan mengimplementasikan fitur lain tanpa kesepakatan.
- Respons AI simulasi bukan integrasi API selesai. Jaga pemisahan data antar pengguna.
- Jelaskan alur kode agar pengguna dapat memahami dan mendemonstrasikannya. Catat bantuan AI dalam dokumentasi.

## Pengembangan lokal

- Python: `.venv/bin/python manage.py runserver 127.0.0.1:8000`
- CSS: `npm run build:css` atau `npm run watch:css` selama mengubah tampilan.
- Checks: `.venv/bin/python manage.py check` dan tes relevan per fitur.
- Jangan commit `.env`, `.venv`, database lokal, atau `node_modules`.
