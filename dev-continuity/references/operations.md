# 操作参考

以下命令使用当前环境中本 Skill 的绝对脚本路径；Windows 统一使用 `py -3 -X utf8`；其他平台使用可用的 Python 3。`PROJECT` 是真实工作目录，`TASK` 是稳定任务标识，`SESSION` 是当前真实对话 ID。不要把示例字样作为实际 ID。

## 检查点

将以下结构写入项目内一个临时 JSON 输入文件，复用现有项目文档的链接。全局规则与 Skill 不保存项目正文；每个项目/任务的机器记录在 `.dev-continuity/TASK/`，不自动提交或修改 gitignore。

```json
{
  "goal": "用户最终目标",
  "acceptance": ["可观察的完成标准"],
  "batch": {"id":"当前有限批次", "scope":"本批处理的有限问题", "done_when":"可判定的批次完成条件"},
  "progress": {"done": [], "active": "当前工作", "remaining": []},
  "decisions": [],
  "preserve": [],
  "operations": [],
  "evidence": [],
  "next": ["下一项具体动作及成功条件"],
  "blockers": [],
  "files": [],
  "sources": []
}
```

`operations` 条目：`{"id":"稳定操作ID","state":"STARTED_UNKNOWN","receipt":"脱敏证据路径或尚无回执","retry":"先查询结果"}`。`evidence` 条目写验证层、日期、结果、路径及适用版本。`files` 只列与恢复正确性相关的项目相对文件，脚本记录其 SHA-256；勿加入密钥文件或正在持续追加的大日志。`sources` 放下述原文 anchor。需要省篇幅时引用已有文档；不可省略不可重复操作及未解决问题。完成操作归档后仍用 operation --id 检索；短入口不逐项重复已完成台账。`compaction_limit` 仅在实际 total-scope 阈值已核实时填写正整数；其他情况不填。

1.4 新任务增加 records；格式、纠正、来源与复核见 [记忆格式](memory.md)。旧JSON仍能读取/保存，新 prepare 要求 batch。batch 范围从已有授权与计划取，不以“找更多问题”代替完成条件；next只推进本批缺口，批次完成再登记下一已授权批次。恢复前核对目标/停止指示，不重复展开已有同版本验证。首次登记使用真实项目目录；Hook不能从父目录发现隔离子目录中的登记。

用户明确选择模型/推理强度时，登记 continuation_settings，例如 {"thinking":"high","source_record":"真实用户要求记录ID"}；model仅在明确选择时加入。source_record须为当前已确认、critical且basis=user的有原文记录，不能用推测或助手建议代替用户选择；变更选择须换用新的用户依据。明确恢复默认时写 {"source_record":"新的恢复默认要求ID"}。首次未明确时省略整个字段；之后完整save省略batch/settings也会沿用旧值，不能借遗漏清除约定。recall首屏展示这两个字段。

```text
py -3 -X utf8 SCRIPT save --project PROJECT --task TASK --session SESSION --input INPUT.json --expected new
py -3 -X utf8 SCRIPT recall --project PROJECT --task TASK
py -3 -X utf8 SCRIPT save --project PROJECT --task TASK --session SESSION --input INPUT.json --expected REVISION
py -3 -X utf8 SCRIPT save --project PROJECT --task TASK --session SESSION --input DELTA.json --expected REVISION --patch
py -3 -X utf8 SCRIPT verify --project PROJECT --task TASK
```

`save` 只接受当前 owner，更新必须给 `show` 返回的 revision。失败时保留输入和上一检查点；锁冲突先确认另一操作是否仍在执行，禁止盲删锁。损坏时从 `checkpoints/` 找最后可核验快照，保留损坏现场再人工恢复指针。输入文件可保留在任务目录，避免在全局配置中存业务内容。

## 原文定位与用量

```text
py -3 -X utf8 SCRIPT anchor --path SOURCE --offset BYTE_OFFSET --length BYTE_LENGTH
py -3 -X utf8 SCRIPT source --input ANCHOR.json
py -3 -X utf8 SCRIPT source --input ANCHOR.json --show
py -3 -X utf8 SCRIPT usage --transcript TRANSCRIPT.jsonl
py -3 -X utf8 SCRIPT cost --transcript TRANSCRIPT.jsonl
```

anchor 默认不复制正文；最多16KiB一段，先按已知对话ID/时间/关键词定位。可变原文用 save --retain-sources 或 source --project PROJECT --input ANCHOR.json --retain 保留小片段，详见记忆格式。source --project 可查保留片段；--show会输出正文，只对已确认非敏感片段使用。会话格式非稳定契约，不能承诺找回未保留且已删除的原文。

`usage` 最多读取末尾 256 KiB，仅解析 `token_count`。给出最近请求样本与名义容量，不是精确剩余量，也不是自动压缩阈值；超过 5 分钟或无法解析即 unknown。按实际阈值校准可传 `--limit N`（仅 total scope）。不修改模型上下文设置以绕过压缩。

cost仅在审计/批次结束时按需运行，流式读取指定一个本地transcript的token_count，累计计数去重、排除首样本继承历史，区分缓存/非缓存输入与输出；计数器重置标出可能低估。不自动包括子代理、其他对话或账号额度，不解释价格，不声称净节省。跨对话汇总先按session身份去重，不混入fork继承历史；无可比任务对照则净节省未知。

## 一次接棒

只有用户明确要求或有效的个人约定已授权自动接续同一目标时创建任务；无此授权交付 prompt 文件即可。Skill 自身不提供创建任务或外部操作的授权；项目与工具的更高优先级边界继续适用。

1. 完成当前安全步骤、保存并按记忆格式对照原始要求/证据完成复核，verify 确认 handoff_ready=true。`transfer --action prepare` 生成 `handoff-prompt.md` 及唯一预约。重复 prepare 拒绝。新 prepare 要求至少一个有依据的有效关键条目、全部关键来源可核验及与当前正文匹配的 memory_review；ok=true 单独不代表可交接。
2. 用已有 create_thread：先 list_projects，遵守worktree/local规则与指定目录。传递prepare返回的continuation_settings中已确认的model/thinking，未确认字段省略；不修改全局默认。提示词只携带短入口、request_id、批次及来源，要求先只读核对；未释放则READY并等旧任务消息，不要求用户输入。不fork整段旧聊天；下一轮核对实际模型/强度，工具不支持明确设置则说明，不悄悄升档。
3. 调用返回真实 threadId 后 `transfer --action target --successor ID`。只有 clientThreadId 时等待解析；回执不明先查创建结果，禁止再次 create。失败记录保留，不自动清除预约。
4. 确认旧任务代码/外部操作已停且现场仍匹配，`transfer --action release`；之后旧任务仅查询回执和发送交接消息，不再写本任务文件。用 `send_message_to_thread` 将 `request_id`、真实 successor ID、RELEASED revision 和无在途写入的说明发给刚创建的任务，明确“核验后 accept，立即继续，不等待用户回复”。消息失败先查投递/运行结果，不自动重复释放或创建。
5. 新任务核对原目标、权限、文件和原文，确认旧 writer 已释放及无冲突，再 `transfer --action accept --session SUCCESSOR`，核对持久化 owner、request_id、phase=ACCEPTED 后直接完成 next。接棒失败保留证据，不写业务文件。旧任务仍在等待回执不等于仍拥有写入权；不能要求旧任务先结束、同时让旧任务等新任务结束而造成互相等待。工具只防止检查点并发，不代替实际在途操作及项目已有 writer/routing 核验。
6. 旧任务使用 `wait_threads` 的 cursor 等待接棒进度，单次最多 60 秒；核对 ACCEPTED/owner 和实际进展后结束旧任务，并提供新任务入口。达到等待上限或工具失联时保留待确认状态，不推定失败、更不重新写入或新建。用户已要求切换界面时可用 `navigate_to_codex_page` 打开新任务；界面切换与后台执行是两件事。

每条 transfer 命令同样带 `--project PROJECT --task TASK --session SESSION --expected REVISION`，每次变更后使用返回的新 revision。同项目可共享记录；使用新 worktree/另一机器时先安全搬运脱敏交接资料、核对源码并重新登记真实路径，不复用旧目录身份。不能安全搬运时交付提示词并说明未完成接棒。

工具不可用/接续失败时，保留当前 owner、预约及 handoff-prompt；不要循环新建任务、启动调度器或把状态标成接棒成功。没有创建工具时优先在当前任务压缩恢复后继续已授权工作，确需用户迁移才提供提示词。任务完整结束时保存 `"completed": true`，Hooks 将停止用量提醒。用户停止优先，不用 Stop 钩子强制续跑。

70%/80% 的近期用量信号只提示整理和迁移评估，不单独触发新任务。能在当前任务继续就继续，原生压缩后恢复记录；确需迁移且内容复核通过才自动接棒。未知用量不猜比例。接棒有新任务启动和短消息的 tokens 成本；每次只带当前摘要及按需证据，先推进 next，避免围绕同一检查点循环创建。里程碑结束前仍有已授权且可独立完成的 next 时直接继续，不以完成一个小修复为整个目标的终点。

只有查询确认创建失败，或已创建的 successor 明确停止且未接手后，旧 owner 才可保存脱敏查询回执并执行 `transfer --action cancel --cancel-receipt PROJECT_RELATIVE_RECEIPT`。脚本保存回执哈希与原预约；取消后可恢复旧任务。回执不明不可取消预约，不通过取消规避重复创建检查。

## 安装与维护

个人级安装保留原全局约定，仅替换开发连续性专用区块；Hooks 合并而不覆盖其他处理器。安装脚本提供备份、文件哈希清单和恢复命令。更换机器重跑安装以绑定本机 Python/Skill 路径。

Hooks 必须经 Codex 的信任机制核准后才运行。已存在的信任不代表修改后的配置仍可信。安装不直接改写信任数据库，不用 bypass 标志。Hook 无法读取或保存时显示失败，保留旧检查点；格式变化须重新核验。

能力验收分为文件已安装、运行时可发现、已信任、真实事件已运行、自动换任务已实测；不可合并称为全部自动化通过。仅触发钩子或语法测试不证明完整接棒。
