# Changelog

## 1.5.0 — 2026-09-22

Fixes demonstrated during long-running task audits. No private task records, transcripts or account data are included.

### Fixed

- Usage sampling starts with a 256 KiB tail and expands only when needed, up to an 8 MiB range. Large image/tool records no longer hide nearby fresh token events within that bound. Unknown results distinguish stale samples, missing files, incompatible events and scan limits.
- `usage --project PROJECT --task TASK --session SESSION` follows the current owner's runtime transcript path after log rotation. Explicit `--transcript` remains supported.
- High-pressure, compaction and batch boundaries now require an explicit migrate/defer/unavailable decision, reason, capability status and next review point. Hooks flag renewed review after compaction; unavailable tools do not masquerade as successful automation.
- New handoffs require acknowledgement that goal, progress, decisions, evidence and next steps were compared. Temporary validation observations can carry `valid_until`; expired critical observations block handoff while preserving their source.
- All-critical current collections receive a maintenance advisory. New handoffs above 95% note capacity are blocked even with an exception reason; 80–95% still requires a concrete retention reason.

### Validation and cost boundaries

- Regression coverage includes large image output, bounded scans, stale samples, transcript changes, unavailable tools, stale decisions, expired observations, capacity limits and completing an existing legacy handoff.
- The installer smoke test allows cold PowerShell startup on hosted Windows runners; production hook timeouts are unchanged.
- Hooks retain throttling and deduplication, add no model calls and do not create tasks themselves. One upgrade hint asks active owners to reload the Skill at a safe boundary.
- Semantic review is an acknowledgement, not a claim of automatically detecting every contradiction. No claim of measured net token savings or guaranteed uninterrupted execution.

### Upgrade

- Reads schemas 1/2/3/4; new saves and transfer writes use schema 4. Installation does not rewrite project checkpoints.
- Existing policy 1/2 handoffs can finish under their original checks. New reservations use policy 3 and `new_handoff_ready`; `handoff_ready` retains its legacy meaning.
- After schema 4 writes, do not resume those tasks with 1.4 or restore an old state pointer. File rollback and task-state recovery are separate.
- Installer defaults, opt-in rules/hooks, ownership, source retention and replay protection are unchanged.

## 1.4.0 — 2026-09-20

First public open-source release. Earlier versions were used locally; no private project records or chat logs are included.

### Continuity

- Bounded current records, immutable source anchors, archived receipts, and revision-checked writes.
- Four-stage ownership transfer with replay guards and finite batch requirements.
- User-evidenced model/reasoning settings preserved across full saves and handoffs.
- Optional retained source slices and separate historical integrity checks.
- Capacity maintenance before new handoffs, deduplicated usage reminders, and observed token accounting.

### Public distribution

- Chinese and English introductions, usage examples, MIT license, contribution and security guidance.
- Skill-only installation by default; global rules and hooks require explicit flags.
- Current documented skill location and configurable destinations; unrelated personal rules preserved.
- Windows/Ubuntu CI for Python 3.11 and 3.14, with a disposable offline example.

### Compatibility

Reads checkpoint schemas 1/2; new saves use schema 3. File rollback does not roll back task state. Automatic task creation requires host tools and explicit user authorization. This release does not claim measured net token savings or support every Codex host integration.
