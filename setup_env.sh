#!/usr/bin/env bash
# xcpc-rating 开发环境（uv 版）
#
# 用法（须在项目根目录 source，激活才会留在当前 shell）:
#   source ./setup_env.sh
#
# 等价于:
#   uv sync
#   . .venv/bin/activate

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "错误: 未找到 uv。安装: brew install uv" >&2
  return 1
fi

cd "${ROOT_DIR}"
uv sync
# shellcheck disable=SC1091
. .venv/bin/activate

echo ">>> 已激活虚拟环境: ${VIRTUAL_ENV}"
echo ">>> Python: $(python --version)"
echo ">>> 可运行: python -m xcpc_core.player.cli list --visible-only"
echo ">>> 测试:   uv run python -m pytest xcpc_core -v"
