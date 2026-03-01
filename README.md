# FFmpeg batch video compression

Compress a directory of **.mp4** video files

## Prerequisites

- ffmpeg
- ffprobe

tested on windows 11

## Usage

```pwsh
# create venv (optional)
python -m venv .venv
.venv\Scripts\Activate.ps1

# install dependencies
pip install -r requirements.txt
# run script
py dynamic_compress_folder.py "path/to/directory"
```

## Notes

- Only **.mp4** is supported for now
