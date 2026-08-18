# 开发进度

> 最近更新：2026-08-18 · 对照 [docs/13-实施路线图.md](docs/13-实施路线图.md)
>
> 记录原则：只记「结论 + 日期」，设计细节留在 `docs/`，变更细节看 git log。

## 总体状态

一期「地基」已完成：数据链全通，72 测试全绿，Reflex 骨架（P0）+ 榜单只读页（P1）均已上线。二~五期未开始。

## 分期进度

| 期 | 内容 | 状态 | 备注 |
|----|------|------|------|
| 一期 | 地基 | ✅ 已完成 | P0 骨架 + P1 榜单页均完成 |
| 二期 | 认证 | ⬜ 未开始 | 依赖一期上线 |
| 三期 | 管理后台 | ⬜ 未开始 | |
| 四期 | 业务补齐 | ⬜ 未开始 | |
| 五期 | 上线 | ⬜ 未开始 | |

## 一期明细

- ✅ 2026-08-02 `pyproject.toml` 统一打包（uv，Python 3.13），`xcpc_core` 单顶层包；`reflex==0.9.7` 声明为可选依赖 `[web]`
- ✅ 2026-08-02 SQLite 建表（`xcpc_core/db/tables.py`）+ store 重构为 repository + `migrate` 一次性迁移（幂等）
- ✅ 2026-08-02 player / team CRUD 六件套（含 CLI），正式赛导入（raw + DB 双写，四川省赛数据已入库归档）
- ✅ 2026-08-02 contest 模块（Contest/Standing upsert）、rating 引擎（placeholder 公式）
- ✅ 2026-08-17 board 榜单聚合（`BoardSnapshot`、竞赛排名、`delta_recent`、`data_version` 进程内缓存）
- ✅ 2026-08-18 Reflex 骨架（`xcpc_web/`，P0 完成）：reflex init 脚手架、包骨架、首页展示真实数据、`reflex run` 起成功
- ✅ 2026-08-18 `/` 榜单只读页（P1 完成）：BoardState 状态管理、筛选/排序/搜索、表格渲染、元信息展示
- ⬜ `xcpc-data update` CLI（`xcpc-site build|deploy` 随静态站方案废弃，可砍）

**一期完成标志**：能用真实数据在浏览器看到榜单。✅ 已达成。

## 实测快照（2026-08-18）

- 测试：72 passed
- DB：24 选手 / 8 队伍 / 1 正式赛（8 standings）；`ratingevent`、`auditlog`、`ojcontest` 等表为空
- 榜单：`board()` 输出 21 行，`algorithm=placeholder_v0`（数值无业务含义，真公式在四期）
- `data/raw/training/`、`data/public/` 为空

## 开放问题（同步自路线图 §5）

- `data/public/` 只读导出是否有外部消费者 —— 待确认，无则砍掉
- 队员自助绑定意愿 —— 待确认

## 日志

| 日期 | 事项 |
|------|------|
| 2026-08-02 | 一期地基主体完成：打包、SQLite、CRUD、导入、contest/rating |
| 2026-08-17 | board 榜单聚合完成（commit `5fff907`） |
| 2026-08-18 | 首次进度盘点；下一步：创建 `xcpc_web` Reflex 骨架 |
| 2026-08-18 | P0 Reflex 骨架完成（`xcpc_web/`，空壳页可运行，core 桥接通） |
| 2026-08-18 | P1 榜单只读页完成（BoardState、筛选/排序/搜索、表格渲染）；一期关闭 |
