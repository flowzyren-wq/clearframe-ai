# Laporan Uji Kualitas ClearFrame

Ringkasan: pengujian ulang menemukan bug serius pada versi sebelumnya. Semua foto yang diproses lewat jalur 2× bawaan engine keluar sebagai mosaik kuadran yang salah posisi, sehingga hasilnya bukan sekadar kurang tajam, tetapi rusak. Setelah jalur itu diganti dengan skala asli 4× dan tile internal dimatikan, hasilnya benar dan detailnya meningkat terukur.

## Apa yang diuji

Tiga foto sintetis dibuat khusus agar tidak memakai foto pribadi siapa pun:

| Foto | Isi | Tantangan |
| --- | --- | --- |
| Potret | Wajah dewasa fiktif, cahaya jendela | Tekstur kulit, rambut, mata |
| Jalan kota | Gang batu, tanaman, papan "CAFE" | Detail halus, teks, refleksi |
| Still life | Cangkir keramik dan kain linen | Butiran glasir, serat kain |

Setiap foto dipakai sebagai *ground truth* 720×1080, lalu diperkecil ke 360×540 (setara foto yang sudah kehilangan detail) dan dinaikkan kembali 2× oleh ClearFrame. Hasilnya dibandingkan dengan ground truth memakai dua ukuran:

- **SSIM** — seberapa mirip struktur dan bentuk dengan aslinya (1,0 = identik).
- **Detail mikro** — rata-rata kekuatan Laplacian, penanda seberapa banyak tekstur halus yang benar-benar terlihat.

## Hasil

Rata-rata tiga foto, 720×1080:

| Varian | SSIM | PSNR (dB) | Detail mikro |
| --- | --- | --- | --- |
| Pembesaran biasa (LANCZOS) | 0,8967 | 30,03 | 8,93 |
| ClearFrame 15% | 0,9007 | 30,13 | 10,06 |
| **ClearFrame 30% (default)** | 0,8966 | 29,54 | 12,01 |
| ClearFrame 50% | 0,8805 | 28,18 | 15,30 |
| ClearFrame 100% | 0,8061 | 24,50 | 25,15 |

Waktu proses di sandbox CPU-only (8 thread, RAM 23 GiB, Vulkan llvmpipe): sekitar 180 detik per foto 360×540 menjadi 720×1080.

![Perbandingan 1:1](comparison.png)

Pada gambar di atas, kolom kanan mempertahankan bentuk wajah, ekspresi, dan warna kulit, tetapi helai rambut, tekstur dinding, dan butiran keramik lebih tegas. Di atas 50% tekstur mulai terasa "digoreng" dan kulit kehilangan kelembutan alami, jadi 30% dipilih sebagai default dan 15% untuk yang ingin perubahan paling halus.

## Bug yang diperbaiki

1. **Kuadran tertukar pada jalur 2×.** Engine mengembalikan gambar dengan empat bagian yang tersusun salah. Terukur pada potret: SSIM hanya 0,227 dan PSNR 10,6 dB, jauh di bawah pembesaran biasa. Jalur 4× bawaan engine benar, jadi pipeline sekarang selalu berjalan 4× lalu memperkecil ke ukuran yang diminta.
2. **Sambungan tile.** Dengan tile 512, muncul garis mendatar di mana isi gambar bergeser. Tile internal kini dimatikan; input besar dipotong menjadi strip mendatar yang saling tumpang tindih lalu dilebur dengan gradasi, sehingga tidak ada garis sambungan.

Dampak praktisnya besar: sebelum perbaikan, seluruh foto dan setiap frame video melewati jalur yang rusak ini. Itulah sebabnya hasil sebelumnya tampak "berbayang" walau kekuatan dinaikkan-turunkan.

## Batas pengujian ini

- Sampel sintetis, bukan foto kamera asli. Foto asli dengan noise sensor, motion blur, atau kompresi berat bisa berperilaku berbeda.
- SSIM/PSNR menghukum detail baru yang plausibel, jadi skor sedikit lebih rendah belum berarti hasilnya lebih buruk secara visual. Karena itu penilaian akhir tetap memakai perbandingan berdampingan.
- Belum ada perbandingan terkontrol dengan Wink. Editor web Wink tidak berhasil dirender di lingkungan pengujian (halaman terbuka, antarmuka kosong), dan tidak ada hasil Wink untuk sampel yang sama. Klaim "2× lebih bagus dari Wink" karena itu **tidak** dibuat.
- Uji video baru mencakup integritas (jumlah frame, urutan, durasi, audio, ukuran), belum kualitas visual per frame pada klip nyata.

Angka mentah ada di [benchmark-results.json](benchmark-results.json).
