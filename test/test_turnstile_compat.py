from __future__ import annotations

import unittest


class TurnstileCompatibilityTests(unittest.TestCase):
    def test_turnstile_module_imports_with_supported_py_mini_racer(self):
        from utils import turnstile

        self.assertTrue(turnstile.MiniRacer)


if __name__ == "__main__":
    unittest.main()
