# Changelog

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
