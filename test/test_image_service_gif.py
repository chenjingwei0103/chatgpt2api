from __future__ import annotations

import unittest
from unittest import mock

from fastapi.responses import Response

from services.image_service import get_image_download_response, get_image_response


class GifResponseTests(unittest.TestCase):
    def test_remote_gif_response_uses_gif_media_type(self):
        storage = mock.Mock()
        storage.has_local.return_value = False
        storage.get_bytes.return_value = b"GIF89a"
        storage.content_type.return_value = "image/gif"
        with mock.patch("services.image_service.image_storage_service", storage):
            response = get_image_response("2026/11/05/sample.gif")
            download = get_image_download_response("2026/11/05/sample.gif")

        self.assertIsInstance(response, Response)
        self.assertEqual(response.media_type, "image/gif")
        self.assertIsInstance(download, Response)
        self.assertEqual(download.media_type, "image/gif")


if __name__ == "__main__":
    unittest.main()
