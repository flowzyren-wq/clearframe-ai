from __future__ import annotations

import json
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

from app import RUNTIME_DIR, create_app
from clearframe.core import _blend_and_save, _engine_command, enhance_image, enhance_video


ENGINE = RUNTIME_DIR / ("realesrgan-ncnn-vulkan.exe" if os.name == "nt" else "realesrgan-ncnn-vulkan")
MODEL_DIR = RUNTIME_DIR / "models"
BACKEND_READY = ENGINE.is_file() and all(
    (MODEL_DIR / f"realesrgan-x4plus{suffix}").is_file() for suffix in (".bin", ".param")
)


@unittest.skipUnless(BACKEND_READY, "Install backend first: python scripts/install_backend.py")
class EnhancementSmokeTests(unittest.TestCase):
    def test_intermediate_video_frame_is_full_size_high_quality_jpeg(self):
        with tempfile.TemporaryDirectory(prefix="clearframe-test-") as temp:
            root = Path(temp)
            source = Image.new("RGB", (16, 12), (105, 125, 145))
            ai = Image.new("RGB", (32, 24), (115, 135, 155))
            output = root / "frame.jpg"
            _blend_and_save(source, ai, output, scale=2, strength=35, output_format="JPEG")
            with Image.open(output) as result:
                self.assertEqual(result.size, (32, 24))
                self.assertEqual(result.format, "JPEG")

    def test_photo_is_2x_and_alpha_is_retained(self):
        with tempfile.TemporaryDirectory(prefix="clearframe-test-") as temp:
            root = Path(temp)
            photo = Image.new("RGBA", (64, 48), (150, 115, 90, 255))
            draw = ImageDraw.Draw(photo)
            draw.rectangle((8, 7, 53, 40), outline=(20, 42, 55, 220), width=2)
            draw.line((0, 47, 63, 0), fill=(25, 118, 130, 180), width=3)
            source, output = root / "source.png", root / "result.png"
            photo.save(source)
            enhance_image(source, output, root / "work", ENGINE, MODEL_DIR, scale=2, strength=55)
            with Image.open(output) as result:
                self.assertEqual(result.size, (128, 96))
                self.assertEqual(result.mode, "RGBA")
                self.assertLess(result.getchannel("A").getextrema()[0], 255)

    def test_video_keeps_frames_audio_and_2x_size(self):
        with tempfile.TemporaryDirectory(prefix="clearframe-test-") as temp:
            root = Path(temp)
            frames = root / "frames"
            frames.mkdir()
            for index, color in enumerate(((45, 95, 125), (70, 115, 135))):
                image = Image.new("RGB", (64, 48), color)
                draw = ImageDraw.Draw(image)
                draw.ellipse((12 + index, 8, 42 + index, 38), outline=(240, 225, 180), width=2)
                image.save(frames / f"frame_{index:02d}.png")
            source = root / "source.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-framerate", "2", "-i", str(frames / "frame_%02d.png"),
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
                "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(source),
            ], check=True)
            output = root / "result.mp4"
            enhance_video(source, output, root / "work", ENGINE, MODEL_DIR,
                          scale=2, strength=45, keep_audio=True, max_seconds=10,
                          batch_size=1)
            probe = subprocess.run([
                "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output)
            ], check=True, capture_output=True, text=True)
            info = json.loads(probe.stdout)
            video_stream = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
            audio_streams = [stream for stream in info["streams"] if stream["codec_type"] == "audio"]
            self.assertEqual((video_stream["width"], video_stream["height"]), (128, 96))
            self.assertEqual(video_stream.get("nb_frames"), "2")
            self.assertTrue(audio_streams, "source audio should remain in the output")
            self.assertAlmostEqual(float(info["format"]["duration"]), 1.0, delta=0.2)


class AppSmokeTests(unittest.TestCase):
    def test_zero_strength_is_exact_lanczos_upscale(self):
        with tempfile.TemporaryDirectory(prefix="clearframe-test-") as temp:
            root = Path(temp)
            source = Image.new("RGB", (7, 5), (100, 120, 140))
            ai = Image.new("RGB", (14, 10), (240, 20, 30))
            output = root / "zero-strength.png"
            _blend_and_save(source, ai, output, scale=2, strength=0)
            with Image.open(output) as result:
                expected = source.resize((14, 10), Image.Resampling.LANCZOS)
                self.assertIsNone(ImageChops.difference(expected, result).getbbox())

    def test_engine_tile_default_and_override(self):
        args = (Path("engine"), Path("models"), Path("input"), Path("output"))
        command = _engine_command(*args)
        self.assertEqual(command[command.index("-s") + 1], "4")
        self.assertEqual(command[command.index("-t") + 1], "0")
        with patch.dict(os.environ, {"CLEARFRAME_TILE_SIZE": "256"}):
            command = _engine_command(*args)
        self.assertEqual(command[command.index("-t") + 1], "256")

    def test_home_renders_in_indonesian(self):
        client = create_app().test_client()
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tingkatkan file", response.data)
        self.assertIn(b"foto dan video", response.data.lower())
        self.assertIn(b'value="30"', response.data)
        self.assertIn(b'min="0"', response.data)

    def test_invalid_upload_is_rejected(self):
        client = create_app().test_client()
        response = client.post("/api/jobs", data={"file": (io.BytesIO(b"GIF89a"), "test.gif", "image/gif")})
        self.assertIn(response.status_code, (415, 503))

    def test_zero_strength_image_job_is_accepted(self):
        with tempfile.TemporaryDirectory(prefix="clearframe-test-") as temp:
            data_root = Path(temp) / "data"
            with patch("app.DATA_ROOT", data_root):
                app = create_app()
                store = app.extensions["clearframe_job_store"]
                client = app.test_client()
                image_bytes = io.BytesIO()
                Image.new("RGB", (8, 8), (90, 110, 130)).save(image_bytes, format="PNG")
                image_bytes.seek(0)
                with patch.object(store.executor, "submit") as submit:
                    response = client.post("/api/jobs", data={
                        "scale": "2", "strength": "0",
                        "file": (image_bytes, "sample.png", "image/png"),
                    })
                self.assertEqual(response.status_code, 202)
                self.assertEqual(submit.call_args.args[8], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
