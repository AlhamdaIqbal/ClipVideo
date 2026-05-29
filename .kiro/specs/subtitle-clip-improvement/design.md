# Subtitle Clip Improvement Bugfix Design

## Overview

Terdapat tiga bug konfigurasi pada pipeline ClipVideo yang perlu diperbaiki secara bersamaan:

1. **FontSize terlalu besar** — nilai `FontSize=20` di-hardcode pada dua lokasi (`export.py` dan `video_effects.py`) menghasilkan subtitle yang tidak proporsional pada resolusi vertikal 1080×1920.
2. **MarginV terlalu kecil** — nilai `MarginV=120` di-hardcode pada dua lokasi yang sama menyebabkan subtitle muncul di area tengah video dan menutupi konten utama.
3. **Clip count terlalu banyak** — `clip_count_target=3` dan `clip_min_count=3` di `app/config.py` menghasilkan hingga 3 clip, padahal pengguna hanya membutuhkan maksimal 2.

Strategi perbaikan: ubah nilai konfigurasi di `app/config.py` dan nilai hardcode di `app/pipeline/export.py` serta `tools/video_effects.py`. Perubahan bersifat minimal dan terisolasi — tidak ada perubahan logika, hanya perubahan nilai konstanta.

---

## Glossary

- **Bug_Condition (C)**: Kondisi yang memicu bug — konfigurasi subtitle dengan FontSize ≥ 18, MarginV ≤ 120, atau clip_count_target/clip_min_count ≥ 3
- **Property (P)**: Perilaku yang diharapkan setelah fix — FontSize < 18, MarginV > 120, dan jumlah clip ≤ 2
- **Preservation**: Perilaku yang tidak boleh berubah — export tanpa subtitle, smart reframe, fallback center crop, encoding video, dan penanganan segmen kurang dari target
- **`export_clip`**: Fungsi di `app/pipeline/export.py` yang mengekspor satu clip video dengan opsional subtitle melalui jalur fallback Center Crop
- **`track_face_and_reframe`**: Fungsi di `tools/video_effects.py` yang melakukan face tracking dan dynamic crop, lalu membakar subtitle dalam satu pass FFmpeg
- **`find_best_clips`**: Fungsi di `app/pipeline/analyze.py` yang memilih clip terbaik berdasarkan skor; menggunakan `clip_count_target` dan `clip_min_count` dari `settings`
- **`force_style`**: Parameter FFmpeg untuk subtitle ASS/SRT yang memungkinkan override gaya tampilan subtitle
- **`smart_reframe`**: Mode export yang menggunakan face tracking (OpenCV) untuk dynamic crop 9:16
- **`settings`**: Instance `Settings` dari `app/config.py` yang dibaca dari environment variables atau nilai default

---

## Bug Details

### Bug Condition

Bug terjadi pada tiga kondisi independen yang semuanya berasal dari nilai konfigurasi yang salah:

1. **Subtitle Size Bug**: Ketika `export_subtitles=True`, string `force_style` di-hardcode dengan `FontSize=20` di dua tempat berbeda, menghasilkan teks subtitle yang terlalu besar dan mendominasi layar pada resolusi 1080×1920.

2. **Subtitle Position Bug**: Ketika `export_subtitles=True`, string `force_style` di-hardcode dengan `MarginV=120` di dua tempat berbeda, menempatkan subtitle terlalu tinggi dari bawah layar sehingga menutupi konten utama.

3. **Clip Count Bug**: `clip_count_target=3` dan `clip_min_count=3` sebagai default di `Settings` menyebabkan `find_best_clips` selalu berusaha menghasilkan 3 clip.

**Formal Specification:**

```
FUNCTION isBugCondition_SubtitleSize(X)
  INPUT: X of type ExportConfig
  OUTPUT: boolean

  RETURN X.export_subtitles = TRUE AND X.subtitle_font_size >= 18
END FUNCTION

FUNCTION isBugCondition_SubtitlePosition(X)
  INPUT: X of type ExportConfig
  OUTPUT: boolean

  RETURN X.export_subtitles = TRUE AND X.subtitle_margin_v <= 120
END FUNCTION

FUNCTION isBugCondition_ClipCount(X)
  INPUT: X of type PipelineConfig
  OUTPUT: boolean

  RETURN X.clip_count_target >= 3 OR X.clip_min_count >= 3
END FUNCTION
```

### Examples

- **Subtitle Size**: Export clip dengan `export_subtitles=True` → subtitle tampil dengan `FontSize=20`, teks terlihat sangat besar dan mendominasi ±10% tinggi layar pada resolusi 1920px
- **Subtitle Position**: Export clip dengan `export_subtitles=True` → subtitle muncul di posisi `MarginV=120` dari bawah, menutupi area konten utama video
- **Clip Count**: Menjalankan pipeline analyze pada video 5 menit → sistem menghasilkan 3 clip padahal pengguna hanya membutuhkan 2
- **Edge case — segmen kurang dari target**: Jika hanya ada 1 segmen yang memenuhi syarat, sistem tetap menghasilkan 1 clip (tidak crash) — perilaku ini harus dipertahankan

---

## Expected Behavior

### Preservation Requirements

**Perilaku yang tidak boleh berubah:**
- Export clip tanpa subtitle (`export_subtitles=False`) harus tetap menghasilkan video tanpa subtitle
- Smart reframe (face tracking via OpenCV) harus tetap berjalan dengan benar dan menghasilkan dynamic crop 9:16
- Jalur fallback Center Crop harus tetap membakar subtitle ke video menggunakan FFmpeg dengan benar
- Output video harus tetap valid: encoding libx264, audio AAC, format vertikal 1080×1920
- Jika jumlah segmen transkrip yang tersedia kurang dari target, sistem harus tetap menghasilkan clip sebanyak yang tersedia (tidak crash)

**Scope:**
Semua input yang TIDAK memenuhi kondisi bug (subtitle dinonaktifkan, atau konfigurasi sudah benar) harus sepenuhnya tidak terpengaruh oleh fix ini. Ini mencakup:
- Semua operasi export tanpa subtitle
- Semua operasi smart reframe (perubahan hanya pada nilai style string, bukan logika tracking)
- Semua operasi concat clip
- Semua operasi transcribe dan download

**Catatan:** Perilaku yang diharapkan setelah fix (FontSize < 18, MarginV > 120, clip ≤ 2) didefinisikan secara formal di bagian Correctness Properties di bawah.

---

## Hypothesized Root Cause

Berdasarkan analisis kode sumber, penyebab root cause adalah:

1. **Nilai hardcode tanpa konstanta terpusat**: String `force_style` di `export.py` (baris subtitle burn) dan `video_effects.py` (baris subtitle burn dalam single-pass FFmpeg) masing-masing mendefinisikan `FontSize=20` dan `MarginV=120` secara independen. Tidak ada konstanta atau konfigurasi terpusat untuk nilai-nilai ini, sehingga perubahan harus dilakukan di dua tempat.

2. **Default config tidak diperbarui sesuai kebutuhan**: `clip_count_target` dan `clip_min_count` di `app/config.py` di-set ke `3` sebagai default, yang merupakan nilai lama sebelum kebutuhan berubah menjadi maksimal 2 clip.

3. **Tidak ada parameter subtitle style di Settings**: Kelas `Settings` tidak memiliki field untuk `subtitle_font_size` atau `subtitle_margin_v`, sehingga nilai-nilai ini tidak bisa dikontrol via environment variable dan harus diubah langsung di kode.

---

## Correctness Properties

Property 1: Bug Condition - Subtitle Font Size

_For any_ konfigurasi export di mana `export_subtitles=True` dan `FontSize` yang digunakan ≥ 18, fungsi export yang sudah diperbaiki SHALL menghasilkan video dengan subtitle yang menggunakan `FontSize` < 18 (target: 11–14) sehingga teks terbaca proporsional tanpa mendominasi layar.

**Validates: Requirements 2.1**

Property 2: Bug Condition - Subtitle Margin Vertical

_For any_ konfigurasi export di mana `export_subtitles=True` dan `MarginV` yang digunakan ≤ 120, fungsi export yang sudah diperbaiki SHALL menghasilkan video dengan subtitle yang menggunakan `MarginV` > 120 (target: 60–80 dalam konteks ASS style, atau nilai yang menempatkan subtitle di area aman bawah layar) sehingga subtitle tidak menutupi konten utama.

**Validates: Requirements 2.2**

Property 3: Bug Condition - Clip Count

_For any_ konfigurasi pipeline di mana `clip_count_target` ≥ 3 atau `clip_min_count` ≥ 3, fungsi `find_best_clips` yang sudah diperbaiki SHALL mengembalikan maksimal 2 clip (`len(result) <= 2`).

**Validates: Requirements 2.3**

Property 4: Preservation - Non-Subtitle dan Non-Count Behavior

_For any_ input di mana TIDAK ada kondisi bug yang terpenuhi (subtitle dinonaktifkan, atau konfigurasi sudah benar), fungsi-fungsi yang diperbaiki SHALL menghasilkan output yang identik dengan fungsi asli, mempertahankan semua perilaku export, smart reframe, fallback crop, encoding, dan penanganan segmen kurang dari target.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

---

## Fix Implementation

### Changes Required

Asumsi root cause analysis benar, perubahan yang diperlukan adalah:

**File 1**: `app/config.py`

**Perubahan**:
1. **Ubah default `clip_count_target`**: dari `3` menjadi `2`
2. **Ubah default `clip_min_count`**: dari `3` menjadi `1`

```python
# Sebelum:
clip_count_target: int = 3
clip_min_count: int = 3

# Sesudah:
clip_count_target: int = 2
clip_min_count: int = 1
```

---

**File 2**: `app/pipeline/export.py`

**Fungsi**: `export_clip` (bagian burn subtitle, sekitar baris `style = (...)`)

**Perubahan**:
3. **Ubah `FontSize`**: dari `20` menjadi `13`
4. **Ubah `MarginV`**: dari `120` menjadi `60`

```python
# Sebelum:
style = (
    "Alignment=2,FontName=Impact,FontSize=20,"
    "PrimaryColour=&H00FFFF,Outline=3,Shadow=0,"
    "MarginV=120"
)

# Sesudah:
style = (
    "Alignment=2,FontName=Impact,FontSize=13,"
    "PrimaryColour=&H00FFFF,Outline=3,Shadow=0,"
    "MarginV=60"
)
```

---

**File 3**: `tools/video_effects.py`

**Fungsi**: `track_face_and_reframe` (bagian subtitle style dalam single-pass FFmpeg)

**Perubahan**:
5. **Ubah `FontSize`**: dari `20` menjadi `13`
6. **Ubah `MarginV`**: dari `120` menjadi `60`

```python
# Sebelum:
style = (
    "Alignment=2,FontName=Impact,FontSize=20,"
    "PrimaryColour=&H00FFFF,Outline=3,Shadow=0,"
    "MarginV=120"
)

# Sesudah:
style = (
    "Alignment=2,FontName=Impact,FontSize=13,"
    "PrimaryColour=&H00FFFF,Outline=3,Shadow=0,"
    "MarginV=60"
)
```

**Catatan**: Nilai `FontSize=13` dan `MarginV=60` dipilih sebagai titik tengah dari rentang yang disebutkan di requirements (FontSize 11–14, MarginV 60–80). Nilai ini dapat disesuaikan lebih lanjut berdasarkan hasil visual testing.

---

## Testing Strategy

### Validation Approach

Strategi testing mengikuti dua fase: pertama, verifikasi bahwa nilai konfigurasi yang baru sudah benar (fix checking); kedua, verifikasi bahwa perilaku yang tidak terkait bug tidak berubah (preservation checking).

Karena bug ini adalah perubahan nilai konfigurasi (bukan logika), exploratory testing difokuskan pada verifikasi nilai yang terbaca oleh sistem, bukan pada reproduksi crash atau error.

### Exploratory Bug Condition Checking

**Goal**: Konfirmasi bahwa nilai lama (FontSize=20, MarginV=120, clip_count=3) memang ada di kode sebelum fix, dan verifikasi bahwa nilai baru sudah teraplikasi dengan benar setelah fix.

**Test Plan**: Baca nilai konfigurasi dari `settings` dan nilai hardcode dari string `style` di `export.py` dan `video_effects.py`. Jalankan pada kode SEBELUM fix untuk mengkonfirmasi bug condition.

**Test Cases**:
1. **Config Clip Count Test**: Baca `settings.clip_count_target` dan `settings.clip_min_count` — akan mengembalikan `3` pada kode unfixed
2. **Export Style FontSize Test**: Parse string `style` di `export_clip` — akan mengandung `FontSize=20` pada kode unfixed
3. **Export Style MarginV Test**: Parse string `style` di `export_clip` — akan mengandung `MarginV=120` pada kode unfixed
4. **Video Effects Style Test**: Parse string `style` di `track_face_and_reframe` — akan mengandung `FontSize=20` dan `MarginV=120` pada kode unfixed

**Expected Counterexamples**:
- `settings.clip_count_target` mengembalikan `3` (bukan ≤ 2)
- String style mengandung `FontSize=20` (bukan < 18)
- String style mengandung `MarginV=120` (bukan > 120)

### Fix Checking

**Goal**: Verifikasi bahwa setelah fix, semua kondisi bug tidak lagi terpenuhi.

**Pseudocode:**
```
FOR ALL X WHERE isBugCondition_SubtitleSize(X) DO
  result ← exportClip'(X)
  ASSERT result.subtitle_font_size < 18
END FOR

FOR ALL X WHERE isBugCondition_SubtitlePosition(X) DO
  result ← exportClip'(X)
  ASSERT result.subtitle_margin_v > 120
END FOR

FOR ALL X WHERE isBugCondition_ClipCount(X) DO
  result ← findBestClips'(X)
  ASSERT len(result) <= 2
END FOR
```

### Preservation Checking

**Goal**: Verifikasi bahwa untuk semua input di mana kondisi bug TIDAK terpenuhi, fungsi yang diperbaiki menghasilkan output yang sama dengan fungsi asli.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition_SubtitleSize(X)
             AND NOT isBugCondition_SubtitlePosition(X)
             AND NOT isBugCondition_ClipCount(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

**Testing Approach**: Property-based testing direkomendasikan untuk preservation checking karena:
- Menghasilkan banyak test case secara otomatis di seluruh domain input
- Menangkap edge case yang mungkin terlewat oleh unit test manual
- Memberikan jaminan kuat bahwa perilaku tidak berubah untuk semua input non-buggy

**Test Plan**: Observasi perilaku pada kode UNFIXED untuk input non-bug, lalu tulis property-based test yang memverifikasi perilaku ini tetap sama setelah fix.

**Test Cases**:
1. **No-Subtitle Export Preservation**: Verifikasi bahwa export dengan `export_subtitles=False` menghasilkan video tanpa subtitle sebelum dan sesudah fix
2. **Clip Count Below Target Preservation**: Verifikasi bahwa jika hanya ada 1 segmen yang memenuhi syarat, sistem tetap menghasilkan 1 clip (tidak crash)
3. **Encoding Preservation**: Verifikasi bahwa output video tetap menggunakan libx264, AAC, dan resolusi 1080×1920
4. **Smart Reframe Logic Preservation**: Verifikasi bahwa logika face tracking tidak terpengaruh oleh perubahan nilai style string

### Unit Tests

- Test bahwa `settings.clip_count_target` bernilai `2` setelah fix
- Test bahwa `settings.clip_min_count` bernilai `1` setelah fix
- Test bahwa string `style` di `export_clip` mengandung `FontSize=13` dan `MarginV=60`
- Test bahwa string `style` di `track_face_and_reframe` mengandung `FontSize=13` dan `MarginV=60`
- Test bahwa `find_best_clips` dengan segmen yang cukup mengembalikan maksimal 2 clip
- Test bahwa `find_best_clips` dengan 1 segmen mengembalikan 1 clip (tidak crash)

### Property-Based Tests

- Generate berbagai konfigurasi `PipelineConfig` dengan `clip_count_target` ≥ 3 dan verifikasi `find_best_clips` selalu mengembalikan ≤ 2 clip
- Generate berbagai jumlah segmen transkrip (1 hingga 10) dan verifikasi `find_best_clips` tidak pernah mengembalikan lebih dari `clip_count_target` clip
- Generate berbagai konfigurasi export dengan `export_subtitles=False` dan verifikasi output path tidak mengandung subtitle artifacts

### Integration Tests

- Test full pipeline: download → transcribe → analyze → export dengan konfigurasi baru, verifikasi menghasilkan ≤ 2 clip
- Test export clip dengan subtitle aktif, verifikasi file SRT di-generate dan di-burn dengan benar
- Test export clip tanpa subtitle, verifikasi tidak ada file SRT sementara yang tertinggal
- Test smart reframe path dengan subtitle, verifikasi single-pass FFmpeg berhasil dengan style baru
