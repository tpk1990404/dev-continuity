# Contributing / 参与贡献

欢迎可复现的问题报告、文档纠正和范围明确的PR。中英文均可。

1. 先搜索已有Issue，说明实际问题及预期行为，避免为假设需求增加新存储或调度层。
2. 使用Python 3.11+；运行README中的两组unittest及离线示例，不需要安装第三方库。
3. 修改存储、交接或恢复逻辑时，补充能暴露原问题的回归用例；覆盖来源完整性、未知操作、防重放和向后兼容边界。
4. 文档中的模拟结果、真实宿主集成和真实业务验收分开描述；不以测试数量或文件体积宣称token节省。
5. PR写清具体问题、行为变化和验证结果。不要提交私有笔记、`.dev-continuity`数据、用户目录、令牌、安装计划或备份。

保持少依赖、小改动，沿用标准库和现有结构。用户授权不能由安装脚本或示例默认授予。

By submitting a contribution, you agree that it may be distributed under this repository's MIT license. Report vulnerabilities through [SECURITY.md](SECURITY.md), not a public reproduction containing private data. Follow our [Code of Conduct](CODE_OF_CONDUCT.md).
