from __future__ import annotations

import unittest
from unittest import mock


class FakeResponse:
    status_code = 200
    text = '{"token":"turn-token"}'

    def json(self):
        return {"token": "turn-token"}


class SentinelSolverClientTests(unittest.TestCase):
    def test_solver_sends_only_challenge_material_and_returns_token(self):
        from services import sentinel_solver_client

        with (
            mock.patch.dict(
                sentinel_solver_client.config.data,
                {"sentinel_solver_url": "http://solver.internal:8080", "sentinel_solver_key": "solver-key"},
            ),
            mock.patch.object(
                sentinel_solver_client.requests,
                "post",
                return_value=FakeResponse(),
            ) as post,
        ):
            token = sentinel_solver_client.solve_turnstile(
                "dx-value",
                "p-value",
                {"prepare_token": "prepare-value", "turnstile": {"required": True}},
            )

        self.assertEqual(token, "turn-token")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer solver-key")
        self.assertEqual(kwargs["json"], {
            "dx": "dx-value",
            "p": "p-value",
            "requirements": {"prepare_token": "prepare-value", "turnstile": {"required": True}},
        })


if __name__ == "__main__":
    unittest.main()
