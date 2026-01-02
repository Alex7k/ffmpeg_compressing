import subprocess
import os
from pathlib import Path
import sys
import datetime
import subprocess
import json
import tempfile

WIDTH = 720
PRESET = "medium"
MAXFPS = 30
AUDIO_KBPS = 128
CRF = 25

def run(cmd):
    subprocess.run(cmd, check=True)

def sizeof_fmt(num, suffix="B"): # https://stackoverflow.com/questions/1094841/get-a-human-readable-version-of-a-file-size
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

def get_duration_seconds(path: Path) -> int:
    out = subprocess.check_output([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ], text=True).strip()
    return int(float(out))

def get_avg_bitrate_kbps(path: Path, duration_s: int) -> int:
    if duration_s <= 0:
        return 0
    size_bytes = path.stat().st_size
    return int((size_bytes * 8) / duration_s / 1000)

if len(sys.argv) <= 1:
    raise ValueError("No path provided")

PATH = Path(sys.argv[1])
if not PATH.exists() or not PATH.is_dir():
    raise ValueError(f"Path doesn't exist or is not a directory: {PATH}")

print("SelectedPath:", PATH)

STATE_PATH = Path(tempfile.gettempdir()) / (
    f"ffcompress_done_w{WIDTH}_fps{MAXFPS}_crf{CRF}_p{PRESET}_ab{AUDIO_KBPS}.json"
)
def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text("utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, separators=(",", ":")), "utf-8")

def sig(p: Path) -> list:
    st = p.stat()
    return [st.st_size, int(st.st_mtime)]

state = load_state()

# collect video files sorted by creation time ascending
vid_paths = sorted([p for p in PATH.glob("*.mp4") if not p.stem.endswith("_temp")], key=lambda p: p.stat().st_mtime)
if not vid_paths:
    print("No .mp4 files found.")
    sys.exit(0)
print(f"Found {len(vid_paths)} video(s).")

print("Consolidating data of videos...")
items = []
for vid_path in vid_paths:
    dur = get_duration_seconds(vid_path)
    bitrate = get_avg_bitrate_kbps(vid_path, dur)
    size = vid_path.stat().st_size
    mtime = vid_path.stat().st_mtime
    items.append((vid_path, dur, bitrate, mtime, size))

total_saved_bytes = 0
saved_bytes = 0

print("Starting processing...")
for i, (path, duration_s, bitrate_kbps, original_mtime, original_size) in enumerate(items, start=1): # index starts at 1
    print("")
    print("="*60)
    print(f"[{i}/{len(items)}] - {path.name} - duration: {str(datetime.timedelta(seconds=duration_s))} - current bitrate: {bitrate_kbps} kbps - current size: {sizeof_fmt(original_size)}")
    resolved_path = str(path.resolve())
    if state.get(resolved_path) == sig(path):
        print("Already handled for this profile; skipping.")
        continue

    temp_file = path.with_name(path.stem + "_temp.mp4")

    ok = False
    discarded = False
    try:
        run([
            "ffmpeg", "-y",
            "-i", str(path),
            "-vf", f"scale={WIDTH}:-2,fps={MAXFPS}",
            "-c:v", "libx264",
            "-preset", PRESET,
            "-crf", str(CRF),
            "-c:a", "aac",
            "-b:a", f"{AUDIO_KBPS}k",
            str(temp_file)
        ])

        if temp_file.exists():
            temp_size = temp_file.stat().st_size
            saved_bytes = original_size - temp_size
            if saved_bytes <= 0:
                print(f"Compressed file not smaller ({sizeof_fmt(temp_size)} >= {sizeof_fmt(original_size)}); discarding.")
                discarded = True
            else:
                os.replace(temp_file, path)
                os.utime(path, (original_mtime, original_mtime))
                ok = True
    except subprocess.CalledProcessError:
        ok = False
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass

        if ok:
            print("Compression OK.")
            total_saved_bytes += saved_bytes
            print(f"Saved {sizeof_fmt(saved_bytes)}")
        elif discarded:
            print("No gain; skipped.")
        else:
            print("FAILED!")

        # mark as handled (after success or no-gain discard)
        if ok or discarded:
            state[resolved_path] = sig(path)
            save_state(state)


print("All videos processed.")
print(f"Total saved: {sizeof_fmt(total_saved_bytes)}")