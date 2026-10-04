import base64
import json
import re
import unittest

from utils.pow import (
    CHROME_JS_HEAP_SIZE_LIMIT,
    _fnv1a_mix,
    build_legacy_requirements_token,
    build_proof_token,
)

_DATE_RE = re.compile(
    r"^[A-Z][a-z]{2} [A-Z][a-z]{2} \d{2} \d{4} \d{2}:\d{2}:\d{2} GMT[+-]\d{4} \(.+\)$"
)


def _decode_answer(token: str, prefix: str) -> tuple[str, list]:
    if not token.startswith(prefix) or not token.endswith("~S"):
        raise AssertionError("token prefix or suffix does not match the page SDK")
    encoded = token[len(prefix):-2]
    payload = json.loads(base64.b64decode(encoded))
    return encoded, payload


class PowTokenTests(unittest.TestCase):
    def test_fnv_matches_sdk_vectors(self) -> None:
        self.assertEqual(_fnv1a_mix("a"), "1a80b1b3")
        self.assertEqual(_fnv1a_mix("seedQUJD"), "2442b1b7")
        self.assertEqual(_fnv1a_mix("0"), "64f08f61")

    def test_requirements_token_matches_page_shape(self) -> None:
        token = build_legacy_requirements_token(
            "Mozilla/5.0 Chrome/154.0.0.0",
            data_build="prod-test",
        )
        encoded, payload = _decode_answer(token, "gAAAAAC")
        self.assertEqual(len(payload), 25)
        self.assertEqual(payload[6], "prod-test")
        self._assert_page_config(payload)
        self.assertEqual(
            base64.b64encode(
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).decode("ascii"),
            encoded,
        )

    def test_proof_token_satisfies_fnv_prefix(self) -> None:
        seed = "server-seed"
        difficulty = "000"
        token = build_proof_token(
            seed,
            difficulty,
            "Mozilla/5.0 Chrome/154.0.0.0",
            script_sources=["https://chatgpt.com/backend-api/sentinel/sdk.js"],
            data_build="prod-test",
        )
        encoded, payload = _decode_answer(token, "gAAAAAB")
        digest = _fnv1a_mix(seed + encoded)
        self.assertLessEqual(digest[: len(difficulty)], difficulty)
        self.assertEqual(len(payload), 25)
        self.assertIsInstance(payload[3], int)
        self.assertIsInstance(payload[9], int)
        self._assert_page_config(payload)

    def _assert_page_config(self, payload: list) -> None:
        self.assertEqual(payload[2], CHROME_JS_HEAP_SIZE_LIMIT)
        self.assertEqual(payload[7], "zh-CN")
        self.assertEqual(payload[8], "zh-CN,en,zh")
        self.assertEqual(payload[15], "")
        self.assertEqual(payload[18:], [0, 0, 0, 0, 0, 0, 0])
        navigator_key = payload[10]
        self.assertTrue(navigator_key == "doNotTrack" or "\u2212" in navigator_key)
        self.assertRegex(payload[1], _DATE_RE)
        self.assertNotIsInstance(payload[13], str)
        self.assertNotIsInstance(payload[17], str)


if __name__ == "__main__":
    unittest.main()

