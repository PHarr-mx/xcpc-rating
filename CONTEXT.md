# 会话上下文

> 最近更新：2026-09-26 · 本文记录「最近一次盘点对话」的结论，供下次打开快速恢复；进度本体见 [PROGRESS.md](PROGRESS.md)，计划与剩余工作见 [docs/08-路线图.md](docs/08-路线图.md)。

## 项目当前状态（2026-09-26）

- **里程碑：一期 ✅ 二期 ✅ 三期 ✅**；四期（业务补齐）、五期（上线）未开始
- **Web P0–P5 全部完成**：榜单 `/`、认证、`/profile`、管理后台 P4a–P4d、`/about`、`/players/{id}`、`/contests/{id}`、URL query 同步、赛年/赛季筛选
- **旁路二项全清**（2026-09-26）：alembic 迁移体系落地（基线 `0001_baseline`，真库已 stamp）+ formal 导入 DTO 前置校验；core 138 + web 94 全绿
- Rating 仍为 `placeholder_v0`（名次线性分 + 做题加成，数值无业务含义）——这是四期要解决的核心

## 最近几次会话做了什么（2026-09-15 → 09-26）

1. **alembic 引入（旁路项一）**：
   - `xcpc_core/db/migrations/`：`env.py`（URL 程序化注入，`render_as_batch=True`）+ `0001_baseline`（16 张表，autogenerate 后人工核对）+ `revision.py`（`uv run python -m xcpc_core.db.migrations.revision -m "..."` 生成后续迁移）。
   - `run_migrations(url)` 自愈式接线：全新库 `upgrade head`；存量库（有 `meta` 表无 `alembic_version`）自动 `stamp head`；`db/migrate.py` 已改用它，`session.create_all` 删除。
   - 守护测试 4 条（`db/tests/test_migrations.py`）：内存库拒绝、fresh upgrade、**漂移检测**（`compare_metadata` 零差异——改 `tables.py` 不写迁移直接红）、存量库 stamp 幂等。
   - 真库 `data/db/xcpc.db` 已 stamp 到 `0001_baseline`（17 张表含 alembic_version，数据完好）。
   - 范围决策：**只接管业务库 xcpc.db**；认证库 `xcpc_web.db`（Reflex SQLModel 独立 metadata）四期不碰，继续 create_all。
2. **formal 导入 DTO 前置校验（旁路项二）**：
   - Pydantic 层：解析结果四不变量（total_teams/total_problems>0、本校队伍非空、有获奖）进 `XcpcioParsedContest` model_validator，`parse_xcpcio_xlsx` 尾部过程式检查删除；`FormalImportParams` 加纯校验——`contest_type` 非空白、`contest_id` 非空白且禁 `/` `\` `..`（此前 contest_id 直接 f-string 拼进 `raw/formal/{id}.json`，存在路径穿越窟窿，已堵上）。
   - 入口层：contest_type 权重表查证前置到 `import_formal_xcpcio_xlsx` 与 `stage_formal_xlsx` 的**最前**（打开任何文件之前），报错列出全部合法类型及标签（`weights.load_formal_types` 新增）；staged 的 `_contest_meta` 改为接收已解析权重（原 `parsed` 参数本来就没用）。
   - 设计要点：**YAML 依赖的校验不进 Pydantic validator**——直接构造（全仓库唯一构造方式）没有 context 可传 repo_root，validator 裸调 find_repo_root 会破坏临时仓库测试隔离；故纯校验进 DTO、配置校验进入口（repo_root 注入约定不变）。
   - 测试 16 条（`importer/tests/test_import_validation.py`），含「前置性证明」：传不存在的 xlsx 路径 + 错误 type，断言抛"未知 contest_type"而非 FileNotFoundError。
3. **上次遗留的 `pelican-riding-bicycle.svg` 已消失**（未跟踪文件，无需处理）。

更早（2026-09-10 → 09-15）：三期关闭、GAP 评估并入路线图、榜单 URL query 同步、data_version 写路径自动 bump、`/about`、P5 详情页（players/contests + recharts）、docs 九篇重构、赛年/赛季筛选真实生效、测试盲区补齐、推送 `90b0cef..aa412c0`。

## 关键技术结论（下次开发直接复用，避免重踩）

### alembic 约定（2026-09-26 起）
- **改 `tables.py` 必须生成迁移**：`uv run python -m xcpc_core.db.migrations.revision -m "..."`（autogenerate 拿 metadata 与 head 状态真库 diff，**生成后人工核对再提交**）；漏写会被 `test_models_match_migrations_no_drift` 拦下。
- 测试内存库**不走 alembic**（自开连接 `:memory:` 建完即丢），conftest 继续 `Base.metadata.create_all`；`run_migrations` 对 `:memory:` 显式抛错。
- `env.py` 开 `render_as_batch=True`：SQLite ALTER 受限，加列/改列走 batch，别手写裸 `op.add_column` 之外的 SQLite DDL。
- 认证库 `xcpc_web.db` 不在迁移体系内（SQLModel `ModelRegistry` 独立 metadata，`create_admin.py` 建）；若将来动它再单独收编。

### Reflex 0.9.7 要点
- State 链手工构建：`_reflex_internal_init=True` + 父链（如 LocalAuthState→AuthState→目标 State）。
- **动态路由参数不能声明同名 state var**（`DynamicRouteArgShadowsStateVarError`），从 `self.router.page.params` 读；`is_self` 等时敏判断也要直读 params 而非 on_load 设置的 var。
- Var 约束：不能 iterate/`or`/`bool()` 一个 Var；列表/字典视图在 State 里**预计算成 view dict**；`rx.cond` 构建时两个分支都求值（`href=None` 会炸，用 `""` 哨兵）；计算属性要 `cache=False`。
- `rx.redirect(path, replace=True)` = 客户端导航（URL 同步用）。

### 测试红线
- **测试里禁止 `import xcpc_web.xcpc_web`（app 模块）**：顶层 `rx.App()` 会破坏 conftest 手搭的 State 链，引发 49 个跨测试 DB 复用失败。
- conftest 用 `configure_session(session)` / `configure_store(store)` DI 注入内存 SQLite（player/team/contest/audit/importer/rating/board 全部已接）；真实 DB 零改动。
- 测试命令：core `uv run python -m pytest xcpc_core -v`（根目录）；web `cd xcpc_web && ../.venv/bin/python -m pytest tests -v`。根 pyproject testpaths 只含 xcpc_core。

### 数据层约定
- board 缓存 key `(mode, period_key, data_version)`；写路径 bump（`db/meta.bump_data_version`）后缓存自动换 key。
- schema 唯一入口 `db.migrations.run_migrations`；`db/migrate.py` = schema 升级 + raw 灌数据（幂等）。
- `RatingEvent` 无 contest_id 字段，从 `event_id.split("#",1)[0]` 取前缀（与 delete_contest 约定一致）。
- openpyxl xcpcio 格式：A1 标题、第 2 行表头、第 3 行起数据；需 A–H 连续题列；只有获奖本校队进 standings。
- web 导入测试需要把 `contest_weights.yaml` **和** `school.yaml` 都拷进临时仓库。

## 下一步（docs/08-路线图 §3）

1. **四期第一步 = 业务定案（写代码前必须拍板）**：① Rating 正式公式（加权 Elo / 队内分摊 / 时间衰减 / 初始分与封顶，见 docs/04 §2–3）；② 训练赛成绩分摊规则（均分 vs 按贡献）。助手已提议产出「公式决策稿」：2–3 个候选公式 + 用现有省赛数据算示例值 + 优劣与实现成本，供用户评审。
2. **四期实现（依赖定案；动表结构已有 alembic 兜底）**：计算器替换（版本号 + 缓存联动 + 测试重写）→ 训练赛录入（导入入口 + `load_training_weight` + raw/training 归档）→ `/admin/rating` 试算页（P6，试算不落库）→ 图表升级。
3. **五期（四期后）**：先定**注册限制**（邀请码 / 域名白名单，公网前必须），再做部署三件套（生产 rxconfig、`reflex export` + rsync、systemd、Caddy、备份 cron，清单见 docs/06 §7——schema 迁移步骤已补入）。
4. 挂起的 12 条开放决策见 docs/08 §4，其中仅 #1 公式、#2 分摊、#4 注册限制是阻塞项。

当前分叉点：**「公式决策稿」是下一个动作**（旁路已清空），等用户拍板后动工。

## 常用命令速查

```bash
source ./setup_env.sh                    # 环境激活（uv 版，项目根目录）
uv run python -m pytest xcpc_core -v     # core 测试
cd xcpc_web && ../.venv/bin/reflex run   # 开发服务器（3000/8000）
uv run python -m xcpc_core.db.migrate    # schema 迁移 + raw 灌数据（幂等）
uv run python -m xcpc_core.db.migrations.revision -m "..."  # 改 tables.py 后生成迁移
```
