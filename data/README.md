# data

数据文件目录，**不含代码**。约定见 [docs/DESIGN.md](../docs/DESIGN.md) 第 2 节。

| 子目录 | 说明 | Git |
|--------|------|-----|
| `raw/` | 原始输入（选手名册、比赛成绩等） | 提交（样例已内置） |
| `config/` | 权重等配置（`contest_weights.yaml`） | 提交 |
| `processed/` | 规范化中间 JSON | 忽略（构建生成） |
| `public/` | 面向前端的导出 JSON | 可提交样例或忽略 |
| `schemas/` | JSON Schema | 随定义提交 |

`raw/` 说明见 [raw/README.md](raw/README.md)。

由 `backend/data` 写入 `processed/`、`public/`；`frontend` 与 Caddy 读取 `public/`。
