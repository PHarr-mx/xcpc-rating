# AI Agent Skills

> **目录**：`skill/`  
> **用途**：Cursor Agent 使用的项目专属工作流指引（`SKILL.md`），与 `docs/`（给人看）和代码注释分离。

---

## 已有技能

| 目录 | 用途 |
|------|------|
| [formal-import/](../skill/formal-import/SKILL.md) | 正式赛导入（`xcpcio_xlsx`）：收集参数 → 预览解析 → 执行导入 → 手动补录打星队 → 报告结果 |
| [player-manage/](../skill/player-manage/SKILL.md) | 选手名册增删改查：检查 → 去重 → 执行 → 报告 |

---

## 技能文件约定

- 每个技能一个子目录，包含 `SKILL.md`
- 技能文件描述 AI 助手应遵循的操作步骤、异常处理、文件引用
- 禁止在技能中写爬取逻辑、子串匹配等不规范操作