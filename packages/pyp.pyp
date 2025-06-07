__pyp_name__ = "pyp"
__pyp_ver__ = "2.0.0"
__pyp_deps__ = ""
__pyp_cli__ = True
__pyp_files__ = {
    "pyp.py": """
#!/usr/bin/env python3

import ast
import os
import sys
import site
import shutil
import subprocess
import urllib.request
from pathlib import Path

PYP_PATH = os.path.abspath(__file__)

STORE = Path.home() / ".pypstore"
CACHE = Path.home() / ".pypcache"

def load_pyp_metadata(pyp_file: str) -> dict:
    with open(pyp_file, "r") as f:
        source = f.read()

    tree = ast.parse(source, filename=pyp_file)
    meta = {}
    context = {"__file__": pyp_file}

    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            key = node.targets[0]
            if isinstance(key, ast.Name) and key.id.startswith("__pyp_"):
                expr = ast.Expression(body=node.value)
                compiled = compile(expr, filename="<pyp>", mode="eval")
                value = eval(compiled, context)
                meta[key.id] = value
                context[key.id] = value

    return meta

import json

PYPPI_REPO = Path.home() / "Projects/pyppi"  # <-- Update path to your pyppi repo
PYPPI_REGISTRY = PYPPI_REPO / "registry.json"
PYPPI_PACKAGES = PYPPI_REPO / "packages"

def push(pyp_file):
    meta = load_pyp_metadata(pyp_file)
    name = meta["__pyp_name__"]
    version = meta.get("__pyp_ver__", "0.0.1")
    cli = bool(meta.get("__pyp_cli__", False))
    desc = meta.get("__doc__", "").strip().splitlines()[0] if "__doc__" in meta else "No description."
    
    PYPPI_PACKAGES.mkdir(parents=True, exist_ok=True)
    target = PYPPI_PACKAGES / f"{name}.pyp"
    shutil.copy(pyp_file, target)

    if PYPPI_REGISTRY.exists():
        with open(PYPPI_REGISTRY) as f:
            registry = json.load(f)
    else:
        registry = {}

    registry[name] = {
        "name": name,
        "version": version,
        "url": f"https://zimoshi.github.io/pyppi/packages/{name}.pyp",
        "description": desc,
        "cli": cli
    }

    with open(PYPPI_REGISTRY, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"✅ Pushed {name} v{version} to local PyPPI at {target}")
    print(f"👉 Next: cd {PYPPI_REPO} && git add . && git commit -m 'Add {name} v{version}' && git push")

import base64
import configparser
import requests

def load_pyppi_config():
    cfg = configparser.ConfigParser()
    cfg.read(Path.home() / ".pyprc")
    section = cfg["pyppi"]
    return section["repo"], section["token"]

def github_upload_file(repo, token, path, content_bytes, message):
    api = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}"}
    content_encoded = base64.b64encode(content_bytes).decode("utf-8")

    # Check if file exists (for SHA)
    res = requests.get(api, headers=headers)
    sha = res.json().get("sha") if res.status_code == 200 else None

    payload = {
        "message": message,
        "content": content_encoded,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    res = requests.put(api, headers=headers, json=payload)
    if res.status_code in (200, 201):
        print(f"✅ Uploaded: {path}")
    else:
        print(f"[!] Failed to upload {path}: {res.json().get('message')}")

def push_remote(pyp_file):
    meta = load_pyp_metadata(pyp_file)
    name = meta["__pyp_name__"]
    version = meta.get("__pyp_ver__", "0.0.1")
    cli = bool(meta.get("__pyp_cli__", False))
    desc = meta.get("__doc__", "").strip().splitlines()[0] if "__doc__" in meta else "No description."

    repo, token = load_pyppi_config()

    # Upload .pyp file
    with open(pyp_file, "rb") as f:
        content_bytes = f.read()
    github_upload_file(repo, token, f"packages/{name}.pyp", content_bytes, f"Add {name} v{version}")

    # Update registry
    registry_url = f"https://raw.githubusercontent.com/{repo}/main/registry.json"
    r = requests.get(registry_url)
    registry = r.json() if r.status_code == 200 else {}

    registry[name] = {
        "name": name,
        "version": version,
        "url": f"https://zimoshi.github.io/pyppi/packages/{name}.pyp",
        "description": desc,
        "cli": cli
    }

    github_upload_file(repo, token, "registry.json", json.dumps(registry, indent=2).encode(), f"Update registry: {name} v{version}")

def install(pyp_file):
    meta = load_pyp_metadata(pyp_file)
    name = meta["__pyp_name__"]
    version = meta.get("__pyp_ver__", "0.0.1")
    deps = meta.get("__pyp_deps__", "")
    files = meta["__pyp_files__"]

    print(f"📦 Installing {name} v{version}...")

    # Create store dir
    module_dir = STORE / name
    if module_dir.exists():
        print(f"[!] Already installed at {module_dir}")
        return

    module_dir.mkdir(parents=True, exist_ok=True)
    for fname, content in files.items():
        (module_dir / fname).write_text(content.strip())

    # Install dependencies
    if deps.strip():
        subprocess.run([sys.executable, "-m", "pip", "install"] + deps.split(","))

    # Symlink to site-packages
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    site_path = Path(site.getsitepackages()[-1])
    symlink_path = site_path / name

    if not os.access(site_path, os.W_OK):
        print("[!] No write access to site-packages, using user site instead.")
        site_path = Path(site.USER_SITE)
        symlink_path = site_path / name

    if symlink_path.exists():
        print(f"[!] Symlink already exists at {symlink_path}")
    else:
        symlink_path.parent.mkdir(parents=True, exist_ok=True)
        symlink_path.symlink_to(module_dir)

    # CLI shim
    if meta.get("__pyp_cli__", False):
        bin_path = Path("/usr/local/bin") / name
        shim = f'#!/bin/bash\nexec python3 -m {name} "$@"\n'
        try:
            with open(bin_path, "w") as f:
                f.write(shim)
            os.chmod(bin_path, 0o755)
            print(f"🔗 CLI available at: {bin_path}")
        except PermissionError:
            print(f"[!] Cannot create CLI at {bin_path}, try with sudo.")

    print(f"✅ Installed {name} → {symlink_path}")

def uninstall(name):
    module_dir = STORE / name
    symlink_path = None

    for path in site.getsitepackages() + [site.USER_SITE]:
        candidate = Path(path) / name
        if candidate.exists() and candidate.is_symlink():
            symlink_path = candidate
            break

    if symlink_path and symlink_path.exists():
        symlink_path.unlink()
        print(f"🧹 Removed symlink: {symlink_path}")
    else:
        print("ℹ️ No symlink found.")

    if module_dir.exists():
        shutil.rmtree(module_dir)
        print(f"🗑️  Removed stored module: {module_dir}")
    else:
        print("ℹ️ No module store found.")

    cli_path = Path("/usr/local/bin") / name
    if cli_path.exists():
        cli_path.unlink()
        print(f"🗑️  Removed CLI: {cli_path}")

def run(name):
    try:
        module = __import__(name)
        if hasattr(module, "main"):
            module.main()
        else:
            print(f"[!] No 'main' function found in {name}.")
    except Exception as e:
        print(f"[!] Failed to run {name}: {e}")

def list_installed():
    if not STORE.exists():
        print("No packages installed.")
        return
    for mod in STORE.iterdir():
        if mod.is_dir():
            print(f"- {mod.name}")

def fetch(pyp_url):
    if not pyp_url.startswith("pyp:"):
        print("[!] Invalid fetch URL.")
        return

    try:
        _, host, path = pyp_url.split(":", 2)
    except ValueError:
        print("[!] Invalid format. Use: pyp:host:path/to/file.pyp")
        return

    url = f"https://{host}/{path}"
    fname = Path(path).name
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / fname

    print(f"🌐 Fetching from {url}")
    try:
        urllib.request.urlretrieve(url, target)
        print(f"✅ Saved as {target}")
    except Exception as e:
        print(f"[!] Fetch failed: {e}")
        return

    install(str(target))  # auto-install

def ensure_cli_wrapper():
    cli = Path("/usr/local/bin/pyp")
    if not cli.exists():
        print("Installing CLI wrapper at /usr/local/bin/pyp")
        cli.write_text(f"#!/bin/bash\\nexec python3 {PYP_PATH} \\"$@\\"\\n")
        cli.chmod(0o755)

def main():
    ensure_cli_wrapper()

    if len(sys.argv) < 2:
        print("Usage: pyp <install|uninstall|run|list|fetch> [args]")
        return

    cmd = sys.argv[1]
    if cmd == "install" and len(sys.argv) == 3:
        install(sys.argv[2])
    elif cmd == "uninstall" and len(sys.argv) == 3:
        uninstall(sys.argv[2])
    elif cmd == "run" and len(sys.argv) == 3:
        run(sys.argv[2])
    elif cmd == "list":
        list_installed()
    elif cmd == "fetch" and len(sys.argv) == 3:
        fetch(sys.argv[2])
    elif cmd == "push" and len(sys.argv) == 3:
        push(sys.argv[2])
    elif cmd == "push" and len(sys.argv) == 4 and sys.argv[3] == "--remote":
        push_remote(sys.argv[2])
    else:
        print("Invalid command.")

if __name__ == "__main__":
    main()
""",
    "__init__.py": """
from .pyp import main
if __name__ == '__main__':
    main()
"""
}
