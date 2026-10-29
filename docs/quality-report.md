# Laporan Uji Kualitas ClearFrame

## Ringkasnya

ClearFrame kini menambahkan penajaman tepi yang sangat ringan pada pembesaran LANCZOS sebelum dicampur dengan AI. Pengaturan AI 0% tetap menghasilkan LANCZOS biasa; detail yang dibangkitkan model tidak ikut dipertajam lagi. Default dinaikkan menjadi 50% agar hasil lebih tegas, dengan catatan bahwa 30% lebih konservatif dan nilai di atas 50% lebih berisiko membuat tekstur tampak buatan.

Di tiga sampel sintetis dengan gambar acuan, langkah penajaman dasar menaikkan SSIM dan detail mikro pada campuran AI 30% maupun 50%. Pada 50%, rata-rata PSNR turun sedikit (0,02 dB) dibanding campuran 50% tanpa penajaman itu, jadi ini trade-off kejernihan, bukan bukti detail baru yang benar. Pada foto yang sama dengan dua hasil Wink, metrik energi tepi ClearFrame 50% masih sedikit di bawah Wink UHD. Tidak ada dasar untuk mengklaim “2× lebih bagus dari Wink”.

## Uji dengan gambar acuan

Tiga gambar sintetis 720×1080 (potret, jalan kota, dan produk) diperkecil menjadi 360×540, lalu diproses kembali ke 720×1080. Karena gambar beresolusi penuh tersedia sebagai acuan, hasil dapat dibandingkan dengan PSNR, SSIM, dan detail mikro rata-rata Laplacian. Detail mikro mengukur kekuatan perubahan lokal—bisa meningkat karena tepi yang berguna, noise, atau artefak.

Rata-rata tiga sampel:

| Varian | SSIM | PSNR (dB) | Detail mikro |
| --- | ---: | ---: | ---: |
| LANCZOS biasa | 0,8967 | 30,03 | 8,93 |
| LANCZOS + penajaman dasar ringan | 0,9044 | 30,18 | 10,27 |
| AI 15%, sebelum perubahan baru | 0,9007 | 30,13 | 10,06 |
| AI 30%, tanpa penajaman dasar | 0,8966 | 29,54 | 12,01 |
| AI 30% + penajaman dasar ringan | 0,9013 | 29,54 | 12,89 |
| AI 50%, tanpa penajaman dasar | 0,8805 | 28,18 | 15,30 |
| **AI 50% + penajaman dasar ringan (default baru)** | **0,8841** | **28,16** | **15,86** |
| AI 100%, tanpa penajaman dasar | 0,8061 | 24,50 | 25,15 |

Penajaman dasar yang dipakai adalah unsharp mask radius 1, kekuatan 40%, ambang 2. Pada AI 30% dan 50%, SSIM naik pada masing-masing dari ketiga sampel. Detail mikro juga naik. Perubahan PSNR kecil dan tidak seragam—karena itu parameter ini dipakai secara konservatif, bukan dianggap pemulihan detail yang pasti benar. Nilai 0% tidak memakai filter ini dan tetap sama persis dengan pembesaran LANCZOS.

![Perbandingan 1:1](comparison.png)

## Perbandingan dengan Wink pada satu foto yang sama

Foto asli dan dua hasil Wink yang dikirim pengguna dibandingkan lokal saja. Semua gambar disesuaikan ke kanvas 2428×2560 dengan LANCZOS. Energi tepi relatif terhadap pembesaran LANCZOS foto asli:

| Hasil | Energi tepi relatif |
| --- | ---: |
| ClearFrame 50% lama, tanpa penajaman dasar baru | 1,375× |
| ClearFrame 50% dengan penajaman dasar baru (perkiraan dari keluaran AI tersimpan) | 1,387× |
| Wink UHD | 1,436× |
| Wink UHD AI | 3,862× |

Angka ClearFrame baru diperkirakan dengan menerapkan langkah penajaman dasar pada keluaran AI 50% yang sudah tersimpan; model tidak dijalankan ulang pada foto pribadi untuk pengukuran ini. Energi tepi bukan skor kualitas persepsi: detail palsu, noise, dan halo juga dapat menaikkannya. Sampel hanya satu potret dan tidak memiliki acuan resolusi tinggi, jadi tabel ini tidak membuktikan pemenang secara visual. Yang dapat dikatakan: perubahan baru membuat hasil sedikit lebih tegas, tetapi belum menyamai energi tepi Wink UHD pada ukuran kanvas ini; Wink UHD AI jauh lebih agresif.

## Implementasi dan batas

- Model tetap `realesrgan-x4plus`, model umum untuk foto dan video. Tidak ada mode/model anime atau sintesis wajah khusus.
- Model dijalankan pada 4× aslinya, lalu diperkecil bila pengguna memilih 2×. Jalur 2× bawaan engine pernah menyusun kuadran secara salah, sehingga tidak dipakai.
- Gambar besar diproses dalam strip bertumpang-tindih. Tile internal engine dimatikan karena sebelumnya menimbulkan sambungan konten bergeser.
- Pada mesin sandbox CPU-only yang tersedia (8 thread, RAM 23 GiB), satu inference resolusi penuh pernah memerlukan sekitar 15 menit. Kecepatan bergantung perangkat; Vulkan software dapat sangat lambat.
- Video tetap diproses per frame, sehingga detail dapat berubah antar-frame saat gerakan cepat. Audio asli dipertahankan jika diminta. Penajaman dasar deterministik diterapkan per frame, tetapi uji ini belum mengukur kualitas video nyata.
- Foto contoh diproses dan dibandingkan lokal, tidak diunggah ke layanan luar.

Angka sintetis mentah ada di [benchmark-results.json](benchmark-results.json); benchmark yang dapat dijalankan ulang ada di [benchmark.py](benchmark.py). Klaim “2× lebih bagus” tidak dibuat karena satu foto dan metrik ini tidak cukup untuk menyimpulkan keunggulan persepsi secara adil.
