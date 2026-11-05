from __future__ import annotations

import unittest

from services.openai_backend_api import OpenAIBackendAPI


class FakeResponse:
    status_code = 200

    def __init__(self, payload: bytes, content_type: str):
        self.content = payload
        self.headers = {"content-type": content_type}


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response

    def get(self, _url: str, timeout: int):
        assert timeout == 120
        return self.response


class ImageDownloadPartsTests(unittest.TestCase):
    def test_download_image_parts_preserves_gif_mime_type(self):
        backend = object.__new__(OpenAIBackendAPI)
        backend.session = FakeSession(FakeResponse(b"GIF89a", "image/gif; charset=binary"))

        self.assertEqual(
            backend.download_image_parts(["https://files.example.test/image.gif"]),
            [(b"GIF89a", "image/gif")],
        )


if __name__ == "__main__":
    unittest.main()
