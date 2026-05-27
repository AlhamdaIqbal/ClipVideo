"""Unit tests for clip analysis (no YouTube/ffmpeg required)."""

from app.models.schemas import TranscriptSegment
from app.pipeline.analyze import find_best_clips


def _build_sample_transcript() -> list[TranscriptSegment]:
    texts = [
        "Pernahkah Anda merasa stuck meski sudah berusaha keras?",
        "Ini pertanyaan yang mengubah cara pandang banyak orang.",
        "Rahasia sebenarnya bukan motivasi sesaat melainkan sistem.",
        "Jadi kesimpulannya fokus pada kebiasaan kecil setiap hari.",
        "Bagaimana cara memulai kebiasaan yang benar?",
        "Mulailah dengan satu persen perbaikan, bukan perubahan drastis.",
        "Intinya konsistensi mengalahkan intensitas dalam jangka panjang.",
        "Mengapa kebanyakan orang gagal di bulan pertama?",
        "Karena mereka menargetkan hasil besar tanpa fondasi yang kuat.",
        "Oleh karena itu, bangun fondasi dulu sebelum mengejar hasil.",
    ]
    segments: list[TranscriptSegment] = []
    t = 0.0
    for txt in texts * 20:
        segments.append(TranscriptSegment(start=t, end=t + 7, text=txt))
        t += 8
    return segments


def test_find_at_least_three_clips():
    clips = find_best_clips(_build_sample_transcript())
    assert len(clips) >= 3


def test_clips_have_valid_duration():
    clips = find_best_clips(_build_sample_transcript())
    for c in clips:
        assert c.end_sec > c.start_sec
        duration = c.end_sec - c.start_sec
        assert 14 <= duration <= 105


def test_clips_can_be_shorter_than_two_minutes():
    clips = find_best_clips(_build_sample_transcript())
    assert any((c.end_sec - c.start_sec) < 90 for c in clips)


def test_clips_do_not_heavily_overlap():
    clips = find_best_clips(_build_sample_transcript())
    for i, a in enumerate(clips):
        for b in clips[i + 1 :]:
            overlap = max(0, min(a.end_sec, b.end_sec) - max(a.start_sec, b.start_sec))
            shorter = min(a.end_sec - a.start_sec, b.end_sec - b.start_sec)
            assert overlap / shorter <= 0.35 if shorter > 0 else True
