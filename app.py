from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from clearframe.core import (
    EnhancementError,
    SUPPORTED_IMAGES,
    SUPPORTED_VIDEOS,
    enhance_image,
    enhance_video,
)


ROOT = Path(__file__).resolve().parent
RUNTIME_DIR = Path(os.environ.get("CLEARFRAME_RUNTIME", ROOT / ".runtime")).expanduser().resolve()
DATA_ROOT = Path(os.environ.get(
    "CLEARFRAME_DATA_DIR", Path(tempfile.gettempdir()) / "clearframe-local"
)).expanduser().resolve()
MAX_UPLOAD_BYTES = int(os.environ.get("CLEARFRAME_MAX_UPLOAD_BYTES", 512 * 1024 * 1024))
JOB_TTL_SECONDS = int(os.environ.get("CLEARFRAME_JOB_TTL_SECONDS", 3600))
MAX_VIDEO_SECONDS = int(os.environ.get("CLEARFRAME_MAX_VIDEO_SECONDS", 180))


class JobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clearframe")
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()

    def _cleanup_loop(self) -> None:
        while True:
            time.sleep(60)
            self.expire()

    def create(self, job: dict) -> None:
        with self.lock:
            self.jobs[job["id"]] = job

    def get(self, job_id: str) -> dict | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def update(self, job_id: str, **changes) -> None:
        with self.lock:
            if job_id in self.jobs:
                if changes.get("status") in {"complete", "error"}:
                    changes.setdefault("finished", time.time())
                self.jobs[job_id].update(changes)

    def expire(self) -> None:
        now = time.time()
        with self.lock:
            expired = [
                key for key, job in self.jobs.items()
                if job.get("status") not in {"queued", "processing"}
                and now - job.get("finished", job.get("created", now)) > JOB_TTL_SECONDS
            ]
            for key in expired:
                self.jobs.pop(key, None)
                shutil.rmtree(DATA_ROOT / key, ignore_errors=True)


def _backend_paths() -> tuple[Path, Path]:
    exe = "realesrgan-ncnn-vulkan.exe" if os.name == "nt" else "realesrgan-ncnn-vulkan"
    engine = RUNTIME_DIR / exe
    model_dir = RUNTIME_DIR / "models"
    return engine, model_dir


def _run_job(store: JobStore, job_id: str, input_path: Path, output_path: Path,
             work_dir: Path, extension: str, scale: int, strength: int, keep_audio: bool) -> None:
    engine, model_dir = _backend_paths()
    try:
        store.update(job_id, status="processing", message="Menyiapkan pemrosesan", progress=1)

        def update_progress(message: str, value: int | None) -> None:
            store.update(job_id, message=message, progress=value)

        if extension in SUPPORTED_IMAGES:
            enhance_image(input_path, output_path, work_dir, engine, model_dir,
                          scale=scale, strength=strength, progress=update_progress)
        else:
            enhance_video(input_path, output_path, work_dir, engine, model_dir,
                          scale=scale, strength=strength, keep_audio=keep_audio,
                          progress=update_progress, max_seconds=MAX_VIDEO_SECONDS)
        store.update(job_id, status="complete", message="Selesai", progress=100,
                     output_size=output_path.stat().st_size)
    except EnhancementError as exc:
        store.update(job_id, status="error", message="Tidak dapat menyelesaikan enhancement",
                     error=str(exc), progress=None)
    except Exception as exc:
        store.update(job_id, status="error", message="Terjadi kesalahan saat memproses file",
                     error=f"{type(exc).__name__}: {exc}", progress=None)
    finally:
        input_path.unlink(missing_ok=True)
        shutil.rmtree(work_dir, ignore_errors=True)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    store = JobStore()
    app.extensions["clearframe_job_store"] = store
    DATA_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)

    @app.get("/")
    def home():
        engine, model_dir = _backend_paths()
        backend_ready = engine.is_file() and all(
            (model_dir / f"realesrgan-x4plus{suffix}").is_file() for suffix in (".bin", ".param")
        )
        return render_template(
            "index.html", backend_ready=backend_ready,
            max_upload_mb=MAX_UPLOAD_BYTES // (1024 * 1024),
            max_video_seconds=MAX_VIDEO_SECONDS,
        )

    @app.get("/api/health")
    def health():
        engine, model_dir = _backend_paths()
        ready = engine.is_file() and all(
            (model_dir / f"realesrgan-x4plus{suffix}").is_file() for suffix in (".bin", ".param")
        )
        return jsonify({"ok": True, "backend_ready": ready})

    @app.post("/api/jobs")
    def submit_job():
        store.expire()
        engine, model_dir = _backend_paths()
        if not engine.is_file() or not all(
            (model_dir / f"realesrgan-x4plus{suffix}").is_file() for suffix in (".bin", ".param")
        ):
            return jsonify({"error": "Backend belum di-install. Jalankan scripts/install_backend.py."}), 503
        uploaded = request.files.get("file")
        if uploaded is None or not uploaded.filename:
            return jsonify({"error": "Pilih satu file foto atau video."}), 400
        safe_name = secure_filename(uploaded.filename)
        extension = Path(safe_name).suffix.lower()
        if extension not in SUPPORTED_IMAGES | SUPPORTED_VIDEOS:
            return jsonify({"error": "Format yang didukung: JPG, PNG, WebP, MP4, MOV, M4V, MKV, dan WebM."}), 415
        try:
            scale = int(request.form.get("scale", "2"))
            strength = int(request.form.get("strength", "30"))
        except ValueError:
            return jsonify({"error": "Nilai skala atau strength tidak valid."}), 400
        if scale not in (2, 4) or not 0 <= strength <= 100:
            return jsonify({"error": "Gunakan skala 2×/4× dan strength 0–100%."}), 400
        keep_audio = request.form.get("keep_audio", "true").lower() in {"true", "1", "on", "yes"}
        job_id = uuid.uuid4().hex
        job_dir = DATA_ROOT / job_id
        job_dir.mkdir(parents=True, mode=0o700)
        input_path = job_dir / f"input{extension}"
        output_extension = ".png" if extension in SUPPORTED_IMAGES else ".mp4"
        output_path = job_dir / f"clearframe_{scale}x{output_extension}"
        work_dir = job_dir / "work"
        uploaded.save(input_path)
        job = {
            "id": job_id,
            "status": "queued",
            "message": "Menunggu antrean",
            "progress": 0,
            "created": time.time(),
            "original_name": safe_name,
            "output_name": f"ClearFrame_{Path(safe_name).stem}_{scale}x{output_extension}",
            "output_path": str(output_path),
            "error": None,
        }
        store.create(job)
        store.executor.submit(_run_job, store, job_id, input_path, output_path, work_dir,
                              extension, scale, strength, keep_audio)
        return jsonify({"id": job_id, "status": "queued"}), 202

    @app.get("/api/jobs/<job_id>")
    def job_status(job_id: str):
        store.expire()
        job = store.get(job_id)
        if job is None:
            return jsonify({"error": "Tugas tidak ditemukan atau hasilnya sudah kedaluwarsa."}), 404
        result = {key: job.get(key) for key in ("id", "status", "message", "progress", "error", "output_size")}
        if job.get("status") == "complete":
            result["download_url"] = f"/api/jobs/{job_id}/download"
            result["output_name"] = job.get("output_name")
        return jsonify(result)

    @app.get("/api/jobs/<job_id>/download")
    def download(job_id: str):
        store.expire()
        job = store.get(job_id)
        if not job or job.get("status") != "complete":
            return jsonify({"error": "Hasil belum siap atau sudah kedaluwarsa."}), 404
        path = Path(job["output_path"])
        if not path.is_file():
            return jsonify({"error": "File hasil sudah tidak tersedia."}), 404
        return send_file(path, as_attachment=True, download_name=job["output_name"])

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({"error": f"Ukuran file melebihi batas {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."}), 413

    return app


app = create_app()

if __name__ == "__main__":
    host = os.environ.get("CLEARFRAME_HOST", "127.0.0.1")
    port = int(os.environ.get("CLEARFRAME_PORT", "7860"))
    if host not in {"127.0.0.1", "localhost", "::1"}:
        print("PERHATIAN: server dapat diakses dari jaringan. Pakai hanya jaringan privat tepercaya.", flush=True)
    app.run(host=host, port=port, threaded=True)
