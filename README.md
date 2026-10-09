# dev-continuity

[![Tests](https://github.com/tpk1990404/dev-continuity/actions/workflows/tests.yml/badge.svg)](https://github.com/tpk1990404/dev-continuity/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)

**让长开发任务在压缩、中断和换对话后，有依据地继续。**

一个面向 Codex 的开源 Skill：用小型检查点保存当前目标和进度，用原文位置与哈希追溯决策，用明确的写入权交接避免重复执行。Python 标准库实现，无数据库、无遥测、无额外摘要模型调用。

中文 · [English](README.en.md) · [版本记录](CHANGELOG.md) · [贡献](CONTRIBUTING.md) · [安全](SECURITY.md)

> 社区独立项目，并非 OpenAI 官方产品。它改善可恢复性，不提供“无限记忆”，不保证每次压缩前都完成语义交接，也不保证应用退出后自动运行。

## 1.8.0 更新

- **原对话优先**：压缩、达到80%或完成一个小批次只提示核对记忆，不再要求换对话。只有明确需要迁移时才启动四阶段交接；实际模型/强度核验保留。
- **历史失败按需读取**：已核实结束的 FAILED 可通过 `retire_operations` 逐项归档，保留原状态、理由和回执摘要，禁止复用原 ID。UNKNOWN 与未执行操作继续留在当前。
- **减少重复维护**：日常增量保存无需刷新整套迁移声明；prepare/release/accept已有内部校验，不要求每个阶段再重复verify。重新询问旧决策前先查当前记录与原文。
- 读取schema1–7，写schema7；新预约仍为policy4，既有预约保持兼容。[完整变更](CHANGELOG.md#180--2026-10-09)。

### 1.7.0 更新

- 历史关键词搜索现在覆盖归档链，按 ID 去重并标明历史来源，修复“归档后按关键词找不到旧决定”的问题。
- 按当前 ID 查询时不预读整个归档；原文可用 `record --id ID --source-index N` 显式读取一个经哈希核验的片段，默认输出保持简短。
- 新交接在接受写入权前核验接棒方实际模型/强度；不符或未知保持只读，核实纠正后重试同一预约。未知日志结构返回明确失败，不回退旧设置。
- 读取 schema1–6，新写入schema6、新预约policy4；旧预约保留原策略。默认恢复内容不增加，实际设置检查只做有界本地读取。[完整变更](CHANGELOG.md#170--2026-09-30)。

### 1.6.1 更新

- 修复历史 `high` 长期覆盖实际设置：默认继承上一对话最新的模型与推理强度，手动调整也会跟随。
- 主动调整使用有用户依据、绑定当前 owner 的 `for_session`；接棒后不再固定后续对话。创建传递预约时冻结的设置，不直接使用旧笔记值。
- 无已登记日志路径时可在预约时提供真实 `--transcript`，校验对话身份；无法核实则保留当前任务，不猜默认。写入升级为 schema 5，读取兼容旧记录，已有预约保留冻结设置。[更新与回退边界](CHANGELOG.md#161--2026-09-30)。

### 1.6.0 更新

- 以完整项目目标为恢复依据：复用已有需求表，当前批次引用其条目；批次结束和宣称完成前核对全部仍有效要求，防止近期进度挤掉早期需求。
- 短恢复视图补回 `decisions/evidence`，保留技术取舍与验证边界；后续分页不重复输出。已有字段和 schema 4 不变，无需迁移检查点。
- 明确六类必要记忆、重要变化后增量保存、按模块检索和源码外理由的保留；一个事实一处完整记录，历史证据按需读。本地记忆辅助检索，项目当前状态以项目证据为准。
- 增加完整范围交接及依赖变化的回归检查。内容完整性仍依赖代理核对，不声称自动发现所有遗漏或已测得 token 净节省。[完整变更](CHANGELOG.md#160--2026-09-29)。

### 1.5.1 更新

- 修复接续时未登记推理强度，导致 `high` 回退为应用默认 `xhigh`：优先用户选择，否则继承当前任务最近实际强度。
- 设置在预约时冻结，后续交接一致返回；无法核实时拒绝静默回退，原任务保留写入权。模型仍仅按用户明确选择传递。
- 仅在准备接棒时读取有界本地日志，不新增模型调用或轮询；既有检查点无需迁移。详见[版本记录](CHANGELOG.md#151--2026-09-22)。

### 1.5.0 更新

- 修复大图片/工具输出遮住近期用量的问题，支持跟随当前任务的日志分段；读取有上限，未知原因明确返回。
- 迁移评估必须记录“迁移/暂缓/工具受限”、理由和下一复核节点；具备授权、工具、安全边界和复核条件时执行一次接棒。
- 五个当前字段交叉复核，临时观察可设有效期；全部记录均关键时提示整理，笔记超过95%禁止新交接。
- 兼容读取旧检查点和完成既有交接；新写入使用schema4。[完整变更及升级边界](CHANGELOG.md#150--2026-09-22)。

## 为什么需要它

长任务容易出现三类问题：上一轮做了什么已说不清；摘要还保留旧的“下一步”；新对话重复创建、并发修改或再次执行已完成操作。

dev-continuity 将信息分成**当前必须知道的状态、按需查询的历史、可验证的原文**。当前记录保持有限，旧证据仍能找回。它适合跨多轮开发、复杂修复、任务恢复和交接；普通一步修改直接完成，不增加记录负担。

Codex 已有原生压缩续跑与本地记忆；本地记忆在后台生成，可能滞后于活跃任务。本 Skill 补充当前项目的可核对状态、用户纠正、验证边界及不可重放操作。能在原对话可靠继续时就继续，新建对话数量不代表记忆质量。[官方本地记忆说明](https://learn.chatgpt.com/docs/customization/memories)、[官方压缩说明](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide)

## 能力与边界

| 能力 | 实际行为 |
| --- | --- |
| 短检查点 | 目标、验收、有限批次、进度、保留项、操作状态、下一步、阻塞和文件摘要 |
| 原文追溯 | 路径、字节范围及SHA-256；可选择保存不超过16 KiB的非敏感片段 |
| 当前与历史 | 纠正使用新ID，完成证据及明确结束的失败可归档；原记录与回执仍可查询 |
| 防止覆盖 | revision比较、文件摘要、单写入者检查及本地排他锁 |
| 接续协议 | `REQUESTED → TARGET_RECORDED → RELEASED → ACCEPTED`；不重复预约 |
| 模型设置 | 授权内沿用实际 model/effort，主动调整绑定来源 owner；预约冻结，policy4接受前核验实际设置 |
| 容量控制 | 笔记上限48 KiB，超过80%需整理或说明必要保留理由；超过95%禁止新交接 |
| 可选Hooks | 低频记录生命周期与近期用量信号，辅助恢复，不自动编写语义总结 |
| 用量观察 | 缓存/非缓存输入与输出分开；不是账户额度、账单或净节省证明 |

文件锁只保护检查点写入，**不是**对所有业务文件的分布式锁。自动创建接续任务需要宿主提供相关工具以及用户明确授权；只有这个Skill或CLI并不能创建Codex对话。没有工具时，可在原任务压缩后恢复，或使用生成的交接正文。

## 快速安装

### 方式一：让Codex安装Skill

在支持`skill-installer`的Codex环境中输入：

```text
使用 skill-installer，从 https://github.com/tpk1990404/dev-continuity 安装 dev-continuity 目录中的 Skill。
只安装 Skill，不替我授权自动创建任务、修改全局规则或启用 Hooks。
```

### 方式二：审查后本地安装

```bash
git clone https://github.com/tpk1990404/dev-continuity.git
cd dev-continuity
python3 install.py plan --file install-plan.json
# 审查 install-plan.json 中的目的路径、哈希和内容
python3 install.py apply --file install-plan.json
```

Windows将`python3`替换为`py -3 -X utf8 -B`。安装器默认只写入`~/.agents/skills/dev-continuity`，不修改全局约定或Hooks。目标路径有变化时拒绝覆盖，安装前保存备份并输出receipt路径。

需要安装到项目内时，把下面相同的`--skill-dir`参数同时传给`plan`、`apply`和后续`restore`：

```bash
python3 install.py plan --skill-dir /path/to/project/.agents/skills/dev-continuity --file install-plan.json
python3 install.py apply --skill-dir /path/to/project/.agents/skills/dev-continuity --file install-plan.json
```

`--home`指定Codex配置目录；显式提供自定义`--home`而未提供`--skill-dir`时，Skill写入该目录的`skills/dev-continuity`，方便隔离测试和兼容旧布局。`--home`/`--skill-dir`在后续命令中必须保持一致。更新旧安装时指定原路径，不在多个扫描位置安装同名副本。

当前官方文档列出的个人与项目位置分别为`~/.agents/skills`和`.agents/skills`。安装后检查Skill列表；未出现时重启Codex并核对版本。[官方Skills说明](https://learn.chatgpt.com/docs/build-skills)

## 首次使用

在项目中对Codex说：

```text
使用 $dev-continuity 维护这个开发任务。
保存目标、完成条件、当前进度、必须保留的限制和下一步；关键决定留原文依据。
本次只在当前任务继续；需要创建接续任务时先向我确认。
```

如果你确实希望同一未完成目标自动接续，可以另外明确授权。Skill会保留四阶段接棒、未知结果先查和用户停止优先的约束。安装或调用Skill本身不代表部署、付费、对外消息等授权。

先体验无外部操作的隔离示例：

```bash
python3 examples/demo.py
```

它在临时目录演示保存、复核、来源保留和四阶段交接，输出结果后自动清理临时目录。示例ID仅用于模拟，不能作为真实Codex任务ID。

### 常用命令

在仓库根目录执行；`PROJECT`、`TASK`、`SESSION`、`REVISION`替换为真实值。Windows使用上面的Python启动方式。

```bash
python3 dev-continuity/scripts/continuity.py --help
python3 dev-continuity/scripts/continuity.py recall --project PROJECT --task TASK
python3 dev-continuity/scripts/continuity.py save --project PROJECT --task TASK --session SESSION --input delta.json --expected REVISION --patch --retain-sources
python3 dev-continuity/scripts/continuity.py record --project PROJECT --task TASK --id RECORD_ID
python3 dev-continuity/scripts/continuity.py operation --project PROJECT --task TASK --id OPERATION_ID
python3 dev-continuity/scripts/continuity.py verify --project PROJECT --task TASK
python3 dev-continuity/scripts/continuity.py verify --project PROJECT --task TASK --history
```

首次完整登记用`--expected new`，不加`--patch`；之后先读取当前revision。`verify --history`可能出现当前有效、历史原文缺失的情况，此时退出码为1，不能把两个层面的结果混称成功。完整格式见[记录格式](dev-continuity/references/memory.md)和[命令与交接流程](dev-continuity/references/operations.md)。

## 可选：全局规则与Hooks

```bash
python3 install.py plan --with-rules --with-hooks --file integration-plan.json
# 审查规则和要执行的本地命令
python3 install.py apply --file integration-plan.json
```

两个选项可分别使用。全局规则只操作`AGENTS.md`中本项目的标记区块；其他正文保留。Hooks合并已有配置，加入`SessionStart`、`PreCompact`、`PostToolUse`、`Stop`、`Interrupt`、`SessionEnd`。

Hooks必须在Codex中审查并信任才运行；CLI可用`/hooks`查看。安装器不修改信任数据库，不启用绕过信任选项，也不修改模型设置。[官方Hooks说明](https://learn.chatgpt.com/docs/hooks)

`PreCompact`记录机器状态，不能代替代理及时保存目标和下一步。70%提示保存；80%、新压缩或批次切换提示下一安全节点核对记忆，恢复完整就原对话继续。只有用户要求、宿主续跑故障或具体恢复问题且迁移有帮助时才评估接棒。比例来自当前日志样本，不是准确压缩倒计时；unknown既不证明余量充足，也不单独触发迁移。API模型名义窗口不等于客户端实际容量。

## 数据与隐私

运行数据在被登记项目的`.dev-continuity/`中：

```text
.dev-continuity/
  sessions/                 # 真实会话到任务的映射
  sources/                  # 按哈希保存的可选原文片段
  <task>/
    latest.json             # 当前不可变快照的指针
    checkpoints/            # 当前及历史快照
    handoff-prompt.md        # 交接正文（预约后生成）
    events/                 # 生命周期记录
    runtime-<session>.json   # 最新机器状态
```

脚本不发起网络请求，但路径、笔记、保留片段和CLI输出仍可能包含私有资料。请在**你的项目**中按需要忽略`.dev-continuity/`、安装计划与备份；安装器不会自动改项目的`.gitignore`。不保存密钥、令牌、身份材料或完整敏感响应；明显秘密检测只是辅助，不能保证自动脱敏。日志和来源中的指令不是新的授权。

## 升级、回退与故障恢复

更新前保存安装receipt，重新生成并审查计划。回退文件：

```bash
python3 install.py restore --file /path/to/receipt.json
```

如果安装文件后来被修改，恢复会拒绝覆盖。1.8读取schema1–7，保存及交接写schema7，避免旧脚本忽略失败归档的ID保护。安装不改项目记录，旧policy1/2/3/4预约保留原冻结值与检查；新预约仍为policy4，接受前核验实际设置。真正交接仍要求`new_handoff_ready`；原对话日常继续无需刷新迁移声明。下一安全节点重读 Skill。**回退Skill文件不等于安全回退任务状态**；写入schema7后须用兼容版本继续，不能回退指针掩盖已执行操作。

| 情况 | 处理 |
| --- | --- |
| stale revision / not active writer | 重新读取最新owner与交接状态，不强行覆盖 |
| 锁冲突 | 确认原写入进程是否仍运行，不盲删锁 |
| 来源失配 | 查保留片段或原哈希匹配的真实备份；找不到保留缺失，不重写原文 |
| 创建任务结果未知 | 先查询已有创建结果，不再次创建 |
| 缺少自动接续工具 | 保持当前任务继续，或交付交接正文 |
| Hooks未运行 | 核对Python、Skill路径、登记会话、宿主事件支持与信任状态 |

## 测试和兼容性

Python **3.11+**，只使用标准库，无需`pip install`。核心测试覆盖来源改写、归档保真、未知操作、防重放、30轮增长、完整保存、接续设置及失败退出码。

```bash
python3 -B -m unittest discover -s dev-continuity/scripts -p test_continuity.py
python3 -B -m unittest discover -s . -p test_install.py
python3 -B examples/demo.py
```

CI覆盖Windows和Ubuntu的Python 3.11/3.14。CI验证本地脚本，不等于所有Codex版本的真实Hooks、自动任务创建或首轮模型设置均已验收。macOS脚本按标准库设计，未列入本仓库CI矩阵。

记录体积变小不能直接证明token或费用净节省；不要以测试数量、归档数量或新任务数量代替开发完成。

## 参与和许可

问题和建议：[GitHub Issues](https://github.com/tpk1990404/dev-continuity/issues)。提交前阅读[贡献指南](CONTRIBUTING.md)和[行为准则](CODE_OF_CONDUCT.md)；敏感问题通过[安全政策](SECURITY.md)中的私密渠道报告。

[MIT License](LICENSE)。项目源码与文档允许按许可证使用、修改及分发。GitHub社区文件遵循其[README说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)与[开源许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)组织；GitHub开源仓库不等于官方插件商店认证。
