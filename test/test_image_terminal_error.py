from __future__ import annotations

import unittest
from unittest import mock

from services.protocol.conversation import (
    ConversationRequest,
    ConversationState,
    image_message_error,
    stream_image_outputs,
    terminal_image_failure_message,
    tool_failure_text,
    update_conversation_state,
)


RATE_LIMIT = (
    "You're generating images too quickly. To ensure the best experience for everyone, "
    "we have rate limits in place. Please wait for an hour before generating more images."
)


class ImageTerminalErrorTest(unittest.TestCase):
    def test_rate_limit_text_is_terminal(self) -> None:
        self.assertEqual(terminal_image_failure_message("", RATE_LIMIT), RATE_LIMIT)
        self.assertEqual(
            terminal_image_failure_message('{"size":"1024x1024","n":1}'),
            "",
        )

    def test_tool_error_is_kept_on_the_conversation_state(self) -> None:
        state = ConversationState()
        event = {
            "message": {
                "author": {"role": "tool", "name": "t2uay3k.sj1i4kz"},
                "content": {"content_type": "text", "parts": [RATE_LIMIT]},
                "metadata": {"is_error": True},
            }
        }
        self.assertEqual(tool_failure_text(event), RATE_LIMIT)
        update_conversation_state(state, "{}", event)
        self.assertEqual(state.tool_error, RATE_LIMIT)

    def test_rate_limit_becomes_http_429(self) -> None:
        error = image_message_error(RATE_LIMIT, conversation_id="conversation")
        self.assertEqual(error.status_code, 429)
        self.assertEqual(error.code, "rate_limit_exceeded")

    def test_terminal_tool_error_does_not_poll(self) -> None:
        backend = mock.Mock()
        backend.resolve_conversation_image_urls.side_effect = AssertionError("should not poll")
        events = [{
            "type": "conversation.done",
            "text": "由于我这边发生了错误，我未能生成图片。",
            "conversation_id": "conversation",
            "file_ids": [],
            "sediment_ids": [],
            "blocked": False,
            "tool_invoked": False,
            "turn_use_case": "image gen",
            "tool_error": RATE_LIMIT,
        }]
        request = ConversationRequest(
            prompt="edit",
            model="gpt-image-2",
            images=["aW1hZ2U="],
        )
        with mock.patch("services.protocol.conversation.conversation_events", return_value=iter(events)):
            outputs = list(stream_image_outputs(backend, request))
        self.assertEqual([item.kind for item in outputs], ["message"])
        self.assertEqual(outputs[0].text, RATE_LIMIT)
        backend.resolve_conversation_image_urls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
