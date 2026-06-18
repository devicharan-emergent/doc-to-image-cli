#!/usr/bin/env bash
# Installer for the doc-to-image CLI.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/devicharan-emergent/doc-to-image-cli/main/install.sh | bash
# Opt-in DOCX support (installs LibreOffice via apt; +~1 GB):
#   curl -fsSL ...install.sh | INSTALL_DOCX=1 bash
#
# Creates an isolated Python venv at $INSTALL_DIR (default /opt/doc-to-image),
# pip-installs the package + PyMuPDF into it, and drops a thin shim at
# $BIN_PATH (default /usr/local/bin/doc-to-image) so the agent can invoke
# `doc-to-image` from anywhere.

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/doc-to-image}"
BIN_PATH="${BIN_PATH:-/usr/local/bin/doc-to-image}"
REPO_URL="${REPO_URL:-https://github.com/devicharan-emergent/doc-to-image-cli.git}"
REPO_REF="${REPO_REF:-main}"
PYTHON="${PYTHON:-python3}"
INSTALL_DOCX="${INSTALL_DOCX:-0}"

log() { printf '[doc-to-image] %s\n' "$*"; }
die() { printf '[doc-to-image] ERROR: %s\n' "$*" >&2; exit 1; }

command -v "${PYTHON}" >/dev/null 2>&1 || die "python3 not found on PATH"
command -v git >/dev/null 2>&1 || die "git not found on PATH (needed by pip to fetch the package)"

log "Creating isolated venv at ${INSTALL_DIR}/venv"
mkdir -p "${INSTALL_DIR}"
"${PYTHON}" -m venv "${INSTALL_DIR}/venv"

log "Upgrading pip"
"${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip

log "Installing doc-to-image (+ pymupdf) from ${REPO_URL}@${REPO_REF}"
"${INSTALL_DIR}/venv/bin/pip" install --quiet "git+${REPO_URL}@${REPO_REF}"

if [ "${INSTALL_DOCX}" = "1" ]; then
  if command -v libreoffice >/dev/null 2>&1 || command -v soffice >/dev/null 2>&1; then
    log "LibreOffice already present — skipping apt install"
  elif command -v apt-get >/dev/null 2>&1; then
    log "Installing LibreOffice (DOCX support; ~1 GB)"
    sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
      libreoffice-core libreoffice-writer
  else
    log "WARNING: INSTALL_DOCX=1 but apt-get not found — install LibreOffice manually for DOCX support"
  fi
fi

log "Writing shim at ${BIN_PATH}"
cat > "${BIN_PATH}" <<EOF
#!/usr/bin/env bash
exec "${INSTALL_DIR}/venv/bin/doc-to-image" "\$@"
EOF
chmod +x "${BIN_PATH}"

log "Installed. Try: doc-to-image --help"
