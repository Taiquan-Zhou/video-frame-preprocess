import tempfile
import unittest
from pathlib import Path

import cv2

from video_frame_preprocess.demo import create_demo_video


class DemoTest(unittest.TestCase):
    def test_create_demo_video_writes_readable_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "demo.mp4"

            create_demo_video(video_path, frame_count=8, fps=4.0, size=(96, 64))

            cap = cv2.VideoCapture(str(video_path))
            try:
                self.assertTrue(cap.isOpened())
                self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 8)
            finally:
                cap.release()


if __name__ == "__main__":
    unittest.main()
