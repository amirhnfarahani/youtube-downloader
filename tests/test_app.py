"""Regression tests for safety and output-file selection.

These tests intentionally do not contact YouTube or perform real downloads.
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ["YTDOWNLOADER_DB_PATH"] = str(
    Path(tempfile.gettempdir()) / f"youtube-downloader-tests-{os.getpid()}.sqlite3"
)

import app as downloader  # noqa: E402


class UrlValidationTests(unittest.TestCase):
    def test_accepts_http_and_https_urls(self):
        self.assertTrue(downloader.valid_media_url("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(downloader.valid_media_url("http://example.com/video"))

    def test_rejects_non_web_urls_and_malformed_values(self):
        for value in ("", "file:///C:/private.txt", "javascript:alert(1)", "not a URL", None):
            with self.subTest(value=value):
                self.assertFalse(downloader.valid_media_url(value))

    def test_info_endpoint_rejects_file_url_without_network_access(self):
        client = downloader.app.test_client()
        response = client.post("/api/info", json={"url": "file:///C:/private.txt"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])

    def test_download_endpoint_rejects_invalid_media_type_and_url(self):
        client = downloader.app.test_client()
        invalid_url = client.post("/api/download", json={"url": "file:///C:/private.txt"})
        self.assertEqual(invalid_url.status_code, 400)
        invalid_type = client.post(
            "/api/download",
            json={"url": "https://www.youtube.com/watch?v=abc", "media_type": "image"},
        )
        self.assertEqual(invalid_type.status_code, 400)


class OutputSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp_dir.name)
        self.job_id = "test-job"

    def tearDown(self):
        self.temp_dir.cleanup()

    def touch(self, extension, mtime):
        path = self.folder / f"{self.job_id}.{extension}"
        path.write_bytes(b"test")
        os.utime(path, (mtime, mtime))
        return path

    def test_video_thumbnail_is_not_selected_even_if_newer(self):
        video = self.touch("mp4", 10)
        self.touch("jpg", 20)
        selected = downloader.find_output_file(str(self.folder), self.job_id, "video")
        self.assertEqual(Path(selected), video)

    def test_audio_selection_prefers_media_not_thumbnail(self):
        audio = self.touch("mp3", 10)
        self.touch("webp", 30)
        selected = downloader.find_output_file(str(self.folder), self.job_id, "audio")
        self.assertEqual(Path(selected), audio)

    def test_partial_or_image_only_output_is_rejected(self):
        self.touch("jpg", 20)
        self.touch("part", 30)
        with self.assertRaises(RuntimeError):
            downloader.find_output_file(str(self.folder), self.job_id, "video")


if __name__ == "__main__":
    unittest.main()
