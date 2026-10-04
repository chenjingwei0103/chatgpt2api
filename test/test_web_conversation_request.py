from __future__ import annotations

import unittest
from unittest import mock

from services.openai_backend_api import (
    DEFAULT_CLIENT_BUILD_NUMBER,
    DEFAULT_CLIENT_OBSERVATION,
    DEFAULT_CLIENT_VERSION,
    ChatRequirements,
    OpenAIBackendAPI,
)


class _Response:
    def __init__(self, payload: dict | None = None, lines: list[str] | None = None) -> None:
        self.status_code = 200
        self._payload = payload or {}
        self._lines = lines or ["data: [DONE]"]
        self.closed = False

    def json(self) -> dict:
        return self._payload

    def iter_lines(self):
        yield from self._lines

    def close(self) -> None:
        self.closed = True


class WebConversationRequestTest(unittest.TestCase):
    @staticmethod
    def _header(headers: dict, name: str) -> str:
        wanted = name.lower()
        for key, value in headers.items():
            if str(key).lower() == wanted:
                return str(value)
        raise AssertionError(f"missing header {name}")

    def _requirements(self) -> ChatRequirements:
        return ChatRequirements(token="req-token", proof_token="proof-token", turnstile_token="turn-token")

    def test_authenticated_text_matches_web_prepare_and_conversation(self) -> None:
        calls = []

        def fake_post(url, headers=None, json=None, timeout=None, stream=None):
            calls.append({"url": url, "headers": headers, "json": json, "stream": stream})
            if url.endswith("/prepare"):
                return _Response({"conduit_token": "conduit-1"})
            return _Response()

        with mock.patch("services.openai_backend_api.account_service.get_account", return_value={}):
            backend = OpenAIBackendAPI(access_token="test-token")
        backend._bootstrap = mock.Mock()
        backend._get_chat_requirements = mock.Mock(return_value=self._requirements())
        backend.session.post = fake_post

        list(backend.stream_conversation(messages=[{"role": "user", "content": "hello"}], model="auto"))

        self.assertEqual(
            [call["url"] for call in calls],
            [
                "https://chatgpt.com/backend-api/f/conversation/prepare",
                "https://chatgpt.com/backend-api/f/conversation",
            ],
        )
        prepare_headers = calls[0]["headers"]
        conversation_headers = calls[1]["headers"]
        lowered_prepare = {str(key).lower() for key in prepare_headers}
        lowered_conversation = {str(key).lower() for key in conversation_headers}
        self.assertEqual(self._header(prepare_headers, "X-Conduit-Token"), "no-token")
        self.assertNotIn("openai-sentinel-chat-requirements-token", lowered_prepare)
        self.assertEqual(self._header(conversation_headers, "X-Conduit-Token"), "conduit-1")
        self.assertEqual(self._header(conversation_headers, "OpenAI-Sentinel-Chat-Requirements-Token"), "req-token")
        self.assertEqual(self._header(conversation_headers, "OpenAI-Sentinel-Turnstile-Token"), "turn-token")
        self.assertEqual(self._header(conversation_headers, "X-OpenAI-Web-Frontend"), "core_web")
        self.assertEqual(self._header(conversation_headers, "X-OAI-Is-Client-Observation"), DEFAULT_CLIENT_OBSERVATION)
        self.assertEqual(self._header(conversation_headers, "X-OpenAI-Web-SSE-Compression"), "identity")
        self.assertEqual(self._header(conversation_headers, "OAI-Client-Version"), DEFAULT_CLIENT_VERSION)
        self.assertEqual(self._header(conversation_headers, "OAI-Client-Build-Number"), DEFAULT_CLIENT_BUILD_NUMBER)
        self.assertIn("Chrome/154.0.0.0", self._header(conversation_headers, "User-Agent"))
        self.assertNotIn("cache-control", lowered_conversation)
        self.assertNotIn("pragma", lowered_conversation)
        self.assertTrue(self._header(conversation_headers, "OAI-Echo-Logs"))
        self.assertTrue(self._header(conversation_headers, "OAI-Telemetry").startswith("[1,"))

        payload = calls[1]["json"]
        self.assertEqual(payload["client_prepare_state"], "success")
        self.assertEqual(payload["parent_message_id"], "client-created-root")
        self.assertEqual(payload["supported_encodings"], ["v1"])
        self.assertEqual(payload["model_response_contracts"][0]["id"], "photo_upload_action.v1")
        self.assertEqual(payload["messages"][0]["content"]["parts"], ["hello"])
        self.assertEqual(payload["messages"][0]["metadata"]["submission_mode"], "manual_send")
        self.assertNotIn("force_use_sse", payload)
        self.assertEqual(calls[0]["json"]["partial_query"]["id"], payload["messages"][0]["id"])
        self.assertEqual(calls[0]["json"]["client_prepare_state"], "success")

    def test_anonymous_text_stays_on_legacy_endpoint(self) -> None:
        calls = []

        def fake_post(url, headers=None, json=None, timeout=None, stream=None):
            calls.append({"url": url, "json": json})
            return _Response()

        backend = OpenAIBackendAPI()
        backend._bootstrap = mock.Mock()
        backend._get_chat_requirements = mock.Mock(return_value=self._requirements())
        backend.session.post = fake_post

        list(backend.stream_conversation(prompt="hello"))

        self.assertEqual(calls[0]["url"], "https://chatgpt.com/backend-anon/conversation")
        self.assertTrue(calls[0]["json"]["force_use_sse"])
        self.assertNotIn("client_prepare_state", calls[0]["json"])

    def test_image_generation_and_edit_use_web_envelope(self) -> None:
        with mock.patch("services.openai_backend_api.account_service.get_account", return_value={}):
            backend = OpenAIBackendAPI(access_token="test-token")

        generated = backend._image_conversation_payload("draw a circle", "gpt-image-2", [])
        self.assertEqual(generated["client_prepare_state"], "success")
        self.assertEqual(generated["system_hints"], ["picture_v2"])
        self.assertEqual(generated["messages"][0]["content"]["content_type"], "text")
        self.assertEqual(generated["messages"][0]["metadata"]["submission_mode"], "manual_send")
        self.assertEqual(generated["parent_message_id"], "client-created-root")

        edited = backend._image_conversation_payload("make it blue", "gpt-image-2", [{
            "file_id": "file-1",
            "width": 16,
            "height": 16,
            "file_size": 12,
            "mime_type": "image/png",
            "file_name": "image_1.png",
        }])
        content = edited["messages"][0]["content"]
        self.assertEqual(content["content_type"], "multimodal_text")
        self.assertEqual(content["parts"][0]["asset_pointer"], "file-service://file-1")
        self.assertEqual(edited["messages"][0]["metadata"]["attachments"][0]["id"], "file-1")
        self.assertEqual(edited["messages"][0]["metadata"]["system_hints"], ["picture_v2"])

        prepare = backend._prepare_payload(edited)
        self.assertEqual(prepare["system_hints"], ["picture_v2"])
        self.assertEqual(prepare["partial_query"]["content"]["content_type"], "multimodal_text")
        prepare_header_names = {str(key).lower() for key in backend._prepare_headers("/backend-api/f/conversation/prepare")}
        self.assertNotIn("openai-sentinel-chat-requirements-token", prepare_header_names)


if __name__ == "__main__":
    unittest.main()
