"""Run with: python -m unittest discover -s tests -v (worker dependencies required)."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np


class ImageValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Keep task dispatch and the expensive OCR model out of these HTTP tests.
        celery_module = Mock()
        celery_module.Celery.return_value.task.return_value = lambda fn: fn
        driver_module = Mock()
        spec = importlib.util.spec_from_file_location("worker_under_test", Path(__file__).resolve().parents[1] / "worker.py")
        cls.worker = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"celery": celery_module, "pero_ocr_driver": driver_module}), patch.dict(os.environ, {
            "CELERY_BROKER_URL": "memory://", "CELERY_RESULT_BACKEND": "cache+memory://",
            "PERO_CONFIG_DIR": "/models/test",
        }):
            spec.loader.exec_module(cls.worker)
        ok, encoded = cv2.imencode(".png", np.zeros((4, 6, 3), dtype=np.uint8))
        assert ok
        cls.image_bytes = encoded.tobytes()

    def request(self, content_type, body=None, status=200):
        headers = {} if content_type is None else {"Content-Type": content_type}
        response = Mock(status_code=status, headers=headers, content=self.image_bytes if body is None else body)
        engine = Mock()
        engine.detect_and_recognize.return_value = [[]]
        with patch.object(self.worker.requests, "get", return_value=response) as get, patch.object(self.worker, "PERO_driver", return_value=engine) as driver:
            result = self.worker.run_ocr("https://example.test/image", [])
            get.assert_called_once_with("https://example.test/image", timeout=10.0)
        return result, driver, engine

    def test_supported_media_types(self):
        for media_type in self.worker.VALID_IMAGE_TYPES:
            for header in (media_type, media_type + "; charset=UTF-8", "  " + media_type.upper() + "  ; charset=UTF-8", " " + media_type.upper() + " "):
                with self.subTest(header=header):
                    result, driver, engine = self.request(header)
                    self.assertNotIn("error", result)
                    driver.assert_called_once()
                    image, boxes = engine.detect_and_recognize.call_args[0]
                    self.assertEqual(image.shape, (4, 6, 3))
                    self.assertEqual(boxes, [(0, 0, 6, 4)])

    def test_missing_and_unsupported_types(self):
        for header in (None, "", "text/html", "text/html; charset=UTF-8", "image/tiff", "image/webp-invalid"):
            with self.subTest(header=header), self.assertLogs(self.worker.logger, level="WARNING") as logs:
                result, driver, _ = self.request(header)
                self.assertIn("valid image", result["error"])
                driver.assert_not_called()
                self.assertIn("HTTP status=200", logs.output[0])
                self.assertIn("Content-Type=", logs.output[0])

    def test_allowed_header_does_not_bypass_decoding(self):
        with self.assertLogs(self.worker.logger, level="WARNING"):
            result, driver, _ = self.request("image/webp; charset=UTF-8", b"not an image")
        self.assertEqual(result, {"error": "Cannot open image."})
        driver.assert_not_called()

    def test_download_failure_diagnostics(self):
        with self.assertLogs(self.worker.logger, level="WARNING") as logs:
            result, driver, _ = self.request("text/html", status=403)
        self.assertEqual(result, {"error": "Cannot download image."})
        driver.assert_not_called()
        self.assertIn("HTTP status=403, Content-Type='text/html'", logs.output[0])


if __name__ == "__main__":
    unittest.main()
