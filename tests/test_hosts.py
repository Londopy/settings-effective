"""Tests for the host line of effective.py: which agent the report ran under, and the
reminder that another host's own config is a different merge.

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from test_effective import Base  # noqa: E402
import effective  # noqa: E402

KEEP = ("HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "PATH", "SYSTEMROOT", "TEMP", "TMP", "ProgramFiles")


def env_only(extra: dict) -> dict:
    return {**{k: v for k, v in os.environ.items() if k in KEEP}, **extra}


class Hosts(Base):
    def test_claude_host_line(self):
        self.user({"model": "opus"})
        with mock.patch.dict(os.environ, env_only({"CLAUDECODE": "1"}), clear=True):
            self.assertEqual(effective.detect_host(), ("claude", "CLAUDECODE"))
            code, out = self.run_main()
        self.assertIn("host            claude   (CLAUDECODE set) reading Claude Code's settings", out)
        self.assertNotIn("different merge", out)

    def test_codex_host_names_its_own_config(self):
        self.user({"model": "opus"})
        with mock.patch.dict(os.environ, env_only({"CODEX_SANDBOX": "seatbelt"}), clear=True):
            code, out = self.run_main()
            rep = self.report()
        self.assertIn("host            codex", out)
        self.assertIn("~/.codex/config.toml", out)
        self.assertIn("different merge", out)
        self.assertEqual(rep["host"], "codex")
        # the subject did not change: Claude Code's user layer is still what gets resolved
        self.assertTrue(any(e["key"] == "model" and e["value"] == "opus" for e in rep["entries"]))

    def test_no_marker_omits_the_line(self):
        with mock.patch.dict(os.environ, env_only({}), clear=True):
            self.assertEqual(effective.detect_host(), (None, None))
            code, out = self.run_main()
            rep = self.report()
        self.assertNotIn("host ", out.splitlines()[1] if len(out.splitlines()) > 1 else "")
        self.assertEqual(rep["host"], "")


if __name__ == "__main__":
    unittest.main()
