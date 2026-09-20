---
name: dev-continuity
description: Maintain resumable development checkpoints, trace decisions to source records, and transfer unfinished work across conversations. Use for long development tasks, context pressure, interruption recovery, or handoff; skip routine one-step edits and unrelated questions.
metadata:
  version: "1.4.0"
---

# 开发连续性

长开发任务使用；普通一步改动直接完成。全局只放通用规则，项目事实隔离；遵守项目 writer/routing。

## 恢复与更新

执行 scripts/continuity.py recall，固定 revision 分页读完当前关键项。核对目标、有限批次及完成条件、当前状态、禁止事项、未完成操作和 next；有疑问用 record --id 取原文，外部操作前用 operation --id 查当前与历史。旧文字和“未找到”不授予执行权限。

在用户纠正、重要验证完成/失败、下一步或授权变化后 save --patch，不等交接才更新。只记实质增量；来源与现场优先，不压缩上一份摘要来替代核对。用户报告、文件、运行加载、真实端到端分别记录；推测保持未核实。

首次登记、归并、归档或来源保护读 [记忆格式](references/memory.md)；保存、接棒及成本查询读 [操作参考](references/operations.md)。Python 3.11+ 标准库；Windows 用 py -3 -X utf8。

## 当前与历史

- critical 表示本次恢复必须读，包含当前目标、权限、禁止、未知操作和验收边界。重要历史保留可查；不把每次完成证据永久列为当前关键项。
- 同 scope 的重复要求先核对原意，再以保留全部必要约束和原文来源的 supersedes 合并；用户要求/决策不能直接退役。版本状态用稳定 scope/status_key 替代；完成验证/操作可带原因退役。历史不能重新指导当前 next。
- 短入口只留当前状态与权威链接，不追加发布流水；历史放既有日志/归档。核对完整必读集合的成本，不把重复内容藏在后页。超过80%容量先整理；必要约束确实无法缩小时，复核中说明原因后才能新交接，不截断约束。
- 会改写的来源用 --retain-sources 保留已核验非敏感原文片段；不是保存整个文件或聊天。verify 校验当前和归档链，verify --history 按需检查历史原文；校验通过仍不证明语义完整或时效。
- 归档先落盘再发布入口；未知/在途操作保持当前，先查回执。已成功操作及历史 ID 不复用；锁冲突不擅删，失败保留上一检查点。

## 持续与接棒

以当前已授权的有限业务批次推进；batch 写范围和可判定完成条件，next 对应该批次缺口。批次完成后进入已授权下一批，不把“继续”解释成无限寻找新缺陷；复用同版本有效证据，不用测试/发布数量代替业务验收。

尚有已授权且独立可做的事项就继续；人工、费用或新业务决定只暂停依赖动作。用户停止优先，目标完成保存 completed=true，不自行新增目标。

70%/80%近期用量仅提示整理/评估，未知不猜比例，不以累计token或账户额度当上下文。压缩先发生则恢复继续。确需迁移时复核内容与来源，预约一次 → 记录真实新任务 → 释放旧写入权 → 接棒执行 next；结果不明先查，不重复创建或并发写入。

continuation_settings 仅登记有用户依据的 model/thinking；创建时显式传递已确认选择，并核对首轮实际设置。无明确选择则省略，不能从旧模型猜偏好或改全局默认。新任务取得实质进展前不再迁移。

Hooks 只低频记录机器状态和短提示，不生成语义摘要、增加模型调用、定时轮询或强制Stop续跑，不承诺应用退出后继续。能力缺失时保留短交接正文；不伪造接棒完成。

升级验证旧记录、防重放、来源改写、增长、中断、有限批次与设置传递；实测和模拟分开。cost 的缓存/非缓存输入与输出仅为观测，字节和累计用量均不能证明净节省。
