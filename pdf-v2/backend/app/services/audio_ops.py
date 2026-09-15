from pathlib import Path
import subprocess, json, shutil, os

def probe_duration(path: Path) -> float:
    try:
        out = subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(path)], text=True)
        return float(json.loads(out)["format"]["duration"])
    except: return 0.0

def trim_mp3(inp: Path, output: Path, start: float, end: float):
    # try stream copy if mp3
    dur = end - start
    if dur <=0: raise ValueError("End must be after start")
    # use ffmpeg; -ss before -i for speed, -c copy when possible else re-encode
    cmd = ["ffmpeg","-y","-ss",str(start),"-t",str(dur),"-i",str(inp),"-c","copy",str(output)]
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if output.stat().st_size==0: raise Exception("empty")
    except:
        cmd2 = ["ffmpeg","-y","-ss",str(start),"-t",str(dur),"-i",str(inp),"-c:a","libmp3lame","-q:a","2",str(output)]
        subprocess.check_call(cmd2)
    return output
