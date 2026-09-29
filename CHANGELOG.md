# Changelog

## 1.6.0 — 2026-09-29

### Memory completeness before cost reduction

- The Skill now explicitly preserves the complete authorized goal across finite batches. It reuses the project's authoritative requirements table and existing critical requirement records, source anchors and dependency hashes. Agents reconcile scope on relevant changes, batch completion and before claiming goal completion; no second requirements database or new schema is introduced.
- Clarified six essential memory categories, including decision reasons, failed attempts and retry conditions. Material changes trigger incremental saves; unchanged context does not require repeated saves, full-history reads or repeated Skill loading. Relevant detail is retrieved by module/question and original record ID.
- Native Codex memory is a retrieval aid for stable preferences, lessons and historical pointers. Current project records and live evidence establish task state. The Skill does not directly edit generated memories or grant itself permission to write long-term rules.

### Recovery fix and validation

- The first unfiltered `recall` page now returns the existing `decisions` and `evidence` fields. Previously they were omitted even from the detailed view, making it possible to recover progress without its rationale or verification limits. Pagination and targeted queries avoid repeating those fields.
- Regression checks cover CLI recovery, non-repeated pagination, a full goal surviving all four handoff phases, and changed authoritative requirements invalidating a dependency-bound critical record even when the old source slice remains readable.
- Scope reconciliation is an agent instruction, not an automatic semantic coverage detector. Tests establish script behavior, not guaranteed long-term recall. No private audit records or transcripts are distributed, and no net token-savings claim is made.

### Upgrade

- Schema 4, policy 3, setting inheritance, source retention, replay guards and installer defaults are unchanged. Existing checkpoints and pending handoffs require no migration; installation does not mutate project state.
- Reload the Skill at the next safe boundary. The current writer can then add missing full-scope references using existing records; do not rewrite another active task's checkpoints.
- No new dependencies, model calls, background scheduler or polling. More complete first-page output has a small payload cost; avoid duplicating long reports in `decisions/evidence`.

## 1.5.1 — 2026-09-22

- Fixed omitted `thinking` during handoff: explicit user settings take priority; otherwise preparation inherits the current owner's latest `turn_context.effort` from its runtime transcript. An explicit user request to restore defaults remains supported. Model overrides still require an explicit user choice.
- Preparation checks transcript session identity, reads at most an 8 MiB tail plus a bounded header, and rejects missing/unknown evidence before reserving a successor. It never falls back to an older effort when the latest turn has an unsupported value.
- Resolved settings and their source are frozen in the handoff receipt and returned throughout target/release/accept. Host creation must pass these values, and actual successor settings must be checked before accepting ownership. The script does not itself control the host or enforce this host-level check.
- Regression tests cover latest effort changes, frozen settings, explicit overrides/default reset, missing or mismatched transcripts, unknown effort and scan bounds. The offline demonstration now exercises inherited `high`.
- Schema 4 and policy 3 remain compatible; existing pending handoffs retain their previous behavior. Installation does not rewrite project state or global defaults. No dependencies, polling or model calls were added; no measured token-savings claim is made.

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
