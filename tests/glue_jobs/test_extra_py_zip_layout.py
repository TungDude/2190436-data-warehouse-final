"""Regression test for the libs.zip layout that Glue's --extra-py-files needs.

We build the zip the same way Terraform does (archive_file in glue.tf), then
spawn a fresh Python interpreter with the zip on sys.path and confirm that:
  1. `import registry` works without the `glue_jobs.bronze_to_silver` package
     prefix (Glue's flat sys.path),
  2. `registry.get('chicago_crime')` returns a handler whose `transform`
     attribute is callable.

The subprocess gets a clean import-cache and the zip is the only thing on
sys.path that exposes the package, so we exercise the production layout.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = ROOT / "src" / "glue_jobs" / "bronze_to_silver"


def _build_libs_zip(dest: Path) -> Path:
    """Mirror the Terraform archive_file logic: zip the package excluding
    main.py and Python build artefacts."""
    zip_path = dest / "libs.zip"
    excludes = {"main.py"}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in PACKAGE_DIR.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(PACKAGE_DIR)
            if rel.parts[0] in excludes:
                continue
            if "__pycache__" in rel.parts:
                continue
            if path.suffix in {".pyc", ".pyo"}:
                continue
            zf.write(path, arcname=str(rel))
    return zip_path


def test_libs_zip_is_importable_under_glue_flat_sys_path(tmp_path):
    zip_path = _build_libs_zip(tmp_path)

    # Sanity: the zip preserves the package directory structure that
    # zipimport needs.
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert "registry.py" in names
    assert "common.py" in names
    assert "sources/chicago_crime.py" in names
    assert "main.py" not in names

    probe = (
        "import sys; "
        f"sys.path.insert(0, {str(zip_path)!r}); "
        "from registry import get; "
        "h = get('chicago_crime'); "
        "assert callable(h.transform), 'transform not callable'; "
        "assert h.SOURCE_NAME == 'chicago_crime'; "
        "print('OK')"
    )

    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, (
        f"zip-layout import failed.\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert result.stdout.strip() == "OK"
