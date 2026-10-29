# ClearFrame

**Prototipe enhancement foto dan video umum** dengan output 2×/4× dan slider untuk menahan detail AI agar hasilnya tetap terlihat natural. Tidak ada mode anime, model anime, atau filter restorasi wajah khusus.

Metode uji dan angkanya ada di [docs/quality-report.md](docs/quality-report.md); skripnya bisa dijalankan ulang dengan `python docs/benchmark.py`.

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
- Model selalu dijalankan pada skala aslinya 4×, lalu hasilnya diperkecil ke 2× bila perlu. Jalur 2× bawaan engine ternyata menyusun kuadran gambar di posisi salah pada pengujian lokal, sehingga tidak dipakai lagi. Tile internal engine juga dimatikan karena meninggalkan sambungan konten bergeser; gambar besar dipotong menjadi strip mendatar yang tumpang tindih lalu dilebur.
- Neural output dicampur dengan versi LANCZOS dari sumber. Default AI 50% dipilih sebagai setelan lebih tegas untuk foto/video sehari-hari; penajaman dasar yang sangat ringan diterapkan pada versi LANCZOS sebelum blending jika AI tidak 0%. Dalam uji tiga gambar sintetis, ini menaikkan SSIM rata-rata campuran AI 50% dari 0,8805 ke 0,8841 dan detail mikro dari 15,30 ke 15,86; PSNR rata-rata turun sedikit dari 28,18 ke 28,16 dB. 30% lebih konservatif untuk tekstur kulit, dan di atas 50% tekstur lebih berisiko tampak buatan. Pilihan 0% tetap pembesaran LANCZOS persis tanpa filter maupun kontribusi AI.
- Foto diekspor sebagai PNG. Video diproses per batch 32 frame untuk membatasi penyimpanan sementara; frame hasil antara memakai JPEG kualitas 98 sebelum encoding video. Urutan, timestamp, resolusi sesuai skala, dan audio asli dipertahankan jika diminta. Jika audio tidak dapat disalin ke MP4, backend mencoba encode AAC. Durasi prototipe default maksimum 180 detik.
- Frame-by-frame super-resolution masih dapat menimbulkan perubahan detail antar-frame pada gerakan cepat. Tidak ada face synthesis; namun model AI tetap bisa mengarang tekstur, jadi periksa hasil dan turunkan strength bila perlu.

## Uji lokal

Jalankan `python -m unittest discover -s tests -v` untuk memeriksa rendering aplikasi, retensi transparansi, mode 0% yang sama persis dengan pembesaran LANCZOS, rumus penajaman dasar sebelum blending AI, ukuran hasil 2×, pemrosesan video lintas batch, durasi, dan audio.

Benchmark memakai tiga foto sintetis sebagai ground truth 720×1080, diperkecil ke 360×540 lalu dinaikkan kembali. Satu inference resolusi penuh 960×1012 pada sandbox CPU-only (8 thread, RAM 23 GiB, Vulkan llvmpipe) memerlukan sekitar 15 menit. Angka kualitas yang dirangkum di laporan adalah SSIM/PSNR terhadap ground truth dan energi tepi; semuanya punya batas dan bukan skor selera visual. Perbandingan sampel Wink sekarang mencakup satu foto pengguna yang sama, tetapi hanya mengukur energi tepi setelah ukuran disamakan—bukan bukti pemenang persepsi. Tidak ada klaim “2× lebih bagus dari Wink”.

## Privasi dan masa simpan

Pemrosesan berlangsung pada mesin yang menjalankan aplikasi. Unggahan dan hasil berada di direktori sementara lokal (`/tmp/clearframe-local` secara default) dan tautan hasil kedaluwarsa setelah satu jam. Tidak ada media yang dimasukkan ke repository. Jika aplikasi dijalankan di komputer cloud, file diproses di komputer cloud tersebut—gunakan file yang memang ingin Anda unggah ke sana.

Atur lokasi dengan `CLEARFRAME_DATA_DIR`, batas unggahan dengan `CLEARFRAME_MAX_UPLOAD_BYTES`, batas durasi dengan `CLEARFRAME_MAX_VIDEO_SECONDS`, ukuran tile dengan `CLEARFRAME_TILE_SIZE`, atau cache model dengan `CLEARFRAME_RUNTIME`.

## Tentang klaim kualitas

ClearFrame adalah prototipe dan belum terbukti lebih baik daripada Wink. Satu foto dan dua hasil Wink yang diberikan pengguna sudah dibandingkan lokal pada kanvas yang sama: energi tepi ClearFrame 50% dengan penajaman dasar diperkirakan 1,387× pembesaran LANCZOS, dibanding Wink UHD 1,436× dan Wink UHD AI 3,862×. Energi tepi juga menghitung noise/artefak, sehingga tidak menunjukkan kualitas persepsi atau keaslian detail. Penilaian yang adil memerlukan beberapa foto dan video nyata serta peninjauan berdampingan. Jangan unggah media ke layanan luar tanpa izin. Model dan proses berjalan lokal, tetapi backend Vulkan perangkat lunak tanpa GPU dapat sangat lambat.

## Sumber dan lisensi

- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — proyek dan model enhancement umum, berlisensi BSD-3-Clause.
- [Real-ESRGAN ncnn Vulkan](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan) — executable portabel, berlisensi MIT.

Kode aplikasi ClearFrame di repository ini berlisensi MIT. File binary dan bobot model diunduh saat setup ke cache lokal; keduanya tidak disimpan atau di-commit ke repository.
