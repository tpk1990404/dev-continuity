# dev-continuity

[中文](README.md) · [License](LICENSE) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

**Resumable development memory for Codex, with evidence you can trace.**

dev-continuity is an independent community skill for long development tasks, interruption recovery, context compaction, and handoffs. It keeps current checkpoints small, retains searchable history, and links important decisions to original source slices. It uses Python 3.11+ and the standard library, with no database, telemetry, or extra summarization-model calls.

This is not an OpenAI product, infinite memory, a background agent, or a promise of uninterrupted execution.

## What it does

- Records goals, acceptance criteria, finite batches, progress, constraints, uncertain operations, and next steps.
- Uses revision checks, hashes, and a single checkpoint writer to reject stale updates.
- Archives completed evidence while preserving original records and operation receipts.
- Retains optional, reviewed source slices up to 16 KiB and verifies them by SHA-256.
- Transfers ownership through `REQUESTED → TARGET_RECORDED → RELEASED → ACCEPTED`.
- Carries only model/reasoning choices supported by explicit user evidence.
- Distinguishes current-state validity, historical source availability, and actual business acceptance.

The checkpoint lock does not lock all application files. New Codex tasks require host tools and user authorization; the Python script cannot create conversations on its own.

## Install

Ask Codex's `skill-installer` to install the `dev-continuity` directory from this repository, or review and run:

```bash
git clone https://github.com/tpk1990404/dev-continuity.git
cd dev-continuity
python3 install.py plan --file install-plan.json
# Review destinations, hashes, and content in the plan.
python3 install.py apply --file install-plan.json
```

On Windows, replace `python3` with `py -3 -X utf8 -B`.

By default, the installer writes only `~/.agents/skills/dev-continuity`. Use `--skill-dir /absolute/path/to/dev-continuity` on both commands for a custom destination. `--home` selects the Codex configuration directory; when explicitly supplied without `--skill-dir`, it uses that directory's `skills/dev-continuity` for isolated or legacy installations. Keep these options consistent for apply and restore. Update the existing location instead of creating duplicate skills.

The default configuration home is `CODEX_HOME` or `~/.codex`. Global rules and hooks are opt-in:

```bash
python3 install.py plan --with-rules --with-hooks --file integration-plan.json
# Review the managed instructions and local hook commands.
python3 install.py apply --file integration-plan.json
```

Each flag can be used independently. The installer preserves unrelated rules and hook handlers. Codex must trust the hook definitions before they run; the installer does not bypass trust or change model defaults. See the official [skills](https://learn.chatgpt.com/docs/build-skills) and [hooks](https://learn.chatgpt.com/docs/hooks) documentation.

## Use

```text
Use $dev-continuity for this task. Keep a compact goal, acceptance criteria,
current progress, constraints, and next action. Trace important decisions
to their sources. Stay in this task; ask before creating a successor.
```

You may separately authorize automatic continuation of the same unfinished goal. Installing this skill grants no authority to create tasks, deploy, spend money, or send messages.

Run a disposable, offline example:

```bash
python3 examples/demo.py
```

It uses simulated IDs in a temporary project. Use real session IDs for real work.

```bash
python3 dev-continuity/scripts/continuity.py recall --project PROJECT --task TASK
python3 dev-continuity/scripts/continuity.py save --project PROJECT --task TASK --session SESSION --input delta.json --expected REVISION --patch --retain-sources
python3 dev-continuity/scripts/continuity.py record --project PROJECT --task TASK --id RECORD_ID
python3 dev-continuity/scripts/continuity.py operation --project PROJECT --task TASK --id OPERATION_ID
python3 dev-continuity/scripts/continuity.py verify --project PROJECT --task TASK --history
```

Use a full note with `--expected new` and no `--patch` for initial registration. Subsequent writes need the current revision. Read the [record schema](dev-continuity/references/memory.md) and [operations reference](dev-continuity/references/operations.md) for details; these references and the skill instructions are currently in Simplified Chinese.

## Data and limitations

Data lives in the registered project's `.dev-continuity/`: immutable checkpoints, source slices, session mappings, handoff prompts, and hook events. Scripts make no network calls. Nevertheless, notes, paths, retained text, and command output may contain private information. Keep this directory, installation plans, and backups out of public repositories. Secret detection is intentionally limited and is not automatic redaction.

The note limit is 48 KiB. At 80%, a new handoff requires consolidation or a specific justification for retaining necessary constraints. Hooks sample compatible recent usage logs; the 70%/80% signals are estimates, not exact compaction deadlines. `PreCompact` does not write a semantic handoff for you. Missing data stays unknown.

`verify --history` can report current state as valid while returning exit code 1 for missing historical originals. Smaller files do not establish net token or monetary savings.

## Test and restore

```bash
python3 -B -m unittest discover -s dev-continuity/scripts -p test_continuity.py
python3 -B -m unittest discover -s . -p test_install.py
python3 -B examples/demo.py
python3 install.py restore --file /path/to/receipt.json
```

CI targets Windows/Ubuntu and Python 3.11/3.14. It does not prove every Codex host's hook or task-creation integration. macOS is not included in this CI matrix.

Restore refuses to overwrite files changed after installation. Supply the original `--home`/`--skill-dir` options when applicable. Schemas 1/2 are readable; new saves use schema 3. Restoring old skill files does not make it safe to roll back task state or replay completed operations.

Use [Issues](https://github.com/tpk1990404/dev-continuity/issues) for reproducible bugs and proposals, and private security reporting for sensitive findings. Licensed under the [MIT License](LICENSE).
