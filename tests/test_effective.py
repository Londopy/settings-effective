"""Tests for effective.py. Stdlib only: python -m unittest discover -s tests -v

Every test points the script at a throwaway --claude-home, --managed-dir, --claude-json
and project inside a temp dir, so nothing here can read a real settings file.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "skills" / "settings-effective" / "scripts"))
import effective  # noqa: E402


def write(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.managed = self.tmp / "managed"
        self.proj = self.tmp / "proj"
        self.claude_json = self.tmp / "claude.json"
        for d in (self.home, self.managed, self.proj / ".claude"):
            d.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    # layer helpers
    def user(self, d): write(self.home / "settings.json", d)
    def project(self, d): write(self.proj / ".claude" / "settings.json", d)
    def local(self, d): write(self.proj / ".claude" / "settings.local.json", d)
    def managed_file(self, d, name="managed-settings.json"): write(self.managed / name, d)
    def dropin(self, d, name): write(self.managed / "managed-settings.d" / name, d)
    def global_json(self, d): write(self.claude_json, d)

    def run_main(self, *args: str) -> tuple[int, str]:
        argv = ["--project", str(self.proj), "--claude-home", str(self.home),
                "--managed-dir", str(self.managed), "--claude-json", str(self.claude_json), *args]
        out = io.StringIO()
        with redirect_stdout(out):
            code = effective.main(argv)
        return code, out.getvalue()

    def report(self, *args: str) -> dict:
        code, out = self.run_main("--json", *args)
        return json.loads(out)

    def entry(self, rep: dict, key: str) -> dict | None:
        return next((e for e in rep["entries"] if e["key"] == key), None)

    def findings(self, rep: dict, key: str | None = None, severity: str | None = None) -> list[dict]:
        return [f for f in rep["findings"]
                if (key is None or f["key"] == key) and (severity is None or f["severity"] == severity)]


# --------------------------------------------------------------------------- precedence

class Precedence(Base):
    def test_user_only(self):
        self.user({"model": "opus"})
        e = self.entry(self.report(), "model")
        self.assertEqual((e["value"], e["source"]), ("opus", "user"))

    def test_project_beats_user(self):
        self.user({"model": "opus"})
        self.project({"model": "sonnet"})
        rep = self.report()
        e = self.entry(rep, "model")
        self.assertEqual((e["value"], e["source"]), ("sonnet", "project"))
        self.assertEqual(e["shadowed"], [{"layer": "user", "value": "opus"}])
        self.assertTrue(any("project wins" in f["message"] for f in self.findings(rep, "model", "info")))

    def test_local_beats_project(self):
        self.project({"model": "sonnet"})
        self.local({"model": "haiku"})
        self.assertEqual(self.entry(self.report(), "model")["source"], "local")

    def test_cli_beats_local(self):
        self.local({"model": "haiku"})
        rep = self.report("--settings", '{"model": "cli"}')
        self.assertEqual(self.entry(rep, "model")["source"], "cli")
        self.assertTrue(any(l["name"] == "cli" and l["present"] for l in rep["layers"]))

    def test_cli_file(self):
        f = self.tmp / "extra.json"
        write(f, {"model": "from-file"})
        self.assertEqual(self.entry(self.report("--settings", str(f)), "model")["value"], "from-file")

    def test_managed_beats_everything(self):
        self.user({"model": "u"}); self.project({"model": "p"}); self.local({"model": "l"})
        self.managed_file({"model": "m"})
        rep = self.report("--settings", '{"model": "c"}')
        self.assertEqual(self.entry(rep, "model")["source"], "managed")

    def test_managed_dropins_merge_alphabetically(self):
        self.managed_file({"model": "base", "permissions": {"deny": ["A"]}})
        self.dropin({"model": "ten", "permissions": {"deny": ["B"]}}, "10-a.json")
        self.dropin({"model": "twenty"}, "20-b.json")
        self.dropin({"model": "hidden"}, ".99-hidden.json")
        write(self.managed / "managed-settings.d" / "notes.txt", "{}")
        rep = self.report()
        self.assertEqual(self.entry(rep, "model")["value"], "twenty")
        self.assertEqual(self.entry(rep, "permissions.deny")["value"], ["A", "B"])
        m = next(l for l in rep["layers"] if l["name"] == "managed")
        self.assertIn("managed-settings.d/ (2)", m["path"])

    def test_same_value_is_not_shadowed(self):
        self.user({"model": "opus"}); self.project({"model": "opus"})
        rep = self.report()
        self.assertEqual(self.entry(rep, "model")["shadowed"], [])
        self.assertEqual(self.findings(rep, "model", "info"), [f for f in self.findings(rep, "model", "info") if "session start" in f["message"]])

    def test_absent_layers_listed(self):
        rep = self.report()
        names = {l["name"]: l for l in rep["layers"]}
        self.assertEqual(set(names), {"managed", "cli", "local", "project", "user", "global"})
        self.assertFalse(any(l["present"] for l in rep["layers"]))


# --------------------------------------------------------------------------- merging

class Merging(Base):
    def test_lists_union_with_sources(self):
        self.user({"permissions": {"allow": ["A", "B"]}})
        self.project({"permissions": {"allow": ["B", "C"]}})
        rep = self.report()
        e = self.entry(rep, "permissions.allow")
        self.assertEqual(e["value"], ["A", "B", "C"])
        self.assertEqual(e["sources"], ["user", "user", "project"])
        self.assertEqual(e["source"], "merged")
        self.assertTrue(any("already listed by user" in f["message"] for f in self.findings(rep, "permissions.allow", "info")))

    def test_objects_merge_per_leaf(self):
        self.user({"attribution": {"commit": "", "pr": ""}})
        self.project({"attribution": {"commit": "Co-Authored-By: X"}})
        rep = self.report()
        self.assertEqual(self.entry(rep, "attribution.commit")["source"], "project")
        self.assertEqual(self.entry(rep, "attribution.pr")["source"], "user")

    def test_whole_value_keys(self):
        self.user({"fallbackModel": ["a", "b"]})
        self.project({"fallbackModel": ["c"]})
        e = self.entry(self.report(), "fallbackModel")
        self.assertEqual((e["value"], e["source"]), (["c"], "project"))

    def test_atomic_objects(self):
        self.user({"statusLine": {"type": "command", "command": "a"}})
        self.project({"statusLine": {"type": "static", "text": "b"}})
        rep = self.report()
        self.assertIsNone(self.entry(rep, "statusLine.command"))
        self.assertEqual(self.entry(rep, "statusLine")["value"], {"type": "static", "text": "b"})

    def test_hooks_merge_and_itemize(self):
        self.user({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "u"}]}]}})
        self.project({"hooks": {"PreToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "p"}]}],
                                "Stop": [{"hooks": [{"type": "command", "command": "s"}]}]}})
        rep = self.report()
        self.assertEqual(self.entry(rep, "hooks.PreToolUse")["sources"], ["user", "project"])
        rows = effective.hook_rows([effective.Entry(**{k: e[k] for k in ("key", "value", "source", "sources", "shadowed")}) for e in rep["entries"]])
        self.assertEqual(rows, [("PreToolUse", "Bash", "u", "user"), ("PreToolUse", "Write", "p", "project"), ("Stop", "*", "s", "project")])
        code, out = self.run_main()
        self.assertIn("hooks     3 handlers", out)

    def test_disable_all_hooks_warns(self):
        self.user({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "s"}]}]}})
        self.project({"disableAllHooks": True})
        self.assertTrue(self.findings(self.report(), "hooks", "warn"))

    def test_env_per_var(self):
        self.user({"env": {"A": "1", "B": "2"}})
        self.project({"env": {"B": "3"}})
        rep = self.report()
        self.assertEqual(self.entry(rep, "env.A")["source"], "user")
        self.assertEqual((self.entry(rep, "env.B")["value"], self.entry(rep, "env.B")["source"]), ("3", "project"))

    def test_env_shell_export_noted(self):
        self.user({"env": {"SE_TEST_VAR": "settings"}})
        old = os.environ.get("SE_TEST_VAR")
        os.environ["SE_TEST_VAR"] = "shell"
        try:
            rep = self.report()
        finally:
            if old is None:
                del os.environ["SE_TEST_VAR"]
            else:
                os.environ["SE_TEST_VAR"] = old
        self.assertTrue(any("shell" in f["message"] for f in self.findings(rep, "env.SE_TEST_VAR", "info")))


# --------------------------------------------------------------------------- scope

class Scope(Base):
    def test_user_or_managed_key_ignored_in_project(self):
        self.user({"autoMode": {"allow": ["Bash(ls)"]}})
        self.project({"autoMode": {"allow": ["Bash(rm)"]}})
        rep = self.report()
        e = self.entry(rep, "autoMode.allow")
        self.assertEqual((e["value"], e["source"]), (["Bash(ls)"], "user"))
        f = self.findings(rep, "autoMode.allow", "error")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["layer"], "project")
        self.assertIn("User or managed", f[0]["message"])

    def test_managed_only_key_ignored_in_user(self):
        self.user({"requiredMinimumVersion": "9.9.9"})
        rep = self.report()
        self.assertIsNone(self.entry(rep, "requiredMinimumVersion"))
        self.assertTrue(self.findings(rep, "requiredMinimumVersion", "error"))

    def test_user_local_or_managed_allows_local_not_project(self):
        self.project({"skipDangerousModePermissionPrompt": True})
        self.local({"skipDangerousModePermissionPrompt": False})
        rep = self.report()
        self.assertEqual(self.entry(rep, "skipDangerousModePermissionPrompt")["source"], "local")
        self.assertEqual([f["layer"] for f in self.findings(rep, "skipDangerousModePermissionPrompt", "error")], ["project"])

    def test_global_config_keys_from_claude_json(self):
        self.global_json({"copyOnSelect": True, "diffTool": "code", "oauthAccount": {"x": 1}, "projects": {}})
        self.user({"copyOnSelect": False})
        rep = self.report()
        self.assertEqual(self.entry(rep, "copyOnSelect")["source"], "global")
        self.assertIsNone(self.entry(rep, "oauthAccount"))
        self.assertTrue(self.findings(rep, "copyOnSelect", "error"))

    def test_unknown_key_did_you_mean(self):
        self.project({"permisions": {"allow": ["A"]}, "skipWorkflowUsageWarning": True})
        rep = self.report()
        f = self.findings(rep, "permisions.allow", "warn")
        self.assertIn("did you mean 'permissions'", f[0]["message"])
        self.assertTrue(self.findings(rep, "skipWorkflowUsageWarning", "warn"))

    def test_invalid_json_file_skipped(self):
        self.user({"model": "opus"})
        self.local('{"model": "haiku"')
        rep = self.report()
        self.assertEqual(self.entry(rep, "model")["source"], "user")
        l = next(l for l in rep["layers"] if l["name"] == "local")
        self.assertFalse(l["present"])
        self.assertIn("invalid JSON", l["error"])
        self.assertTrue(any(f["layer"] == "local" and f["severity"] == "error" for f in rep["findings"]))

    def test_strict(self):
        self.user({"model": "opus"})
        self.assertEqual(self.run_main("--strict")[0], 0)
        self.project({"autoMode": {}})          # empty object is a leaf -> ignored-scope error
        self.assertEqual(self.run_main("--strict")[0], 1)


# --------------------------------------------------------------------------- exceptions

class SecurityExceptions(Base):
    def test_disable_connectors_true_from_project_beats_managed_false(self):
        self.managed_file({"disableClaudeAiConnectors": False})
        self.project({"disableClaudeAiConnectors": True})
        rep = self.report()
        e = self.entry(rep, "disableClaudeAiConnectors")
        self.assertEqual((e["value"], e["source"]), (True, "project"))
        notes = self.findings(rep, "disableClaudeAiConnectors")
        self.assertTrue(any("security key" in f["message"] for f in notes))
        self.assertFalse(any("managed wins" in f["message"] for f in notes))

    def test_max_effort_lowest_cap(self):
        self.managed_file({"maxEffortLevel": "max"})
        self.user({"maxEffortLevel": "high"})
        self.project({"maxEffortLevel": "low"})
        self.assertEqual(self.entry(self.report(), "maxEffortLevel")["value"], "low")

    def test_remote_control_false_only_from_project_or_local(self):
        self.managed_file({"remoteControlAtStartup": True})
        self.user({"remoteControlAtStartup": False})
        self.assertEqual(self.entry(self.report(), "remoteControlAtStartup")["value"], True)
        self.local({"remoteControlAtStartup": False})
        self.assertEqual(self.entry(self.report(), "remoteControlAtStartup")["value"], False)

    def test_use_auto_mode_during_plan_project_false_ignored(self):
        self.managed_file({"useAutoModeDuringPlan": True})
        self.project({"useAutoModeDuringPlan": False})
        rep = self.report()
        self.assertEqual(self.entry(rep, "useAutoModeDuringPlan")["value"], True)
        self.assertTrue(self.findings(rep, "useAutoModeDuringPlan", "error"))   # project may not set it at all
        self.local({"useAutoModeDuringPlan": False})
        self.assertEqual(self.entry(self.report(), "useAutoModeDuringPlan")["value"], False)

    def test_cross_session_inbound_stricter(self):
        self.user({"crossSessionInbound": "refuse"})
        self.project({"crossSessionInbound": "accept"})
        self.assertEqual(self.entry(self.report(), "crossSessionInbound")["value"], "accept")   # project wins normally
        self.managed_file({"crossSessionInbound": "accept"})
        self.project({"crossSessionInbound": "hold"})
        self.assertEqual(self.entry(self.report(), "crossSessionInbound")["value"], "hold")     # stricter honored


# --------------------------------------------------------------------------- permissions and trust

class Permissions(Base):
    def test_allow_vs_ask_and_deny(self):
        self.user({"permissions": {"allow": ["Bash(npm test)", "Read(.env)", "weird rule!"]}})
        self.project({"permissions": {"ask": ["Bash(npm test)"], "deny": ["Read(.env)"]}})
        rep = self.report()
        msgs = [f["message"] for f in self.findings(rep, "permissions.allow", "warn")]
        self.assertTrue(any("ask wins" in m for m in msgs))
        self.assertTrue(any("deny wins" in m for m in msgs))
        self.assertTrue(any("not Tool or Tool(spec) shaped" in m for m in msgs))

    def test_trust(self):
        self.project({"permissions": {"allow": ["A"]}, "env": {"X": "1"}})
        self.assertIsNone(self.report()["trusted"])
        self.global_json({"projects": {str(self.proj): {"hasTrustDialogAccepted": False, "allowedTools": ["Bash(ls)"]}}})
        rep = self.report()
        self.assertIs(rep["trusted"], False)
        self.assertEqual(rep["legacy_allowed_tools"], ["Bash(ls)"])
        self.assertTrue(any("trust" in f["message"] for f in self.findings(rep, "permissions.allow", "warn")))
        self.assertTrue(any("trust" in f["message"] for f in self.findings(rep, "env.X", "warn")))
        self.global_json({"projects": {str(self.proj).replace("\\", "/"): {"hasTrustDialogAccepted": True}}})
        rep = self.report()
        self.assertIs(rep["trusted"], True)
        self.assertFalse(self.findings(rep, "env.X", "warn"))

    def test_bypass_disabled(self):
        self.user({"permissions": {"defaultMode": "bypassPermissions"}})
        self.managed_file({"permissions": {"disableBypassPermissionsMode": "disable"}})
        self.assertTrue(self.findings(self.report(), "permissions.defaultMode", "warn"))


# --------------------------------------------------------------------------- cli

class Cli(Base):
    def test_project_walks_up_to_dot_claude(self):
        self.project({"model": "p"})
        sub = self.proj / "src" / "deep"
        sub.mkdir(parents=True)
        code, out = self.run_main("--project", str(sub), "--json")
        rep = json.loads(out)
        self.assertEqual(Path(rep["project"]), self.proj.resolve())
        self.assertEqual(self.entry(rep, "model")["value"], "p")

    def test_key_filter_itemizes(self):
        self.user({"permissions": {"allow": ["A", "B"]}, "model": "x"})
        code, out = self.run_main("--key", "permissions.allow")
        self.assertIn("A", out)
        self.assertNotIn("model", out.split("findings")[0].split("index")[1])

    def test_problems_only(self):
        self.user({"outputStyle": "x"})
        code, out = self.run_main("--problems-only")
        self.assertIn("findings", out)
        self.assertNotIn("outputStyle", out)

    def test_explain(self):
        code, out = self.run_main("--explain", "modelPicker")
        self.assertEqual(code, 0)
        self.assertIn("User or managed", out)
        self.assertIn("taken whole", out)
        code, out = self.run_main("--explain", "permisions.alow")
        self.assertEqual(code, 1)
        self.assertIn("permissions.allow", out)

    def test_index_is_populated(self):
        self.assertGreater(len(effective.SETTINGS_INDEX), 150)
        self.assertNotEqual(effective.INDEX_DATE, "unknown")
        self.assertEqual(effective.SETTINGS_INDEX["modelPicker"][0], "User or managed")
        self.assertEqual(effective.SETTINGS_INDEX["copyOnSelect"][0], "Global config")
        self.assertEqual({v[0] for v in effective.SETTINGS_INDEX.values()}, set(effective.SCOPE_LAYERS))

    def test_report_text(self):
        self.user({"model": "opus"})
        self.project({"autoMode": {"allow": ["x"]}})
        code, out = self.run_main()
        self.assertIn("user            loaded", out)
        self.assertIn("project         loaded", out)
        self.assertIn("trust           unknown", out)
        self.assertIn("IGNORED  autoMode.allow", out)
        self.assertIn("1 ignored", out)


if __name__ == "__main__":
    unittest.main()
