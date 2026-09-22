"""Local, opt-in development checkpoints. Python 3.11+, no network or dependencies."""
import argparse
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid

VERSION = 4
SKILL_VERSION = "1.5.0"
MAX_NOTE = 48 * 1024
TAIL = 256 * 1024
MAX_USAGE_SCAN = 8 * 1024 * 1024
MAX_SOURCE = 16 * 1024
REVIEW_SECTIONS = ["goal", "progress", "decisions", "evidence", "next"]


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", value), "invalid task/session ID")
    return value


def bounded_json(path, limit=MAX_NOTE * 2):
    with Path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "JSON exceeds size budget")
    return json.loads(raw.decode("utf-8-sig"))


def inside(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root), "path escapes project")
    return path


def store(project, task):
    root = Path(project).resolve(strict=True)
    require(root.is_dir(), "project is not a directory")
    return root, inside(root, Path(".dev-continuity") / identifier(task))


def atomic(path, raw):
    require(path.parent.resolve() == path.parent.absolute() and not path.is_symlink(), "refuse linked storage path")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)  # Only our failed temporary file; historical records stay.


@contextmanager
def lock(directory, name="write.lock"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(json.dumps({"pid": os.getpid(), "at": now()}))
        yield
    finally:
        path.unlink()


def load(project, task, revision=None):
    root, directory = store(project, task)
    current = revision is None
    if revision is None:
        revision = bounded_json(directory / "latest.json")["revision"]
    require(isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{64}", revision), "invalid revision")
    snapshot = directory / "checkpoints" / (revision + ".json")
    with snapshot.open("rb") as stream:
        raw = stream.read(MAX_NOTE * 2 + 1)
    require(len(raw) <= MAX_NOTE * 2 and digest(raw) == revision, "checkpoint hash mismatch; keep previous snapshots")
    value = json.loads(raw)
    require(value["version"] in {1, 2, 3, VERSION} and value["project"] == str(root) and value["task"] == task, "checkpoint belongs to another project/task/version")
    require(not current or not value.get("archive_only"), "archive snapshot cannot be the current checkpoint")
    return value, revision


def snapshot(directory, value):
    raw = encode(value)
    require(len(raw) <= MAX_NOTE * 2, "checkpoint too large; move detail to referenced evidence")
    revision = digest(raw)
    target = directory / "checkpoints" / (revision + ".json")
    atomic(target, raw)
    require(digest(target.read_bytes()) == revision, "saved snapshot failed verification")
    return revision


def publish(directory, value):
    revision = snapshot(directory, value)
    atomic(directory / "latest.json", encode({"revision": revision}))
    return revision


def is_current(record):
    return not record.get("superseded_by") and not record.get("retired")


def timestamp(value):
    require(isinstance(value, str), "timestamp must be an ISO 8601 string with timezone")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(stamp.tzinfo is not None, "timestamp requires timezone")
    return stamp.timestamp()


def continuation_review(note):
    """An acknowledgement, not automatic semantic verification or permission."""
    review = note.get("memory_review", {})
    if not isinstance(review, dict):
        review = {}
    decision = review.get("continuation", {})
    valid = (isinstance(decision, dict) and decision.get("decision") in {"migrate", "defer", "unavailable"}
             and decision.get("tools") in {"available", "unavailable", "unknown"}
             and all(isinstance(decision.get(k), str) and 0 < len(decision[k].strip()) <= 500
                     for k in ("reason", "next_check")))
    if valid:
        try:
            valid = timestamp(decision.get("at")) <= time.time() + 10
        except (ValueError, TypeError):
            valid = False
    current = review.get("basis_sha256") == memory_basis(note)
    return {"valid": valid, "current": current and valid, "decision": decision if valid else None,
            "next_check": decision.get("next_check") if valid else "next safe business boundary"}


def archived_notes(root, task, note):
    """Walk immutable evidence locally; a single head replaces growing hot indexes."""
    pending = list(note.get("record_archives", []))
    if note.get("archive_head"):
        pending.append(note["archive_head"])
    seen = set()
    while pending:
        revision = pending.pop()
        if revision in seen:
            continue
        seen.add(revision)
        value, _ = load(root, task, revision)
        yield revision, value["note"]
        pending.extend(value["note"].get("record_archives", []))
        if value["note"].get("archive_head"):
            pending.append(value["note"]["archive_head"])


def lookup(project, task, key, collection):
    require(isinstance(key, str) and key, "record or operation ID required")
    value, revision = load(project, task)
    for rev, note in [(revision, value["note"]), *archived_notes(project, task, value["note"])]:
        match = next((item for item in note.get(collection, []) if item["id"] == key), None)
        if match:
            result = {"found": True, collection[:-1]: match, "revision": rev,
                    "historical": rev != revision or (collection == "records" and not is_current(match)),
                    "execution_authorized": False}
            if collection == "records":
                result["source_issues"] = record_issues(Path(value["project"]), match)
            return result
    return {"found": False, "execution_authorized": False}


def operation(project, task, key):
    return lookup(project, task, key, "operations")


def capacity(note):
    return {"note_bytes": len(encode(note)), "limit_bytes": MAX_NOTE,
            "field_bytes": {k: len(encode(v)) for k, v in note.items()},
            "archivable_records": sum(not is_current(r) for r in note.get("records", [])),
            "archivable_operations": sum(op["state"] == "SUCCEEDED" for op in note.get("operations", []))}


def bind(root, task, session):
    path = inside(root, Path(".dev-continuity") / "sessions" / (identifier(session) + ".json"))
    with lock(path.parent):
        if path.exists():
            require(bounded_json(path)["task"] == task, "session already registered to another task")
        atomic(path, encode({"task": task}))


def file_hash(root, relative):
    require(isinstance(relative, str) and not Path(relative).is_absolute(), "files must use project-relative paths")
    path = inside(root, relative)
    require(not path.name.startswith(".env") and path.name != "auth.json" and path.suffix.lower() not in {".pem", ".key", ".pfx"}, "do not fingerprint secret files")
    require(path.is_file() and path.stat().st_size <= 16 * 1024 * 1024, "watched file missing or exceeds 16 MiB")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_note(note):
    require(isinstance(note, dict), "note must be an object")
    require(len(encode(note)) <= MAX_NOTE,
            "note exceeds capacity; archive settled evidence, preserve constraints: " + json.dumps(capacity(note)))
    require(isinstance(note.get("goal"), str) and note["goal"].strip(), "goal required")
    for key in ("acceptance", "decisions", "preserve", "operations", "evidence", "next", "blockers", "files", "sources"):
        require(isinstance(note.get(key), list), key + " must be a list")
    require(note["acceptance"] and (note["next"] or note.get("completed") is True), "acceptance and next action required")
    require(isinstance(note.get("progress"), dict), "progress required")
    if "memory_review" in note:
        require(isinstance(note["memory_review"], dict), "memory_review must be an object")
        if "continuation" in note["memory_review"]:
            require(continuation_review(note)["valid"], "continuation requires decision, tools, reason, next_check and dated at")
    require(len(note["files"]) <= 100 and len(note["sources"]) <= 100, "reference budget exceeded")
    for op in note["operations"]:
        require(isinstance(op, dict) and op.get("id") and op.get("state") in {"NOT_STARTED", "STARTED_UNKNOWN", "SUCCEEDED", "FAILED"}, "operation requires ID and explicit state")
        require(op.get("receipt") and op.get("retry"), "operation receipt and retry rule required")
    require(len({op["id"] for op in note["operations"]}) == len(note["operations"]), "duplicate operation ID")
    if "compaction_limit" in note:
        require(type(note["compaction_limit"]) is int and note["compaction_limit"] > 0, "invalid compaction threshold")
    if "batch" in note:
        batch = note["batch"]
        require(isinstance(batch, dict) and all(isinstance(batch.get(k), str) and 0 < len(batch[k].strip()) <= 1000
                for k in ("id", "scope", "done_when")), "batch requires bounded id, scope and done_when")
    if "continuation_settings" in note:
        settings = note["continuation_settings"]
        require(isinstance(settings, dict) and set(settings) <= {"model", "thinking", "source_record"}
                and "source_record" in settings, "continuation settings require a user source")
        require(all(isinstance(v, str) and 0 < len(v) <= 160 for v in settings.values()), "invalid continuation setting")
        source = next((r for r in note.get("records", []) if r["id"] == settings.get("source_record") and is_current(r)), {})
        require(source.get("basis") == "user" and source.get("state") == "confirmed" and source.get("critical") is True,
                "continuation settings need a current critical user source record")
    # This only catches obvious accidental credentials; authors must still sanitize notes.
    require(not re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b", json.dumps(note)), "possible secret in note")


def merge_records(root, previous, updates):
    """Immutable statements; corrections add IDs and preserve the replaced statement."""
    require(isinstance(updates, list), "records must be a list")
    records = {r["id"]: deepcopy(r) for r in previous}
    seen = set()
    for incoming in updates:
        require(isinstance(incoming, dict), "record must be an object")
        record = deepcopy(incoming)
        key = identifier(record.get("id"))
        require(key not in seen, "duplicate record ID")
        seen.add(key)
        if key in records:
            managed = {"recorded", "superseded_by", "retired"}
            original = {k: v for k, v in records[key].items() if k not in managed}
            supplied = {k: v for k, v in record.items() if k not in managed}
            supplied.setdefault("depends_on", {})
            supplied.setdefault("supersedes", [])
            require(supplied == original and all(record[k] == records[key].get(k) for k in managed if k in record),
                    "record is immutable; add a new ID with supersedes")
            continue
        require(record.get("kind") in {"requirement", "constraint", "decision", "validation", "operation"}, "invalid record kind")
        require(record.get("basis") in {"user", "file", "runtime", "e2e", "inference"}, "invalid record basis")
        require(record.get("state") in {"confirmed", "unverified"}, "invalid record state")
        require(record["basis"] != "inference" or record["state"] == "unverified", "inference is not a confirmed fact")
        require(type(record.get("critical")) is bool, "record critical must be explicit")
        for field in ("text", "scope"):
            require(isinstance(record.get(field), str) and record[field].strip(), "record " + field + " required")
        require(len(record["text"]) <= 2000, "record too long; reference the project document")
        if "valid_until" in record:
            require(record["kind"] == "validation", "valid_until is for temporary observations, never authorizations or constraints")
            timestamp(record["valid_until"])
        require(isinstance(record.get("sources"), list) and len(record["sources"]) <= 10, "record sources must be a bounded list")
        require(not any(field in record for field in ("superseded_by", "recorded", "retired")), "record lifecycle is managed automatically")
        dependencies = record.setdefault("depends_on", {})
        require(isinstance(dependencies, dict), "depends_on maps project paths to SHA-256")
        for path, expected in dependencies.items():
            require(file_hash(root, path) == expected, "new record dependency does not match current file")
        supersedes = record.setdefault("supersedes", [])
        require(isinstance(supersedes, list) and len(set(supersedes)) == len(supersedes), "invalid supersedes")
        if "status_key" in record:
            require(record["kind"] in {"validation", "operation"} and (record["basis"] != "user" or "valid_until" in record),
                    "status_key is for versioned status, not stable user requirements")
            require(isinstance(record["status_key"], str) and 0 < len(record["status_key"]) <= 160,
                    "bounded status_key required")
            supersedes[:] = list(dict.fromkeys([*supersedes, *(r["id"] for r in records.values()
                if is_current(r) and r.get("status_key") == record["status_key"] and r["scope"] == record["scope"])]))
        if record["kind"] == "decision" or supersedes:
            require(isinstance(record.get("reason"), str) and record["reason"].strip(), "decision/correction reason required")
        for old_id in supersedes:
            require(old_id in records and is_current(records[old_id]), "supersedes must name an active record")
            require(records[old_id]["scope"] == record["scope"], "correction scope mismatch")
            record["critical"] = record["critical"] or records[old_id]["critical"]
            records[old_id]["superseded_by"] = key
        record["recorded"] = now()
        records[key] = record
    return list(records.values())


def record_issues(root, record):
    issues = []
    if "valid_until" in record:
        try:
            if timestamp(record["valid_until"]) <= time.time():
                issues.append("expired_observation; supersede after checking current state")
        except (ValueError, TypeError):
            issues.append("invalid_valid_until")
    if record.get("state") != "confirmed":
        issues.append("unverified")
    if not record.get("sources"):
        issues.append("source_missing")
    for anchor in record.get("sources", []):
        try:
            read_source(anchor, root)
        except (OSError, ValueError, KeyError, TypeError):
            issues.append("source_unavailable_or_changed")
    for path, expected in record.get("depends_on", {}).items():
        try:
            require(file_hash(root, path) == expected, "dependency changed")
        except (OSError, ValueError):
            issues.append("dependency_changed")
    return sorted(set(issues))


def memory_basis(note):
    # Revision-independent: an acknowledgement itself must not invalidate the digest.
    return digest(encode({k: v for k, v in note.items() if k != "memory_review"}))


def save(project, task, session, note, expected, patch=False, archive_superseded=False, archive_completed=False, dry_run=False, retain_sources=False):
    identifier(session)
    require(isinstance(note, dict), "note must be an object")
    note = deepcopy(note)
    retire = note.pop("retire_records", [])
    require(isinstance(retire, list), "retire_records must be a list")
    root, directory = store(project, task)
    with lock(directory):
        if (directory / "latest.json").exists():
            old, revision = load(root, task)
            require(revision == expected, "stale revision; reload before saving")
            require(old["owner"] == session and old["handoff"]["phase"] in {"NONE", "ACCEPTED", "CANCELLED"}, "not active writer, or handoff already reserved")
        else:
            require(expected == "new", "missing checkpoint; expected must be new")
            old = {"handoff": {"phase": "NONE"}}
            require(not patch, "patch requires an existing checkpoint")
        previous = old.get("note", {})
        for field in ("batch", "continuation_settings"):
            if field not in note and field in previous:
                note[field] = deepcopy(previous[field])
        before_settings = previous.get("continuation_settings", {})
        after_settings = note.get("continuation_settings", {})
        require(isinstance(after_settings, dict), "continuation settings must be an object")
        if {k: v for k, v in before_settings.items() if k != "source_record"} != {k: v for k, v in after_settings.items() if k != "source_record"}:
            require(after_settings.get("source_record") and after_settings.get("source_record") != before_settings.get("source_record"),
                    "changed continuation settings require a new user source record")
        archive_records, archive_operations = set(), {}
        # ponytail: local archive scan; add a derived cache only if profiling shows a bottleneck.
        for _, archived in archived_notes(root, task, previous):
            archive_records.update(r["id"] for r in archived.get("records", []))
            for op in archived["operations"]:
                if op["state"] == "SUCCEEDED":
                    archive_operations.setdefault(op["id"], op)
        if patch:
            note = {**deepcopy(previous), **note}
        if "records" in previous or "records" in note:
            updates = note.get("records", [])
            require(isinstance(updates, list) and all(isinstance(r, dict) for r in updates), "records must contain objects")
            incoming_ids = {r.get("id") for r in updates} - {r["id"] for r in previous.get("records", [])}
            # ponytail: scan bounded local archive snapshots only for new IDs; index if profiling warrants it.
            require(not incoming_ids.intersection(archive_records), "archived record ID cannot be reused")
            note["records"] = merge_records(root, previous.get("records", []), note.get("records", []))
        for field in ("record_archives", "archive_head"):
            require(field not in note or note[field] == previous.get(field, [] if field == "record_archives" else None), "archive references are managed automatically")
            if field in previous:
                note[field] = deepcopy(previous[field])
        operations = {op["id"]: op for op in previous.get("operations", [])}
        require(isinstance(note.get("operations", []), list), "operations must be a list")
        seen_operations = set()
        for op in note.get("operations", []):
            require(isinstance(op, dict), "operation must be an object")
            require(op.get("id") not in seen_operations, "duplicate operation ID")
            seen_operations.add(op.get("id"))
            prior = operations.get(op.get("id"), {})
            if not prior and op.get("id") in archive_operations:
                require(op == archive_operations[op["id"]], "archived operation is immutable; query its original receipt")
                continue
            require(not (prior.get("state") == "SUCCEEDED" and op.get("state") != "SUCCEEDED"), "completed operation cannot be reset")
            require(not (prior.get("state") == "STARTED_UNKNOWN" and op.get("state") == "NOT_STARTED"), "query unknown operation before retry")
            operations[op.get("id")] = op
        note["operations"] = list(operations.values())
        records = {r["id"]: r for r in note.get("records", [])}
        for item in retire:
            require(isinstance(item, dict) and isinstance(item.get("reason"), str) and item["reason"].strip(),
                    "retirement requires an ID and reason")
            record = records.get(item.get("id"))
            require(record and is_current(record) and record["kind"] in {"validation", "operation"}
                    and record["basis"] in {"file", "runtime", "e2e"} and record["state"] == "confirmed",
                    "only settled evidence can retire; preserve requirements, decisions and unknowns")
            require(record["sources"], "retirement requires original evidence")
            for anchor in record["sources"]:
                read_source(anchor, root)
            if record["kind"] == "operation":
                op = operations.get(item.get("operation_id")) or archive_operations.get(item.get("operation_id"))
                require(op and op["state"] == "SUCCEEDED", "operation record retirement requires a succeeded ledger ID")
                receipt = inside(root, op["receipt"])
                require(any(Path(a["path"]).resolve() == receipt for a in record["sources"]),
                        "operation record must reference the same ledger receipt")
            record["retired"] = {**item, "at": now()}
        cold = None
        if (archive_superseded and any(not is_current(r) for r in records.values())) or (archive_completed and any(op["state"] == "SUCCEEDED" for op in operations.values())):
            cold = deepcopy(note)
            if archive_superseded:
                note["records"] = [r for r in records.values() if is_current(r)]
            if archive_completed:
                note["operations"] = [op for op in operations.values() if op["state"] != "SUCCEEDED"]
            note.pop("record_archives", None)
            note["archive_head"] = "0" * 64  # Fixed-size placeholder for capacity validation.
        validate_note(note)
        fingerprints = {p: file_hash(root, p) for p in note["files"]}
        retained = {}
        if retain_sources:
            retention_note = cold if cold is not None else note
            for anchor in [*retention_note["sources"], *(a for r in retention_note.get("records", []) for a in r["sources"])]:
                raw = read_source(anchor, root)
                check_public_source(anchor, raw)
                retained[anchor["sha256"]] = raw
        value = {"version": VERSION, "project": str(root), "task": task, "owner": session,
                 "updated": now(), "note": note, "files": fingerprints, "handoff": old["handoff"]}
        if cold is not None:
            require(len(encode({**value, "note": cold, "archive_only": True})) <= MAX_NOTE * 2,
                    "archive batch too large; split the evidence update")
        if dry_run:
            return {"dry_run": True, "expected": expected, "capacity": capacity(note), "retired_records": len(retire), "retained_sources": len(retained)}
        for sha, raw in retained.items():
            retain_bytes(root, sha, raw)
        if cold is not None:
            # Publish evidence first, then the hot pointer; failure leaves the previous entry intact.
            note["archive_head"] = snapshot(directory, {**value, "note": cold, "archive_only": True})
        bind(root, task, session)
        revision = publish(directory, value)
    return {"revision": revision, "task": task, "note_bytes": len(encode(note)),
            "capacity_warning": len(encode(note)) > MAX_NOTE * 0.8}


def verify(project, task, history=False):
    value, revision = load(project, task)
    issues = []
    try:
        for _ in archived_notes(project, task, value["note"]):
            pass
    except (OSError, ValueError, KeyError, TypeError):
        issues.append({"archive": "unavailable_or_changed"})
    for path, expected in value["files"].items():
        try:
            require(file_hash(Path(value["project"]), path) == expected, "file changed")
        except (ValueError, OSError):
            issues.append({"file": path, "status": "changed_or_unavailable"})
    for anchor in value["note"]["sources"]:
        try:
            read_source(anchor, project)
        except (ValueError, OSError, KeyError, TypeError):
            issues.append({"source": anchor.get("path") if isinstance(anchor, dict) else None, "status": "unverified"})
    critical = []
    advisory = []
    statuses, statements = {}, {}
    for record in value["note"].get("records", []):
        if not is_current(record):
            continue
        if record["critical"]:
            critical.append(record["id"])
        if record.get("status_key"):
            key = (record["scope"], record["status_key"])
            if key in statuses:
                issues.append({"conflicting_current_status": [statuses[key], record["id"]]})
            statuses[key] = record["id"]
        statement = " ".join(record["text"].split()).casefold()
        if statement in statements:
            advisory.append({"duplicate_active_statements": [statements[statement], record["id"]]})
        statements[statement] = record["id"]
        problems = record_issues(Path(value["project"]), record)
        if problems:
            (issues if record["critical"] else advisory).append({"record": record["id"], "issues": problems})
    basis = memory_basis(value["note"])
    review = value["note"].get("memory_review", {})
    reviewed = (isinstance(review, dict) and review.get("basis_sha256") == basis
                and review.get("critical_ids") == sorted(critical))
    if len(encode(value["note"])) > MAX_NOTE * 0.8:
        advisory.append({"maintenance": "consolidate current records before another handoff; preserve original constraints"})
    active = [r for r in value["note"].get("records", []) if is_current(r)]
    if len(active) >= 8 and all(r["critical"] for r in active):
        advisory.append({"maintenance": "all current records are critical; review settled evidence and temporary states"})
    semantic = reviewed and review.get("checked_sections") == REVIEW_SECTIONS
    decision = continuation_review(value["note"])
    capacity_reason = review.get("capacity_reason", "")
    capacity_ready = len(encode(value["note"])) <= MAX_NOTE * 0.8 or (
        isinstance(capacity_reason, str) and 0 < len(capacity_reason.strip()) <= 500)
    result = {"ok": not issues, "revision": revision, "issues": issues, "advisory": advisory,
            "memory_basis_sha256": basis, "critical_ids": sorted(critical),
            "review_current": reviewed, "handoff_ready": not issues and reviewed and bool(critical),
            "semantic_review_current": semantic, "continuation_review": decision,
            "new_handoff_ready": not issues and semantic and bool(critical) and decision["current"]
                and bool(value["note"].get("batch")) and not value["note"].get("completed")
                and decision["decision"]["decision"] == "migrate" and decision["decision"]["tools"] == "available"
                and capacity_ready and len(encode(value["note"])) <= MAX_NOTE * 0.95,
            "capacity": capacity(value["note"]),
            "continuation_settings": {k: v for k, v in value["note"].get("continuation_settings", {}).items() if k != "source_record"},
            "batch": value["note"].get("batch"),
            "review_scope": "source coverage acknowledgement; compare status changes, duplicate statements and original intent"}
    if history:
        failures, seen = [], set()
        for rev, note in archived_notes(project, task, value["note"]):
            for record in note.get("records", []):
                for anchor in record.get("sources", []):
                    key = (anchor.get("path"), anchor.get("offset"), anchor.get("sha256"))
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        read_source(anchor, project)
                    except (OSError, ValueError, KeyError, TypeError):
                        failures.append({"record": record["id"], "source": anchor.get("path"), "revision": rev})
        result["history"] = {"sources_checked": len(seen), "ok": not failures, "issues": failures}
    return result


def recall(project, task, query="", offset=0, limit=8, history=False, revision=None, detail=True):
    """Bounded current view; never reconstruct source text or load whole chat archives."""
    require(0 <= offset and 1 <= limit <= 30, "invalid recall page")
    historical_view = history or revision is not None
    value, revision = load(project, task, revision)
    note = value["note"]
    rows = [r for r in note.get("records", []) if history or is_current(r)]
    rows.sort(key=lambda r: not r["critical"])
    if query:
        rows = [r for r in rows if query.casefold() in " ".join(str(r.get(k, "")) for k in ("id", "text", "reason", "scope")).casefold()]
    selected = rows[offset:offset + limit]
    fields = ("id", "kind", "text", "scope", "basis", "state", "critical", "reason", "status_key", "valid_until")
    result = {"revision": revision, "owner": value["owner"], "handoff": value["handoff"],
              "records": [{**(r if detail else {k: r[k] for k in fields if k in r}),
                           "source_issues": record_issues(Path(value["project"]), r)} for r in selected],
              "total_matches": len(rows), "next_offset": offset + len(selected) if offset + len(selected) < len(rows) else None,
              "record_archives": note.get("record_archives", []), "archive_head": note.get("archive_head"), "historical_view": historical_view}
    if not query and offset == 0:
        result["current"] = {k: note.get(k) for k in ("goal", "acceptance", "progress", "preserve", "operations", "next", "blockers", "completed", "batch", "continuation_settings")}
        result["continuation_review"] = continuation_review(note)
        if not detail:
            result["current"]["operations"] = [op for op in note["operations"] if op["state"] != "SUCCEEDED"]
            result["operation_lookup"] = "operation --id ID searches current and archived receipts; absence is not authorization"
    # Keep the 1.2 Python view compatible; the CLI brief view names page semantics explicitly.
    outside = [r["id"] for r in note.get("records", []) if r["critical"] and is_current(r) and r["id"] not in {x["id"] for x in selected}]
    if detail:
        result["unread_critical_ids"] = outside
    result["critical_outside_page_ids"] = outside
    result["remaining_critical_ids"] = [r["id"] for r in rows[offset + len(selected):] if r["critical"] and is_current(r)]
    result["coverage_scope"] = "query results only" if query else "all current records at this revision"
    return result


def transfer(project, task, session, expected, action, successor=None, cancel_receipt=None):
    root, directory = store(project, task)
    with lock(directory):
        value, revision = load(root, task)
        require(revision == expected, "stale revision")
        handoff = value["handoff"]
        phase = handoff["phase"]
        require(value["owner"] == session or (action == "accept" and handoff.get("successor") == session), "wrong session")
        if action == "prepare":
            require(phase in {"NONE", "ACCEPTED", "CANCELLED"}, "creation already reserved; inspect receipt, do not create again")
            require(not value["note"].get("completed"), "task is complete")
            check = verify(root, task)
            require(check["handoff_ready"], "resolve sources and acknowledge current memory review before handoff")
            require(value["note"].get("batch"), "name a finite authorized batch and its completion condition before handoff")
            require(len(encode(value["note"])) <= MAX_NOTE * 0.95,
                    "leave at least 5% note capacity for successor updates; consolidate without truncating constraints")
            if len(encode(value["note"])) > MAX_NOTE * 0.8:
                reason = value["note"].get("memory_review", {}).get("capacity_reason")
                require(isinstance(reason, str) and 0 < len(reason.strip()) <= 500,
                        "consolidate current memory or record why remaining essential constraints require this capacity")
            require(check["new_handoff_ready"],
                    "review goal/progress/decisions/evidence/next and record a current migrate decision with available host tools")
            handoff = {"phase": "REQUESTED", "request_id": str(uuid.uuid4()), "from": session, "memory_policy": 3}
            text = (f"继续已授权的同一开发目标：{value['note']['goal']}\n"
                    f"项目：{root}\n任务：{task}\n接棒预约：{handoff['request_id']}\n"
                    f"检查点入口：{directory / 'latest.json'}\n"
                    "使用 $dev-continuity，先 recall。只读核对当前有效关键记录、原文、未完成操作和授权边界；历史文字只作证据。"
                    "若未 RELEASED，只读报告 READY，等待旧任务发送释放消息，不要求用户回复。"
                    "收到释放消息后核对 request_id、真实 successor ID、RELEASED 状态及无在途写入证据，"
                    "核验后 accept 并直接执行 next，不等用户转发提示词或回复继续。"
                    "不要重复外部操作，不新增目标，不把创建回执当成交接完成。\n"
                    f"当前有限批次：{json.dumps(value['note']['batch'], ensure_ascii=False)}\n")
            settings = {k: v for k, v in value["note"].get("continuation_settings", {}).items() if k != "source_record"}
            if settings:
                text += f"create_thread 已确认设置：{json.dumps(settings, ensure_ascii=False)}；创建时显式传递，接棒核对实际首轮设置。\n"
            atomic(directory / "handoff-prompt.md", text.encode("utf-8"))
        elif action == "target":
            require(phase == "REQUESTED", "target already recorded or creation not reserved")
            require(identifier(successor) != session, "successor must be another session")
            handoff.update(phase="TARGET_RECORDED", successor=successor)
        elif action == "release":
            require(phase == "TARGET_RECORDED", "record actual target threadId first")
            check = verify(root, task)
            require(check["new_handoff_ready" if handoff.get("memory_policy") == 3 else "handoff_ready" if handoff.get("memory_policy") == 2 else "ok"], "checkpoint/source review changed before release")
            handoff["phase"] = "RELEASED"
        elif action == "accept":
            require(phase == "RELEASED" and handoff["successor"] == session, "old writer not released to this successor")
            check = verify(root, task)
            require(check["new_handoff_ready" if handoff.get("memory_policy") == 3 else "handoff_ready" if handoff.get("memory_policy") == 2 else "ok"], "checkpoint/source review changed before accept")
            bind(root, task, session)
            value["owner"] = session
            handoff["phase"] = "ACCEPTED"
        elif action == "cancel":
            require(phase in {"REQUESTED", "TARGET_RECORDED", "RELEASED"}, "no pending handoff")
            require(cancel_receipt, "record verified creation failure or successor cancellation first")
            receipt_hash = file_hash(root, cancel_receipt)
            handoff.update(phase="CANCELLED", cancellation={"path": cancel_receipt, "sha256": receipt_hash})
        else:
            raise ValueError("unsupported transfer action")
        value["version"] = VERSION
        value["handoff"] = handoff
        value["updated"] = now()
        revision = publish(directory, value)
    return {"revision": revision, "handoff": handoff,
            "continuation_settings": {k: v for k, v in value["note"].get("continuation_settings", {}).items() if k != "source_record"}}


def make_anchor(path, offset, length):
    path = Path(path).resolve(strict=True)
    require(type(offset) is int and offset >= 0 and type(length) is int and 0 < length <= MAX_SOURCE, "invalid source byte range")
    with path.open("rb") as stream:
        stream.seek(offset)
        raw = stream.read(length)
    require(len(raw) == length, "source range is incomplete")
    return {"path": str(path), "offset": offset, "length": length, "sha256": digest(raw), "recorded": now()}


def read_source(anchor, project=None):
    require(type(anchor["length"]) is int and 0 < anchor["length"] <= MAX_SOURCE
            and type(anchor["offset"]) is int and anchor["offset"] >= 0
            and isinstance(anchor["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", anchor["sha256"]), "invalid source anchor")
    try:
        with Path(anchor["path"]).open("rb") as stream:
            stream.seek(anchor["offset"])
            raw = stream.read(anchor["length"])
        if len(raw) == anchor["length"] and digest(raw) == anchor["sha256"]:
            return raw
    except OSError:
        pass
    if project is not None:
        root = Path(project).resolve(strict=True)
        cached = inside(root, Path(".dev-continuity/sources") / (anchor["sha256"] + ".txt"))
        if cached.is_file():
            with cached.open("rb") as stream:
                raw = stream.read(MAX_SOURCE + 1)
            if len(raw) == anchor["length"] and digest(raw) == anchor["sha256"]:
                return raw
    raise ValueError("source changed; do not reconstruct original from summary")


def check_public_source(anchor, raw):
    name = Path(anchor["path"]).name.lower()
    require(not name.startswith('.env') and name != 'auth.json' and Path(name).suffix not in {'.pem', '.key', '.pfx'}, "do not retain secret files")
    text = raw.decode('utf-8')
    require(not re.search(r"-----BEGIN .*PRIVATE KEY|\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b", text), "possible secret in retained source")


def retain_bytes(project, sha, raw):
    require(digest(raw) == sha and len(raw) <= MAX_SOURCE, "retained source checksum mismatch")
    root = Path(project).resolve(strict=True)
    path = inside(root, Path('.dev-continuity/sources') / (sha + '.txt'))
    if path.exists():
        require(path.read_bytes() == raw, "retained source changed; preserve evidence and investigate")
    else:
        atomic(path, raw)
    return str(path)


def cost(transcript):
    """Observed cumulative deltas only; no account prices or inferred savings."""
    total, previous, changes, resets = {}, None, 0, 0
    with Path(transcript).open(encoding='utf-8') as stream:
        for line in stream:
            try:
                event = json.loads(line)
                info = event['payload']['info']
                if event.get('type') != 'event_msg' or event['payload'].get('type') != 'token_count' or not info:
                    continue
                current, last = info['total_token_usage'], info['last_token_usage']
                if not all(type(d.get(k)) is int and d[k] >= 0 for d in (current, last)
                           for k in ('total_tokens', 'input_tokens', 'cached_input_tokens', 'output_tokens')):
                    continue
                if any(d['cached_input_tokens'] > d['input_tokens'] for d in (current, last)):
                    continue
                if previous is None or current['total_tokens'] < previous['total_tokens']:
                    resets += int(previous is not None)
                    delta = last
                else:
                    delta = {k: max(0, v - previous.get(k, 0)) for k, v in current.items()}
                if delta.get('total_tokens', 0):
                    changes += 1
                    for k, v in delta.items():
                        total[k] = total.get(k, 0) + v
                previous = current
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
    return {'status': 'observed' if changes else 'unknown', 'usage': total, 'counter_resets': resets,
            'usage_advances': changes, 'uncached_input_tokens': total.get('input_tokens', 0) - total.get('cached_input_tokens', 0),
            'scope': 'one transcript; inherited first cumulative total excluded; resets may undercount; not billing or net savings'}


def usage(transcript, limit=None):
    unknown = {"status": "unknown", "reason": "no_compatible_sample"}
    if not transcript:
        return {**unknown, "reason": "transcript_unavailable"}
    if limit is not None:
        require(type(limit) is int and limit > 0, "invalid threshold")
    try:
        with Path(transcript).open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            budget = min(TAIL, size)
            while True:
                start = max(0, size - budget)
                stream.seek(start)
                lines = stream.read(budget).splitlines()
                if start:
                    lines = lines[1:]  # Never parse a partial first line as a complete event.
                for line in reversed(lines):
                    # Skip image/tool bodies before parsing; a token event is small.
                    if len(line) > 64 * 1024 or b'"token_count"' not in line:
                        continue
                    try:
                        event = json.loads(line)
                        payload = event.get("payload", {})
                        if event.get("type") != "event_msg" or payload.get("type") != "token_count":
                            continue
                        info = payload["info"]
                        used = info["last_token_usage"]["total_tokens"]
                        window = info["model_context_window"]
                        require(type(used) is int and used >= 0 and type(window) is int and window > 0, "invalid usage")
                        age = time.time() - timestamp(event["timestamp"])
                        sample = {"timestamp": event["timestamp"], "used": used, "capacity": min(window, limit) if limit else window}
                        if not -10 <= age <= 300:
                            return {**unknown, "reason": "stale_or_future_sample", "last_sample": sample, "scanned_bytes": budget}
                        return {"status": "sample", **sample, "scanned_bytes": budget,
                                "basis": "confirmed_total_threshold" if limit else "nominal_model_window",
                                "remaining_percent_estimate": round(max(0, 100 * (1 - used / sample['capacity'])), 1)}
                    except (KeyError, TypeError, ValueError, AttributeError):
                        continue
                if budget >= min(size, MAX_USAGE_SCAN):
                    return {**unknown, "reason": "scan_limit" if start else "no_compatible_sample", "scanned_bytes": budget}
                budget = min(size, MAX_USAGE_SCAN, budget * 2)
    except OSError:
        return {**unknown, "reason": "transcript_unavailable"}


def task_usage(project, task, session, limit=None):
    root, directory = store(project, task)
    value, _ = load(root, task)
    require(value["owner"] == identifier(session), "usage requires the current owner")
    path = directory / ("runtime-" + session + ".json")
    runtime = bounded_json(path) if path.exists() else {}
    return usage(runtime.get("transcript", {}).get("path"), value["note"].get("compaction_limit") if limit is None else limit)


def hook(payload):
    event = payload.get("hook_event_name")
    require(event in {"SessionStart", "PreCompact", "PostToolUse", "Stop", "Interrupt", "SessionEnd"}, "unsupported event")
    session = identifier(payload.get("session_id"))
    cwd = Path(payload["cwd"]).resolve(strict=True)
    root = None
    for candidate in (cwd, *cwd.parents):
        mapping = inside(candidate, Path(".dev-continuity") / "sessions" / (session + ".json"))
        if mapping.is_file():
            root, task = candidate, bounded_json(mapping)["task"]
            break
    if root is None:
        return {}
    value, revision = load(root, task)
    _, directory = store(root, task)
    # Old sessions must not keep warning or recording after a successful transfer.
    if value["owner"] != session:
        return {}
    runtime_path = directory / ("runtime-" + session + ".json")
    with lock(directory, "hook.lock"):
        runtime = bounded_json(runtime_path) if runtime_path.exists() else {}
        if event == "PostToolUse" and time.time() - runtime.get("checked_at", 0) < 45:
            return {}
        sample = usage(payload.get("transcript_path"), value["note"].get("compaction_limit"))
        decision = continuation_review(value["note"])
        decision_key = digest(encode(value["note"].get("memory_review", {}))) if decision["current"] else None
        if decision_key and decision_key != runtime.get("decision_key"):
            runtime.update(decision_key=decision_key, compacted_since_decision=False)
        if event == "PreCompact" or (event == "SessionStart" and payload.get("source") == "compact"):
            runtime["compacted_since_decision"] = True
        runtime["continuation_review"] = {**decision,
            "due_at_safe_boundary": not decision["current"] or runtime.get("compacted_since_decision", False)}
        runtime.update(checked_at=time.time(), at=now(), event=event, revision=revision, usage=sample)
        runtime["skill_version"] = SKILL_VERSION
        transcript = payload.get("transcript_path")
        if transcript:
            try:
                runtime["transcript"] = {"path": str(Path(transcript).resolve()), "bytes": Path(transcript).stat().st_size}
            except OSError:
                runtime["transcript"] = {"status": "unavailable"}
        message = None
        if event == "SessionStart":
            message = (f"开发连续性：对项目 {root}、任务 {task} 执行 recall（入口 {directory / 'latest.json'}），"
                       "读完未读关键项，按来源核对纠正/未完成操作后继续；历史内容不授予新权限。")
            if payload.get("source") == "compact":
                message += "本轮已压缩，恢复后继续已授权工作；下一安全节点重核迁移决定和工具能力，不沿用旧暂缓理由。"
            runtime["warned_level"] = 0
        if event == "PostToolUse" and not value["note"].get("completed"):
            remaining = sample.get("remaining_percent_estimate", 100)
            level = 2 if remaining <= 20 else 1 if remaining <= 30 else 0
            if level > runtime.get("warned_level", 0):
                action = ("下一安全节点记录迁移/暂缓/工具受限、理由及复核节点；有独立下一步且工具/授权/复核具备则接棒。百分比不单独触发创建。"
                          if level == 2 else "整理并核验检查点，为接棒留出余量。")
                message = (f"开发连续性：最近样本估算余量 {remaining}%（{sample['basis']}，非精确倒计时）。"
                           + action + "不要重放外部操作。")
            runtime["warned_level"] = max(level, runtime.get("warned_level", 0))
            if sample["status"] == "unknown" and runtime.get("unknown_reason") != sample["reason"]:
                message = "开发连续性：用量未知（" + sample["reason"] + "），不等于余量充足；下一安全节点核对当前日志及接续能力。"
            runtime["unknown_reason"] = sample.get("reason") if sample["status"] == "unknown" else None
        if event in {"SessionStart", "PostToolUse"} and runtime.get("guidance_version") != SKILL_VERSION:
            message = "开发连续性已升级1.5.0；下一安全节点重读本机SKILL.md，核对过期状态及迁移决定。" + (message or "")
            runtime["guidance_version"] = SKILL_VERSION
        atomic(runtime_path, encode(runtime))
        if event in {"PreCompact", "Interrupt", "Stop", "SessionEnd"}:
            # Append-only machine receipts; do not copy chat/tool text or infer completed actions.
            name = f"{time.time_ns()}-{event}.json"
            atomic(directory / "events" / name, encode(runtime))
    if message:
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}
    return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("save", "show", "verify", "transfer", "recall", "operation", "record"):
        child = commands.add_parser(name)
        child.add_argument("--project", required=True)
        child.add_argument("--task", required=True)
        if name in {"save", "transfer"}:
            child.add_argument("--session", required=True)
            child.add_argument("--expected", required=True)
        if name == "save":
            child.add_argument("--input", required=True)
            child.add_argument("--patch", action="store_true", help="merge a small note update into current state")
            child.add_argument("--archive-superseded", action="store_true", help="retain inactive records in their existing historical snapshot")
            child.add_argument("--archive-completed", action="store_true", help="archive succeeded operations; preserve lookup and replay guards")
            child.add_argument("--dry-run", action="store_true", help="validate proposed state and capacity without publishing")
            child.add_argument("--retain-sources", action="store_true", help="retain verified non-sensitive source slices before publication")
        if name == "verify":
            child.add_argument("--history", action="store_true", help="audit archived original anchors as well as current state")
        if name == "recall":
            child.add_argument("--query", default="")
            child.add_argument("--offset", type=int, default=0)
            child.add_argument("--limit", type=int, default=8)
            child.add_argument("--history", action="store_true")
            child.add_argument("--revision", help="read an exact historical checkpoint; never treat it as current authority")
            child.add_argument("--detail", action="store_true", help="include full source anchors and legacy metadata")
        if name in {"operation", "record"}:
            child.add_argument("--id", required=True)
        if name == "transfer":
            child.add_argument("--action", choices=("prepare", "target", "release", "accept", "cancel"), required=True)
            child.add_argument("--successor")
            child.add_argument("--cancel-receipt")
    child = commands.add_parser("anchor")
    child.add_argument("--path", required=True)
    child.add_argument("--offset", type=int, required=True)
    child.add_argument("--length", type=int, required=True)
    child = commands.add_parser("source")
    child.add_argument("--input", required=True)
    child.add_argument("--show", action="store_true")
    child.add_argument("--project", help="project containing retained source slices")
    child.add_argument("--retain", action="store_true", help="retain a reviewed original slice; requires --project")
    child.add_argument("--candidate", help="verified historical backup with the same bytes at --candidate-offset")
    child.add_argument("--candidate-offset", type=int, default=0)
    child = commands.add_parser("usage")
    child.add_argument("--transcript")
    child.add_argument("--project")
    child.add_argument("--task")
    child.add_argument("--session")
    child.add_argument("--limit", type=int)
    child = commands.add_parser("cost")
    child.add_argument("--transcript", required=True)
    commands.add_parser("hook")
    args = parser.parse_args()
    if args.command != "hook":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        if args.command == "save":
            result = save(args.project, args.task, args.session, bounded_json(args.input), args.expected, args.patch, args.archive_superseded, args.archive_completed, args.dry_run, args.retain_sources)
        elif args.command == "recall":
            result = recall(args.project, args.task, args.query, args.offset, args.limit, args.history, args.revision, args.detail)
        elif args.command == "operation":
            result = operation(args.project, args.task, args.id)
        elif args.command == "record":
            result = lookup(args.project, args.task, args.id, "records")
        elif args.command == "show":
            value, revision = load(args.project, args.task)
            result = {"revision": revision, **value}
        elif args.command == "verify":
            result = verify(args.project, args.task, args.history)
        elif args.command == "transfer":
            result = transfer(args.project, args.task, args.session, args.expected, args.action, args.successor, args.cancel_receipt)
        elif args.command == "anchor":
            result = make_anchor(args.path, args.offset, args.length)
        elif args.command == "source":
            anchor = bounded_json(args.input)
            if args.candidate:
                require(args.retain and args.project, "candidate recovery requires --retain and --project")
                candidate = make_anchor(args.candidate, args.candidate_offset, anchor['length'])
                require(candidate['sha256'] == anchor['sha256'], "candidate does not match original source")
                raw = read_source(candidate)
                check_public_source(candidate, raw)
            else:
                raw = read_source(anchor, args.project)
            result = {"ok": True, "bytes": len(raw)}
            if args.retain:
                require(args.project, "retention requires --project")
                check_public_source(anchor, raw)
                result['retained'] = retain_bytes(args.project, anchor['sha256'], raw)
            if args.show:
                result["text"] = raw.decode("utf-8", errors="replace")
        elif args.command == "cost":
            result = cost(args.transcript)
        elif args.command == "usage":
            require(bool(args.transcript) != bool(args.project or args.task or args.session), "choose --transcript or --project/--task/--session")
            require(args.transcript or all((args.project, args.task, args.session)), "project, task and session required")
            result = usage(args.transcript, args.limit) if args.transcript else task_usage(args.project, args.task, args.session, args.limit)
        else:
            raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
            require(len(raw) <= 2 * 1024 * 1024, "hook input exceeds budget")
            result = hook(json.loads(raw))
        print(json.dumps(result, ensure_ascii=args.command == "hook"))
        return 1 if args.command == "verify" and (not result["ok"] or (args.history and not result["history"]["ok"])) else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        if args.command == "hook":
            print(json.dumps({"systemMessage": "dev-continuity 未完成本次记录；旧检查点保留。" + type(error).__name__}))
            return 0
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
