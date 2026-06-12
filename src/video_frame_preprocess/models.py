"""Shared data models for video frame preprocessing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class QualityMetrics:
    sharpness: float
    brightness: float
    contrast: float


@dataclass(frozen=True)
class QualityThresholds:
    min_sharpness: float
    min_brightness: float
    max_brightness: float
    min_contrast: float


@dataclass(frozen=True)
class FrameCandidate:
    index: int
    timestamp_sec: float
    quality: QualityMetrics


@dataclass(frozen=True)
class SelectedFrame:
    source_index: int
    output_index: int
    timestamp_sec: float
    quality: QualityMetrics
    output_path: Path | None
    sha256: str | None = None
