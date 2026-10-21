#!/usr/bin/env bash
# MeshForge for Maya - Automated Installer for macOS & Linux

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="${SCRIPT_DIR}/meshforge_maya"

echo "======================================================================"
echo "          MeshForge for Maya - Automated Installer (Unix)            "
echo "======================================================================"

if [ ! -d "${PKG_DIR}" ]; then
    echo "[ERROR] Could not find folder meshforge_maya in ${SCRIPT_DIR}"
    exit 1
fi

# Detect OS and set Maya directory
if [[ "$OSTYPE" == "darwin"* ]]; then
    MAYA_BASE="${HOME}/Library/Preferences/Autodesk/maya"
else
    MAYA_BASE="${HOME}/maya"
fi

MODULES_DIR="${MAYA_BASE}/modules"
SCRIPTS_DIR="${MAYA_BASE}/scripts"

mkdir -p "${MODULES_DIR}"
mkdir -p "${SCRIPTS_DIR}"

MOD_FILE="${MODULES_DIR}/meshforge_maya.mod"
echo "+ meshforge_maya 0.2.0 ${PKG_DIR}" > "${MOD_FILE}"
echo "PYTHONPATH +:= .." >> "${MOD_FILE}"

echo "[OK] Created module descriptor: ${MOD_FILE}"

USERSETUP="${SCRIPTS_DIR}/userSetup.py"
HOOK="# --- MeshForge Maya Startup Integration ---"

if [ -f "${USERSETUP}" ] && grep -q "${HOOK}" "${USERSETUP}"; then
    echo "[OK] Startup integration was already active in userSetup.py"
else
    cat <<EOF >> "${USERSETUP}"

# --- MeshForge Maya Startup Integration ---
import sys
mf_path = r'${SCRIPT_DIR}'
if mf_path not in sys.path:
    sys.path.insert(0, mf_path)
EOF
    echo "[OK] Registered in ${USERSETUP}"
fi

echo ""
echo "======================================================================"
echo "  SUCCESS: MeshForge for Maya has been successfully installed!        "
echo "======================================================================"
echo "Open Maya and run: import meshforge_maya; meshforge_maya.show()"
echo "Or drag 'install.mel' into the 3D viewport for a Shelf button."
echo ""
