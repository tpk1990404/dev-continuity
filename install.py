"""Install reviewed dev-continuity files; preserve unrelated settings and backups."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import tempfile

BASE = Path(__file__).resolve().parent
BEGIN, END = "<!-- dev-continuity:start -->", "<!-- dev-continuity:end -->"


def sha(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def put(path, raw):
    if path.parent.resolve() != path.parent.absolute() or path.is_symlink():
        raise ValueError("refuse linked install path")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".dev-continuity-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def make_plan(home, skill_dir=None, with_rules=False, with_hooks=False):
    skill = skill_dir or home / "skills" / "dev-continuity"
    changes = {}
    if with_rules:
        global_path = home / "AGENTS.md"
        original = global_path.read_bytes() if global_path.exists() else b""
        fragment = (BASE / "global-rule.md").read_bytes().strip()
        begin, end = BEGIN.encode(), END.encode()
        if begin in original or end in original:
            if original.count(begin) != 1 or original.count(end) != 1 or original.index(begin) > original.index(end):
                raise ValueError("ambiguous managed global section")
            raw = re.sub(re.escape(begin) + b".*?" + re.escape(end), lambda _: fragment, original, flags=re.S)
        else:
            raw = original + (b"\n\n" if original else b"") + fragment + b"\n"
        changes[global_path] = raw
    for source in sorted((BASE / "dev-continuity").rglob("*")):
        if source.is_file() and "__pycache__" not in source.parts:
            changes[skill / source.relative_to(BASE / "dev-continuity")] = source.read_bytes()
    if with_hooks:
        hook_path = home / "hooks.json"
        hooks = json.loads(hook_path.read_text(encoding="utf-8-sig")) if hook_path.exists() else {}
        events = hooks.setdefault("hooks", {})
        script = skill / "scripts" / "continuity.py"
        command = shlex.join([sys.executable, str(script), "hook"])
        # py is the native Windows launcher; a quoted executable alone is not a PowerShell invocation.
        windows_command = f'py -3 "{script}" hook' if shutil.which("py") else f'python "{script}" hook'
        for event in ("SessionStart", "PreCompact", "PostToolUse", "Stop", "Interrupt", "SessionEnd"):
            groups = events.setdefault(event, [])
            for group in groups:
                handlers = group.get("hooks", [])
                group["hooks"] = [h for h in handlers if h.get("statusMessage") != "dev-continuity"]
            groups[:] = [g for g in groups if g.get("hooks")]
            handler = {"type": "command", "command": command, "commandWindows": windows_command,
                       "timeout": 3, "statusMessage": "dev-continuity"}
            if event in {"SessionStart", "PostToolUse"}:
                handler["additionalContextLimit"] = 300
            groups.append({"hooks": [handler]})
        changes[hook_path] = (json.dumps(hooks, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    plan = []
    for path, raw in changes.items():
        if not (path in {home / "AGENTS.md", home / "hooks.json"} or path.is_relative_to(skill)) or path.resolve() != path or path.is_symlink():
            raise ValueError("install path escapes home")
        before = path.read_bytes() if path.exists() else None
        if raw != before:
            plan.append({"path": str(path), "before_sha256": sha(before), "after_sha256": sha(raw),
                         "content": raw.decode("utf-8")})
    return plan


def apply(home, plan_path, skill_dir=None):
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    allow = {home / "AGENTS.md", home / "hooks.json"}
    skill = skill_dir or home / "skills" / "dev-continuity"
    for item in plan:
        path = Path(item["path"])
        if path not in allow and not path.is_relative_to(skill):
            raise ValueError("unexpected destination")
        if path.resolve() != path or sha(path.read_bytes() if path.exists() else None) != item["before_sha256"]:
            raise ValueError("destination changed after review: " + str(path))
        if sha(item["content"].encode("utf-8")) != item["after_sha256"]:
            raise ValueError("plan content checksum mismatch")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = home / "backups" / "dev-continuity" / stamp
    receipt = {"installed_at": stamp, "files": [], "status": "PREPARED"}
    for index, item in enumerate(plan):
        path = Path(item["path"])
        record = {k: v for k, v in item.items() if k != "content"}
        if path.exists():
            original = backup / (str(index) + ".original")
            put(original, path.read_bytes())
            record["backup"] = str(original)
        receipt["files"].append(record)
    receipt_path = backup / "receipt.json"
    put(receipt_path, json.dumps(receipt, indent=2).encode("utf-8"))
    # receipt exists before any destination changes; a crash can be recovered conservatively.
    for item in plan:
        path = Path(item["path"])
        if sha(path.read_bytes() if path.exists() else None) != item["before_sha256"]:
            raise ValueError("destination changed during install")
        put(path, item["content"].encode("utf-8"))
    receipt["status"] = "INSTALLED"
    put(receipt_path, json.dumps(receipt, indent=2).encode("utf-8"))
    return {"receipt": str(receipt_path), "files": len(plan)}


def restore(home, receipt_path, skill_dir=None):
    skill = skill_dir or home / "skills" / "dev-continuity"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    for item in receipt["files"]:
        path = Path(item["path"])
        if path.resolve() != path or not (path in {home / "AGENTS.md", home / "hooks.json"} or path.is_relative_to(skill)):
            raise ValueError("restore escapes home")
        current_hash = sha(path.read_bytes() if path.exists() else None)
        if current_hash not in {item["before_sha256"], item["after_sha256"]}:
            raise ValueError("file changed since install; refusing to overwrite: " + str(path))
        if item.get("backup") and sha(Path(item["backup"]).read_bytes()) != item["before_sha256"]:
            raise ValueError("backup checksum mismatch")
    for item in reversed(receipt["files"]):
        path = Path(item["path"])
        if path.resolve() != path or not (path in {home / "AGENTS.md", home / "hooks.json"} or path.is_relative_to(skill)):
            raise ValueError("restore escapes home")
        current = path.read_bytes() if path.exists() else None
        if sha(current) == item["before_sha256"]:
            continue
        if sha(current) != item["after_sha256"]:
            raise ValueError("file changed since install; refusing to overwrite: " + str(path))
        put(receipt_path.parent / (path.name + ".installed-backup"), current)
        if item.get("backup"):
            raw = Path(item["backup"]).read_bytes()
            if sha(raw) != item["before_sha256"]:
                raise ValueError("backup checksum mismatch")
            put(path, raw)
        else:
            path.unlink()  # Exact installed file, verified and backed up; no recursive deletion.
    return {"restored": True}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("plan", "apply", "restore"))
    p.add_argument("--home", help="Codex config directory; defaults to CODEX_HOME or ~/.codex")
    p.add_argument("--skill-dir", help="Exact skill destination; defaults to ~/.agents/skills/dev-continuity (custom --home uses HOME/skills/dev-continuity)")
    p.add_argument("--with-rules", action="store_true", help="plan: opt in to the managed AGENTS.md section")
    p.add_argument("--with-hooks", action="store_true", help="plan: opt in to lifecycle hooks; Codex trust is still required")
    p.add_argument("--file", required=True)
    a = p.parse_args()
    home = Path(a.home or os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
    skill = Path(a.skill_dir).expanduser().resolve() if a.skill_dir else ((home / "skills/dev-continuity") if a.home else (Path.home() / ".agents/skills/dev-continuity").resolve())
    path = Path(a.file).resolve()
    if a.action == "plan":
        plan = make_plan(home, skill, a.with_rules, a.with_hooks)
        put(path, (json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        print(json.dumps({"plan": str(path), "changed_files": len(plan), "destinations": [x["path"] for x in plan]}, ensure_ascii=False))
    else:
        print(json.dumps(apply(home, path, skill) if a.action == "apply" else restore(home, path, skill)))
