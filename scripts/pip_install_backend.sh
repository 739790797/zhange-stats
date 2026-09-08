#!/usr/bin/env bash
# EasyOCR 会依赖 torch。PyPI 默认 Linux 轮是 CUDA（数 GB）。
# 先装官方 CPU 轮并钉住版本，再 pip install -r。
set -euo pipefail

PYTHON="${1:?python}"
BACKEND_DIR="${2:?backend dir}"
REQ="${BACKEND_DIR}/requirements.txt"
INDEX="https://download.pytorch.org/whl/cpu"

if [[ ! -f "${REQ}" ]]; then
  echo "缺少 ${REQ}" >&2
  exit 1
fi

"${PYTHON}" -m pip install torch torchvision --index-url "${INDEX}"
CONSTRAINT="$(mktemp)"
trap 'rm -f "${CONSTRAINT}"' EXIT
"${PYTHON}" -m pip freeze | grep -E '^(torch|torchvision)==' > "${CONSTRAINT}" || true
if [[ -s "${CONSTRAINT}" ]]; then
  "${PYTHON}" -m pip install -r "${REQ}" -c "${CONSTRAINT}"
else
  "${PYTHON}" -m pip install -r "${REQ}"
fi
"${PYTHON}" -m pip uninstall -y opencv-python >/dev/null 2>&1 || true
"${PYTHON}" -m pip install -q --force-reinstall --no-deps "opencv-python-headless>=4.8.0"
