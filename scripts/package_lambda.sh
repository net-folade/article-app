#!/usr/bin/env bash
# Build a Lambda zip with Linux x86_64 packages.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${ROOT}/build"
STAGE="${BUILD}/package"
ZIP="${BUILD}/deploy.zip"

PY_VERSION="3.13"
PLATFORM="manylinux2014_x86_64"

# Confirm the staging path before deleting it.
if [[ "${STAGE}" != "${ROOT}/build/package" ]]; then
  echo "refusing to clean unexpected path: ${STAGE}" >&2
  exit 1
fi

echo "==> cleaning ${BUILD}"
rm -rf -- "${STAGE}"
rm -f -- "${ZIP}"
mkdir -p "${STAGE}"

echo "==> installing dependencies for ${PLATFORM}, python ${PY_VERSION}"
python3 -m pip install \
  --quiet \
  --requirement "${ROOT}/requirements.txt" \
  --target "${STAGE}" \
  --platform "${PLATFORM}" \
  --python-version "${PY_VERSION}" \
  --implementation cp \
  --only-binary=:all: \
  --upgrade

# Keep src at the zip root. Lambda already includes boto3.
echo "==> copying src/"
cp -R "${ROOT}/src" "${STAGE}/src"
# Keep *.dist-info because some packages read it at runtime.
find "${STAGE}" -type d -name __pycache__ -prune -exec rm -rf -- {} +

echo "==> zipping"
(cd "${STAGE}" && zip -qr "${ZIP}" .)

SIZE=$(du -h "${ZIP}" | cut -f1)
echo "==> ${ZIP} (${SIZE})"
