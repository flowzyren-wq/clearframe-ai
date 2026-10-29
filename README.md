# ClearFrame

A local photo and video upscaler. Choose 2× or 4× output and adjust how much AI-generated detail to blend in. It uses Real-ESRGAN NCNN Vulkan.

## Requirements

- Python 3.10 or newer
- FFmpeg (`ffmpeg` and `ffprobe` on your `PATH`)
- Vulkan support; a compatible GPU is recommended

## Run locally

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/install_backend.py
python app.py
```

Open `http://127.0.0.1:7860`. The app listens on your computer only by default. To use it on a private network, set `CLEARFRAME_HOST=0.0.0.0`. Don’t expose it to the public internet without access controls.

The installer downloads the backend and model to `.runtime/`; they are not stored in the repository.

## Use

Upload a photo or video, choose 2× or 4×, and adjust the AI strength. At 0%, ClearFrame uses a LANCZOS resize with no AI blend. Videos are processed frame by frame; you can keep the original audio.

## Privacy and limitations

Files are processed on the computer running the app. Uploads and results are kept in the system’s temporary directory (`clearframe-local` by default); result links expire after one hour. Set `CLEARFRAME_DATA_DIR` to choose another location.

AI can add details that weren’t in the original. Fast motion can also cause details to change between video frames, so check the result before using it.

## Tests

```bash
python -m unittest discover -s tests -v
```

ClearFrame is licensed under MIT. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for third-party licenses.
