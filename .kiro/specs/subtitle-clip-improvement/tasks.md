# Implementation Plan

## Overview

Implementasi bugfix untuk tiga masalah konfigurasi pada pipeline ClipVideo: subtitle FontSize terlalu besar, MarginV terlalu kecil, dan clip count terlalu banyak. Mengikuti exploratory bugfix workflow: tulis exploration test → tulis preservation test → implementasi fix → validasi.

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"] },
    { "wave": 2, "tasks": ["2"] },
    { "wave": 3, "tasks": ["3.1", "3.2", "3.3"] },
    { "wave": 4, "tasks": ["3.4"] },
    { "wave": 5, "tasks": ["3.5"] },
    { "wave": 6, "tasks": ["4"] }
  ]
}
```

## Tasks

- [x] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - Subtitle FontSize, MarginV, dan Clip Count Bug
  - **CRITICAL**: Test ini HARUS GAGAL pada kode yang belum diperbaiki — kegagalan mengkonfirmasi bug ada
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: Test ini mengkodekan perilaku yang diharapkan — test akan memvalidasi fix ketika lulus setelah implementasi
  - **GOAL**: Munculkan counterexample yang mendemonstrasikan bug ada
  - **Scoped PBT Approach**: Karena bug ini adalah nilai konfigurasi deterministik, scope property ke kasus konkret yang gagal
  - Test 1a — Config Clip Count: Baca `settings.clip_count_target` dan `settings.clip_min_count`, assert keduanya ≥ 3 (konfirmasi bug condition `isBugCondition_ClipCount`)
  - Test 1b — Export Style FontSize: Parse string `style` di fungsi `export_clip` pada `app/pipeline/export.py`, assert mengandung `FontSize=20` (konfirmasi `isBugCondition_SubtitleSize`)
  - Test 1c — Export Style MarginV: Parse string `style` di fungsi `export_clip`, assert mengandung `MarginV=120` (konfirmasi `isBugCondition_SubtitlePosition`)
  - Test 1d — Video Effects Style: Parse string `style` di fungsi `track_face_and_reframe` pada `tools/video_effects.py`, assert mengandung `FontSize=20` dan `MarginV=120`
  - Jalankan test pada kode UNFIXED
  - **EXPECTED OUTCOME**: Test GAGAL (ini benar — membuktikan bug ada)
  - Dokumentasikan counterexample yang ditemukan: `settings.clip_count_target=3`, `FontSize=20`, `MarginV=120`
  - Tandai task selesai ketika test sudah ditulis, dijalankan, dan kegagalan terdokumentasi
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Subtitle dan Non-Count Behavior
  - **IMPORTANT**: Ikuti observation-first methodology
  - Observasi perilaku pada kode UNFIXED untuk input non-buggy (di mana `isBugCondition_*` mengembalikan False)
  - Observasi 1: `find_best_clips` dengan 1 segmen tersedia → mengembalikan 1 clip (tidak crash)
  - Observasi 2: `export_clip` dengan `export_subtitles=False` → menghasilkan video tanpa subtitle artifacts
  - Observasi 3: Nilai encoding output tetap libx264, AAC, resolusi 1080×1920
  - Tulis property-based test: untuk semua jumlah segmen (1 hingga 10), `find_best_clips` tidak pernah mengembalikan lebih dari `clip_count_target` clip dan tidak crash
  - Tulis property-based test: untuk semua konfigurasi export dengan `export_subtitles=False`, output path tidak mengandung subtitle artifacts
  - Verifikasi test LULUS pada kode UNFIXED (mengkonfirmasi baseline behavior yang harus dipertahankan)
  - **EXPECTED OUTCOME**: Test LULUS (mengkonfirmasi baseline behavior untuk dipertahankan)
  - Tandai task selesai ketika test sudah ditulis, dijalankan, dan lulus pada kode unfixed
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 3. Fix subtitle style dan clip count configuration

  - [x] 3.1 Perbaiki default clip count di `app/config.py`
    - Ubah `clip_count_target` dari `3` menjadi `2`
    - Ubah `clip_min_count` dari `3` menjadi `1`
    - _Bug_Condition: isBugCondition_ClipCount(X) where X.clip_count_target >= 3 OR X.clip_min_count >= 3_
    - _Expected_Behavior: find_best_clips mengembalikan maksimal 2 clip (len(result) <= 2)_
    - _Preservation: Jika segmen tersedia < target, sistem tetap menghasilkan clip sebanyak yang tersedia (tidak crash)_
    - _Requirements: 2.3, 3.5_

  - [x] 3.2 Perbaiki nilai FontSize dan MarginV di `app/pipeline/export.py`
    - Ubah `FontSize` dari `20` menjadi `13` pada string `style` di fungsi `export_clip`
    - Ubah `MarginV` dari `120` menjadi `60` pada string `style` di fungsi `export_clip`
    - _Bug_Condition: isBugCondition_SubtitleSize(X) where X.export_subtitles=True AND FontSize >= 18_
    - _Bug_Condition: isBugCondition_SubtitlePosition(X) where X.export_subtitles=True AND MarginV <= 120_
    - _Expected_Behavior: subtitle_font_size < 18 (target 13), subtitle_margin_v > 120 (target 60 dalam konteks ASS style)_
    - _Preservation: Export tanpa subtitle (export_subtitles=False) tidak terpengaruh; encoding libx264/AAC/1080×1920 tetap sama_
    - _Requirements: 2.1, 2.2, 3.1, 3.3, 3.4_

  - [x] 3.3 Perbaiki nilai FontSize dan MarginV di `tools/video_effects.py`
    - Ubah `FontSize` dari `20` menjadi `13` pada string `style` di fungsi `track_face_and_reframe`
    - Ubah `MarginV` dari `120` menjadi `60` pada string `style` di fungsi `track_face_and_reframe`
    - _Bug_Condition: isBugCondition_SubtitleSize(X) dan isBugCondition_SubtitlePosition(X) pada jalur smart reframe_
    - _Expected_Behavior: subtitle_font_size < 18, subtitle_margin_v > 120 pada single-pass FFmpeg_
    - _Preservation: Logika face tracking dan dynamic crop tidak berubah; hanya nilai style string yang dimodifikasi_
    - _Requirements: 2.1, 2.2, 3.2, 3.4_

  - [ ] 3.4 Verify bug condition exploration test sekarang lulus
    - **Property 1: Expected Behavior** - Subtitle FontSize, MarginV, dan Clip Count Bug
    - **IMPORTANT**: Jalankan ulang test YANG SAMA dari task 1 — JANGAN tulis test baru
    - Test dari task 1 mengkodekan perilaku yang diharapkan
    - Ketika test ini lulus, mengkonfirmasi expected behavior terpenuhi
    - Jalankan bug condition exploration test dari langkah 1
    - **EXPECTED OUTCOME**: Test LULUS (mengkonfirmasi bug sudah diperbaiki)
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.5 Verify preservation tests masih lulus
    - **Property 2: Preservation** - Non-Subtitle dan Non-Count Behavior
    - **IMPORTANT**: Jalankan ulang test YANG SAMA dari task 2 — JANGAN tulis test baru
    - Jalankan preservation property tests dari langkah 2
    - **EXPECTED OUTCOME**: Test LULUS (mengkonfirmasi tidak ada regresi)
    - Konfirmasi semua test masih lulus setelah fix (tidak ada regresi)

- [ ] 4. Checkpoint - Pastikan semua test lulus
  - Jalankan seluruh test suite: `python -m pytest tests/ -v`
  - Pastikan semua test lulus, tanyakan kepada user jika ada pertanyaan yang muncul
  - Verifikasi bahwa tidak ada test yang sebelumnya lulus menjadi gagal

## Notes

- Bug ini adalah perubahan nilai konfigurasi murni — tidak ada perubahan logika, hanya perubahan nilai konstanta di tiga file
- Exploration test (task 1) bersifat deterministik: cukup baca nilai dari source code dan konfigurasi, tidak perlu menjalankan FFmpeg atau pipeline penuh
- Preservation test (task 2) menggunakan property-based testing untuk memberikan jaminan lebih kuat bahwa perilaku non-buggy tidak berubah
- Nilai `FontSize=13` dan `MarginV=60` dipilih sebagai titik tengah dari rentang yang disebutkan di requirements (FontSize 11–14, MarginV 60–80); dapat disesuaikan berdasarkan hasil visual testing
- Perubahan di `export.py` dan `video_effects.py` harus dilakukan secara konsisten — keduanya menggunakan string `style` yang identik
