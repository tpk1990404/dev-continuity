"""Run with: python -m unittest discover -s PATH_TO_SCRIPTS -p test_continuity.py"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import continuity as c


class ContinuityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "a.txt").write_text("one", encoding="utf-8")
        self.note = {"goal": "recover the same goal", "acceptance": ["observable result"],
                     "batch": {"id": "fix-one", "scope": "repair the reported regression", "done_when": "reproduction passes and result is recorded"},
                     "progress": {"done": [], "active": "fix", "remaining": ["verify"]},
                     "decisions": [], "preserve": ["dirty work"], "operations": [], "evidence": [],
                     "next": ["verify"], "blockers": [], "files": ["a.txt"], "sources": []}
        (self.root / "request.txt").write_bytes(b"Preserve dirty work. Never repeat a paid operation.\n")
        self.note["records"] = [self.record("boundary", "Preserve dirty work; no repeated paid calls.")]

    def record(self, key, text, **kwargs):
        source = self.root / "request.txt"
        return {"id": key, "kind": "constraint", "text": text, "scope": "task",
                "basis": "user", "state": "confirmed", "critical": True,
                "sources": [c.make_anchor(source, 0, source.stat().st_size)], **kwargs}

    def review(self, owner, revision):
        check = c.verify(self.root, "task")
        return c.save(self.root, "task", owner, {"memory_review": {
            "basis_sha256": check["memory_basis_sha256"], "critical_ids": check["critical_ids"],
            "checked_sections": c.REVIEW_SECTIONS, "continuation": self.decision()}}, revision, patch=True)["revision"]

    def decision(self, decision="migrate", tools="available"):
        return {"decision": decision, "tools": tools, "reason": "Synthetic safe batch boundary",
                "next_check": "After the next material progress update or compaction", "at": c.now()}

    def saved(self):
        revision = c.save(self.root, "task", "old", self.note, "new")["revision"]
        return self.review("old", revision)

    def test_revision_and_failed_publication_preserve_previous(self):
        revision = self.saved()
        with self.assertRaisesRegex(ValueError, "stale"):
            c.save(self.root, "task", "old", self.note, "new")
        atomic = c.atomic
        def fail_pointer(path, raw):
            if path.name == "latest.json":
                raise OSError("simulated interrupted publication")
            return atomic(path, raw)
        changed = deepcopy(self.note)
        changed["next"] = ["second action"]
        with patch.object(c, "atomic", fail_pointer), self.assertRaises(OSError):
            c.save(self.root, "task", "old", changed, revision)
        self.assertEqual(c.load(self.root, "task")[1], revision)
        self.assertEqual(c.load(self.root, "task")[0]["note"]["next"], ["verify"])
        self.assertTrue(c.verify(self.root, "task")["ok"])

    def test_owner_paths_and_project_isolation(self):
        revision = self.saved()
        with self.assertRaisesRegex(ValueError, "writer"):
            c.save(self.root, "task", "other", self.note, revision)
        with self.assertRaises(ValueError):
            c.save(self.root, "../escape", "old", self.note, "new")
        with self.assertRaises(ValueError):
            c.save(self.root, "second-task", "old", self.note, "new")
        other = self.root / "other-project"
        other.mkdir()
        self.assertEqual(c.hook({"cwd": str(other), "session_id": "unregistered", "hook_event_name": "SessionStart"}), {})
        self.assertFalse((other / ".dev-continuity").exists())
        with self.assertRaises(FileNotFoundError):
            c.load(other, "task")

    def test_source_anchor_append_allowed_change_rejected(self):
        source = self.root / "source.jsonl"
        source.write_bytes(b"first\nsecond\n")
        anchor = c.make_anchor(source, 6, 6)
        with source.open("ab") as stream:
            stream.write(b"third\n")
        self.assertEqual(c.read_source(anchor), b"second")
        source.write_bytes(b"first\nSECOND\n")
        with self.assertRaisesRegex(ValueError, "source changed"):
            c.read_source(anchor)
        with self.assertRaises(ValueError):
            c.make_anchor(source, 0, c.MAX_SOURCE + 1)

    def test_file_drift_and_transfer_ownership(self):
        revision = self.saved()
        (self.root / "a.txt").write_text("two", encoding="utf-8")
        self.assertFalse(c.verify(self.root, "task")["ok"])
        with self.assertRaises(ValueError):
            c.transfer(self.root, "task", "old", revision, "prepare")
        (self.root / "a.txt").write_text("one", encoding="utf-8")
        revision = c.transfer(self.root, "task", "old", revision, "prepare")["revision"]
        prompt = (self.root / ".dev-continuity/task/handoff-prompt.md").read_text(encoding="utf-8")
        self.assertIn("不要求用户回复", prompt)
        self.assertIn("直接执行 next", prompt)
        with self.assertRaisesRegex(ValueError, "reserved"):
            c.transfer(self.root, "task", "old", revision, "prepare")
        revision = c.transfer(self.root, "task", "old", revision, "target", "new")["revision"]
        with self.assertRaises(ValueError):
            c.transfer(self.root, "task", "new", revision, "accept")
        revision = c.transfer(self.root, "task", "old", revision, "release")["revision"]
        with self.assertRaises(ValueError):
            c.save(self.root, "task", "old", self.note, revision)
        revision = c.transfer(self.root, "task", "new", revision, "accept")["revision"]
        self.assertEqual(c.load(self.root, "task")[0]["owner"], "new")
        with self.assertRaises(ValueError):
            c.save(self.root, "task", "old", self.note, revision)
        self.assertTrue(c.save(self.root, "task", "new", self.note, revision)["revision"])

    def sample(self, stamp=None, used=85):
        path = self.root / "transcript.jsonl"
        value = {"timestamp": stamp or c.now(), "type": "event_msg", "payload": {"type": "token_count", "info": {
            "last_token_usage": {"total_tokens": used}, "total_token_usage": {"total_tokens": 999999}, "model_context_window": 100}}}
        path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        return path

    def test_usage_ignores_cumulative_and_rejects_stale_missing(self):
        path = self.sample()
        self.assertEqual(c.usage(path)["remaining_percent_estimate"], 15)
        self.assertEqual(c.usage(path, 90)["capacity"], 90)
        self.assertEqual(c.usage(None)["status"], "unknown")
        self.sample((datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat())
        self.assertEqual(c.usage(path)["status"], "unknown")
        path.write_bytes(b"x" * (c.TAIL + 5))
        self.assertEqual(c.usage(path)["status"], "unknown")

    def test_hooks_short_recovery_throttle_and_machine_receipt(self):
        revision = self.saved()
        transcript = self.sample()
        payload = {"cwd": str(self.root), "session_id": "old", "hook_event_name": "PostToolUse", "transcript_path": str(transcript)}
        result = c.hook(payload)
        self.assertIn("15.0%", result["hookSpecificOutput"]["additionalContext"])
        self.assertIn("不单独触发", result["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(c.hook(payload), {})
        payload["hook_event_name"] = "PreCompact"
        self.assertEqual(c.hook(payload), {})
        receipts = list((self.root / ".dev-continuity/task/events").glob("*.json"))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(json.loads(receipts[0].read_text())["revision"], revision)
        payload["hook_event_name"] = "SessionStart"
        payload["source"] = "compact"
        self.assertIn("latest.json", c.hook(payload)["hookSpecificOutput"]["additionalContext"])
        self.assertIn("恢复后继续", c.hook(payload)["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(c.load(self.root, "task")[1], revision)

    def test_lock_and_corrupt_checkpoint_fail_closed(self):
        revision = self.saved()
        _, directory = c.store(self.root, "task")
        with c.lock(directory), self.assertRaises(FileExistsError):
            c.save(self.root, "task", "old", self.note, revision)
        (directory / "checkpoints" / (revision + ".json")).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            c.load(self.root, "task")

    def test_unknown_operations_and_secret_guard(self):
        self.note["operations"] = [{"id": "payment", "state": "STARTED_UNKNOWN", "receipt": "unknown", "retry": "query before retry"}]
        self.saved()
        self.note["operations"][0]["state"] = "maybe"
        with self.assertRaises(ValueError):
            c.validate_note(self.note)

    def test_cancel_requires_evidence_and_preserves_reservation(self):
        revision = self.saved()
        result = c.transfer(self.root, "task", "old", revision, "prepare")
        revision = result["revision"]
        request = result["handoff"]["request_id"]
        with self.assertRaises(ValueError):
            c.transfer(self.root, "task", "old", revision, "cancel")
        (self.root / "failure.txt").write_text("creation failed with definitive response", encoding="utf-8")
        result = c.transfer(self.root, "task", "old", revision, "cancel", cancel_receipt="failure.txt")
        self.assertEqual(result["handoff"]["request_id"], request)
        self.assertEqual(result["handoff"]["phase"], "CANCELLED")
        self.assertTrue(c.save(self.root, "task", "old", self.note, result["revision"])["revision"])
        self.note["operations"] = []
        self.note["decisions"] = ["sk-" + "x" * 30]
        with self.assertRaises(ValueError):
            c.validate_note(self.note)

    def test_review_coverage_sources_and_dependency_invalidation(self):
        legacy = deepcopy(self.note)
        legacy.pop("records")
        revision = c.save(self.root, "task", "old", legacy, "new")["revision"]
        self.assertTrue(c.verify(self.root, "task")["ok"])
        self.assertFalse(c.verify(self.root, "task")["handoff_ready"])
        with self.assertRaisesRegex(ValueError, "review"):
            c.transfer(self.root, "task", "old", revision, "prepare")
        revision = c.save(self.root, "task", "old", {"records": self.note["records"]}, revision, patch=True)["revision"]
        self.assertFalse(c.verify(self.root, "task")["review_current"])
        revision = self.review("old", revision)
        self.assertTrue(c.verify(self.root, "task")["handoff_ready"])
        revision = c.save(self.root, "task", "old", {"next": ["a different action"]}, revision, patch=True)["revision"]
        self.assertFalse(c.verify(self.root, "task")["review_current"])
        evidence = self.record("tested-version", "Code tested; real device unverified.", kind="validation", basis="file",
                               depends_on={"a.txt": c.file_hash(self.root, "a.txt")})
        revision = c.save(self.root, "task", "old", {"records": [evidence]}, revision, patch=True)["revision"]
        revision = self.review("old", revision)
        (self.root / "a.txt").write_text("changed", encoding="utf-8")
        # Refreshing general file fingerprints must not silently refresh historical validation.
        c.save(self.root, "task", "old", {}, revision, patch=True)
        self.assertIn("dependency_changed", c.recall(self.root, "task", "tested-version")["records"][0]["source_issues"])
        self.assertFalse(c.verify(self.root, "task")["handoff_ready"])
        (self.root / "request.txt").unlink()
        self.assertIn("source_unavailable_or_changed", c.recall(self.root, "task", "boundary")["records"][0]["source_issues"])
        self.assertIn("source_unavailable_or_changed", c.lookup(self.root, "task", "boundary", "records")["source_issues"])

    def test_corrections_archive_paging_and_no_resurrection(self):
        revision = self.saved()
        correction = self.record("boundary-2", "Preserve dirty work; investigate receipts first.",
                                 reason="User clarification", supersedes=["boundary"], critical=False)
        revision = c.save(self.root, "task", "old", {"records": [correction]}, revision, patch=True)["revision"]
        current = c.recall(self.root, "task")
        self.assertEqual([r["id"] for r in current["records"]], ["boundary-2"])
        self.assertTrue(current["records"][0]["critical"])
        self.assertEqual(len(c.recall(self.root, "task", history=True)["records"]), 2)
        revision = c.save(self.root, "task", "old", {}, revision, patch=True, archive_superseded=True)["revision"]
        archived_revision = c.recall(self.root, "task")["archive_head"]
        self.assertTrue(c.recall(self.root, "task", history=True, revision=archived_revision)["historical_view"])
        self.assertEqual(len(c.recall(self.root, "task", history=True, revision=archived_revision)["records"]), 2)
        with self.assertRaisesRegex(ValueError, "cannot be reused"):
            c.save(self.root, "task", "old", {"records": self.note["records"]}, revision, patch=True)
        many = [self.record("extra-" + str(n), "Other required constraint " + str(n)) for n in range(10)]
        revision = c.save(self.root, "task", "old", {"records": many}, revision, patch=True)["revision"]
        page = c.recall(self.root, "task")
        self.assertEqual(len(page["records"]), 8)
        self.assertEqual(len(page["unread_critical_ids"]), 3)
        self.assertEqual(len(c.recall(self.root, "task", offset=page["next_offset"])["records"]), 3)
        changed = deepcopy(page["records"][0])
        changed.pop("source_issues")
        changed["text"] = "erase original meaning"
        with self.assertRaisesRegex(ValueError, "immutable"):
            c.save(self.root, "task", "old", {"records": [changed]}, revision, patch=True)

    def test_five_transfers_retain_critical_facts_and_unknown_operations(self):
        self.note["records"].append(self.record("acceptance", "Code checked; real device NOT tested.", kind="validation", basis="file"))
        self.note["operations"] = [{"id": "provider-call", "state": "STARTED_UNKNOWN", "receipt": "no definitive receipt", "retry": "query first; do not replay"}]
        revision = self.saved()
        owner = "old"
        for n in range(5):
            revision = c.transfer(self.root, "task", owner, revision, "prepare")["revision"]
            successor = "successor-" + str(n)
            revision = c.transfer(self.root, "task", owner, revision, "target", successor)["revision"]
            revision = c.transfer(self.root, "task", owner, revision, "release")["revision"]
            revision = c.transfer(self.root, "task", successor, revision, "accept")["revision"]
            owner = successor
            # Fresh process reads only the saved entrypoint, not this test's in-memory note.
            run = subprocess.run([sys.executable, str(Path(c.__file__)), "recall", "--project", str(self.root), "--task", "task"],
                                 capture_output=True, text=True, encoding="utf-8", check=True)
            recovered = json.loads(run.stdout)
            self.assertEqual({r["id"] for r in recovered["records"]}, {"boundary", "acceptance"})
            self.assertEqual(next(r["text"] for r in recovered["records"] if r["id"] == "acceptance"), "Code checked; real device NOT tested.")
            self.assertEqual(recovered["current"]["operations"][0]["state"], "STARTED_UNKNOWN")
            revision = c.save(self.root, "task", owner, {"next": ["query receipt, pass " + str(n)], "records": [], "operations": []}, revision, patch=True)["revision"]
            revision = self.review(owner, revision)
        with self.assertRaisesRegex(ValueError, "unknown"):
            c.save(self.root, "task", owner, {"operations": [{"id": "provider-call", "state": "NOT_STARTED", "receipt": "none", "retry": "retry"}]}, revision, patch=True)

    def test_missing_sources_inference_and_completed_operation_guards(self):
        revision = self.saved()
        ungrounded = self.record("no-source", "Unverified assertion", sources=[], state="unverified")
        revision = c.save(self.root, "task", "old", {"records": [ungrounded]}, revision, patch=True)["revision"]
        self.assertFalse(c.verify(self.root, "task")["handoff_ready"])
        with self.assertRaisesRegex(ValueError, "inference"):
            c.save(self.root, "task", "old", {"records": [self.record("guess", "A guess", basis="inference")]}, revision, patch=True)
        done = {"id": "once", "state": "SUCCEEDED", "receipt": "receipt.txt", "retry": "never"}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            c.save(self.root, "task", "old", {"operations": [done, done]}, revision, patch=True)
        revision = c.save(self.root, "task", "old", {"operations": [done]}, revision, patch=True)["revision"]
        with self.assertRaisesRegex(ValueError, "cannot be reset"):
            c.save(self.root, "task", "old", {"operations": [{**done, "state": "FAILED"}]}, revision, patch=True)

    def test_existing_legacy_transfer_can_finish_without_fabricating_review(self):
        note = deepcopy(self.note)
        note.pop("records")
        c.save(self.root, "task", "old", note, "new")
        value, _ = c.load(self.root, "task")
        # Persist the exact handoff shape written by 1.1 before an upgrade.
        value["version"] = 1
        value["handoff"] = {"phase": "TARGET_RECORDED", "request_id": "legacy-request", "from": "old", "successor": "new"}
        _, directory = c.store(self.root, "task")
        revision = c.publish(directory, value)
        revision = c.transfer(self.root, "task", "old", revision, "release")["revision"]
        c.transfer(self.root, "task", "new", revision, "accept")
        current, _ = c.load(self.root, "task")
        self.assertEqual(current["owner"], "new")
        self.assertNotIn("memory_review", current["note"])
        self.assertFalse(c.verify(self.root, "task")["handoff_ready"])

    def test_status_replacement_removes_obsolete_next_step(self):
        revision = self.saved()
        before = self.record("local", "Local checks passed; not deployed.", kind="validation", basis="file", status_key="deployment")
        revision = c.save(self.root, "task", "old", {"records": [before]}, revision, patch=True)["revision"]
        after = self.record("deployed", "Deployed; real device remains unverified.", kind="validation", basis="runtime",
                            status_key="deployment", reason="Deployment receipt arrived")
        revision = c.save(self.root, "task", "old", {"records": [after]}, revision, patch=True, archive_superseded=True)["revision"]
        rows = c.recall(self.root, "task")["records"]
        self.assertEqual({r["id"] for r in rows}, {"boundary", "deployed"})
        old = c.recall(self.root, "task", history=True, revision=c.load(self.root, "task")[0]["note"]["archive_head"])
        self.assertIn("local", {r["id"] for r in old["records"]})
        self.assertEqual(next(r for r in old["records"] if r["id"] == "local")["superseded_by"], "deployed")

    def test_archive_retirement_preserves_unknowns_and_replay_guards(self):
        self.note["records"].append(self.record("release", "This exact release completed.", kind="operation", basis="runtime"))
        done = {"id": "once", "state": "SUCCEEDED", "receipt": "request.txt", "retry": "never replay"}
        unknown = {"id": "pending", "state": "STARTED_UNKNOWN", "receipt": "unknown", "retry": "query first"}
        self.note["operations"] = [done, unknown]
        revision = self.saved()
        delta = {"retire_records": [{"id": "release", "reason": "Completed release is historical evidence", "operation_id": "once"}]}
        preview = c.save(self.root, "task", "old", delta, revision, patch=True, archive_superseded=True, archive_completed=True, dry_run=True)
        self.assertEqual(c.load(self.root, "task")[1], revision)
        revision = c.save(self.root, "task", "old", delta, revision, patch=True, archive_superseded=True, archive_completed=True)["revision"]
        self.assertEqual(c.load(self.root, "task")[0]["note"]["operations"], [unknown])
        self.assertEqual(c.operation(self.root, "task", "once")["operation"], done)
        self.assertTrue(c.operation(self.root, "task", "once")["historical"])
        retired = c.lookup(self.root, "task", "release", "records")
        self.assertTrue(retired["historical"])
        self.assertEqual(retired["record"]["retired"]["operation_id"], "once")
        self.assertFalse(c.operation(self.root, "task", "missing")["execution_authorized"])
        with self.assertRaisesRegex(ValueError, "immutable"):
            c.save(self.root, "task", "old", {"operations": [{**done, "state": "NOT_STARTED"}]}, revision, patch=True)
        with self.assertRaisesRegex(ValueError, "unknown"):
            c.save(self.root, "task", "old", {"operations": [{**unknown, "state": "NOT_STARTED"}]}, revision, patch=True)
        with self.assertRaisesRegex(ValueError, "cannot be reused"):
            c.save(self.root, "task", "old", {"records": [self.note["records"][-1]]}, revision, patch=True)
        with self.assertRaisesRegex(ValueError, "managed"):
            c.save(self.root, "task", "old", {"archive_head": None}, revision, patch=True)
        with self.assertRaisesRegex(ValueError, "preserve requirements"):
            c.save(self.root, "task", "old", {"retire_records": [{"id": "boundary", "reason": "save space"}]}, revision, patch=True)
        self.assertLess(preview["capacity"]["note_bytes"], c.MAX_NOTE)

    def test_archive_crash_corruption_and_constant_size_head(self):
        revision = self.saved()
        revisions = []
        for i in range(12):
            op = {"id": "done-" + str(i), "state": "SUCCEEDED", "receipt": "receipt.txt", "retry": "never replay"}
            revision = c.save(self.root, "task", "old", {"operations": [op]}, revision, patch=True, archive_completed=True)["revision"]
            value, _ = c.load(self.root, "task")
            revisions.append(value["note"]["archive_head"])
            self.assertEqual(value["note"]["operations"], [])
            self.assertNotIn("record_archives", value["note"])
        self.assertTrue(c.operation(self.root, "task", "done-0")["found"])
        atomic = c.atomic
        def fail_pointer(path, raw):
            if path.name == "latest.json":
                raise OSError("interrupted hot publication")
            atomic(path, raw)
        with patch.object(c, "atomic", fail_pointer), self.assertRaises(OSError):
            c.save(self.root, "task", "old", {"operations": [{**op, "id": "new-done"}]}, revision, patch=True, archive_completed=True)
        self.assertEqual(c.load(self.root, "task")[1], revision)
        _, directory = c.store(self.root, "task")
        (directory / "checkpoints" / (revisions[0] + ".json")).write_bytes(b"{}")
        self.assertFalse(c.verify(self.root, "task")["ok"])
        with self.assertRaises(ValueError):
            c.operation(self.root, "task", "unseen")

    def test_brief_utf8_paging_and_capacity_diagnostics(self):
        self.note["goal"] = "继续已授权工作"
        self.note["records"].extend(self.record("extra-" + str(i), "Important fact " + str(i)) for i in range(10))
        revision = self.saved()
        first = c.recall(self.root, "task", detail=False)
        last = c.recall(self.root, "task", offset=first["next_offset"], revision=revision, detail=False)
        self.assertEqual(last["remaining_critical_ids"], [])
        self.assertNotIn("unread_critical_ids", last)
        self.assertNotIn("sources", first["records"][0])
        self.assertIn("sources", c.recall(self.root, "task", detail=True)["records"][0])
        run = subprocess.run([sys.executable, str(Path(c.__file__)), "recall", "--project", str(self.root), "--task", "task"],
                             capture_output=True, check=True, env={**os.environ, "PYTHONIOENCODING": "gbk"})
        self.assertIn("继续已授权工作", run.stdout.decode("utf-8"))
        with self.assertRaisesRegex(ValueError, "field_bytes"):
            c.save(self.root, "task", "old", {"next": ["x" * c.MAX_NOTE]}, revision, patch=True)
        self.assertEqual(c.load(self.root, "task")[1], revision)

    def test_legacy_archive_migration_and_unknown_retirement_rejected(self):
        self.note["record_archives"] = []
        self.note["operations"] = [{"id": "pending", "state": "STARTED_UNKNOWN", "receipt": "unknown", "retry": "query first"}]
        self.note["records"].append(self.record("pending-record", "Provider status remains unknown", kind="operation", basis="runtime"))
        revision = self.saved()
        value, _ = c.load(self.root, "task")
        value["note"]["record_archives"] = [revision]
        _, directory = c.store(self.root, "task")
        revision = c.publish(directory, value)
        with self.assertRaisesRegex(ValueError, "succeeded ledger"):
            c.save(self.root, "task", "old", {"retire_records": [{"id": "pending-record", "reason": "not settled", "operation_id": "pending"}]}, revision, patch=True)
        done = {"id": "done", "state": "SUCCEEDED", "receipt": "receipt.txt", "retry": "never"}
        c.save(self.root, "task", "old", {"operations": [done]}, revision, patch=True, archive_completed=True)
        value, _ = c.load(self.root, "task")
        self.assertNotIn("record_archives", value["note"])
        self.assertTrue(value["note"]["archive_head"])
        self.assertEqual(c.operation(self.root, "task", "pending")["operation"]["state"], "STARTED_UNKNOWN")


    def test_batch_settings_and_capacity_are_preserved_at_handoff(self):
        self.note['records'].append(self.record('settings', 'User chose high reasoning.', kind='requirement'))
        self.note['continuation_settings'] = {'thinking': 'high', 'source_record': 'settings'}
        revision = self.saved()
        result = c.transfer(self.root, 'task', 'old', revision, 'prepare')
        self.assertEqual(result['continuation_settings'], {'thinking': 'high'})
        prompt = (self.root/'.dev-continuity/task/handoff-prompt.md').read_text(encoding='utf-8')
        self.assertIn('fix-one', prompt)
        self.assertIn('"thinking": "high"', prompt)
        self.assertNotIn('"model":', prompt)
        # New reservations require a finite batch even when old-format memory can be read.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root/'a.txt').write_text('one')
            legacy = deepcopy(self.note)
            legacy.pop('batch')
            rev = c.save(root,'legacy','owner',legacy,'new')['revision']
            check = c.verify(root,'legacy')
            rev = c.save(root,'legacy','owner',{'memory_review':{'basis_sha256':check['memory_basis_sha256'],'critical_ids':check['critical_ids']}},rev,patch=True)['revision']
            with self.assertRaisesRegex(ValueError,'finite'):
                c.transfer(root,'legacy','owner',rev,'prepare')
        bad = deepcopy(self.note)
        bad['continuation_settings']['source_record'] = 'missing'
        with self.assertRaisesRegex(ValueError,'user source'):
            c.validate_note(bad)

    def test_capacity_warning_requires_resolution_before_new_handoff(self):
        self.note['evidence'] = ['x'*39500]
        revision = self.saved()
        self.assertTrue(c.verify(self.root,'task')['advisory'])
        with self.assertRaisesRegex(ValueError,'consolidate'):
            c.transfer(self.root,'task','old',revision,'prepare')
        check = c.verify(self.root,'task')
        revision = c.save(self.root,'task','old',{'memory_review':{
            'basis_sha256':check['memory_basis_sha256'],'critical_ids':check['critical_ids'],
            'checked_sections':c.REVIEW_SECTIONS,'continuation':self.decision(),
            'capacity_reason':'Essential active incident evidence; no settled facts remain to archive.'}},revision,patch=True)['revision']
        self.assertEqual(c.transfer(self.root,'task','old',revision,'prepare')['handoff']['phase'],'REQUESTED')

    def test_full_save_preserves_settings_and_reset_requires_new_user_basis(self):
        self.note['records'].append(self.record('settings', 'User chose high reasoning.', kind='requirement'))
        self.note['continuation_settings'] = {'thinking': 'high', 'source_record': 'settings'}
        revision = self.saved()
        legacy = deepcopy(self.note)
        legacy.pop('batch')
        legacy.pop('continuation_settings')
        revision = c.save(self.root, 'task', 'old', legacy, revision)['revision']
        current = c.recall(self.root, 'task')['current']
        self.assertEqual(current['continuation_settings'], self.note['continuation_settings'])
        self.assertEqual(current['batch'], self.note['batch'])
        with self.assertRaisesRegex(ValueError, 'new user source'):
            c.save(self.root, 'task', 'old', {'continuation_settings': {'source_record': 'settings'}}, revision, patch=True)
        reset = self.record('settings-reset', 'User explicitly restored default settings.', kind='requirement', supersedes=['settings'], reason='User changed preference')
        c.save(self.root, 'task', 'old', {'records': [reset], 'continuation_settings': {'source_record': 'settings-reset'}}, revision, patch=True)
        self.assertEqual(c.verify(self.root, 'task')['continuation_settings'], {})

    def test_retained_slices_survive_mutation_and_history_audit_detects_missing(self):
        revision = c.save(self.root,'task','old',self.note,'new',retain_sources=True)['revision']
        source = self.root/'request.txt'
        anchor = self.note['records'][0]['sources'][0]
        original = source.read_bytes()
        source.write_bytes(b'new unrelated content')
        self.assertEqual(c.read_source(anchor,self.root),original)
        with self.assertRaisesRegex(ValueError,'source changed'):
            c.read_source(anchor)
        self.assertTrue(c.verify(self.root,'task')['ok'])
        retained = self.root/'.dev-continuity/sources'/f"{anchor['sha256']}.txt"
        retained.write_bytes(b'tampered')
        self.assertFalse(c.verify(self.root,'task')['ok'])
        with self.assertRaisesRegex(ValueError,'source changed'):
            c.read_source(anchor,self.root)
        retained.write_bytes(original)
        correction = self.record('boundary-new','Same constraint with corrected detail.',supersedes=['boundary'],reason='User correction')
        revision = c.save(self.root,'task','old',{'records':[correction]},revision,patch=True,archive_superseded=True,retain_sources=True)['revision']
        retained.unlink()
        self.assertTrue(c.verify(self.root,'task')['ok'])
        self.assertFalse(c.verify(self.root,'task',history=True)['history']['ok'])
        run = subprocess.run([sys.executable, str(Path(c.__file__)), 'verify', '--project', str(self.root), '--task', 'task', '--history'], capture_output=True)
        self.assertEqual(run.returncode, 1)
        self.assertFalse(json.loads(run.stdout)['history']['ok'])
        self.assertFalse(c.lookup(self.root,'task','boundary','records')['execution_authorized'])

    def test_retention_is_dry_run_safe_and_rejects_secret_sources(self):
        c.save(self.root,'task','old',self.note,'new',dry_run=True,retain_sources=True)
        self.assertFalse((self.root/'.dev-continuity/sources').exists())
        secret = self.root/'.env'
        secret.write_bytes(b'not-a-real-secret')
        self.note['records'][0]['sources']=[c.make_anchor(secret,0,secret.stat().st_size)]
        with self.assertRaisesRegex(ValueError,'secret files'):
            c.save(self.root,'task','old',self.note,'new',retain_sources=True)
        self.assertFalse((self.root/'.dev-continuity/task/latest.json').exists())

    def test_thirty_updates_bound_current_memory_and_preserve_history(self):
        self.note['operations']=[{'id':'unknown','state':'STARTED_UNKNOWN','receipt':'query only','retry':'never replay'}]
        revision = self.saved()
        sizes=[]
        for n in range(30):
            row=self.record('status-'+str(n),'Version '+str(n)+' checked; device pending.',kind='validation',basis='file',status_key='current',reason='New version replaces prior validation')
            revision=c.save(self.root,'task','old',{'records':[row]},revision,patch=True,archive_superseded=True,retain_sources=True)['revision']
            sizes.append(c.verify(self.root,'task')['capacity']['note_bytes'])
        self.assertLess(max(sizes)-min(sizes),600)
        self.assertEqual(len(c.recall(self.root,'task')['records']),2)
        self.assertEqual(c.operation(self.root,'task','unknown')['operation']['state'],'STARTED_UNKNOWN')
        self.assertTrue(c.lookup(self.root,'task','status-0','records')['historical'])
        self.assertEqual(c.lookup(self.root,'task','boundary','records')['record']['text'],self.note['records'][0]['text'])
        self.assertTrue(c.verify(self.root,'task',history=True)['history']['ok'])

    def test_cost_deduplicates_counters_and_excludes_inherited_history(self):
        p=self.root/'usage.jsonl'
        rows=[]
        for count in [110,110,120]:
            rows.append({'type':'event_msg','payload':{'type':'token_count','info':{
                'total_token_usage':{'input_tokens':count,'cached_input_tokens':count-10,'output_tokens':0,'total_tokens':count},
                'last_token_usage':{'input_tokens':10,'cached_input_tokens':8,'output_tokens':0,'total_tokens':10}}}})
        p.write_text('\n'.join(json.dumps(x) for x in rows),encoding='utf-8')
        result=c.cost(p)
        self.assertEqual(result['usage']['total_tokens'],20)
        self.assertEqual(result['usage_advances'],2)
        self.assertEqual(result['uncached_input_tokens'],2)

    def test_usage_dip_does_not_repeat_warning_until_compaction(self):
        self.saved()
        payload={'cwd':str(self.root),'session_id':'old','hook_event_name':'PostToolUse','transcript_path':str(self.sample(used=85))}
        self.assertTrue(c.hook(payload))
        runtime=self.root/'.dev-continuity/task/runtime-old.json'
        for used in [65,85]:
            self.sample(used=used)
            value=json.loads(runtime.read_text());value['checked_at']=0;runtime.write_text(json.dumps(value))
            self.assertEqual(c.hook(payload),{})
        self.assertTrue(c.hook({**payload,'hook_event_name':'SessionStart','source':'compact'}))

    def test_image_payload_does_not_hide_fresh_usage_and_scan_is_bounded(self):
        path = self.sample()
        with path.open('ab') as stream:
            stream.write(json.dumps({'type':'response_item','payload':{'image':'x' * (3 * 1024 * 1024)}}).encode() + b'\n')
        self.assertEqual(c.usage(path)['used'], 85)
        self.assertGreater(c.usage(path)['scanned_bytes'], c.TAIL)
        with path.open('ab') as stream:
            stream.write(b'x' * c.MAX_USAGE_SCAN)
        result = c.usage(path)
        self.assertEqual(result['reason'], 'scan_limit')
        self.assertLessEqual(result['scanned_bytes'], c.MAX_USAGE_SCAN)
        self.assertNotIn('remaining_percent_estimate', result)
        self.sample((datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat())
        self.assertEqual(c.usage(path)['reason'], 'stale_or_future_sample')

    def test_usage_resolves_current_segment_and_unknown_warning_is_deduplicated(self):
        self.saved()
        first = self.sample()
        payload = {'cwd':str(self.root),'session_id':'old','hook_event_name':'PostToolUse','transcript_path':str(first)}
        c.hook(payload)
        second = self.root / 'new-segment.jsonl'
        second.write_bytes(first.read_bytes())
        first.unlink()
        c.hook({**payload,'hook_event_name':'SessionStart','transcript_path':str(second)})
        self.assertEqual(c.task_usage(self.root,'task','old')['used'],85)
        with self.assertRaisesRegex(ValueError,'owner'):
            c.task_usage(self.root,'task','another')
        with self.assertRaisesRegex(ValueError,'threshold'):
            c.task_usage(self.root,'task','old',0)
        second.write_bytes(b'no compatible sample')
        runtime = self.root / '.dev-continuity/task/runtime-old.json'
        for expected in [True,False]:
            state = json.loads(runtime.read_text());state['checked_at']=0;runtime.write_text(json.dumps(state))
            self.assertEqual(bool(c.hook({**payload,'transcript_path':str(second)})),expected)

    def test_decision_requires_capability_semantic_review_and_fresh_basis(self):
        revision = self.saved()
        self.assertTrue(c.verify(self.root,'task')['new_handoff_ready'])
        for decision,tools in [('defer','available'),('unavailable','unavailable'),('migrate','unknown')]:
            check=c.verify(self.root,'task')
            review={'basis_sha256':check['memory_basis_sha256'],'critical_ids':check['critical_ids'],
                    'checked_sections':c.REVIEW_SECTIONS,'continuation':self.decision(decision,tools)}
            revision=c.save(self.root,'task','old',{'memory_review':review},revision,patch=True)['revision']
            self.assertFalse(c.verify(self.root,'task')['new_handoff_ready'])
            with self.assertRaisesRegex(ValueError,'record a current migrate'):
                c.transfer(self.root,'task','old',revision,'prepare')
        revision=self.review('old',revision)
        revision=c.save(self.root,'task','old',{'next':['a changed next action']},revision,patch=True)['revision']
        self.assertFalse(c.verify(self.root,'task')['continuation_review']['current'])
        revision=self.review('old',revision)
        note,_=c.load(self.root,'task');review=note['note']['memory_review'];review.pop('checked_sections')
        revision=c.save(self.root,'task','old',{'memory_review':review},revision,patch=True)['revision']
        self.assertTrue(c.verify(self.root,'task')['handoff_ready'])
        self.assertFalse(c.verify(self.root,'task')['new_handoff_ready'])

    def test_expired_observation_blocks_handoff_without_erasing_user_constraints(self):
        until=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()
        self.note['records'].append(self.record('online','User is temporarily online',kind='validation',
                                                valid_until=until,status_key='availability'))
        revision=self.saved()
        with patch.object(c.time,'time',return_value=c.timestamp(until)+1):
            check=c.verify(self.root,'task')
            self.assertFalse(check['ok'])
            self.assertFalse(check['new_handoff_ready'])
            self.assertIn('expired_observation',str(check['issues']))
            self.assertTrue(c.lookup(self.root,'task','online','records')['found'])
        replacement=self.record('offline','Availability must be checked again',kind='validation',
            valid_until=(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat(),status_key='availability',reason='New user status')
        c.save(self.root,'task','old',{'records':[replacement]},revision,patch=True,archive_superseded=True)
        self.assertTrue(c.lookup(self.root,'task','online','records')['historical'])
        self.assertFalse(c.lookup(self.root,'task','boundary','records')['historical'])

    def test_legacy_pending_handoff_completes_without_rewriting_its_review(self):
        revision=self.saved()
        revision=c.transfer(self.root,'task','old',revision,'prepare')['revision']
        value,_=c.load(self.root,'task');value['version']=3;value['handoff']['memory_policy']=2
        value['note']['memory_review'].pop('checked_sections');value['note']['memory_review'].pop('continuation')
        _,directory=c.store(self.root,'task');revision=c.publish(directory,value)
        self.assertEqual(c.load(self.root,'task')[0]['version'],3)
        for action in ['target','release','accept']:
            revision=c.transfer(self.root,'task','new' if action=='accept' else 'old',revision,action,successor='new')['revision']
        value,_=c.load(self.root,'task')
        self.assertEqual(value['version'],4)
        self.assertEqual(value['owner'],'new')
        self.assertEqual(value['handoff']['phase'],'ACCEPTED')

    def test_compaction_invalidates_deferral_and_capacity_exception_has_ceiling(self):
        revision=self.saved()
        payload={'cwd':str(self.root),'session_id':'old','hook_event_name':'SessionStart','transcript_path':str(self.sample())}
        c.hook(payload)
        c.hook({**payload,'hook_event_name':'PreCompact'})
        runtime=self.root/'.dev-continuity/task/runtime-old.json'
        self.assertTrue(json.loads(runtime.read_text())['continuation_review']['due_at_safe_boundary'])
        revision=self.review('old',revision)
        c.hook(payload)
        self.assertFalse(json.loads(runtime.read_text())['continuation_review']['due_at_safe_boundary'])
        value,_=c.load(self.root,'task')
        padding='x'*(c.MAX_NOTE-len(c.encode(value['note']))-500)
        revision=c.save(self.root,'task','old',{'evidence':[padding]},revision,patch=True)['revision']
        revision=self.review('old',revision)
        value,_=c.load(self.root,'task');review=value['note']['memory_review'];review['capacity_reason']='Retained pending review'
        revision=c.save(self.root,'task','old',{'memory_review':review},revision,patch=True)['revision']
        with self.assertRaisesRegex(ValueError,'5%'):
            c.transfer(self.root,'task','old',revision,'prepare')


if __name__ == "__main__":
    unittest.main()
