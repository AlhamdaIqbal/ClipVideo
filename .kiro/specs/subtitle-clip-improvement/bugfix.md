# Bugfix Requirements Document

## Introduction

Terdapat tiga masalah pada fitur clip video yang dihasilkan dari pipeline ClipVideo:

1. **Subtitle terlalu besar** — ukuran font subtitle (`FontSize=20`) terlalu besar untuk resolusi output 1080×1920, sehingga teks terlihat tidak proporsional dan mengganggu tampilan visual.
2. **Posisi subtitle mengganggu konten** — subtitle muncul di area tengah-bawah video dengan margin vertikal yang tidak cukup (`MarginV=120`), sehingga menutupi konten utama video alih-alih berada di area aman bagian bawah.
3. **Jumlah clip yang di-generate terlalu banyak** — sistem saat ini menghasilkan hingga 3 clip (`clip_count_target=3`, `clip_min_count=3`), padahal pengguna hanya membutuhkan maksimal 2 clip untuk mempercepat proses dan mendapatkan hasil yang lebih cepat.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN video clip di-export dengan subtitle diaktifkan THEN sistem menampilkan subtitle dengan ukuran font yang terlalu besar (FontSize=20) sehingga teks terlihat tidak proporsional pada resolusi 1080×1920

1.2 WHEN video clip di-export dengan subtitle diaktifkan THEN sistem menempatkan subtitle dengan MarginV=120 yang tidak cukup, sehingga subtitle muncul di area tengah video dan menutupi konten utama

1.3 WHEN pipeline analyze dan export dijalankan untuk menghasilkan clip THEN sistem menghasilkan hingga 3 clip (clip_count_target=3, clip_min_count=3), melebihi kebutuhan pengguna yang hanya memerlukan maksimal 2 clip

### Expected Behavior (Correct)

2.1 WHEN video clip di-export dengan subtitle diaktifkan THEN sistem SHALL menampilkan subtitle dengan ukuran font yang proporsional (FontSize lebih kecil, misalnya 11–14) sehingga teks terbaca dengan baik tanpa mendominasi layar

2.2 WHEN video clip di-export dengan subtitle diaktifkan THEN sistem SHALL menempatkan subtitle di area bawah video yang aman dengan MarginV yang cukup besar (misalnya 60–80) agar tidak menutupi konten utama video

2.3 WHEN pipeline analyze dan export dijalankan untuk menghasilkan clip THEN sistem SHALL membatasi jumlah clip yang di-generate maksimal 2 clip (clip_count_target=2, clip_min_count=1) sehingga proses lebih cepat dan output lebih ringkas

### Unchanged Behavior (Regression Prevention)

3.1 WHEN video clip di-export tanpa subtitle (export_subtitles=False) THEN sistem SHALL CONTINUE TO menghasilkan clip video tanpa subtitle seperti sebelumnya

3.2 WHEN smart reframe (face tracking) diaktifkan THEN sistem SHALL CONTINUE TO melakukan face tracking dan dynamic crop dengan benar, terlepas dari perubahan ukuran dan posisi subtitle

3.3 WHEN subtitle di-generate melalui jalur fallback Center Crop (non-smart-reframe) THEN sistem SHALL CONTINUE TO membakar subtitle ke video dengan benar menggunakan FFmpeg

3.4 WHEN pipeline export menghasilkan clip THEN sistem SHALL CONTINUE TO menghasilkan file video yang valid dengan encoding libx264, audio AAC, dan format vertikal 1080×1920

3.5 WHEN jumlah segmen transkrip yang tersedia kurang dari target clip THEN sistem SHALL CONTINUE TO menghasilkan clip sebanyak yang tersedia (tidak crash jika hanya ada 1 clip yang memenuhi syarat)

---

## Bug Condition Pseudocode

### Bug Condition Functions

```pascal
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

### Property: Fix Checking

```pascal
// Property: Fix Checking - Subtitle Size
FOR ALL X WHERE isBugCondition_SubtitleSize(X) DO
  result ← exportClip'(X)
  ASSERT result.subtitle_font_size < 18
END FOR

// Property: Fix Checking - Subtitle Position
FOR ALL X WHERE isBugCondition_SubtitlePosition(X) DO
  result ← exportClip'(X)
  ASSERT result.subtitle_margin_v > 120
END FOR

// Property: Fix Checking - Clip Count
FOR ALL X WHERE isBugCondition_ClipCount(X) DO
  result ← findBestClips'(X)
  ASSERT len(result) <= 2
END FOR
```

### Property: Preservation Checking

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition_SubtitleSize(X)
             AND NOT isBugCondition_SubtitlePosition(X)
             AND NOT isBugCondition_ClipCount(X) DO
  ASSERT F(X) = F'(X)
END FOR
```
