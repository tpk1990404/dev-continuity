# 记忆格式：当前、原文与归档

复用项目权威文档。记录只留必要结论和原文 anchor（路径、字节范围、哈希）；缺依据标 unverified，不以自己新写的摘要冒充用户原文。秘密与个人敏感信息不入笔记。

## 关键记录

records 按 ID 合并，省略或空数组不删除旧记录：

```json
{"records":[{"id":"login-status-v2","kind":"validation","text":"此版本已加载；真机未验。","scope":"login/deployment","status_key":"current","basis":"runtime","state":"confirmed","critical":true,"sources":[],"depends_on":{},"reason":"发布回执替代原未部署状态"}]}
```

sources 必须换成真实 anchor；这是格式示例，不是可直接确认的事实。

- kind：requirement、constraint、decision、validation、operation。basis：user、file、runtime、e2e、inference；推测只能 unverified。
- critical 表示恢复必读的目标、权限、禁止、未完成及验收边界，不是历史重要程度。新条目先判断是否替代同一现状或重复要求；不要只追加“继续工作”等同义指示。
- text 最多 2000 字符，sources 最多 10 个 anchor；depends_on 是项目相对路径到 SHA-256 的映射，只绑定会使结论失效的文件。
- status_key 适用于 validation/operation 版本状态；同 scope 同 key 的新记录自动 supersedes 旧状态，须给 reason。一个 key 只表达一个状态维度，不覆盖仍有效约束或其他验收层。
- 旧记录没有 status_key 时不猜测归组，需核对后显式 supersedes 同 scope 的旧 ID，或将完成证据转历史。正文不可原位修改；纠正新增 ID，decision/correction 须说明原因，继承旧关键性。

发布后替代“未部署”现状，保留当时测试和尚未完成的设备验证；不能用来源未变证明旧“下一步”仍有效。

## 少量读取

```text
py -3 -X utf8 SCRIPT recall --project PROJECT --task TASK
py -3 -X utf8 SCRIPT recall --project PROJECT --task TASK --revision REV --offset NEXT_OFFSET
py -3 -X utf8 SCRIPT record --project PROJECT --task TASK --id RECORD_ID
py -3 -X utf8 SCRIPT operation --project PROJECT --task TASK --id OPERATION_ID
```

CLI recall 默认短视图，省略完整 anchors/依赖哈希及已完成操作。record / operation 按 ID 查当前和归档，返回历史标记与 revision；找不到或读取失败不能当作“允许再做”。recall --detail 保留 1.2 完整输出；Python recall 默认 detail=True，兼容既有调用。

每页默认 8 条。remaining_critical_ids 表示当前查询结果后续页；critical_outside_page_ids 表示不在本页，不能当作累计未读。query 分页不证明覆盖全部关键项。固定 revision，状态变化后重新核对。历史细查用 recall --revision REV --history --query 关键词，不作为当前指令。

## 增量保存与归档

```text
py -3 -X utf8 SCRIPT save --project PROJECT --task TASK --session SESSION --expected REV --input DELTA.json --patch --dry-run
py -3 -X utf8 SCRIPT save --project PROJECT --task TASK --session SESSION --expected REV --input DELTA.json --patch --archive-superseded --archive-completed
```

容量紧张、迁移或批量整理时先 dry-run，不必每次预检。verify 返回 capacity 与可归档数量；save 超限返回字段体积。当前正文仍限 48 KiB；冷快照至多 96 KiB，过大批次拆分。

--archive-superseded 移出已替代/已退役记录；--archive-completed 仅移出 SUCCEEDED 操作。FAILED、STARTED_UNKNOWN、NOT_STARTED 留在当前台账。归档操作仍按 ID 检查，禁止重置；完全相同的重存保持幂等。原 ID 不复用，不以新 ID 绕过单次许可。

没有后续替代状态的完成验证，可在 patch 中显式退役：

```json
{"retire_records":[{"id":"closed-validation","reason":"该版本验证已完成，作为历史证据保留"},{"id":"closed-release-record","reason":"本份发布许可已消费","operation_id":"original-release-operation"}]}
```

只允许 confirmed 且有可读来源的 file/runtime/e2e 验证或操作退役。操作记录须关联 SUCCEEDED 台账 ID，且来源指向同一项目内回执。用户要求、约束、决策不能退役；归并或纠正使用同 scope 的 supersedes，合并正文覆盖全部仍有效含义，原文 anchor 不省略。新决定覆盖旧措辞时明确替代，不能把“在电脑旁”等临时可用状态当永久权限。未完成、未知和仍影响当前验收的内容不得为省空间退役。

固定长度 archive_head 指向归档链；旧 record_archives 仍可读，首次归档后移入链中。先写包含退役原因和正文的不可变快照，再发布短入口；失败保留上一入口，可能有未引用快照，勿盲删。链丢失/损坏阻止复核和安全查重，不能解释为没有历史。

其他列表如 next/evidence 仍完整替换，先核对当前字段。archive_head、record_archives、recorded、superseded_by、retired 由脚本管理，不能手填绕过检查。

## 交接复核

对照原始要求、纠正和证据，核对目标/完成标准、禁止事项、未完成、未验证、不可重复操作和下一步权限；检查重复与过时状态。verify 的 advisory 可提示重复正文，无法识别所有语义矛盾。

完成内容核对后，把 verify 的 memory_basis_sha256 和完整 critical_ids 写入小 patch：

```json
{"memory_review":{"basis_sha256":"实际值","critical_ids":["实际关键ID"]}}
```

save --patch 后 verify 确认 handoff_ready。正文变化使复核失效；来源/依赖/归档变化也会阻止交接。复核不是自动证明完整或新授权。

容量超过80%时先归并重复、归档完成证据和压短入口。确实都是必要约束时可在同次 memory_review 加 capacity_reason（不超过500字符），说明不能缩减的具体原因；prepare 否则拒绝新交接。不是要求删除事实，也不阻止当前任务继续修复记录。memory_review 仍需基于实际核对，不能机械复制摘要充当语义审查。

## 原文耐久性

优先引用现有不可变报告。对会改写的文件，save --retain-sources 将本次当前及即将归档记录的已核验原文片段存入项目 .dev-continuity/sources/SHA256.txt；旧来源路径、字节范围和哈希不改。dry-run 不写片段；每段至多16KiB，只保留复核过的非敏感内容，不复制聊天全集。自动检查仅拦截明显秘密，不能替代人工脱敏。

read_source/record/verify 在原位置失配时，核对本项目相同SHA的保留片段；它证明当时原文，不证明当前状态。代码验证仍使用 depends_on 检测适用版本变化。跨目录/机器迁移要连同片段安全搬运，不能只复制 latest.json。

source --project PROJECT --input ANCHOR.json --retain 可显式保存某段。原文已改写时，仅能用 --candidate BACKUP --candidate-offset OFFSET 从真实旧备份恢复，字节必须匹配原哈希；不从摘要重写“原文”。找不到则保留失配状态。

verify --history 按需审计历史原文，单独返回 history.ok，历史失配也返回非零退出码；当前 ok 与历史原文完整性不能混称。普通 verify 不重复扫描历史原文内容。

1.1/1.2/1.3（schema 1/2）可读；1.4新保存使用schema 3，旧脚本拒绝误读，避免忽略保留片段或接续约定。已有预约可按原策略完成，不擅改 owner。安装回滚只恢复Skill文件，不能回退后写schema 3数据；数据恢复须保留升级后进展，由当前 writer 核对。
