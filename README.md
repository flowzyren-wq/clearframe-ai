# ClearFrame

**Prototipe enhancement foto dan video umum** dengan output 2×/4× dan slider untuk menahan detail AI agar hasilnya tetap terlihat natural. Tidak ada mode anime, model anime, atau filter restorasi wajah khusus.

## Jalankan lokal

Persyaratan: Python 3.10+, FFmpeg (`ffmpeg` dan `ffprobe` di `PATH`), dan dukungan Vulkan pada sistem. Pada GPU yang kompatibel, Real-ESRGAN NCNN Vulkan memakai akselerasi yang tersedia; tanpa GPU, backend Vulkan perangkat lunak tetap bisa berjalan tetapi dapat jauh lebih lambat. Tile default 512 dituning untuk overhead lebih rendah; set `CLEARFRAME_TILE_SIZE=256` atau lebih kecil (minimal 32) jika GPU memiliki VRAM terbatas, atau 0 untuk mode otomatis.

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/install_backend.py
python app.py
```

Buka `http://127.0.0.1:7860`. Server hanya bind ke localhost secara default. Untuk memakai komputer lain di jaringan privat, set `CLEARFRAME_HOST=0.0.0.0`; jangan expose server tanpa autentikasi ke internet, karena siapa pun yang bisa mengaksesnya dapat mengirim file untuk diproses.

## Cara kerja

- Backend memakai model general-purpose `realesrgan-x4plus` dari Real-ESRGAN. Installer mengunduh rilis portabel resmi tetapi **hanya mengekstrak model umum**; model anime tidak disimpan di proyek atau dipasang.
- Neural output dicampur dengan versi LANCZOS dari sumber. Slider “Enhancement strength” mengontrol pencampuran ini; default 20% dipilih sebagai titik awal konservatif setelah inspeksi frame HD menunjukkan kontur AI bergeser pada 35%, bukan jaminan paling baik untuk semua file.
- Foto diekspor sebagai PNG. Video diproses per batch 32 frame untuk membatasi penyimpanan sementara; frame hasil antara memakai JPEG kualitas 98 sebelum encoding video. Urutan, timestamp, resolusi sesuai skala, dan audio asli dipertahankan jika diminta. Jika audio tidak dapat disalin ke MP4, backend mencoba encode AAC. Durasi prototipe default maksimum 180 detik.
- Frame-by-frame super-resolution masih dapat menimbulkan perubahan detail antar-frame pada gerakan cepat. Tidak ada face synthesis; namun model AI tetap bisa mengarang tekstur, jadi periksa hasil dan turunkan strength bila perlu.

## Uji lokal

Jalankan `python -m unittest discover -s tests -v` untuk memeriksa rendering aplikasi, retensi transparansi, ukuran hasil 2×, pemrosesan video lintas batch, durasi, dan audio. Di sandbox CPU-only (8 thread, RAM 23 GiB, Vulkan llvmpipe), satu frame 720×1280 memerlukan 620 detik untuk keluaran 1440×2560 dengan tile 512; ini mengonfirmasi satu frame skala penuh, bukan keseluruhan video. Klip uji berisi animasi dan overlay teks, jadi tidak membuktikan kualitas pada foto wajah atau video nyata lain. Angka resolusi atau ketajaman saja tidak membuktikan detail lebih akurat.

## Privasi dan masa simpan

Pemrosesan berlangsung pada mesin yang menjalankan aplikasi. Unggahan dan hasil berada di direktori sementara lokal (`/tmp/clearframe-local` secara default) dan tautan hasil kedaluwarsa setelah satu jam. Tidak ada media yang dimasukkan ke repository. Jika aplikasi dijalankan di komputer cloud, file diproses di komputer cloud tersebut—gunakan file yang memang ingin Anda unggah ke sana.

Atur lokasi dengan `CLEARFRAME_DATA_DIR`, batas unggahan dengan `CLEARFRAME_MAX_UPLOAD_BYTES`, batas durasi dengan `CLEARFRAME_MAX_VIDEO_SECONDS`, ukuran tile dengan `CLEARFRAME_TILE_SIZE`, atau cache model dengan `CLEARFRAME_RUNTIME`.

## Tentang klaim kualitas

ClearFrame adalah prototipe, bukan produk yang sudah tervalidasi terhadap Wink. Belum ada benchmark terkontrol “2× lebih bagus” terhadap Wink; hasil sangat bergantung pada kualitas sumber, subjek, gerakan, dan perangkat. Bandingkan sebelum/sesudah pada beberapa foto dan video nyata sebelum menyimpulkan kualitasnya. Model dan proses berjalan lokal, tetapi backend Vulkan perangkat lunak tanpa GPU dapat sangat lambat.

## Sumber dan lisensi

- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — proyek dan model enhancement umum, berlisensi BSD-3-Clause.
- [Real-ESRGAN ncnn Vulkan](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan) — executable portabel, berlisensi MIT.

Kode aplikasi ClearFrame di repository ini berlisensi MIT. File binary dan bobot model diunduh saat setup ke cache lokal; keduanya tidak disimpan atau di-commit ke repository.
