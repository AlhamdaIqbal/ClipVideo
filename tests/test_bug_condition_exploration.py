"""
Bug Condition Exploration Tests — Task 1
=========================================
Tujuan: Konfirmasi bahwa bug MEMANG ADA pada kode yang belum diperbaiki.

Test-test ini mengkodekan PERILAKU YANG DIHARAPKAN (setelah fix).
Pada kode UNFIXED, test-test ini HARUS GAGAL — kegagalan membuktikan bug ada.
Setelah fix diimplementasikan (Task 3), test-test ini akan LULUS.

**Validates: Requirements 1.1, 1.2, 1.3**
"""

import ast
import inspect
import re
import textwrap

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Helper: ekstrak string `style` dari source code fungsi
# ---------------------------------------------------------------------------

def _get_export_clip_style_string() -> str:
    """
    Baca source code `export_clip` dari app/pipeline/export.py dan
    ekstrak nilai string `style` yang digunakan untuk subtitle burn.
    """
    from app.pipeline import export as export_module
    source = inspect.getsource(export_module)
    # Cari pola: style = ( ... "MarginV=..." )
    match = re.search(
        r'style\s*=\s*\(\s*"([^"]+)"\s*"([^"]+)"\s*"([^"]+)"\s*\)',
        source
    )
    if match:
        return match.group(1) + match.group(2) + match.group(3)
    # Fallback: cari style = "..." single-line
    match2 = re.search(r'style\s*=\s*"([^"]+)"', source)
    if match2:
        return match2.group(1)
    raise AssertionError("Tidak dapat menemukan string `style` di export_clip")


def _get_video_effects_style_string() -> str:
    """
    Baca source code `track_face_and_reframe` dari tools/video_effects.py dan
    ekstrak nilai string `style` yang digunakan untuk subtitle burn.
    """
    from tools import video_effects as ve_module
    source = inspect.getsource(ve_module)
    # Cari pola: style = ( ... "MarginV=..." )
    match = re.search(
        r'style\s*=\s*\(\s*"([^"]+)"\s*"([^"]+)"\s*"([^"]+)"\s*\)',
        source
    )
    if match:
        return match.group(1) + match.group(2) + match.group(3)
    match2 = re.search(r'style\s*=\s*"([^"]+)"', source)
    if match2:
        return match2.group(1)
    raise AssertionError("Tidak dapat menemukan string `style` di track_face_and_reframe")


# ---------------------------------------------------------------------------
# Test 1a — Config Clip Count
# ---------------------------------------------------------------------------

def test_1a_config_clip_count_target_is_not_buggy():
    """
    **Validates: Requirements 1.3**

    Bug Condition: isBugCondition_ClipCount(X) where X.clip_count_target >= 3

    Pada kode UNFIXED: settings.clip_count_target == 3 → test GAGAL (bug terkonfirmasi)
    Setelah fix: settings.clip_count_target == 2 → test LULUS

    Counterexample yang diharapkan pada kode unfixed:
      settings.clip_count_target = 3  (seharusnya < 3, target = 2)
    """
    from app.config import settings

    # Assert expected (fixed) behavior: clip_count_target harus < 3
    assert settings.clip_count_target < 3, (
        f"BUG TERKONFIRMASI: settings.clip_count_target = {settings.clip_count_target} "
        f"(>= 3). Nilai ini terlalu besar — seharusnya 2."
    )


def test_1a_config_clip_min_count_is_not_buggy():
    """
    **Validates: Requirements 1.3**

    Bug Condition: isBugCondition_ClipCount(X) where X.clip_min_count >= 3

    Pada kode UNFIXED: settings.clip_min_count == 3 → test GAGAL (bug terkonfirmasi)
    Setelah fix: settings.clip_min_count == 1 → test LULUS

    Counterexample yang diharapkan pada kode unfixed:
      settings.clip_min_count = 3  (seharusnya < 3, target = 1)
    """
    from app.config import settings

    # Assert expected (fixed) behavior: clip_min_count harus < 3
    assert settings.clip_min_count < 3, (
        f"BUG TERKONFIRMASI: settings.clip_min_count = {settings.clip_min_count} "
        f"(>= 3). Nilai ini terlalu besar — seharusnya 1."
    )


# ---------------------------------------------------------------------------
# Test 1b — Export Style FontSize
# ---------------------------------------------------------------------------

def test_1b_export_clip_style_fontsize_is_not_buggy():
    """
    **Validates: Requirements 1.1**

    Bug Condition: isBugCondition_SubtitleSize(X) where FontSize >= 18

    Pada kode UNFIXED: style mengandung "FontSize=20" → test GAGAL (bug terkonfirmasi)
    Setelah fix: style mengandung "FontSize=13" → test LULUS

    Counterexample yang diharapkan pada kode unfixed:
      style string mengandung "FontSize=20"  (seharusnya FontSize < 18, target = 13)
    """
    style = _get_export_clip_style_string()

    # Ekstrak nilai FontSize dari style string
    match = re.search(r'FontSize=(\d+)', style)
    assert match, f"Tidak dapat menemukan FontSize di style string: {style!r}"

    font_size = int(match.group(1))

    # Assert expected (fixed) behavior: FontSize harus < 18
    assert font_size < 18, (
        f"BUG TERKONFIRMASI: export_clip style mengandung FontSize={font_size} "
        f"(>= 18). Nilai ini terlalu besar — seharusnya < 18 (target: 13). "
        f"Style string: {style!r}"
    )


# ---------------------------------------------------------------------------
# Test 1c — Export Style MarginV
# ---------------------------------------------------------------------------

def test_1c_export_clip_style_marginv_is_not_buggy():
    """
    **Validates: Requirements 1.2**

    Bug Condition: isBugCondition_SubtitlePosition(X) where MarginV <= 120

    Pada kode UNFIXED: style mengandung "MarginV=120" → test GAGAL (bug terkonfirmasi)
    Setelah fix: style mengandung "MarginV=60" → test LULUS

    Counterexample yang diharapkan pada kode unfixed:
      style string mengandung "MarginV=120"  (seharusnya MarginV > 120, target = 60)

    CATATAN: Dalam konteks ASS force_style, MarginV=60 menempatkan subtitle lebih
    dekat ke bawah layar (area aman), sedangkan MarginV=120 menempatkannya lebih
    tinggi sehingga menutupi konten utama.
    """
    style = _get_export_clip_style_string()

    # Ekstrak nilai MarginV dari style string
    match = re.search(r'MarginV=(\d+)', style)
    assert match, f"Tidak dapat menemukan MarginV di style string: {style!r}"

    margin_v = int(match.group(1))

    # Assert expected (fixed) behavior: MarginV harus > 120
    # (Dalam ASS style, nilai lebih kecil = lebih dekat ke bawah = posisi lebih aman)
    # Bug: MarginV=120 terlalu tinggi dari bawah, menutupi konten
    # Fix: MarginV=60 lebih dekat ke bawah, tidak menutupi konten
    assert margin_v < 120, (
        f"BUG TERKONFIRMASI: export_clip style mengandung MarginV={margin_v} "
        f"(>= 120). Nilai ini menempatkan subtitle terlalu tinggi — "
        f"seharusnya < 120 (target: 60). "
        f"Style string: {style!r}"
    )


# ---------------------------------------------------------------------------
# Test 1d — Video Effects Style (FontSize dan MarginV)
# ---------------------------------------------------------------------------

def test_1d_video_effects_style_fontsize_is_not_buggy():
    """
    **Validates: Requirements 1.1**

    Bug Condition: isBugCondition_SubtitleSize pada jalur smart reframe

    Pada kode UNFIXED: track_face_and_reframe style mengandung "FontSize=20"
    → test GAGAL (bug terkonfirmasi)
    Setelah fix: style mengandung "FontSize=13" → test LULUS

    Counterexample yang diharapkan pada kode unfixed:
      style string di video_effects.py mengandung "FontSize=20"
    """
    style = _get_video_effects_style_string()

    # Ekstrak nilai FontSize dari style string
    match = re.search(r'FontSize=(\d+)', style)
    assert match, f"Tidak dapat menemukan FontSize di style string video_effects: {style!r}"

    font_size = int(match.group(1))

    # Assert expected (fixed) behavior: FontSize harus < 18
    assert font_size < 18, (
        f"BUG TERKONFIRMASI: track_face_and_reframe style mengandung FontSize={font_size} "
        f"(>= 18). Nilai ini terlalu besar — seharusnya < 18 (target: 13). "
        f"Style string: {style!r}"
    )


def test_1d_video_effects_style_marginv_is_not_buggy():
    """
    **Validates: Requirements 1.2**

    Bug Condition: isBugCondition_SubtitlePosition pada jalur smart reframe

    Pada kode UNFIXED: track_face_and_reframe style mengandung "MarginV=120"
    → test GAGAL (bug terkonfirmasi)
    Setelah fix: style mengandung "MarginV=60" → test LULUS

    Counterexample yang diharapkan pada kode unfixed:
      style string di video_effects.py mengandung "MarginV=120"
    """
    style = _get_video_effects_style_string()

    # Ekstrak nilai MarginV dari style string
    match = re.search(r'MarginV=(\d+)', style)
    assert match, f"Tidak dapat menemukan MarginV di style string video_effects: {style!r}"

    margin_v = int(match.group(1))

    # Assert expected (fixed) behavior: MarginV harus < 120
    assert margin_v < 120, (
        f"BUG TERKONFIRMASI: track_face_and_reframe style mengandung MarginV={margin_v} "
        f"(>= 120). Nilai ini menempatkan subtitle terlalu tinggi — "
        f"seharusnya < 120 (target: 60). "
        f"Style string: {style!r}"
    )


# ---------------------------------------------------------------------------
# Property-Based Test: Bug Condition Exploration (Hypothesis)
# ---------------------------------------------------------------------------

@given(
    clip_count_target=st.integers(min_value=3, max_value=10),
    clip_min_count=st.integers(min_value=3, max_value=10),
)
@h_settings(max_examples=3)
def test_1a_property_clip_count_bug_condition(clip_count_target, clip_min_count):
    """
    **Validates: Requirements 1.3**

    Property: Untuk semua konfigurasi di mana clip_count_target >= 3 ATAU
    clip_min_count >= 3, kondisi bug terpenuhi (isBugCondition_ClipCount = True).

    Ini adalah property exploration test — mengkonfirmasi bahwa nilai-nilai
    seperti yang ada di kode unfixed (3, 3) memenuhi kondisi bug.

    Pada kode UNFIXED: settings menggunakan nilai-nilai ini → bug ada.
    """
    # Konfirmasi bahwa kondisi ini memang merupakan bug condition
    is_bug_condition = clip_count_target >= 3 or clip_min_count >= 3
    assert is_bug_condition, (
        f"Seharusnya bug condition: clip_count_target={clip_count_target}, "
        f"clip_min_count={clip_min_count}"
    )

    # Konfirmasi bahwa settings saat ini (unfixed) memenuhi bug condition
    from app.config import settings
    current_is_bug = settings.clip_count_target >= 3 or settings.clip_min_count >= 3
    assert not current_is_bug, (
        f"BUG TERKONFIRMASI (property): settings saat ini memenuhi bug condition — "
        f"clip_count_target={settings.clip_count_target}, "
        f"clip_min_count={settings.clip_min_count}. "
        f"Seharusnya clip_count_target < 3 DAN clip_min_count < 3."
    )
