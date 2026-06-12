import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from video_frame_preprocess.health import check_frame_dir


def _write_image(path: Path) -> None:
    image = np.full((32, 48, 3), 120, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_valid_artifact(frame_dir: Path) -> None:
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_path = frame_dir / "frame_000000_src_000000.jpg"
    _write_image(frame_path)
    (frame_dir / "selected_frames.txt").write_text(
        "output_index\tsource_index\ttimestamp_sec\tpath\tsha256\n"
        f"0\t0\t0.000000\t{frame_path.as_posix()}\t{_sha256(frame_path)}\n",
        encoding="utf-8",
    )
    (frame_dir / "frame_report.csv").write_text("source_index,selected\n0,1\n", encoding="utf-8")
    (frame_dir / "summary.json").write_text(
        json.dumps(
            {
                "source_frames": 1,
                "analyzed_candidates": 1,
                "selected_frames": 1,
                "quality_dropped_candidates": 0,
                "sampling_skipped_frames": 0,
                "retention_ratio": 1.0,
                "source_retention_ratio": 1.0,
            }
        ),
        encoding="utf-8",
    )
    (frame_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "source": {"video": "input/sample.mp4", "fps": 5.0, "frames": 1},
                "outputs": {
                    "frame_dir": frame_dir.as_posix(),
                    "selected_frames": (frame_dir / "selected_frames.txt").as_posix(),
                    "report": (frame_dir / "frame_report.csv").as_posix(),
                    "summary": (frame_dir / "summary.json").as_posix(),
                    "filtered_video": None,
                },
                "selection": {
                    "source_frames": 1,
                    "analyzed_candidates": 1,
                    "selected_frames": 1,
                    "quality_dropped_candidates": 0,
                    "sampling_skipped_frames": 0,
                    "retention_ratio": 1.0,
                    "source_retention_ratio": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )


class HealthCheckTest(unittest.TestCase):
    def test_check_frame_dir_accepts_valid_preprocess_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_dir = Path(tmp) / "sample_clear_frames"
            _write_valid_artifact(frame_dir)

            result = check_frame_dir(frame_dir)

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.frame_count, 1)
            self.assertEqual(result.selected_count, 1)
            self.assertEqual(result.status, "ok")

    def test_check_frame_dir_reports_missing_selected_frame_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_dir = Path(tmp) / "sample_clear_frames"
            _write_valid_artifact(frame_dir)
            (frame_dir / "frame_000000_src_000000.jpg").unlink()

            result = check_frame_dir(frame_dir)

            self.assertFalse(result.ok)
            self.assertIn("selected frame path does not exist", "\n".join(result.errors))
            self.assertEqual(result.status, "error")

    def test_check_frame_dir_accepts_cli_relative_selected_frame_paths(self):
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            try:
                os.chdir(tmp_path)
                frame_dir = tmp_path / "outputs" / "sample_clear_frames"
                _write_valid_artifact(frame_dir)
                frame_path = Path("outputs") / "sample_clear_frames" / "frame_000000_src_000000.jpg"
                (frame_dir / "selected_frames.txt").write_text(
                    "output_index\tsource_index\ttimestamp_sec\tpath\tsha256\n"
                    f"0\t0\t0.000000\t{frame_path.as_posix()}\t{_sha256(frame_dir / frame_path.name)}\n",
                    encoding="utf-8",
                )

                result = check_frame_dir(frame_dir)

                self.assertTrue(result.ok, result.errors)
            finally:
                os.chdir(old_cwd)

    def test_check_frame_dir_reports_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_dir = Path(tmp) / "sample_clear_frames"
            _write_valid_artifact(frame_dir)
            (frame_dir / "frame_000000_src_000000.jpg").write_bytes(b"changed")

            result = check_frame_dir(frame_dir)

            self.assertFalse(result.ok)
            self.assertIn("sha256 mismatch", "\n".join(result.errors))


if __name__ == "__main__":
    unittest.main()
