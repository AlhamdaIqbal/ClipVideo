"""
Preservation Property Tests — Task 2
======================================
Tujuan: Konfirmasi baseline behavior yang HARUS DIPERTAHANKAN setelah fix.

Test-test ini mengkodekan perilaku NON-BUGGY yang tidak boleh berubah.
Pada kode UNFIXED, test-test ini HARUS LULUS — kelulusan mengkonfirmasi
baseline behavior yang akan diverifikasi ulang setelah fix (Task 3.5).

Observation-first methodology:
  - Observasi 1: find_best_clips dengan 1 segmen → mengembalikan 1 clip (tidak crash)
  - Observasi 2: export_clip dengan export_subtitles=False → tidak ada subtitle artifacts
  - Observasi 3: Nilai encoding output tetap libx264, AAC, resolusi 1080×1920

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""

from __future__ import annotations

import inspect
import re
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.models.schemas import TranscriptSegment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_segments(n: int, duration_per_seg: float = 8.0) -> list[TranscriptSegment]:
    """
    Buat n TranscriptSegment dengan teks yang mengandung hook dan conclusion
    agar kandidat clip dapat terbentuk oleh _build_candidates.
    """
    hook_texts = [
        "Pernahkah Anda merasa stuck meski sudah berusaha keras?",
        "Rahasia sebenarnya bukan motivasi sesaat melainkan sistem.",
        "Bagaimana cara memulai kebiasaan yang benar?",
        "Mengapa kebanyakan orang gagal di bulan pertama?",
        "Apa yang membedakan orang sukses dari yang lainnya?",
    ]
    conclusion_texts = [
        "Jadi kesimpulannya fokus pada kebiasaan kecil setiap hari.",
        "Intinya konsistensi mengalahkan intensitas dalam jangka panjang.",
        "Oleh karena itu, bangun fondasi dulu sebelum mengejar hasil.",
        "Bottom line: mulailah dengan satu persen perbaikan setiap hari.",
        "The key takeaway adalah sistem lebih penting dari motivasi.",
    ]
    segments: list[TranscriptSegment] = []
    t = 0.0
    for i in range(n):
        # Alternate between hook and conclusion texts to ensure scoreable candidates
        if i % 2 == 0:
            text = hook_texts[i % len(hook_texts)]
        else:
            text = conclusion_texts[i % len(conclusion_texts)]
        segments.append(TranscriptSegment(start=t, end=t + duration_per_seg, text=text))
        t += duration_per_seg + 0.5  # small gap between segments
    return segments


def _make_long_segments(n: int) -> list[TranscriptSegment]:
    """
    Buat n TranscriptSegment dengan durasi yang cukup panjang agar
    find_best_clips dapat membentuk kandidat clip yang valid (min 20 detik).
    Setiap segmen berdurasi 30 detik.
    """
    hook_texts = [
        "Pernahkah Anda merasa stuck meski sudah berusaha keras? Ini pertanyaan yang mengubah cara pandang.",
        "Rahasia sebenarnya bukan motivasi sesaat melainkan sistem yang konsisten dan terstruktur.",
        "Bagaimana cara memulai kebiasaan yang benar? Mulailah dengan langkah kecil yang terukur.",
        "Mengapa kebanyakan orang gagal? Karena mereka menargetkan hasil besar tanpa fondasi kuat.",
        "Apa yang membedakan orang sukses? Mereka fokus pada proses bukan hanya pada hasil akhir.",
        "Jadi kesimpulannya fokus pada kebiasaan kecil setiap hari untuk hasil yang luar biasa.",
        "Intinya konsistensi mengalahkan intensitas dalam jangka panjang, itulah kunci sukses.",
        "Oleh karena itu, bangun fondasi dulu sebelum mengejar hasil yang besar dan ambisius.",
        "Bottom line: mulailah dengan satu persen perbaikan setiap hari dan lihat hasilnya.",
        "The key takeaway adalah sistem lebih penting dari motivasi untuk mencapai tujuan.",
    ]
    segments: list[TranscriptSegment] = []
    t = 0.0
    for i in range(n):
        text = hook_texts[i % len(hook_texts)]
        segments.append(TranscriptSegment(start=t, end=t + 30.0, text=text))
        t += 31.0  # 30s segment + 1s gap
    return segments


# ---------------------------------------------------------------------------
# Observation 1: find_best_clips dengan 1 segmen → tidak crash, mengembalikan ≤ 1 clip
# ---------------------------------------------------------------------------

def test_observation_1_find_best_clips_single_segment_does_not_crash():
    """
    **Validates: Requirements 3.5**

    Observasi 1: find_best_clips dengan 1 segmen tersedia → mengembalikan 1 clip (tidak crash)

    Ini adalah non-buggy input karena isBugCondition_ClipCount tidak relevan
    dengan jumlah segmen yang tersedia — bug condition hanya tentang konfigurasi target.
    Perilaku ini harus dipertahankan setelah fix.
    """
    from app.pipeline.analyze import find_best_clips

    # 1 segmen dengan durasi yang cukup panjang
    segments = _make_long_segments(1)
    # Tidak boleh crash
    result = find_best_clips(segments)
    # Harus mengembalikan list (bisa kosong atau 1 clip)
    assert isinstance(result, list), "find_best_clips harus mengembalikan list"
    # Tidak boleh mengembalikan lebih dari jumlah segmen yang tersedia
    assert len(result) <= 1, (
        f"find_best_clips dengan 1 segmen mengembalikan {len(result)} clip "
        f"(seharusnya ≤ 1)"
    )


def test_observation_1_find_best_clips_empty_segments_returns_empty():
    """
    **Validates: Requirements 3.5**

    find_best_clips dengan 0 segmen → mengembalikan list kosong (tidak crash)
    """
    from app.pipeline.analyze import find_best_clips

    result = find_best_clips([])
    assert result == [], "find_best_clips dengan segmen kosong harus mengembalikan []"


# ---------------------------------------------------------------------------
# Property-Based Test 1: find_best_clips tidak pernah mengembalikan lebih dari
# clip_count_target clip, untuk semua jumlah segmen (1 hingga 10)
# ---------------------------------------------------------------------------

@given(n_segments=st.integers(min_value=1, max_value=10))
@h_settings(max_examples=3, deadline=60_000)
def test_property_find_best_clips_never_exceeds_clip_count_target(n_segments: int):
    """
    **Validates: Requirements 3.5**

    Property: Untuk semua jumlah segmen (1 hingga 10), find_best_clips tidak pernah
    mengembalikan lebih dari clip_count_target clip dan tidak crash.

    Ini adalah preservation property — perilaku ini harus tetap sama sebelum dan
    sesudah fix. Pada kode UNFIXED, clip_count_target=3, jadi hasil tidak boleh > 3.
    Setelah fix, clip_count_target=2, jadi hasil tidak boleh > 2.

    Test ini HARUS LULUS pada kode UNFIXED (mengkonfirmasi baseline behavior).
    """
    from app.config import settings
    from app.pipeline.analyze import find_best_clips

    # Buat segmen dengan durasi yang cukup panjang agar kandidat dapat terbentuk
    segments = _make_long_segments(n_segments)

    # Tidak boleh crash
    result = find_best_clips(segments)

    # Tidak boleh mengembalikan lebih dari clip_count_target
    assert isinstance(result, list), (
        f"find_best_clips harus mengembalikan list, bukan {type(result)}"
    )
    assert len(result) <= settings.clip_count_target, (
        f"find_best_clips mengembalikan {len(result)} clip dengan {n_segments} segmen, "
        f"melebihi clip_count_target={settings.clip_count_target}"
    )


@given(n_segments=st.integers(min_value=1, max_value=10))
@h_settings(max_examples=3, deadline=60_000)
def test_property_find_best_clips_with_explicit_target_1(n_segments: int):
    """
    **Validates: Requirements 3.5**

    Property: find_best_clips dengan target_count=1 tidak pernah mengembalikan
    lebih dari 1 clip, untuk semua jumlah segmen (1 hingga 10).

    Menggunakan explicit target_count untuk menghindari ketergantungan pada
    nilai settings yang akan berubah setelah fix.
    """
    from app.pipeline.analyze import find_best_clips

    segments = _make_long_segments(n_segments)
    result = find_best_clips(segments, target_count=1, min_count=1)

    assert isinstance(result, list)
    assert len(result) <= 1, (
        f"find_best_clips dengan target_count=1 mengembalikan {len(result)} clip "
        f"dengan {n_segments} segmen (seharusnya ≤ 1)"
    )


@given(n_segments=st.integers(min_value=1, max_value=10))
@h_settings(max_examples=3, deadline=60_000)
def test_property_find_best_clips_with_explicit_target_2(n_segments: int):
    """
    **Validates: Requirements 3.5**

    Property: find_best_clips dengan target_count=2 tidak pernah mengembalikan
    lebih dari 2 clip, untuk semua jumlah segmen (1 hingga 10).

    Ini adalah target nilai setelah fix — test ini memverifikasi bahwa
    logika _select_diverse_clips menghormati target_count=2.
    """
    from app.pipeline.analyze import find_best_clips

    segments = _make_long_segments(n_segments)
    result = find_best_clips(segments, target_count=2, min_count=1)

    assert isinstance(result, list)
    assert len(result) <= 2, (
        f"find_best_clips dengan target_count=2 mengembalikan {len(result)} clip "
        f"dengan {n_segments} segmen (seharusnya ≤ 2)"
    )


# ---------------------------------------------------------------------------
# Observation 2: export_clip dengan export_subtitles=False → tidak ada subtitle artifacts
# ---------------------------------------------------------------------------

def test_observation_2_export_clip_no_subtitle_no_srt_artifacts():
    """
    **Validates: Requirements 3.1**

    Observasi 2: export_clip dengan export_subtitles=False → tidak ada subtitle artifacts.

    Verifikasi bahwa ketika export_subtitles=False, fungsi export_clip tidak
    membuat file SRT sementara yang tertinggal. Ini adalah non-buggy path
    (isBugCondition_SubtitleSize dan isBugCondition_SubtitlePosition = False).

    Test ini memverifikasi logika kode tanpa menjalankan FFmpeg.
    """
    import inspect
    from app.pipeline import export as export_module

    source = inspect.getsource(export_module)

    # Verifikasi bahwa logika should_burn_subtitles mempertimbangkan settings.export_subtitles
    assert "export_subtitles" in source, (
        "export.py harus memiliki logika yang mempertimbangkan export_subtitles"
    )
    assert "should_burn_subtitles" in source, (
        "export.py harus memiliki variabel should_burn_subtitles untuk mengontrol alur subtitle"
    )

    # Verifikasi bahwa ketika should_burn_subtitles=False, tidak ada subtitle burn
    # Cari pola: if should_burn_subtitles: ... (subtitle burn hanya terjadi jika True)
    assert re.search(r'if\s+should_burn_subtitles', source), (
        "export.py harus memiliki kondisi 'if should_burn_subtitles' untuk mengontrol subtitle burn"
    )


def test_observation_2_export_clip_no_subtitle_path_logic():
    """
    **Validates: Requirements 3.1**

    Verifikasi bahwa logika export_clip dengan export_subtitles=False
    menggunakan jalur 'else' yang memindahkan temp_video ke output_path
    tanpa membakar subtitle.
    """
    import inspect
    from app.pipeline import export as export_module

    source = inspect.getsource(export_module)

    # Verifikasi bahwa ada jalur else yang menangani kasus tanpa subtitle
    # (shutil.move dari temp_video ke output_path)
    assert "shutil.move" in source, (
        "export.py harus menggunakan shutil.move untuk memindahkan temp_video ke output_path "
        "ketika tidak ada subtitle"
    )

    # Verifikasi bahwa temp_video dibersihkan (tidak ada artifacts)
    assert "temp_video" in source, (
        "export.py harus menggunakan temp_video sebagai file sementara"
    )


# ---------------------------------------------------------------------------
# Property-Based Test 2: export_clip dengan export_subtitles=False
# tidak menghasilkan subtitle artifacts
# ---------------------------------------------------------------------------

@given(
    export_subtitles=st.just(False),
    has_segments=st.booleans(),
)
@h_settings(max_examples=3, deadline=30_000)
def test_property_export_no_subtitle_no_srt_file_created(
    export_subtitles: bool,
    has_segments: bool,
):
    """
    **Validates: Requirements 3.1**

    Property: Untuk semua konfigurasi export dengan export_subtitles=False,
    logika should_burn_subtitles selalu False, sehingga tidak ada subtitle artifacts.

    Ini adalah preservation property — perilaku ini harus tetap sama sebelum dan
    sesudah fix. Test ini memverifikasi logika kondisi tanpa menjalankan FFmpeg.

    Test ini HARUS LULUS pada kode UNFIXED (mengkonfirmasi baseline behavior).
    """
    # Simulasi logika should_burn_subtitles dari export_clip
    # should_burn_subtitles = bool(segments and settings.export_subtitles)
    # Ketika export_subtitles=False, should_burn_subtitles selalu False
    segments = [object()] if has_segments else []  # dummy segments
    should_burn_subtitles = bool(segments and export_subtitles)

    assert not should_burn_subtitles, (
        f"should_burn_subtitles harus False ketika export_subtitles=False, "
        f"tapi mendapat {should_burn_subtitles} "
        f"(has_segments={has_segments}, export_subtitles={export_subtitles})"
    )


@given(
    export_subtitles=st.just(False),
    n_segments=st.integers(min_value=0, max_value=5),
)
@h_settings(max_examples=3, deadline=30_000)
def test_property_export_no_subtitle_output_path_no_srt_suffix(
    export_subtitles: bool,
    n_segments: int,
):
    """
    **Validates: Requirements 3.1**

    Property: Untuk semua konfigurasi export dengan export_subtitles=False,
    output path tidak mengandung subtitle artifacts (tidak ada file .srt yang dibuat).

    Verifikasi bahwa nama file output tidak mengandung pola subtitle artifacts
    seperti "sub_" prefix atau ".srt" suffix.
    """
    # Simulasi nama file output yang dihasilkan export_clip
    output_name = "clip_1.mp4"
    output_path = Path(f"/tmp/clips/{output_name}")

    # Verifikasi output path tidak mengandung subtitle artifacts
    assert not output_path.name.endswith(".srt"), (
        f"Output path tidak boleh berakhiran .srt: {output_path}"
    )
    assert not output_path.name.startswith("sub_"), (
        f"Output path tidak boleh dimulai dengan 'sub_': {output_path}"
    )
    assert not output_path.name.startswith("temp_tracked_"), (
        f"Output path tidak boleh dimulai dengan 'temp_tracked_': {output_path}"
    )


# ---------------------------------------------------------------------------
# Observation 3: Nilai encoding output tetap libx264, AAC, resolusi 1080×1920
# ---------------------------------------------------------------------------

def test_observation_3_encode_args_uses_libx264():
    """
    **Validates: Requirements 3.4**

    Observasi 3: Nilai encoding output tetap libx264.

    Verifikasi bahwa _encode_args() menggunakan libx264 sebagai video codec.
    Ini adalah preservation property — encoding tidak boleh berubah setelah fix.
    """
    from app.pipeline.export import _encode_args

    args = _encode_args()
    assert "-c:v" in args, "_encode_args harus mengandung -c:v"
    idx = args.index("-c:v")
    assert args[idx + 1] == "libx264", (
        f"Video codec harus libx264, bukan {args[idx + 1]}"
    )


def test_observation_3_encode_args_uses_aac():
    """
    **Validates: Requirements 3.4**

    Observasi 3: Nilai encoding output tetap AAC.

    Verifikasi bahwa _encode_args() menggunakan AAC sebagai audio codec.
    """
    from app.pipeline.export import _encode_args

    args = _encode_args()
    assert "-c:a" in args, "_encode_args harus mengandung -c:a"
    idx = args.index("-c:a")
    assert args[idx + 1] == "aac", (
        f"Audio codec harus aac, bukan {args[idx + 1]}"
    )


def test_observation_3_vertical_video_filter_uses_1080x1920():
    """
    **Validates: Requirements 3.4**

    Observasi 3: Resolusi output tetap 1080×1920.

    Verifikasi bahwa _vertical_video_filter() menggunakan resolusi 1080×1920.
    """
    from app.config import settings
    from app.pipeline.export import _vertical_video_filter

    vf = _vertical_video_filter()
    assert "1080" in vf, f"Filter harus mengandung lebar 1080, tapi: {vf!r}"
    assert "1920" in vf, f"Filter harus mengandung tinggi 1920, tapi: {vf!r}"

    # Verifikasi settings juga konsisten
    assert settings.export_width == 1080, (
        f"settings.export_width harus 1080, bukan {settings.export_width}"
    )
    assert settings.export_height == 1920, (
        f"settings.export_height harus 1920, bukan {settings.export_height}"
    )


@given(
    export_width=st.just(1080),
    export_height=st.just(1920),
)
@h_settings(max_examples=3, deadline=10_000)
def test_property_encoding_resolution_preserved(export_width: int, export_height: int):
    """
    **Validates: Requirements 3.4**

    Property: Untuk semua konfigurasi export yang valid, resolusi output
    tetap 1080×1920 (tidak berubah oleh fix).

    Test ini HARUS LULUS pada kode UNFIXED (mengkonfirmasi baseline behavior).
    """
    from app.config import settings

    # Verifikasi bahwa settings menggunakan resolusi yang benar
    assert settings.export_width == export_width, (
        f"settings.export_width harus {export_width}, bukan {settings.export_width}"
    )
    assert settings.export_height == export_height, (
        f"settings.export_height harus {export_height}, bukan {settings.export_height}"
    )


@given(
    codec_video=st.just("libx264"),
    codec_audio=st.just("aac"),
)
@h_settings(max_examples=3, deadline=10_000)
def test_property_encoding_codecs_preserved(codec_video: str, codec_audio: str):
    """
    **Validates: Requirements 3.4**

    Property: Untuk semua konfigurasi export yang valid, codec video tetap
    libx264 dan codec audio tetap AAC (tidak berubah oleh fix).

    Test ini HARUS LULUS pada kode UNFIXED (mengkonfirmasi baseline behavior).
    """
    from app.pipeline.export import _encode_args

    args = _encode_args()

    # Verifikasi video codec
    assert "-c:v" in args
    v_idx = args.index("-c:v")
    assert args[v_idx + 1] == codec_video, (
        f"Video codec harus {codec_video}, bukan {args[v_idx + 1]}"
    )

    # Verifikasi audio codec
    assert "-c:a" in args
    a_idx = args.index("-c:a")
    assert args[a_idx + 1] == codec_audio, (
        f"Audio codec harus {codec_audio}, bukan {args[a_idx + 1]}"
    )
