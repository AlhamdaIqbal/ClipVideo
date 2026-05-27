from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.config import settings
from app.models.schemas import TranscriptSegment

# Hook signals (ID + EN)
QUESTION_WORDS = re.compile(
    r"\b(apa|mengapa|kenapa|bagaimana|siapa|kapan|dimana|berapa|"
    r"what|why|how|who|when|where|which|ever|pernahkah|tahukah)\b",
    re.I,
)
HOOK_KEYWORDS = re.compile(
    r"\b(rahasia|ternyata|jangan|salah|fakta|shocking|never|secret|"
    r"truth|mistake|warning|stop|hati-hati|bahaya|viral|insane|crazy)\b",
    re.I,
)
FILLER_OPENERS = re.compile(
    r"\b(halo\s+guys|hai\s+guys|jangan\s+lupa\s+subscribe|like\s+and\s+subscribe|"
    r"selamat\s+datang\s+kembali)\b",
    re.I,
)
CONCLUSION_PHRASES = re.compile(
    r"\b(jadi|kesimpulannya|intinya|akhirnya|oleh\s+karena\s+itu|"
    r"so\b|in\s+conclusion|that's\s+why|the\s+key|takeaway|bottom\s+line|"
    r"to\s+sum\s+up|pelajaran|kesimpulan)\b",
    re.I,
)
TRAILING_CONNECTORS = re.compile(r"\b(dan|but|tapi|atau|and|or)\s*$", re.I)


@dataclass
class CandidateClip:
    start_sec: float
    end_sec: float
    text: str
    hook_text: str
    conclusion_text: str
    topic: str
    hook_score: float
    conclusion_score: float
    interest_score: float
    total_score: float
    segment_indices: list[int]


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def find_best_clips(
    segments: list[TranscriptSegment],
    *,
    min_count: int | None = None,
    target_count: int | None = None,
) -> list[CandidateClip]:
    if not segments:
        return []

    min_count = min_count or settings.clip_min_count
    target_count = target_count or settings.clip_count_target

    candidates = _build_candidates(segments)
    if not candidates:
        return []

    _score_candidates(candidates, segments)
    selected = _select_diverse_clips(candidates, target_count, min_count)
    return selected


def _build_candidates(segments: list[TranscriptSegment]) -> list[CandidateClip]:
    min_len = settings.clip_min_seconds
    max_len = settings.clip_max_seconds
    step = settings.clip_window_step
    duration_step = max(5.0, settings.clip_duration_step)
    candidates: list[CandidateClip] = []

    if not segments:
        return candidates

    video_end = segments[-1].end
    t = segments[0].start
    window_lengths = _candidate_window_lengths(min_len, max_len, duration_step)
    seen_ranges: set[tuple[int, int]] = set()

    while t < video_end:
        for window_len in window_lengths:
            window_end = t + window_len
            indices = [
                i
                for i, seg in enumerate(segments)
                if seg.end > t and seg.start < window_end
            ]
            if not indices:
                continue

            start_sec = segments[indices[0]].start
            end_sec = segments[indices[-1]].end
            duration = end_sec - start_sec

            if duration < min_len * 0.8:
                continue

            if duration > max_len:
                end_sec = start_sec + max_len
                indices = [i for i in indices if segments[i].start < end_sec]
                if indices:
                    end_sec = segments[indices[-1]].end

            start_sec, end_sec, indices = _snap_to_natural_boundaries(
                segments, indices, start_sec, end_sec, min_len, max_len
            )
            duration = end_sec - start_sec
            if duration < min_len * 0.7 or duration > max_len * 1.15:
                continue

            range_key = (round(start_sec), round(end_sec))
            if range_key in seen_ranges:
                continue
            seen_ranges.add(range_key)

            texts = [segments[i].text for i in indices]
            full_text = " ".join(texts)
            hook_text = " ".join(texts[: min(3, len(texts))])
            conclusion_text = " ".join(texts[-min(3, len(texts)) :])
            topic = _derive_topic(texts)

            candidates.append(
                CandidateClip(
                    start_sec=start_sec,
                    end_sec=end_sec,
                    text=full_text,
                    hook_text=hook_text,
                    conclusion_text=conclusion_text,
                    topic=topic,
                    hook_score=0.0,
                    conclusion_score=0.0,
                    interest_score=0.0,
                    total_score=0.0,
                    segment_indices=indices,
                )
            )
        t += step

    return candidates


def _candidate_window_lengths(min_len: float, max_len: float, duration_step: float) -> list[float]:
    lengths: list[float] = []
    length = min_len
    while length <= max_len:
        lengths.append(length)
        length += duration_step
    if not lengths or lengths[-1] < max_len:
        lengths.append(max_len)
    return lengths


def _snap_to_natural_boundaries(
    segments: list[TranscriptSegment],
    indices: list[int],
    start_sec: float,
    end_sec: float,
    min_len: float,
    max_len: float,
) -> tuple[float, float, list[int]]:
    if len(indices) >= 2:
        gap_before = segments[indices[0]].start - (
            segments[indices[0] - 1].end if indices[0] > 0 else 0
        )
        if gap_before > 1.5 and (end_sec - segments[indices[0]].start) >= min_len:
            start_sec = segments[indices[0]].start

    if len(indices) >= 2:
        last_i = indices[-1]
        if last_i + 1 < len(segments):
            gap_after = segments[last_i + 1].start - segments[last_i].end
            if gap_after > 1.5 and (segments[last_i].end - start_sec) >= min_len:
                end_sec = segments[last_i].end

    duration = end_sec - start_sec
    if duration > max_len:
        end_sec = start_sec + max_len
        indices = [i for i in indices if segments[i].start <= end_sec]
        if indices:
            end_sec = segments[indices[-1]].end

    return start_sec, end_sec, indices


def _derive_topic(texts: list[str]) -> str:
    combined = " ".join(texts)
    words = re.findall(r"[a-zA-ZÀ-ÿ0-9]{4,}", combined.lower())
    stop = {
        "yang", "dengan", "untuk", "dari", "ini", "itu", "dan", "atau",
        "the", "that", "this", "with", "have", "akan", "juga", "saya",
        "kamu", "kita", "mereka", "ada", "bisa", "sudah", "very", "just",
    }
    freq: dict[str, int] = {}
    for w in words:
        if w not in stop:
            freq[w] = freq.get(w, 0) + 1
    top = sorted(freq, key=freq.get, reverse=True)[:4]
    if top:
        label = " ".join(w.capitalize() for w in top)
        return label[:80]
    snippet = texts[0][:80] if texts else "Clip"
    return snippet + ("..." if len(snippet) >= 80 else "")


def _score_hook(text: str) -> float:
    score = 0.0
    first = text[:200]
    if "?" in first:
        score += 0.35
    if QUESTION_WORDS.search(first):
        score += 0.25
    if HOOK_KEYWORDS.search(first):
        score += 0.25
    if re.search(r"\d+", first[:80]):
        score += 0.15
    words = first.split()
    if words and len(words) <= 15:
        score += 0.15
    if FILLER_OPENERS.search(first):
        score -= 0.4
    return max(0.0, min(1.0, score))


def _score_conclusion(text: str) -> float:
    score = 0.0
    tail = text[-250:]
    if CONCLUSION_PHRASES.search(tail):
        score += 0.45
    if tail.strip().endswith((".", "!", "?")):
        score += 0.25
    if TRAILING_CONNECTORS.search(tail):
        score -= 0.3
    if tail.rstrip().endswith("..."):
        score -= 0.25
    words = tail.split()
    if 5 <= len(words) <= 40:
        score += 0.15
    return max(0.0, min(1.0, score))


def _score_interest(candidate: CandidateClip, all_texts: list[str], durations: list[float]) -> float:
    duration = candidate.end_sec - candidate.start_sec
    ideal_min = settings.clip_ideal_min_seconds
    ideal_max = settings.clip_ideal_max_seconds
    length_score = 1.0
    if duration < ideal_min:
        length_score = duration / ideal_min
    elif duration > ideal_max:
        length_score = max(0.25, ideal_max / duration)

    try:
        vectorizer = TfidfVectorizer(max_features=500, stop_words="english")
        matrix = vectorizer.fit_transform(all_texts)
        idx = all_texts.index(candidate.text)
        row = matrix[idx].toarray().flatten()
        density = float(row.sum()) / max(1, (row > 0).sum())
        tfidf_score = min(1.0, density / 3.0)
    except Exception:
        tfidf_score = 0.5

    return min(1.0, 0.4 * length_score + 0.6 * tfidf_score)


def _score_candidates(candidates: list[CandidateClip], segments: list[TranscriptSegment]) -> None:
    all_texts = [c.text for c in candidates]
    for c in candidates:
        c.hook_score = _score_hook(c.hook_text)
        c.conclusion_score = _score_conclusion(c.conclusion_text)
        c.interest_score = _score_interest(c, all_texts, [])
        c.total_score = (
            0.35 * c.hook_score
            + 0.35 * c.conclusion_score
            + 0.30 * c.interest_score
        )


def _overlap_ratio(a: CandidateClip, b: CandidateClip) -> float:
    overlap_start = max(a.start_sec, b.start_sec)
    overlap_end = min(a.end_sec, b.end_sec)
    if overlap_end <= overlap_start:
        return 0.0
    overlap = overlap_end - overlap_start
    shorter = min(a.end_sec - a.start_sec, b.end_sec - b.start_sec)
    return overlap / shorter if shorter > 0 else 0.0


_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _embedding_model


def _select_diverse_clips(
    candidates: list[CandidateClip],
    target_count: int,
    min_count: int,
) -> list[CandidateClip]:
    min_hook = settings.min_hook_score
    min_conclusion = settings.min_conclusion_score

    filtered = [
        c
        for c in candidates
        if c.hook_score >= min_hook and c.conclusion_score >= min_conclusion
    ]
    pool = filtered if len(filtered) >= min_count else sorted(candidates, key=lambda x: -x.total_score)

    pool = sorted(pool, key=lambda c: -c.total_score)

    embeddings = _embed_texts([c.text for c in pool])
    selected: list[CandidateClip] = []
    selected_indices: list[int] = []
    threshold = settings.embedding_similarity_threshold

    for i, cand in enumerate(pool):
        if len(selected) >= target_count:
            break
        dominated = False
        for j in selected_indices:
            if _overlap_ratio(cand, pool[j]) > 0.2:
                dominated = True
                break
            if embeddings is not None:
                sim = float(np.dot(embeddings[i], embeddings[j]))
                if sim >= threshold:
                    dominated = True
                    break
        if not dominated:
            selected.append(cand)
            selected_indices.append(i)

    if len(selected) < min_count:
        for cand in pool:
            if cand in selected:
                continue
            if any(_overlap_ratio(cand, s) > 0.35 for s in selected):
                continue
            selected.append(cand)
            if len(selected) >= min_count:
                break

    selected.sort(key=lambda c: -c.total_score)
    return selected[:target_count]


def _embed_texts(texts: list[str]) -> np.ndarray | None:
    if len(texts) < 2:
        return None
    try:
        model = _get_embedding_model()
        emb = model.encode(texts, normalize_embeddings=True)
        return np.array(emb)
    except Exception:
        return None
