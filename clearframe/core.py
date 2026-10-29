from __future__ import annotations

import json
import os
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps


GENERAL_MODEL = "realesrgan-x4plus"
SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEOS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
Progress = Callable[[str, int | None], None]
VIDEO_BATCH_SIZE = 32
VIDEO_FRAME_JPEG_QUALITY = 98


class EnhancementError(RuntimeError):
    """A user-readable processing error."""


def _run(command: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise EnhancementError(f"Tool tidak ditemukan: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise EnhancementError("Pemrosesan melewati batas waktu.") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        detail = detail[-1600:] if detail else "Tidak ada detail dari tool pemrosesan."
        raise EnhancementError(detail)
    return result


def _ffprobe(path: Path) -> dict:
    result = _run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EnhancementError("Metadata file tidak dapat dibaca.") from exc


def _engine_command(engine: Path, model_dir: Path, input_path: Path, output_path: Path,
                    scale: int, *, tile: int = 256) -> list[str]:
    return [
        str(engine), "-i", str(input_path), "-o", str(output_path),
        "-n", GENERAL_MODEL, "-s", str(scale), "-t", str(tile),
        "-m", str(model_dir), "-f", "png",
    ]


def _blend_and_save(source: Image.Image, ai_result: Image.Image, output: Path,
                    scale: int, strength: int, output_format: str = "PNG") -> None:
    source = ImageOps.exif_transpose(source)
    alpha = source.getchannel("A") if source.mode in ("RGBA", "LA") else None
    rgb = source.convert("RGB")
    target_size = (rgb.width * scale, rgb.height * scale)
    baseline = rgb.resize(target_size, Image.Resampling.LANCZOS)
    enhanced = ai_result.convert("RGB")
    if enhanced.size != target_size:
        raise EnhancementError(
            f"Model mengembalikan ukuran {enhanced.width}×{enhanced.height}, "
            f"padahal yang diharapkan {target_size[0]}×{target_size[1]}."
        )
    result = Image.blend(baseline, enhanced, max(0, min(100, strength)) / 100.0)
    if alpha is not None:
        enlarged_alpha = alpha.resize(target_size, Image.Resampling.LANCZOS)
        result.putalpha(enlarged_alpha)
    save_args = {"format": output_format}
    if output_format.upper() == "WEBP":
        save_args["quality"] = 96
        save_args["method"] = 6
    elif output_format.upper() in {"JPEG", "JPG"}:
        save_args["quality"] = VIDEO_FRAME_JPEG_QUALITY
        save_args["subsampling"] = 0
    result.save(output, **save_args)


def enhance_image(source_path: Path, output_path: Path, work_dir: Path,
                  engine: Path, model_dir: Path, scale: int = 2,
                  strength: int = 35, progress: Progress | None = None) -> None:
    if progress:
        progress("Menyiapkan foto", 5)
    work_dir.mkdir(parents=True, exist_ok=True)
    input_png = work_dir / "input.png"
    model_png = work_dir / "model-output.png"
    try:
        with Image.open(source_path) as opened:
            source = ImageOps.exif_transpose(opened).copy()
        alpha = source.getchannel("A") if source.mode in ("RGBA", "LA") else None
        rgb = source.convert("RGB")
        rgb.save(input_png, format="PNG")
        if progress:
            progress("Meningkatkan detail foto", 20)
        _run(_engine_command(engine, model_dir, input_png, model_png, scale))
        with Image.open(model_png) as output:
            result = output.copy()
        # Keep the original alpha channel separately; the neural model is used for RGB only.
        source_for_blend = rgb if alpha is None else Image.merge("RGBA", (*rgb.split(), alpha))
        _blend_and_save(source_for_blend, result, output_path, scale, strength, "PNG")
        if progress:
            progress("Selesai", 100)
    except EnhancementError:
        raise
    except Exception as exc:
        raise EnhancementError(f"Gagal memproses foto: {exc}") from exc
    finally:
        input_png.unlink(missing_ok=True)
        model_png.unlink(missing_ok=True)


def _fps_from_stream(stream: dict) -> Fraction:
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = stream.get(key)
        if value and value != "0/0":
            try:
                fps = Fraction(value)
                if fps > 0:
                    return fps
            except (ValueError, ZeroDivisionError):
                pass
    return Fraction(30, 1)


def _frame_durations(source_path: Path, frame_count: int, fps: Fraction) -> list[float]:
    if frame_count <= 0:
        raise EnhancementError("Video tidak memiliki frame yang dapat diproses.")
    result = _run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time,pkt_duration_time",
        "-of", "json", str(source_path),
    ])
    try:
        frames = json.loads(result.stdout).get("frames", [])
    except json.JSONDecodeError:
        frames = []
    fallback = float(1 / fps)
    timestamps: list[float | None] = []
    packet_durations: list[float | None] = []
    for frame in frames[:frame_count]:
        try:
            timestamps.append(float(frame["best_effort_timestamp_time"]))
        except (KeyError, TypeError, ValueError):
            timestamps.append(None)
        try:
            packet_durations.append(float(frame["pkt_duration_time"]))
        except (KeyError, TypeError, ValueError):
            packet_durations.append(None)
    if len(timestamps) != frame_count:
        return [fallback] * frame_count
    durations: list[float] = []
    for index in range(frame_count):
        dt = None
        if index + 1 < frame_count and timestamps[index] is not None and timestamps[index + 1] is not None:
            candidate = timestamps[index + 1] - timestamps[index]
            if candidate > 0:
                dt = candidate
        if dt is None and index < len(packet_durations) and packet_durations[index] and packet_durations[index] > 0:
            dt = packet_durations[index]
        durations.append(dt if dt and dt > 0 else fallback)
    return durations


def _concat_quote(path: Path) -> str:
    # Work paths are generated UUIDs, but escape defensively for ffconcat syntax.
    return str(path).replace("'", "'\\''")


def _encode_video(concat_list: Path, source_path: Path, output_path: Path,
                  duration: float | None, keep_audio: bool) -> None:
    base = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-safe", "0", "-f", "concat", "-i", str(concat_list),
        "-i", str(source_path), "-map", "0:v:0",
    ]
    if keep_audio:
        base += ["-map", "1:a?"]
    base += ["-map_metadata", "-1", "-c:v", "libx264", "-preset", "medium",
             "-crf", "17", "-pix_fmt", "yuv420p", "-fps_mode", "vfr"]
    if keep_audio:
        base += ["-c:a", "copy"]
    if duration and duration > 0:
        base += ["-t", f"{duration:.6f}"]
    base += ["-movflags", "+faststart", str(output_path)]
    try:
        _run(base)
    except EnhancementError:
        if not keep_audio:
            raise
        output_path.unlink(missing_ok=True)
        # Some uncommon source audio codecs cannot be copied into MP4; transcode only then.
        fallback = base.copy()
        audio_index = fallback.index("-c:a")
        fallback[audio_index:audio_index + 2] = ["-c:a", "aac", "-b:a", "192k"]
        _run(fallback)


def enhance_video(source_path: Path, output_path: Path, work_dir: Path,
                  engine: Path, model_dir: Path, scale: int = 2,
                  strength: int = 35, keep_audio: bool = True,
                  progress: Progress | None = None,
                  max_seconds: int = 180,
                  batch_size: int = VIDEO_BATCH_SIZE) -> None:
    if batch_size < 1:
        raise EnhancementError("Ukuran batch frame harus minimal 1.")
    work_dir.mkdir(parents=True, exist_ok=True)
    input_dir = work_dir / "frames-in"
    output_dir = work_dir / "frames-out"
    input_dir.mkdir()
    output_dir.mkdir()
    concat_list = work_dir / "frames.ffconcat"
    try:
        metadata = _ffprobe(source_path)
        video_streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
        if not video_streams:
            raise EnhancementError("File ini tidak memiliki track video.")
        video_stream = video_streams[0]
        duration_text = metadata.get("format", {}).get("duration") or video_stream.get("duration")
        duration = float(duration_text) if duration_text else None
        if duration and duration > max_seconds:
            raise EnhancementError(f"Batas prototipe saat ini {max_seconds} detik per video.")
        fps = _fps_from_stream(video_stream)
        if progress:
            progress("Mengekstrak frame dan menjaga urutannya", 5)
        _run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_path),
            "-map", "0:v:0", "-fps_mode", "passthrough", "-start_number", "0",
            str(input_dir / "frame_%08d.png"),
        ])
        source_frames = sorted(input_dir.glob("frame_*.png"))
        if not source_frames:
            raise EnhancementError("FFmpeg tidak menemukan frame video.")
        durations = _frame_durations(source_path, len(source_frames), fps)
        if progress:
            progress(f"Meningkatkan {len(source_frames)} frame ({scale}×) dalam batch", 15)
        for start in range(0, len(source_frames), batch_size):
            batch_input = work_dir / "batch-in"
            batch_output = work_dir / "batch-ai"
            batch_input.mkdir()
            batch_output.mkdir()
            originals = source_frames[start:start + batch_size]
            try:
                for original_path in originals:
                    link_path = batch_input / original_path.name
                    try:
                        os.link(original_path, link_path)
                    except OSError:
                        shutil.copyfile(original_path, link_path)
                _run(_engine_command(engine, model_dir, batch_input, batch_output, scale))
                ai_frames = sorted(batch_output.glob("frame_*.png"))
                if len(ai_frames) != len(originals):
                    raise EnhancementError(
                        "Jumlah frame berubah saat peningkatan batch "
                        f"{start // batch_size + 1} ({len(originals)} → {len(ai_frames)})."
                    )
                for offset, (original_path, ai_path) in enumerate(zip(originals, ai_frames)):
                    index = start + offset
                    with Image.open(original_path) as original, Image.open(ai_path) as ai:
                        original_copy, ai_copy = original.copy(), ai.copy()
                    if original_copy.mode in ("RGBA", "LA"):
                        alpha = original_copy.getchannel("A")
                        blend_source = Image.merge("RGBA", (*original_copy.convert("RGB").split(), alpha))
                    else:
                        blend_source = original_copy.convert("RGB")
                    _blend_and_save(
                        blend_source, ai_copy,
                        output_dir / f"frame_{index:08d}.jpg",
                        scale, strength, "JPEG",
                    )
            finally:
                shutil.rmtree(batch_input, ignore_errors=True)
                shutil.rmtree(batch_output, ignore_errors=True)
            completed = min(start + len(originals), len(source_frames))
            if progress:
                progress(
                    f"Memproses frame {completed}/{len(source_frames)}",
                    15 + int(60 * completed / len(source_frames)),
                )
        output_frames = sorted(output_dir.glob("frame_*.jpg"))
        if len(output_frames) != len(source_frames):
            raise EnhancementError(
                f"Jumlah frame hasil berubah ({len(source_frames)} → {len(output_frames)})."
            )
        with concat_list.open("w", encoding="utf-8") as listing:
            listing.write("ffconcat version 1.0\n")
            for path, frame_duration in zip(output_frames, durations):
                listing.write(f"file '{_concat_quote(path)}'\n")
                listing.write(f"duration {frame_duration:.9f}\n")
            # The concat demuxer applies the final duration to a following entry.
            listing.write(f"file '{_concat_quote(output_frames[-1])}'\n")
        if progress:
            progress("Mengodekan video dan menyalin audio asli", 96)
        _encode_video(concat_list, source_path, output_path, duration, keep_audio)
        if progress:
            progress("Selesai", 100)
    except EnhancementError:
        raise
    except Exception as exc:
        raise EnhancementError(f"Gagal memproses video: {exc}") from exc
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
