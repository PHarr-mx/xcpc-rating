#!/usr/bin/env bash
# xcpc-rating 开发环境初始化
#
# 用法（须在项目根目录 source，激活才会留在当前 shell）:
#   source ./setup_env.sh
#   # 或
#   . ./setup_env.sh

set -euo pipefail

ENV_NAME="xcpc_rating"
PYTHON_VERSION="3.13"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS="${ROOT_DIR}/requirements.txt"

# backend/data → player 包；backend → utils 包
PYTHONPATH_VALUE="${ROOT_DIR}/backend/data:${ROOT_DIR}/backend"

_is_sourced() {
  [[ "${BASH_SOURCE[0]}" != "${0}" ]]
}

_init_conda() {
  local candidates=(
    "${CONDA_EXE:+$(dirname "$(dirname "$CONDA_EXE")")/etc/profile.d/conda.sh}"
    "${HOME}/miniconda3/etc/profile.d/conda.sh"
    "${HOME}/anaconda3/etc/profile.d/conda.sh"
    "/opt/miniconda3/etc/profile.d/conda.sh"
    "/usr/local/miniconda3/etc/profile.d/conda.sh"
  )

  for conda_sh in "${candidates[@]}"; do
    if [[ -n "${conda_sh}" && -f "${conda_sh}" ]]; then
      # shellcheck disable=SC1090
      source "${conda_sh}"
      return 0
    fi
  done

  if command -v conda &>/dev/null; then
    return 0
  fi

  echo "错误: 未找到 conda，请先安装 Miniconda/Anaconda 或手动初始化 conda。" >&2
  return 1
}

_env_exists() {
  conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"
}

_create_env() {
  echo ">>> 创建 conda 环境: ${ENV_NAME} (python=${PYTHON_VERSION})"
  conda create -n "${ENV_NAME}" "python=${PYTHON_VERSION}" pip -y
}

_install_deps() {
  echo ">>> 安装 Python 依赖: ${REQUIREMENTS}"
  conda run -n "${ENV_NAME}" python -m pip install -U pip
  conda run -n "${ENV_NAME}" python -m pip install -r "${REQUIREMENTS}"
}

_activate_and_export() {
  conda activate "${ENV_NAME}"
  export PYTHONPATH="${PYTHONPATH_VALUE}${PYTHONPATH:+:${PYTHONPATH}}"
  export XCPC_RATING_ROOT="${ROOT_DIR}"

  echo ">>> 已激活环境: ${ENV_NAME}"
  echo ">>> Python: $(python --version)"
  echo ">>> PYTHONPATH=${PYTHONPATH}"
  echo ">>> 可运行: pytest"
  echo ">>> 可运行: xcpc-player list --visible-only"
}

_main() {
  if ! _is_sourced; then
    echo "请使用 source 运行本脚本，以便 conda 激活与 PYTHONPATH 生效:" >&2
    echo "  source ${ROOT_DIR}/setup_env.sh" >&2
    return 1 2>/dev/null || exit 1
  fi

  _init_conda

  if ! _env_exists; then
    _create_env
    _install_deps
  else
    echo ">>> conda 环境已存在: ${ENV_NAME}"
    # 依赖未装或版本过旧时补装（pip install 幂等）
    if ! conda run -n "${ENV_NAME}" python -c "import player, utils" &>/dev/null; then
      echo ">>> 检测到依赖缺失，正在安装..."
      _install_deps
    fi
  fi

  _activate_and_export
}

_main
