#!/usr/bin/env python3
"""Validate video-frame-preprocess output artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

FRAME_EXTENSIONS = {".jpg", ".jpeg", ".png"}
REQUIRED_FILES = ("run_manifest.json", "frame_report.csv", "selected_frames.txt", "summary.json")


@dataclass(frozen=True)
class HealthResult:
    frame_dir: str
    status: str
    frame_count: int
    selected_count: int
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _frame_paths(frame_dir: Path) -> list[Path]:
    return sorted(path for path in frame_dir.iterdir() if path.is_file() and path.suffix.lower() in FRAME_EXTENSIONS)


def _load_json(path: Path, errors: list[str]) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"cannot read JSON {path.name}: {exc}")
        return {}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _selected_frame_paths(selected_frames_path: Path, errors: list[str]) -> list[tuple[Path, str | None]]:
    try:
        lines = selected_frames_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        errors.append(f"cannot read selected_frames.txt: {exc}")
        return []

    if not lines:
        errors.append("selected_frames.txt is empty")
        return []
    header = lines[0].split("\t")
    if header not in (
        ["output_index", "source_index", "timestamp_sec", "path"],
        ["output_index", "source_index", "timestamp_sec", "path", "sha256"],
    ):
        errors.append("selected_frames.txt header is invalid")
        return []

    paths: list[tuple[Path, str | None]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        parts = line.split("\t")
        if len(parts) != len(header):
            errors.append(f"selected_frames.txt line {line_number} has {len(parts)} columns")
            continue
        path_text = parts[3]
        if not path_text:
            errors.append(f"selected_frames.txt line {line_number} has empty path")
            continue
        path = Path(path_text)
        if not path.is_absolute():
            candidates = [
                Path.cwd() / path,
                selected_frames_path.parent / path,
                selected_frames_path.parent / path.name,
            ]
            path = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])
        sha256 = parts[4] if len(header) == 5 and parts[4] else None
        paths.append((path, sha256))
    return paths


def check_frame_dir(frame_dir: Path) -> HealthResult:
    errors: list[str] = []
    warnings: list[str] = []
    frame_dir = frame_dir.resolve()

    if not frame_dir.is_dir():
        return HealthResult(
            frame_dir=frame_dir.as_posix(),
            status="error",
            frame_count=0,
            selected_count=0,
            errors=[f"frame_dir does not exist: {frame_dir}"],
            warnings=[],
        )

    for name in REQUIRED_FILES:
        if not (frame_dir / name).is_file():
            errors.append(f"missing required file: {name}")

    frames = _frame_paths(frame_dir)
    manifest = _load_json(frame_dir / "run_manifest.json", errors) if (frame_dir / "run_manifest.json").is_file() else {}
    summary = _load_json(frame_dir / "summary.json", errors) if (frame_dir / "summary.json").is_file() else {}

    selected_paths = (
        _selected_frame_paths(frame_dir / "selected_frames.txt", errors)
        if (frame_dir / "selected_frames.txt").is_file()
        else []
    )
    for selected_path, expected_sha256 in selected_paths:
        if not selected_path.is_file():
            errors.append(f"selected frame path does not exist: {selected_path}")
            continue
        if expected_sha256 is not None:
            actual_sha256 = _file_sha256(selected_path)
            if actual_sha256 != expected_sha256:
                errors.append(f"sha256 mismatch: {selected_path}")

    selected_count = len(selected_paths)
    if selected_count and len(frames) != selected_count:
        errors.append(f"frame file count {len(frames)} does not match selected count {selected_count}")

    manifest_selected = manifest.get("selection", {}).get("selected_frames")
    if manifest_selected is not None and int(manifest_selected) != selected_count:
        errors.append(f"manifest selected_frames {manifest_selected} does not match selected count {selected_count}")

    summary_selected = summary.get("selected_frames")
    if summary_selected is not None and int(summary_selected) != selected_count:
        errors.append(f"summary selected_frames {summary_selected} does not match selected count {selected_count}")

    if any(path.name.startswith(("audit", "preview")) for path in frames):
        warnings.append("unexpected preview/audit-like image name found in frame directory")

    return HealthResult(
        frame_dir=frame_dir.as_posix(),
        status="error" if errors else "ok",
        frame_count=len(frames),
        selected_count=selected_count,
        errors=errors,
        warnings=warnings,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate video-frame-preprocess output artifacts.")
    parser.add_argument("frame_dir", type=Path, help="Frame output directory containing run_manifest.json")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = check_frame_dir(args.frame_dir)
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(f"status: {result.status}")
        print(f"frame_dir: {result.frame_dir}")
        print(f"frames: {result.frame_count}")
        print(f"selected: {result.selected_count}")
        for warning in result.warnings:
            print(f"warning: {warning}")
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
