#!/usr/bin/env python3
"""Download the official portable Real-ESRGAN runtime and keep only its general model."""
from __future__ import annotations

import os
import platform
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get("CLEARFRAME_RUNTIME", ROOT / ".runtime")).expanduser().resolve()
VERSION = "v0.2.5.0"
ASSETS = {
    "Linux": ("realesrgan-ncnn-vulkan-20220424-ubuntu.zip", "realesrgan-ncnn-vulkan"),
    "Darwin": ("realesrgan-ncnn-vulkan-20220424-macos.zip", "realesrgan-ncnn-vulkan"),
    "Windows": ("realesrgan-ncnn-vulkan-20220424-windows.zip", "realesrgan-ncnn-vulkan.exe"),
}
MODEL_FILES = (
    "models/realesrgan-x4plus.bin",
    "models/realesrgan-x4plus.param",
)


def main() -> int:
    system = platform.system()
    if system not in ASSETS:
        print(f"Platform belum didukung: {system}. Gunakan Linux, macOS, atau Windows.", file=sys.stderr)
        return 2
    archive_name, executable_name = ASSETS[system]
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    model_dir = RUNTIME / "models"
    executable = RUNTIME / executable_name
    expected = [executable, *(model_dir / Path(item).name for item in MODEL_FILES)]
    if all(path.is_file() for path in expected):
        print("Backend general-purpose sudah terpasang.")
        return 0

    url = f"https://github.com/xinntao/Real-ESRGAN/releases/download/{VERSION}/{archive_name}"
    print(f"Mengunduh backend Real-ESRGAN resmi ({system})…")
    fd, temp_name = tempfile.mkstemp(prefix="clearframe-backend-", suffix=".zip", dir=RUNTIME)
    os.close(fd)
    temp_archive = Path(temp_name)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ClearFrame-local-prototype"})
        with urllib.request.urlopen(request, timeout=60) as response, temp_archive.open("wb") as out:
            shutil.copyfileobj(response, out)
        with zipfile.ZipFile(temp_archive) as archive:
            names = set(archive.namelist())
            required = {executable_name, *MODEL_FILES}
            missing = required - names
            if missing:
                raise RuntimeError(f"Release resmi tidak menyertakan file yang dibutuhkan: {sorted(missing)}")
            model_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            with archive.open(executable_name) as src, executable.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            for member in MODEL_FILES:
                target = model_dir / Path(member).name
                with archive.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        if system != "Windows":
            executable.chmod(executable.stat().st_mode | 0o111)
        print(f"Backend siap di {RUNTIME}")
        print("Hanya model umum realesrgan-x4plus yang dipasang; model anime tidak diekstrak.")
        print("Catatan: Linux/macOS memerlukan Vulkan yang bekerja dan FFmpeg tersedia di PATH.")
        return 0
    except Exception as exc:
        for path in expected:
            path.unlink(missing_ok=True)
        print(f"Gagal memasang backend: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        temp_archive.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
