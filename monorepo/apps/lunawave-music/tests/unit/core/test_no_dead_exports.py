import ast
import os
import re
from pathlib import Path


def test_no_dead_exports_in_security_module():
    """
    Memastikan setiap fungsi public di security.py (nama tanpa awalan underscore)
    dipanggil minimal 1 kali di luar file itu sendiri (di seluruh monorepo).
    Test ini mencegah akumulasi dead code seperti fungsi verify_token() lama.

    Phase 2 dari framework extraction (docs/extraction/) memindahkan
    implementasi asli security.py ke packages/lunawave-framework/. File
    core/security.py di app repo sekarang cuma backward-compat shim (impor
    ulang, tidak ada `def` di sana) -- jadi target scan AST diarahkan ke
    lokasi implementasi yang sebenarnya, dan pencarian caller diperluas ke
    seluruh monorepo (apps/ + packages/), bukan cuma app repo, karena
    caller yang sah sekarang bisa muncul di kedua sisi.
    """
    app_repo_root = Path(__file__).resolve().parent.parent.parent.parent
    monorepo_root = app_repo_root.parent.parent
    security_file = (
        monorepo_root
        / "packages"
        / "lunawave-framework"
        / "src"
        / "lunawave_framework"
        / "core"
        / "security"
        / "security.py"
    )

    # Allowlist untuk fungsi yang memang disiapkan untuk modul lain yang belum ditulis
    # atau ada alasan sah lainnya.
    allowlist = set()

    with open(security_file, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(security_file))

    # Temukan semua public function defs
    public_funcs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if not node.name.startswith("_"):
                public_funcs.append(node.name)

    # Walk seluruh monorepo (apps/ + packages/) mencari caller
    # Untuk kesederhanaan, kita bisa membaca semua file .py (kecuali
    # security.py itu sendiri) dan mengecek kemunculan nama fungsinya
    # sebagai word boundary (misal: \bfunc_name\b). Namun karena ini unit
    # test, performa pencarian dalam memori untuk repo kecil masih oke.
    py_files_content = []
    for root, _, files in os.walk(monorepo_root):
        if (
            ".git" in root
            or "__pycache__" in root
            or ".pytest_cache" in root
            or "venv" in root
            or ".venv" in root
        ):
            continue
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                if file_path.resolve() == security_file.resolve():
                    continue
                try:
                    with open(file_path, encoding="utf-8") as f:
                        py_files_content.append(f.read())
                except Exception:
                    pass

    all_content_str = "\n".join(py_files_content)

    dead_funcs = []
    for func in public_funcs:
        if func in allowlist:
            continue

        # Cari exact match sebagai identifier (batas \b)
        pattern = re.compile(rf"\b{func}\b")
        if not pattern.search(all_content_str):
            dead_funcs.append(func)

    assert not dead_funcs, (
        f"Fungsi public di security.py (packages/lunawave-framework/.../security.py) "
        f"tidak terpakai di tempat lain di monorepo: {', '.join(dead_funcs)}. "
        f"Hapus fungsi tersebut, atau tambahkan ke allowlist jika ada alasan sah."
    )
