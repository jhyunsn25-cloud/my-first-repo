"""나레이션 이어붙이기 + BGM 덕킹 + 라우드니스 정규화."""
import os
import subprocess
import wave


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
