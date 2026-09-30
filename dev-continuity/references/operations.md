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

新任务增加 records；格式、纠正、来源与复核见 [记忆格式](memory.md)。旧JSON仍能读取/保存，新 prepare 要求 batch 和当前迁移复核。batch 范围从已有授权与计划取，不以“找更多问题”代替完成条件；next只推进本批缺口，批次完成再登记下一已授权批次。恢复前核对目标/停止指示，不重复展开已有同版本验证。首次登记使用真实项目目录；Hook不能从父目录发现隔离子目录中的登记。

默认无需登记固定模型/强度：prepare 读取当前 owner 的最新实际 model/effort。确需在下一接续主动调整、且有授权依据时，登记 continuation_settings，例如 {"thinking":"medium","source_record":"本次调整要求ID","for_session":"当前owner的真实ID"}；只改一项时另一项继承实际设置。source_record须为当前已确认、critical且basis=user的有原文记录，不能以助手建议代替授权；变更设置或重新绑定 owner 必须使用新的用户依据。明确恢复默认写 {"source_record":"新的恢复默认要求ID","for_session":"当前owner的真实ID"}，本次返回空设置。

for_session 绑定来源 owner 的接续选择，取消预约后同 owner 可重试；接棒后原绑定失效。旧记录缺少 for_session 时仅保留历史，不覆盖当前实际设置。完整save省略batch/settings仍保留旧内容，不自动重新绑定；recall所示保存值不是最终创建参数。沿用模型须有符合宿主要求的用户授权，本人明确要求“新对话沿用之前模型和强度”可作为依据；无此授权不能用代理建议指定模型。

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
py -3 -X utf8 SCRIPT usage --project PROJECT --task TASK --session SESSION
py -3 -X utf8 SCRIPT cost --transcript TRANSCRIPT.jsonl
```

anchor 默认不复制正文；最多16KiB一段，先按已知对话ID/时间/关键词定位。可变原文用 save --retain-sources 或 source --project PROJECT --input ANCHOR.json --retain 保留小片段，详见记忆格式。source --project 可查保留片段；--show会输出正文，只对已确认非敏感片段使用。会话格式非稳定契约，不能承诺找回未保留且已删除的原文。

`usage` 优先从当前owner的runtime解析最新transcript.path，避免固定旧日志分段；也可显式指定一个路径，两种模式不可混用。默认先查末尾256 KiB，未找到时按倍增窗口向前，最大尾部范围8 MiB（最坏累计读取不足16 MiB），跳过大工具/图片行。仅解析token_count的小事件；不把大图片读入模型上下文。超过边界返回scan_limit，过期返回stale_or_future_sample，无兼容事件/文件分别说明原因。unknown不是余量充足。

样本超过5分钟不用于比例判断，last_sample仅为诊断；当前字段是最近请求样本与名义容量，不是精确剩余量或自动压缩阈值。按已核实total-scope阈值可传 --limit N。不修改模型设置绕过压缩。Hook仍45秒节流、同原因unknown去重，不增加模型调用；升级后首次可提示事件提醒当前owner重读Skill。

cost仅在审计/批次结束时按需运行，流式读取指定一个本地transcript的token_count，累计计数去重、排除首样本继承历史，区分缓存/非缓存输入与输出；计数器重置标出可能低估。不自动包括子代理、其他对话或账号额度，不解释价格，不声称净节省。跨对话汇总先按session身份去重，不混入fork继承历史；无可比任务对照则净节省未知。

## 一次接棒

只有用户明确要求或有效的个人约定已授权自动接续同一目标时创建任务；无此授权交付 prompt 文件即可。Skill 自身不提供创建任务或外部操作的授权；项目与工具的更高优先级边界继续适用。

1. 完成当前安全步骤，实际核对创建、投递及等待工具和既有授权；按记忆格式保存五字段复核与migrate决定，verify 确认 new_handoff_ready=true。`transfer --action prepare` 生成 `handoff-prompt.md` 及唯一预约。重复 prepare 拒绝。新 prepare 要求有限batch、有效关键来源、容量余量及与当前正文匹配的memory_review；ok=true或旧handoff_ready=true单独不足。未知操作须在语义核验时确认已停止写入、结果如何查询；不以迁移触发重放。
2. 用已有 create_thread：先 list_projects，遵守worktree/local规则、目录及设置继承授权。传递prepare返回的continuation_settings，不能直接传note历史字段。默认从当前owner的runtime.transcript.path读取最近同一条turn_context.model/effort，校验session_meta身份，最多读取尾部8 MiB；未登记路径时 prepare 可加 --transcript REAL_LOG。缺文件、身份不符、字段/格式未知或超界未找到均在预约前失败，不回退旧值。仅 for_session 对应当前owner的调整生效：部分调整继承另一项，完整指定或明确恢复默认可用用户依据；不支持的设置不能自动替换。handoff冻结值不在后续阶段重算；旧预约按原值完成。提示词携带短入口、request_id、批次及来源，要求先只读核对；未释放则READY并等旧任务消息，不fork整段聊天。
3. 调用返回真实 threadId 后 `transfer --action target --successor ID`。只有 clientThreadId 时等待解析；回执不明先查创建结果，禁止再次 create。失败记录保留，不自动清除预约。
4. 确认旧任务代码/外部操作已停且现场仍匹配，`transfer --action release`；之后旧任务仅查询回执和发送交接消息，不再写本任务文件。用 `send_message_to_thread` 将 `request_id`、真实 successor ID、RELEASED revision 和无在途写入的说明发给刚创建的任务，明确“核验后 accept，立即继续，不等待用户回复”。消息失败先查投递/运行结果，不自动重复释放或创建。
5. 新任务核对原目标、权限、文件和原文，确认旧 writer 已释放及无冲突，再 `transfer --action accept --session SUCCESSOR`。新policy4在bind前读取接棒方最近实际model/effort，与冻结值一致才接受；Hook尚未登记接棒日志时加 `--transcript SUCCESSOR_REAL_LOG`，校验该日志身份为SUCCESSOR。设置不符、未知或日志缺失则保留RELEASED与原owner，接棒方继续只读；纠正宿主设置并取得真实新日志证据后重试同一预约，禁止另建任务绕过。matched回执保留实际来源；明确恢复默认的空设置记explicit_defaults_requested，不冒充实际值已匹配。旧policy1/2/3预约按原策略完成；--transcript只允许prepare/accept，不能改冻结值。核对owner、request_id、ACCEPTED后执行next。工具不代替真实在途操作与项目writer核验，脚本不会修改宿主设置；不要让双方互等结束。
6. 旧任务使用 `wait_threads` 的 cursor 等待接棒进度，单次最多 60 秒；核对 ACCEPTED/owner 和实际进展后结束旧任务，并提供新任务入口。达到等待上限或工具失联时保留待确认状态，不推定失败、更不重新写入或新建。用户已要求切换界面时可用 `navigate_to_codex_page` 打开新任务；界面切换与后台执行是两件事。

每条 transfer 命令同样带 `--project PROJECT --task TASK --session SESSION --expected REVISION`，每次变更后使用返回的新 revision。同项目可共享记录；使用新 worktree/另一机器时先安全搬运脱敏交接资料、核对源码并重新登记真实路径，不复用旧目录身份。不能安全搬运时交付提示词并说明未完成接棒。

工具不可用/接续失败时，保留当前owner、预约及已有handoff-prompt；不要循环新建任务、启动调度器或假报成功。尚未预约且创建/投递工具缺失，记录unavailable与具体缺失能力、下次能力变化时复核，并简短告知用户。在原任务压缩恢复后继续独立事项；不重复搜索未变化的工具，必要时交付短正文。任务完整结束时保存 `"completed": true`，用户停止优先，不用Stop钩子强制续跑。

70%整理；80%、新压缩、批次切换后的下一安全节点必须有迁移决定。具备已授权独立next、接续工具、来源复核与无未决创建时执行一次接棒；暂缓写具体原因与下一业务节点，不以“还能继续”无限延期。已结束或待用户决定且无独立next时不创建。正文变化使决定不再current；Hook在新压缩后标记due_at_safe_boundary，复核后更新at。阈值不单独授权创建；Hooks不执行调度、工具创建或语义复核。新任务先取得实质进展再考虑迁移。

只有查询确认创建失败，或已创建的 successor 明确停止且未接手后，旧 owner 才可保存脱敏查询回执并执行 `transfer --action cancel --cancel-receipt PROJECT_RELATIVE_RECEIPT`。脚本保存回执哈希与原预约；取消后可恢复旧任务。回执不明不可取消预约，不通过取消规避重复创建检查。

## 安装与维护

个人级安装保留原全局约定，仅替换开发连续性专用区块；Hooks 合并而不覆盖其他处理器。安装脚本提供备份、文件哈希清单和恢复命令。更换机器重跑安装以绑定本机 Python/Skill 路径。

Hooks 必须经 Codex 的信任机制核准后才运行。已存在的信任不代表修改后的配置仍可信。安装不直接改写信任数据库，不用 bypass 标志。Hook 无法读取或保存时显示失败，保留旧检查点；格式变化须重新核验。

能力验收分为文件已安装、运行时可发现、已信任、真实事件已运行、自动换任务已实测；不可合并称为全部自动化通过。仅触发钩子或语法测试不证明完整接棒。
