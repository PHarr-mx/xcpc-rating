# AI Agent Skills

> **目录**：`skill/`  
> **用途**：AI Agent 使用的项目专属工作流指引（`SKILL.md`），与 `docs/`（给人看）和代码注释分离。
> 开发工作流与 Agent 协作建议见 [12-开发流程建议](12-开发流程建议.md) §7。

---

## 已有技能

| 目录 | 用途 |
|------|------|
| [formal-import/](../skill/formal-import/SKILL.md) | 正式赛导入（`xcpcio_xlsx`）：收集参数 → 预览解析 → 执行导入 → 手动补录打星队 → 报告结果 |
| [player-manage/](../skill/player-manage/SKILL.md) | 选手名册增删改查：检查 → 去重 → 执行 → 报告 |
| [team-manage/](../skill/team-manage/SKILL.md) | 队伍名册增删改查：队员集合识别、别名管理 |

---

## 技能文件约定

- 每个技能一个子目录，包含 `SKILL.md`
- 技能文件描述 AI 助手应遵循的操作步骤、异常处理、文件引用
- 禁止在技能中写爬取逻辑、子串匹配等不规范操作
- 技能内的 CLI/API 路径随包结构迁移（`backend/data` → `xcpc_core`）同步更新
