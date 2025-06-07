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
        cli.write_text(""\"#!/bin/bash\nexec python3 -m pyp "$@"\n""\")
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
