# 记忆格式：当前、原文与归档

复用项目权威文档。记录只留必要结论和原文 anchor（路径、字节范围、哈希）；缺依据标 unverified，不以自己新写的摘要冒充用户原文。秘密与个人敏感信息不入笔记。

## 从完整目标恢复，不从最近批次猜测

不增加新格式，使用现有字段：

| 信息 | 保存位置 | 恢复时读取 |
| --- | --- | --- |
| 完整目标与需求入口 | goal/acceptance；一条 critical requirement 引用已有需求表 | 短入口必读；表在范围变化、批次结束、完成核对时按需查 |
| 用户要求、纠正 | requirement/constraint/decision + 原文 sources | 当前关键约束必读；其他按模块查询 |
| 技术取舍及理由 | decisions 短结论/record ID；decision 的 reason 与 sources | 当前步骤涉及的决定及被否决方案 |
| 完成及验证边界 | progress/evidence 短结论/报告路径；validation | 相关版本与环境；历史完成详情退出必读 |
| 失败尝试、未解问题 | validation + reason；blockers/next | 触发条件、已有排查、重试前提；未知操作另保留台账 |
| 当前现场和下一步 | files/preserve/operations/next | 脏文件、在途操作、可执行动作及完成条件 |

需求表每项保留已有编号、当前状态和证据/原因。batch.scope 只列本批条目引用；goal 不收窄为 batch。只有用户明确变更才能取消或后置原目标，外部阻塞不是删除需求的依据。没有现成表时，在现有项目计划中补最短清单，不再造台账。

完整需求入口可用现有 critical requirement 的 sources 引用原文、depends_on 绑定权威表的 SHA-256。表变化会使旧入口校验失败；核对新表、全部仍有效要求及用户纠正后，用同 scope 新 ID 和 reason 显式 supersedes，重新复核。保留片段只证明旧原文，不能绕过依赖变化。不要把经常追加流水的综合日志绑定成范围文件，以免无关更新触发全量复核。

这些是代理的内容核对责任。脚本只检查来源、依赖和复核声明，不会理解需求表或自动发现语义遗漏；没有登记完整范围的旧任务，安装不会自动补齐。

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
- 临时观察用 kind=validation 和带时区的 valid_until（ISO 8601）；basis=user 的临时在线观察有此字段才可用 status_key。到期显示 expired_observation，关键观察阻止新交接，原文仍可查，绝不自动删除或扩大权限。valid_until 不可用于 requirement/constraint/decision/operation；既有记录不可补写，核对后新增同scope替代记录。
- 旧记录没有 status_key 时不猜测归组，需核对后显式 supersedes 同 scope 的旧 ID，或将完成证据转历史。正文不可原位修改；纠正新增 ID，decision/correction 须说明原因，继承旧关键性。

发布后替代“未部署”现状，保留当时测试和尚未完成的设备验证；不能用来源未变证明旧“下一步”仍有效。

## 少量读取

```text
py -3 -X utf8 SCRIPT recall --project PROJECT --task TASK
py -3 -X utf8 SCRIPT recall --project PROJECT --task TASK --revision REV --offset NEXT_OFFSET
py -3 -X utf8 SCRIPT record --project PROJECT --task TASK --id RECORD_ID
py -3 -X utf8 SCRIPT record --project PROJECT --task TASK --id RECORD_ID --source-index 0
py -3 -X utf8 SCRIPT operation --project PROJECT --task TASK --id OPERATION_ID
```

CLI recall 默认短视图，省略完整 anchors/依赖哈希及已完成操作。record / operation 按 ID 查当前和归档，返回历史标记与 revision；找不到或读取失败不能当作“允许再做”。recall --detail 保留 1.2 完整输出；Python recall 默认 detail=True，兼容既有调用。

1.7 的 recall --history --query 搜索固定 revision 可达的当前与归档记录，按 ID 去重、当前优先；历史行带 historical/record_revision，不算入当前必读欠项，也不授予执行权限。默认恢复不扫描归档正文。按 ID 查询先命中当前，未命中才读归档；历史损坏不能解释为没有记录。

record 默认只返回记录及原文位置；加 --source-index N 可读取第 N 个已确认非敏感片段（从0起），最多16KiB并校验原哈希，可回读保留原文。一次只取一个片段；不自动展开所有来源或整段聊天。明显秘密检查不替代人工脱敏，历史原文可读不证明当前结论有效。

1.6 首个无 query 页面同时返回 decisions/evidence，避免只恢复进度却遗漏取舍与验证边界；后续页不重复这部分。字段保持短结论和引用，长详情用 record/原文按需查。不要每轮 show 全文、每次都扫描历史或重新读同一 Skill；revision、相关依赖或实际问题变化才补读。项目明确要求完整阅读的文件仍须遵守。

每页默认 8 条。remaining_critical_ids 表示当前查询结果后续页；critical_outside_page_ids 表示不在本页，不能当作累计未读。query 分页不证明覆盖全部关键项。固定 revision，状态变化后重新核对。历史细查用 recall --revision REV --history --query 关键词，不作为当前指令。

## 增量保存与归档

### 安全维护

批量整理是当前 owner 在安全节点的一次有限任务，不增加每轮维护或定时清理。不要由另一对话冒用 owner 写入；准备期间 revision 变化则重新核对，不覆盖新进展。即使 dry-run 也会短暂申请写锁，独立检查应只读，执行预演交给当前 owner 或隔离副本。

先保留本次基线、拟变更清单及其可达归档、已保留原文片段和相关回执，核验备份可读、哈希一致；latest.json 只是入口，不是完整备份。原文在可变文件时先按“原文耐久性”保留已核非敏感片段；来源已失配则保留待核，不能用新摘要冒充原文。已有有效不可变证据可复用，不重复复制整个项目。

先从证据明确的少量已结束操作开始，核对退出当前待办后才使用下述归档命令。FAILED 标签、回执文件存在或后续成功均不单独证明本操作已结束；同一操作的原回执、重试条件和后续处理须对应。首批不混入要求/决定归并，不设必须缩短多少的目标。归并确有重复的要求时，逐项保留原文中的条件、例外、否定、理由和适用范围；有疑义不合并。

预演通过后再保存；逐个检查本批归档 ID 可查、原字段及回执保持、UNKNOWN/未执行项保持、未涉及字段未变，并从恢复入口核对目标/约束/验证边界和下一步。保存中断先查询实际入口；发现遗漏停止扩大维护。后续开发已推进时通过当前版本补偿修复本次变更，不能回退旧指针或用备份覆盖新进展、回执及操作状态。脚本验证保护机械一致性，原意是否完整仍需对照原文。

```text
py -3 -X utf8 SCRIPT save --project PROJECT --task TASK --session SESSION --expected REV --input DELTA.json --patch --dry-run
py -3 -X utf8 SCRIPT save --project PROJECT --task TASK --session SESSION --expected REV --input DELTA.json --patch --archive-superseded --archive-completed
```

容量紧张、迁移或批量整理时先 dry-run，不必每次预检。verify 返回 capacity 的计量口径和可归档数量；save 预演显示目标格式。当前正文限 48 KiB，按无排版空白的 UTF-8 JSON 计量；实际单个快照仍至多 96 KiB，哈希和原文编码保持。旧格式的在途预约按原计量核验。

--archive-superseded 移出已替代/已退役记录；--archive-completed 仅移出 SUCCEEDED 操作。FAILED 默认保持当前；STARTED_UNKNOWN、NOT_STARTED 必须保持当前。归档操作仍按 ID 检查，禁止重置；完全相同的重存保持幂等。原 ID 不复用，不以新 ID 绕过单次许可。

1.8允许把已确认结束、退出当前待办的失败显式归档，不再让历史失败永久挤占当前笔记：

```json
{"retire_operations":[{"id":"failed-attempt-id","reason":"已核对原回执，失败尝试已结束，后续候选另有回执；本项仅作历史查询"}]}
```

该输入随 save --patch 使用，无需额外归档开关。只接受上一检查点已为 FAILED、且本次未修改的操作，要求可读的项目内回执；理由最多500字符。脚本保留原 ID/state/receipt/retry，附退役理由、时间及回执SHA-256，先写不可变归档再发布入口。不能在同次patch把UNKNOWN改FAILED后藏入历史；仍需重试或结果不确定的条目继续留在当前。普通命令拼写错误无需逐条登记为外部操作，只有影响恢复、验证或重试安全的失败才进入台账。

operation --id 仍返回完整失败与历史标记，核对回执摘要并通过 receipt_issues 报告改写/缺失；读取不授权重试，原 ID 不可改状态重用。原始失败回执保留，不用短索引替换或省略重试前提。是否确实结束仍由代理核对业务证据，不能把文件存在/哈希匹配当作自动证明。

没有后续替代状态的完成验证，可在 patch 中显式退役：

```json
{"retire_records":[{"id":"closed-validation","reason":"该版本验证已完成，作为历史证据保留"},{"id":"closed-release-record","reason":"本份发布许可已消费","operation_id":"original-release-operation"}]}
```

只允许 confirmed 且有可读来源的 file/runtime/e2e 验证或操作退役。操作记录须关联 SUCCEEDED 台账 ID，且来源指向同一项目内回执。用户要求、约束、决策不能退役；归并或纠正使用同 scope 的 supersedes，合并正文覆盖全部仍有效含义，原文 anchor 不省略。新决定覆盖旧措辞时明确替代，不能把“在电脑旁”等临时可用状态当永久权限。未完成、未知和仍影响当前验收的内容不得为省空间退役。

固定长度 archive_head 指向归档链；旧 record_archives 仍可读，首次归档后移入链中。先写包含退役原因和正文的不可变快照，再发布短入口；失败保留上一入口，可能有未引用快照，勿盲删。链丢失/损坏阻止复核和安全查重，不能解释为没有历史。

其他列表如 next/evidence 仍完整替换，先核对当前字段。archive_head、record_archives、recorded、superseded_by、retired 由脚本管理，不能手填绕过检查。

## 阶段复核

实质批次结束、约定的 next_check 到达或已确认恢复异常时，把复核并入正常收尾：对照完整需求入口和本阶段新增纠正，确认未完成、验证边界及不可重放事项仍可恢复，再决定原对话继续、暂缓迁移或确需交接。同一 batch 内完成了约定故事/检查，也要同步短结论及下一具体节点；不能因 batch.id 未变或没有 Hook 提示而沿用已过节点。同版本证据复用；不逐次保存或压缩重审，不按聊天长度、天数或压缩次数决定迁移。

原对话继续或迁移暂缓时，复用 memory_review.continuation 的 decision/tools/reason/next_check/at。在约定节点实际核对后同步短结论，其他时候仅在理由或复核点实质变化时更新。reason 写当前进度、未完成和继续方式的具体依据，next_check 写可观察的业务节点；例如“本候选已验收，未完成项与原文可恢复，原对话继续已授权接入；接入收口后核对”。at 表示本次确实做过核对，不能只刷新时间消除提醒，也不声称重读了未读内容。不要只写“以后再看”或把 next_check 自动改成每次保存。工具未核实填 unknown，不为一次 defer 额外探测全部工具。

save --patch 是字段级合并：更新时保留当前 memory_review 其他成员，仅替换 continuation；没有旧对象则只保存 continuation。不能为让旧声明看起来有效而刷新 basis_sha256/critical_ids/checked_sections。短结论不能代替缺失或失效的完整语义审计；若同版本正文审计仍有效，可复用该证据并更新迁移决定。真正 prepare 仍须满足下节全部条件，本地预约不是外部授权。

临时“不接棒”用现有用户记录保存原话、来源、适用范围，并在 reason 引用其 ID、在 next_check 写相关节点。若旧记录混合了多项要求，先查原文，不能因一句“暂时”归并掉其他仍有效内容。明确的条件式限制按原条件判断，用户明确解除则按原格式追加替代记录；范围含糊且确需迁移时保留限制并向用户澄清一次。阶段变化只是复核信号，不是解除权限，也不默认变成所有后续阶段的永久禁令。仅暂停依赖迁移的动作，继续原对话中独立已授权工作。

只在结论影响继续方式、遇到具体恢复问题或需要澄清时向用户简述原因及下一节点，不要求固定段落或额外回复。脚本不理解自然语言节点是否已经发生，代理须结合实际进度判断；遗漏先补复核，不靠再建一套状态或定时提醒掩盖。

## 交接复核

对照原始要求、纠正和证据，交叉核对 goal/progress/decisions/evidence/next；goal 核对包括完整需求入口与本批范围，不能拿本批验收代替完整目标验收。删除当前字段中过期的“未构建/未定位”等状态，历史快照保留。核对禁止事项、未完成、未验证、不可重复操作和下一步权限；全部记录均关键时重新判断恢复必要性。verify 的 advisory 可提示重复正文，无法识别所有语义矛盾，checked_sections只是人工/代理确认。

完成内容核对后，把 verify 的 memory_basis_sha256 和完整 critical_ids 写入小 patch：

```json
{"memory_review":{"basis_sha256":"实际值","critical_ids":["实际关键ID"],"checked_sections":["goal","progress","decisions","evidence","next"],"continuation":{"decision":"migrate","tools":"available","reason":"原对话出现已核实的恢复问题，必要原文已补齐，迁移有助于继续；本步安全结束、下一步已授权且接续工具可用","next_check":"接棒取得实质进展后","at":"实际复核时间，带时区"}}}
```

真正准备交接时，完整复核声明须与当前正文匹配；已有同版本有效审计可以复用，否则完成内容核对、取得basis/critical_ids并保存。仅将 defer 改为 migrate，也须实际核对迁移必要性、当前限制、下一步授权和工具可用性；不能把旧审计冒充刚做的全文重读。prepare内部重新verify，不必再跑一遍相同验证。日常 save --patch 可保留失效的旧 memory_review，原对话继续不要求刷新它。decision 为 migrate/defer/unavailable，tools 为 available/unavailable/unknown；reason/next_check各1—500字符，at为真实带时区时间。工具能力须实际查询，不是写available就获得能力或授权。实际迁移问题待解决时defer给复核节点，unavailable给能力变化条件。正文变化使交接复核失效；新压缩要求核对记忆，但恢复正常无需重写迁移声明。来源/依赖/归档变化仍按原校验阻止无效交接。

handoff_ready 保留旧策略的机械复核含义；semantic_review_current 表示本正文五字段已确认核对；continuation_review显示迁移决定是否对应当前正文；new_handoff_ready 才表示符合1.5新建预约条件。四者都不证明自然语言语义完整，不是外部权限。

容量超过80%时先归并重复、归档完成证据和压短入口。80%—95%且确实都是必要约束时，可在同次 memory_review 加 capacity_reason（不超过500字符），说明不能缩减的具体原因；超过95%不允许用理由绕过新交接，须留下至少5%更新余量。不是要求删除事实，也不阻止当前任务继续修复记录。该阈值约束文件容量，不是模型token百分比。

## 原文耐久性

优先引用现有不可变报告。对会改写的文件，在改写前用 source --retain 保留受影响的已核非敏感片段，或在正常保存时用 save --retain-sources 保留当前及即将归档记录的已核片段。存入项目 .dev-continuity/sources/SHA256.txt，旧来源路径、字节范围和哈希不改。dry-run 不写片段；每段至多16KiB，不复制聊天全集，也不为每次保存重复备份不可变来源。自动检查仅拦截明显秘密，不能替代人工脱敏。

指定 project 时，相对来源以该项目为基准，不回退到进程当前目录；相对路径不能越出项目（含符号链接）。已有绝对来源保持兼容，项目外历史来源须明确用绝对路径或已核保留片段。未指定 project 的 source 仍按当前目录解析。read_source/record/verify 在原位置失配时，核对本项目相同SHA的保留片段；它证明当时原文，不证明当前状态。代码验证仍使用 depends_on 检测适用版本变化。跨目录/机器迁移要连同片段安全搬运，不能只复制 latest.json。

source --project PROJECT --input ANCHOR.json --retain 可显式保存某段。原文已改写或位置移动时，先在已知原文件/备份中定位；用 --candidate FILE --candidate-offset OFFSET 从核实的真实字节恢复，长度及完整SHA必须匹配原锚点。仍保留原路径、偏移和哈希；只增加保留片段，不改旧引用或检查点。找不到则保留失配状态，不从摘要重写“原文”、刷新哈希或自动扫描所有聊天。

verify --history 按需审计历史原文，单独返回 history.ok，历史失配也返回非零退出码；当前 ok 与历史原文完整性不能混称。普通 verify 不重复扫描历史原文内容。

1.9 读取格式1–8；普通兼容写入仍用7。首次保存超过旧正文上限，或首次准备只有新计量允许的预约时，才与该次修订一起写8。格式8不会因正文变小自动降级，v1.8.3拒绝读写最新格式8。既有预约保留原策略、编号、设置和核验；安装不会迁移项目数据。恢复兼容程序即可从最新状态继续；若必须交由 v1.8.3 写入，见[安全导出](operations.md#安全导出给-v183)。
