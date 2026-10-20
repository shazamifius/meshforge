"""MeshForge - Système autonome de vérification et d'installation des mises à jour.
Interagit avec l'API publique GitHub du dépôt shazamifius/meshforge.
Fonctionne de manière non-bloquante (asynchrone) sans jamais geler l'interface Blender.
"""

from __future__ import annotations
import os
import sys
import json
import re
import shutil
import tempfile
import threading
import time
import zipfile
import urllib.request
import urllib.error
import ssl

REPO_OWNER = "shazamifius"
REPO_NAME = "meshforge"
GITHUB_REPO = f"{REPO_OWNER}/{REPO_NAME}"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}"
GITHUB_RELEASES_URL = f"{GITHUB_API_URL}/releases/latest"
GITHUB_ALL_RELEASES_URL = f"{GITHUB_API_URL}/releases"
GITHUB_TAGS_URL = f"{GITHUB_API_URL}/tags"
GITHUB_COMMITS_URL = f"{GITHUB_API_URL}/commits/master"
GITHUB_ZIPBALL_URL = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/master.zip"
GITHUB_PAGE_URL = f"https://github.com/{GITHUB_REPO}"

# État global du gestionnaire de mise à jour (thread-safe)
_UPDATE_LOCK = threading.Lock()
_UPDATE_STATE = {
    "status": "IDLE",            # IDLE, CHECKING, UPDATE_AVAILABLE, UP_TO_DATE, DOWNLOADING, INSTALLED, ERROR
    "has_update": False,
    "current_version": "0.1.0",
    "latest_version": "0.1.0",
    "release_title": "",
    "release_notes": "",
    "download_url": "",
    "release_url": GITHUB_PAGE_URL,
    "last_check_time": 0.0,
    "last_check_str": "Jamais",
    "error_message": "",
    "download_progress": 0,      # 0 à 100
}


def get_addon_root() -> str:
    """Retourne le répertoire racine contenant l'add-on MeshForge."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_current_version_str() -> str:
    """Récupère la version actuelle depuis __init__.py ou blender_manifest.toml."""
    try:
        root = get_addon_root()
        # 1. Essayer le fichier __init__.py
        init_path = os.path.join(root, "__init__.py")
        if os.path.exists(init_path):
            with open(init_path, "r", encoding="utf-8") as f:
                content = f.read()
                m = re.search(r'"version"\s*:\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', content)
                if m:
                    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"

        # 2. Essayer blender_manifest.toml
        manifest_path = os.path.join(root, "blender_manifest.toml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()
                m = re.search(r'version\s*=\s*"([^"]+)"', content)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return "0.1.0"


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Convertit une chaîne de version ('0.1.0', 'v1.2.3', 'v0.2') en tuple d'entiers."""
    cleaned = version_str.strip().lstrip("vV")
    parts = []
    for piece in cleaned.split("."):
        # Extraire les chiffres initiaux
        sub = re.match(r"^(\d+)", piece)
        if sub:
            parts.append(int(sub.group(1)))
        else:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer_version(candidate_ver: str, current_ver: str) -> bool:
    """Compare deux versions sémantiques. Retourne True si candidate > current."""
    t_cand = parse_version_tuple(candidate_ver)
    t_curr = parse_version_tuple(current_ver)
    return t_cand > t_curr


def get_update_state() -> dict:
    """Retourne une copie de l'état actuel de mise à jour."""
    with _UPDATE_LOCK:
        return dict(_UPDATE_STATE)


def _set_update_state(**kwargs):
    with _UPDATE_LOCK:
        _UPDATE_STATE.update(kwargs)


def _create_ssl_context():
    """Crée un contexte SSL sécurisé tolérant aux certificats de l'environnement."""
    ctx = ssl.create_default_context()
    return ctx


def check_for_updates_sync(timeout: float = 8.0) -> dict:
    """Interroge l'API GitHub de manière synchrone pour détecter les mises à jour.
    
    Retourne un dictionnaire contenant le diagnostic complet.
    """
    curr_ver = get_current_version_str()
    _set_update_state(
        status="CHECKING",
        current_version=curr_ver,
        error_message=""
    )

    headers = {
        "User-Agent": f"MeshForge-Addon/{curr_ver} (Blender; Python {sys.version.split()[0]})",
        "Accept": "application/vnd.github.v3+json",
    }

    ctx = _create_ssl_context()
    has_update = False
    latest_ver = curr_ver
    release_title = ""
    release_notes = ""
    download_url = GITHUB_ZIPBALL_URL
    release_url = GITHUB_PAGE_URL

    try:
        # Étape 1 : Vérifier la dernière 'Release' formelle
        req = urllib.request.Request(GITHUB_RELEASES_URL, headers=headers)
        release_data = None
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                if resp.status == 200:
                    release_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code != 404:  # 404 est normal si aucune release formelle n'a encore été publiée
                raise

        if release_data:
            tag = release_data.get("tag_name", "").strip()
            latest_ver = tag.lstrip("vV")
            release_title = release_data.get("name", f"Version {latest_ver}")
            release_notes = release_data.get("body", "")
            release_url = release_data.get("html_url", GITHUB_PAGE_URL)

            # Recherche d'un asset zip dédié (ex: meshforge.zip)
            assets = release_data.get("assets", [])
            for asset in assets:
                asset_name = asset.get("name", "").lower()
                if asset_name.endswith(".zip"):
                    download_url = asset.get("browser_download_url")
                    break
            if not download_url:
                download_url = release_data.get("zipball_url", GITHUB_ZIPBALL_URL)

            has_update = is_newer_version(latest_ver, curr_ver)

        else:
            # Étape 2 : Si pas de release, inspecter les tags GitHub
            req_tags = urllib.request.Request(GITHUB_TAGS_URL, headers=headers)
            with urllib.request.urlopen(req_tags, timeout=timeout, context=ctx) as resp:
                tags_data = json.loads(resp.read().decode("utf-8"))

            if tags_data and isinstance(tags_data, list) and len(tags_data) > 0:
                top_tag = tags_data[0].get("name", "").strip()
                latest_ver = top_tag.lstrip("vV")
                download_url = tags_data[0].get("zipball_url", GITHUB_ZIPBALL_URL)
                release_title = f"Version {latest_ver}"
                release_notes = f"Tag Git : {top_tag}"
                has_update = is_newer_version(latest_ver, curr_ver)
            else:
                # Aucun tag ou release : le dépôt est au commit initial
                latest_ver = curr_ver
                has_update = False
                release_title = f"MeshForge v{curr_ver}"
                release_notes = "Vous disposez de la version la plus récente."

        # Succès de la vérification
        status = "UPDATE_AVAILABLE" if has_update else "UP_TO_DATE"
        now_str = time.strftime("%d/%m/%Y à %H:%M")
        
        _set_update_state(
            status=status,
            has_update=has_update,
            current_version=curr_ver,
            latest_version=latest_ver,
            release_title=release_title,
            release_notes=release_notes,
            download_url=download_url,
            release_url=release_url,
            last_check_time=time.time(),
            last_check_str=now_str,
            error_message=""
        )

    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower():
            err_msg = "Délai d'attente dépassé (vérifiez votre connexion internet)."
        elif "nodename nor servname provided" in err_msg.lower() or "getaddrinfo failed" in err_msg.lower():
            err_msg = "Impossible de joindre GitHub (vérifiez votre connexion internet)."
        
        _set_update_state(
            status="ERROR",
            error_message=err_msg,
            last_check_time=time.time(),
            last_check_str=time.strftime("%d/%m/%Y à %H:%M")
        )

    return get_update_state()


def check_for_updates_async(callback=None):
    """Lance la recherche de mise à jour en arrière-plan sans bloquer Blender."""
    def worker():
        res = check_for_updates_sync()
        if callback:
            try:
                callback(res)
            except Exception:
                pass
        
        # Redessiner l'interface Blender si possible
        try:
            import bpy
            def redraw():
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
                return None
            bpy.app.timers.register(redraw)
        except Exception:
            pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def install_update_sync(download_url: str | None = None) -> tuple[bool, str]:
    """Télécharge l'archive de mise à jour et met à jour l'add-on sur place de façon sécurisée.
    
    Retourne (succès: bool, message: str).
    """
    state = get_update_state()
    url = download_url or state.get("download_url") or GITHUB_ZIPBALL_URL
    addon_dir = get_addon_root()

    # Vérification d'intégrité du répertoire cible
    if not os.path.exists(os.path.join(addon_dir, "__init__.py")):
        return False, f"Répertoire add-on invalide : {addon_dir}"

    _set_update_state(status="DOWNLOADING", download_progress=0)

    tmp_dir = tempfile.mkdtemp(prefix="meshforge_update_")
    zip_path = os.path.join(tmp_dir, "update.zip")
    extract_dir = os.path.join(tmp_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    try:
        headers = {
            "User-Agent": "MeshForge-Updater",
            "Accept": "application/octet-stream, application/zip, */*",
        }
        is_local_file = url.startswith("file://") or os.path.isabs(url)
        if is_local_file:
            local_src = url[7:] if url.startswith("file://") else url
            if local_src.startswith("/") and len(local_src) > 2 and local_src[2] == ":":
                local_src = local_src[1:]
            shutil.copy2(local_src, zip_path)
            _set_update_state(download_progress=100)
        else:
            ctx = _create_ssl_context()
            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=30.0, context=ctx) as response, open(zip_path, "wb") as out_file:
                total_bytes = 0
                if hasattr(response, "getheader"):
                    total_size = response.getheader("Content-Length")
                    total_bytes = int(total_size) if total_size and total_size.isdigit() else 0
                elif hasattr(response, "headers") and response.headers:
                    total_size = response.headers.get("Content-Length")
                    total_bytes = int(total_size) if total_size and total_size.isdigit() else 0

                downloaded = 0
                block_size = 16384

                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes > 0:
                        prog = int((downloaded / total_bytes) * 100)
                        _set_update_state(download_progress=prog)

        if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
            return False, "Le téléchargement de l'archive a échoué (fichier vide)."

        # Extraction et inspection
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        # Identifier où se trouvent les fichiers réels de l'add-on
        # Cas 1 : Archive GitHub release directe (fichiers à la racine de l'archive)
        # Cas 2 : Archive zipball GitHub (les fichiers sont dans un sous-dossier type 'shazamifius-meshforge-xyz')
        source_content_dir = extract_dir
        if not os.path.exists(os.path.join(extract_dir, "__init__.py")):
            subdirs = [os.path.join(extract_dir, d) for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
            for sd in subdirs:
                if os.path.exists(os.path.join(sd, "__init__.py")):
                    source_content_dir = sd
                    break

        if not os.path.exists(os.path.join(source_content_dir, "__init__.py")):
            return False, "Archive corrompue : __init__.py introuvable dans la mise à jour."

        # Remplacement sélectif sécurisé :
        items_to_copy = [
            "__init__.py",
            "blender_manifest.toml",
            "preferences.py",
            "properties.py",
            "CHANGELOG.md",
            "README.md",
            "LICENSES.md",
            "core",
            "operators",
            "ui",
            "tools",
        ]

        for item in items_to_copy:
            src_item = os.path.join(source_content_dir, item)
            dst_item = os.path.join(addon_dir, item)

            if os.path.exists(src_item):
                if os.path.isdir(src_item):
                    if os.path.exists(dst_item):
                        shutil.rmtree(dst_item)
                    shutil.copytree(src_item, dst_item)
                else:
                    shutil.copy2(src_item, dst_item)

        # Nettoyage des éventuels pycache résiduels
        for root_d, dirs, files in os.walk(addon_dir):
            if "__pycache__" in dirs:
                try:
                    shutil.rmtree(os.path.join(root_d, "__pycache__"))
                except Exception:
                    pass

        new_ver = get_current_version_str()
        _set_update_state(
            status="INSTALLED",
            has_update=False,
            current_version=new_ver,
            latest_version=new_ver
        )

        return True, f"Mise à jour v{new_ver} installée avec succès ! Redémarrez Blender pour charger la nouvelle version."

    except Exception as e:
        _set_update_state(status="ERROR", error_message=str(e))
        return False, f"Erreur pendant l'installation : {e}"

    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
