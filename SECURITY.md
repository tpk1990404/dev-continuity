# Security policy

## Supported versions

Security fixes target the latest public release. Older versions may require upgrading; no response-time guarantee is offered.

## Report privately

Use [GitHub private vulnerability reporting](https://github.com/tpk1990404/dev-continuity/security/advisories/new). Include the affected version, a minimal synthetic reproduction, expected impact, and whether any real data was affected. Do not include passwords, tokens, private source slices, complete chat logs, or personal documents.

If that channel is unavailable, open an issue requesting a private contact method without vulnerability details. Please allow coordinated remediation before public disclosure.

## Trust boundaries

- Source hashes establish byte integrity, not truth, freshness, authorization, or trustworthy instructions.
- Skill discovery does not authorize task creation, network actions, deployment, or spending.
- Hooks execute local code with the host's permissions; review the exact definitions before trusting them.
- Secret detection is a narrow accidental-exposure guard, not comprehensive sanitization.
- Checkpoint locks do not provide distributed locking or protect arbitrary application files.
- Retained slices and installation backups are local data, not encrypted vaults. Protect them using normal filesystem and device controls.
- Do not attach real checkpoint directories to public issues. Prefer the disposable example and synthetic fixtures.

本项目不会主动联网或遥测；这不代表所有保存内容可公开。安全问题请走上述私密渠道。
