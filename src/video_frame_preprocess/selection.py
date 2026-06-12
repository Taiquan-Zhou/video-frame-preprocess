"""Frame candidate selection policies."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .models import FrameCandidate, QualityThresholds
from .quality import passes_quality, quality_score


def choose_frame_candidates(
    candidates: Sequence[FrameCandidate],
    *,
    thresholds: QualityThresholds,
    min_gap: int,
) -> list[FrameCandidate]:
    """Filter candidates by quality and minimum source-frame distance."""
    selected: list[FrameCandidate] = []
    last_selected_index: int | None = None
    min_gap = max(1, int(min_gap))

    for candidate in candidates:
        if not passes_quality(candidate, thresholds):
            continue
        if last_selected_index is not None and candidate.index - last_selected_index < min_gap:
            continue
        selected.append(candidate)
        last_selected_index = candidate.index

    return selected


def choose_quality_filter_candidates(
    candidates: Sequence[FrameCandidate],
    *,
    thresholds: QualityThresholds,
    min_gap: int,
) -> list[FrameCandidate]:
    """Keep all usable frames and only drop frames that fail hard quality gates."""
    return choose_frame_candidates(candidates, thresholds=thresholds, min_gap=min_gap)


def _enforce_max_drop_ratio(
    candidates: Sequence[FrameCandidate],
    selected: list[FrameCandidate],
    *,
    thresholds: QualityThresholds,
    max_drop_ratio: float,
) -> list[FrameCandidate]:
    if not candidates:
        return selected
    max_drop_ratio = min(max(float(max_drop_ratio), 0.0), 1.0)
    min_keep = int(np.ceil(len(candidates) * (1.0 - max_drop_ratio)))
    if len(selected) >= min_keep:
        return selected

    selected_indices = {candidate.index for candidate in selected}
    rejected = [candidate for candidate in candidates if candidate.index not in selected_indices]
    rejected.sort(key=lambda candidate: quality_score(candidate, thresholds), reverse=True)
    restored = selected + rejected[: max(0, min_keep - len(selected))]
    return sorted(restored, key=lambda candidate: candidate.index)


def _enforce_max_consecutive_drops(
    candidates: Sequence[FrameCandidate],
    selected: list[FrameCandidate],
    *,
    thresholds: QualityThresholds,
    max_consecutive_drops: int,
) -> list[FrameCandidate]:
    max_consecutive_drops = max(0, int(max_consecutive_drops))
    if max_consecutive_drops <= 0 or not candidates:
        return selected

    selected_indices = {candidate.index for candidate in selected}
    restored: list[FrameCandidate] = []
    run: list[FrameCandidate] = []

    def flush_run() -> None:
        nonlocal run
        if len(run) > max_consecutive_drops:
            needed = len(run) - max_consecutive_drops
            run.sort(key=lambda candidate: quality_score(candidate, thresholds), reverse=True)
            restored.extend(run[:needed])
        run = []

    for candidate in candidates:
        if candidate.index in selected_indices:
            flush_run()
            continue
        run.append(candidate)
    flush_run()

    if not restored:
        return selected
    merged = selected + restored
    dedup = {candidate.index: candidate for candidate in merged}
    return [dedup[index] for index in sorted(dedup)]


def choose_quality_filter_candidates_safe(
    candidates: Sequence[FrameCandidate],
    *,
    thresholds: QualityThresholds,
    min_gap: int,
    max_drop_ratio: float,
    max_consecutive_drops: int,
) -> list[FrameCandidate]:
    """Conservative quality filter for reconstruction input."""
    selected = choose_quality_filter_candidates(candidates, thresholds=thresholds, min_gap=min_gap)
    selected = _enforce_max_drop_ratio(
        candidates,
        selected,
        thresholds=thresholds,
        max_drop_ratio=max_drop_ratio,
    )
    return _enforce_max_consecutive_drops(
        candidates,
        selected,
        thresholds=thresholds,
        max_consecutive_drops=max_consecutive_drops,
    )


def choose_best_frame_candidates(
    candidates: Sequence[FrameCandidate],
    *,
    thresholds: QualityThresholds,
    target_fps: float,
    min_gap: int,
    fill_missing_buckets: bool = True,
) -> list[FrameCandidate]:
    """Pick the best-quality frame in each target-FPS time bucket."""
    if target_fps <= 0:
        return choose_frame_candidates(candidates, thresholds=thresholds, min_gap=min_gap)

    best_passing_by_bucket: dict[int, FrameCandidate] = {}
    best_passing_score_by_bucket: dict[int, float] = {}
    best_any_by_bucket: dict[int, FrameCandidate] = {}
    best_any_score_by_bucket: dict[int, float] = {}
    for candidate in candidates:
        bucket = int(candidate.timestamp_sec * target_fps)
        score = quality_score(candidate, thresholds)
        if bucket not in best_any_by_bucket or score > best_any_score_by_bucket[bucket]:
            best_any_by_bucket[bucket] = candidate
            best_any_score_by_bucket[bucket] = score
        if not passes_quality(candidate, thresholds):
            continue
        if bucket not in best_passing_by_bucket or score > best_passing_score_by_bucket[bucket]:
            best_passing_by_bucket[bucket] = candidate
            best_passing_score_by_bucket[bucket] = score

    selected: list[FrameCandidate] = []
    min_gap = max(1, int(min_gap))
    all_buckets = sorted(best_any_by_bucket)
    bucket_to_pick: dict[int, FrameCandidate] = {}
    for bucket in all_buckets:
        if bucket in best_passing_by_bucket:
            bucket_to_pick[bucket] = best_passing_by_bucket[bucket]
        elif fill_missing_buckets:
            bucket_to_pick[bucket] = best_any_by_bucket[bucket]

    for candidate in sorted(bucket_to_pick.values(), key=lambda item: item.index):
        if not selected:
            selected.append(candidate)
            continue
        if candidate.index - selected[-1].index >= min_gap:
            selected.append(candidate)
            continue
        if quality_score(candidate, thresholds) > quality_score(selected[-1], thresholds):
            selected[-1] = candidate
    return selected
