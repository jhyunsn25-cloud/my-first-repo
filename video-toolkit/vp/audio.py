"""나레이션 이어붙이기 + BGM 덕킹 + 라우드니스 정규화."""
import os
import subprocess
import wave

import numpy as np

SR = 48000


def concat_narration(segments, pad, dst):
    """segments: [(wav경로, 길이)] → 장면마다 pad 초 무음을 붙여 하나의 wav. 반환: 장면 시작시각 리스트."""
    starts, t = [], 0.0
    with wave.open(dst, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(48000)
        for path, dur in segments:
            starts.append(t)
            with wave.open(path, "rb") as w:
                out.writeframes(w.readframes(w.getnframes()))
                n = w.getnframes()
            gap = int(pad * 48000)
            out.writeframes(b"\x00\x00" * gap)
            t += (n + gap) / 48000
    return starts, t


def mix(narration, total, cfg, bgm, dst):
    a = cfg["audio"]
    if bgm and os.path.exists(bgm):
        fade_out = max(0.0, total - 2.0)
        bg = (f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={a['bgm_db']}dB,"
              f"atrim=0:{total:.3f},afade=t=in:d=1.5,afade=t=out:st={fade_out:.3f}:d=2[bg];"
              f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[n1][n2];")
        if a.get("duck", True):
            bg += "[bg][n2]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350[bd];"
        else:
            bg += "[n2]anullsink;[bg]anull[bd];"
        filt = bg + f"[n1][bd]amix=inputs=2:duration=first:normalize=0,loudnorm=I={a['loudness']}:TP=-1.5:LRA=11[a]"
        cmd = ["ffmpeg", "-y", "-i", narration, "-stream_loop", "-1", "-i", bgm,
               "-filter_complex", filt, "-map", "[a]", "-ar", "48000", dst]
    else:
        cmd = ["ffmpeg", "-y", "-i", narration, "-af",
               f"aformat=channel_layouts=stereo,loudnorm=I={a['loudness']}:TP=-1.5:LRA=11", "-ar", "48000", dst]
    subprocess.run(cmd, check=True, capture_output=True)


def _decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def sfx_events(project, timeline):
    """장면 sfx 목록 + 요소별 sfx + (설정 시) 요소 등장 자동 효과음 → [(경로, 시각, dB)]"""
    a = project.cfg["audio"]
    auto = a.get("sfx_on_enter")
    ev = []
    for it in timeline:
        sc, st = it["scene"], it["start"]
        for x in sc.get("sfx", []):
            ev.append((project.path(x["src"]), st + float(x.get("at", 0)), float(x.get("db", a["sfx_db"]))))
        for v in sc.get("visuals", []):
            src = v.get("sfx", auto)
            if src:
                ev.append((project.path(src), st + float(v.get("at", 0.2)), float(v.get("sfx_db", a["sfx_db"]))))
    return ev


def add_sfx(narration, events, dst):
    """나레이션 wav 위에 효과음을 시각에 맞춰 얹는다. 효과음이 없으면 원본 경로 반환."""
    if not events:
        return narration
    with wave.open(narration, "rb") as w:
        base = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    out = base.copy()
    cache = {}
    for path, t, db in events:
        if path not in cache:
            cache[path] = _decode(path)
        clip = cache[path] * (10 ** (db / 20))
        i = int(t * SR)
        if i >= len(out):
            continue
        n = min(len(clip), len(out) - i)
        out[i:i + n] += clip[:n]
    peak = np.abs(out).max()
    if peak > 0.99:
        out *= 0.99 / peak
    with wave.open(dst, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return dst


AUDIO_EXT = (".wav", ".mp3", ".ogg", ".m4a", ".flac", ".aif", ".aiff")


def _fix_name(name):
    """윈도우 압축기(cp949)로 만든 zip 의 한글 파일명이 깨져 보이면 복원."""
    if any("\uac00" <= ch <= "\ud7a3" for ch in name) or name.isascii():
        return name
    try:
        fixed = name.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name
    return fixed if any("\uac00" <= ch <= "\ud7a3" for ch in fixed) else name


def import_pack(zip_path, dest):
    """효과음 zip 을 dest 로 풀기. 한글 파일명(cp949) 깨짐 보정. 반환: 풀린 오디오 파일 목록."""
    import zipfile
    os.makedirs(dest, exist_ok=True)
    out = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = _fix_name(info.filename)
            if info.is_dir() or name.startswith("__MACOSX") or not name.lower().endswith(AUDIO_EXT):
                continue
            rel = name.replace("\\", "/").lstrip("/")
            target = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as f:
                f.write(src.read())
            out.append(rel)
    return out
