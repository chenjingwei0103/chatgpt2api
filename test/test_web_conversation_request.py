from __future__ import annotations

import unittest
from unittest import mock

import base64
import json

from services.openai_backend_api import (
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
        self.assertEqual(self._header(prepare_headers, "X-OpenAI-Web-Frontend"), "codex_webview")
        self.assertEqual(self._header(prepare_headers, "Originator"), "Codex Browser")
        self.assertEqual(self._header(prepare_headers, "X-OpenAI-Codex-Window-Type"), "browser")
        self.assertEqual(self._header(prepare_headers, "X-OAI-Mcp-Form-Version"), "2")
        self.assertNotIn("x-openai-target-path", lowered_prepare)
        self.assertNotIn("oai-client-version", lowered_prepare)
        self.assertEqual(self._header(conversation_headers, "X-OpenAI-Web-Frontend"), "codex_webview")
        self.assertEqual(self._header(conversation_headers, "Originator"), "Codex Browser")
        self.assertEqual(self._header(conversation_headers, "X-OpenAI-Web-SSE-Compression"), "gzip")
        self.assertNotIn("x-openai-target-path", lowered_conversation)
        self.assertNotIn("x-oai-is-client-observation", lowered_conversation)
        self.assertNotIn("oai-client-version", lowered_conversation)
        self.assertNotIn("oai-client-build-number", lowered_conversation)
        self.assertNotIn("oai-telemetry", lowered_conversation)
        self.assertIn("Chrome/155.0.0.0", self._header(conversation_headers, "User-Agent"))
        self.assertTrue(self._header(conversation_headers, "oai-did"))
        self.assertNotIn("cache-control", lowered_conversation)
        self.assertNotIn("pragma", lowered_conversation)
        self.assertTrue(self._header(conversation_headers, "OAI-Echo-Logs"))

        payload = calls[1]["json"]
        self.assertEqual(payload["client_prepare_state"], "success")
        self.assertEqual(payload["parent_message_id"], "client-created-root")
        self.assertEqual(payload["supported_encodings"], ["v1"])
        self.assertEqual(payload["model_response_contracts"][0]["id"], "photo_upload_action.v1")
        self.assertEqual(payload["messages"][0]["content"]["parts"], ["hello"])
        self.assertEqual(payload["messages"][0]["metadata"]["submission_mode"], "manual_send")
        self.assertNotIn("force_use_sse", payload)
        self.assertEqual(calls[0]["json"]["partial_query"]["id"], payload["messages"][0]["id"])
        self.assertEqual(calls[0]["json"]["client_prepare_state"], "sent")
        self.assertEqual(calls[0]["json"]["partial_query"]["author"], {"role": "user"})
        self.assertEqual(calls[0]["json"]["timezone"], "UTC")
        self.assertEqual(calls[0]["json"]["timezone_offset_min"], 0)

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
        self.assertNotIn("system_hints", generated)
        self.assertEqual(generated["timezone"], "UTC")
        self.assertEqual(generated["timezone_offset_min"], 0)
        self.assertEqual(generated["client_contextual_info"]["app_surface"], "codex_browser")
        self.assertEqual(generated["messages"][0]["content"]["content_type"], "text")
        self.assertEqual(generated["messages"][0]["metadata"], {})
        self.assertEqual(generated["parent_message_id"], "client-created-root")
        self.assertNotIn("local_function_names", generated)
        self.assertNotIn("browser_context", generated)
        self.assertNotIn("turn_attribution", generated)
        self.assertNotIn("genui_state_snapshots", generated)

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
        self.assertNotIn("system_hints", edited["messages"][0]["metadata"])
        self.assertNotIn("system_hints", edited)

        prepare = backend._prepare_payload(edited)
        self.assertNotIn("system_hints", prepare)
        self.assertEqual(prepare["client_prepare_state"], "sent")
        self.assertEqual(prepare["partial_query"]["author"], {"role": "user"})
        self.assertEqual(prepare["partial_query"]["content"]["content_type"], "multimodal_text")
        self.assertNotIn("local_function_names", prepare)
        prepare_header_names = {str(key).lower() for key in backend._prepare_headers("/backend-api/f/conversation/prepare")}
        self.assertNotIn("openai-sentinel-chat-requirements-token", prepare_header_names)

    def test_account_id_header_comes_from_access_token(self) -> None:
        payload = {"https://api.openai.com/auth": {"chatgpt_account_id": "acct-from-jwt"}}
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"e30.{body}.sig"
        with mock.patch("services.openai_backend_api.account_service.get_account", return_value={}):
            backend = OpenAIBackendAPI(access_token=token)
        headers = backend._conversation_headers(
            "/backend-api/f/conversation",
            self._requirements(),
            "conduit-1",
        )
        self.assertEqual(self._header(headers, "ChatGPT-Account-Id"), "acct-from-jwt")

    def test_account_id_header_falls_back_to_account_check(self) -> None:
        with mock.patch("services.openai_backend_api.account_service.get_account", return_value={}):
            backend = OpenAIBackendAPI(access_token="not-a-jwt")
        backend._get_default_account = mock.Mock(return_value={"account_id": "acct-from-check"})
        headers = backend._conversation_headers(
            "/backend-api/f/conversation",
            self._requirements(),
            "conduit-1",
        )
        self.assertEqual(self._header(headers, "ChatGPT-Account-Id"), "acct-from-check")
        backend._get_default_account.assert_called_once()


    def test_auto_model_not_found_retries_with_concrete_model(self) -> None:
        calls = []

        class _ErrorResponse(_Response):
            def __init__(self) -> None:
                super().__init__({"detail": "Model not found"})
                self.status_code = 404

            def iter_content(self, chunk_size=None):
                yield b'{"detail":"Model not found"}'

            def close(self) -> None:
                self.closed = True

        def fake_post(url, headers=None, json=None, timeout=None, stream=None):
            calls.append({"url": url, "json": json})
            if url.endswith("/prepare"):
                return _Response({"conduit_token": "conduit-2"})
            if (json or {}).get("model") == "auto":
                return _ErrorResponse()
            return _Response()

        with mock.patch("services.openai_backend_api.account_service.get_account", return_value={}):
            backend = OpenAIBackendAPI(access_token="test-token")
        backend._get_chat_requirements = mock.Mock(return_value=self._requirements())
        backend.session.post = fake_post
        payload = backend._image_conversation_payload("draw a circle", "gpt-image-2", [])
        payload["model"] = "auto"
        backend._start_image_generation("draw a circle", self._requirements(), "conduit-1", "gpt-image-2", [], payload)
        conversation_models = [
            call["json"].get("model")
            for call in calls
            if call["url"].endswith("/conversation")
        ]
        self.assertEqual(conversation_models, ["auto", "gpt-6-mini"])


if __name__ == "__main__":
    unittest.main()
