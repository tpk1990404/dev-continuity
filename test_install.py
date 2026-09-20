import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import os
import unittest

spec = importlib.util.spec_from_file_location("installer", Path(__file__).with_name("install.py"))
i = importlib.util.module_from_spec(spec)
spec.loader.exec_module(i)


class InstallTest(unittest.TestCase):
    def test_default_skill_only_external_directory_and_exact_rule_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            home = root / 'config'; home.mkdir()
            skill = root / 'agents/skills/dev-continuity'
            original = b'\xef\xbb\xbf# Existing\r\nKeep exact bytes.\r\n'
            (home / 'AGENTS.md').write_bytes(original)
            hooks = b'{"hooks":{}}\n'; (home / 'hooks.json').write_bytes(hooks)
            plan = i.make_plan(home, skill)
            self.assertTrue(all(Path(item['path']).is_relative_to(skill) for item in plan))
            plan_file = root / 'plan.json'; plan_file.write_text(json.dumps(plan),encoding='utf8')
            receipt = i.apply(home, plan_file, skill)
            self.assertEqual((home / 'AGENTS.md').read_bytes(), original)
            self.assertEqual((home / 'hooks.json').read_bytes(), hooks)
            i.restore(home, Path(receipt['receipt']), skill)
            plan = i.make_plan(home, skill, with_rules=True)
            rules = next(x for x in plan if x['path'] == str(home/'AGENTS.md'))
            self.assertTrue(rules['content'].encode('utf8').startswith(original))
            (home/'AGENTS.md').write_text('<!-- dev-continuity:end -->',encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'ambiguous'):
                i.make_plan(home, skill, with_rules=True)

    def test_merge_idempotence_rollback_and_drift_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            original = "# Existing policy\nDo not remove.\n\n## 记忆的应用\nOld guidance\n\n## Another rule\nKeep this.\n"
            (home / "AGENTS.md").write_text(original, encoding="utf-8")
            other_hook = {"type": "command", "command": "echo existing"}
            hooks = {"hooks": {"Stop": [{"hooks": [other_hook]}]}}
            (home / "hooks.json").write_text(json.dumps(hooks), encoding="utf-8")
            plan = i.make_plan(home, with_rules=True, with_hooks=True)
            plan_file = home / "plan.json"
            plan_file.write_text(json.dumps(plan), encoding="utf-8")
            result = i.apply(home, plan_file)
            self.assertEqual(i.make_plan(home, with_rules=True, with_hooks=True), [])
            raw_text = (home / "AGENTS.md").read_bytes()
            text = raw_text.decode("utf-8")
            self.assertIn("Do not remove.", text)
            self.assertIn("Keep this.", text)
            self.assertIn("Old guidance", text)
            current = json.loads((home / "hooks.json").read_text())
            self.assertIn(other_hook, current["hooks"]["Stop"][0]["hooks"])
            if os.name == "nt":
                handler = current["hooks"]["SessionStart"][0]["hooks"][0]
                payload = json.dumps({"hook_event_name": "SessionStart", "cwd": str(home), "session_id": "unregistered"}).encode()
                run = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", handler["commandWindows"]],
                                     input=payload, capture_output=True, timeout=5)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(json.loads(run.stdout), {})
            (home / "AGENTS.md").write_text(text + "user edit", encoding="utf-8")
            with self.assertRaises(ValueError):
                i.restore(home, Path(result["receipt"]))
            self.assertTrue((home / "skills/dev-continuity/SKILL.md").exists())
            (home / "AGENTS.md").write_bytes(raw_text)
            i.restore(home, Path(result["receipt"]))
            self.assertEqual((home / "AGENTS.md").read_text(encoding="utf-8"), original)
            self.assertEqual(json.loads((home / "hooks.json").read_text()), hooks)


if __name__ == "__main__":
    unittest.main()
