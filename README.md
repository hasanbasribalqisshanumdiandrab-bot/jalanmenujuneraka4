# Cari Jawaban Soal (materi PDF / foto / PPTX)

Situs statis tanpa backend. Cocok untuk GitHub Pages.

## Pasang (sekali)
1. Buat repo GitHub baru, unggah **seluruh isi** folder ini (termasuk folder `.github`).
2. Settings → Pages → Source: *Deploy from a branch* → `main` / `(root)`.
3. Settings → Actions → General → Workflow permissions → **Read and write permissions**.
4. Buka `https://USERNAME.github.io/NAMA-REPO/`.

## Update materi
Unggah PDF / foto / PPTX baru ke folder `materi/` (lewat web GitHub: Add file → Upload files).
GitHub Actions otomatis membaca (OCR) file baru, memperbarui `data/`, lalu situs ikut terbarui
(tunggu ±2-5 menit). Hapus file dari `materi/` untuk menghapusnya dari pencarian.

## Jalan manual di PC (opsional)
    pip install pytesseract pillow python-pptx requests
    python materi_sync.py            # atau: python materi_sync.py --watch
Butuh Tesseract (+ bahasa Indonesia) dan poppler. Lihat komentar di atas `materi_sync.py`.

## Catatan
- Repo publik = isi materi bisa dibaca siapa saja. Gunakan repo private bila perlu (Pages private butuh paket GitHub berbayar).
- Hasil OCR bisa keliru; setiap hasil menampilkan gambar halaman asli untuk dicek.
- "Kemungkinan jawaban" hanyalah perkiraan dari kecocokan kata.
