# Backend Python

`data/` 数据流水线（`player` 等包）、`utils/` 公共工具（`Plog` 等）。

包结构与 **CLI 入口** 在仓库根目录 [`pyproject.toml`](../pyproject.toml) 统一配置。

## Conda（推荐）

在项目根目录：

```bash
source ./setup_env.sh
```

## 手动安装

```bash
conda create -n xcpc_rating python=3.13 pip -y
conda activate xcpc_rating
pip install -r requirements.txt   # 等价于 pip install -e ".[dev]"

pytest
xcpc-player list --visible-only
```

见 [docs/DESIGN.md](../docs/DESIGN.md)。
