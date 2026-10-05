"""TTS 합성 + 목표 속도(분당 음절) 보정.

provider:
  edge   — edge-tts (무료, 인터넷 필요). 개인·테스트용. 상업 이용 전 약관 확인.
  google — Google Cloud Text-to-Speech (유료, GOOGLE_APPLICATION_CREDENTIALS 필요).
  file   — 직접 녹음. project/voice/<scene_id>.wav|mp3 를 그대로 사용.
  silent — 무음(분량만 맞춤). 타이밍·레이아웃 테스트용.
"""
import asyncio
import hashlib
import json
import os
import shutil
import subprocess

from . import text as T


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def _to_wav(src, dst, tempo=1.0):
    af = ["-af", f"atempo={tempo:.4f}"] if abs(tempo - 1.0) > 1e-3 else []
    _run(["ffmpeg", "-y", "-i", src, *af, "-ar", "48000", "-ac", "1", dst])


def _silent(seconds, dst):
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{seconds:.3f}", dst])


def _edge(text, voice, dst):
    import edge_tts

    async def go():
        await edge_tts.Communicate(text, voice).save(dst)
    asyncio.run(go())


def _google(text, voice, dst):
    from google.cloud import texttospeech as tts
    client = tts.TextToSpeechClient()
    resp = client.synthesize_speech(
        input=tts.SynthesisInput(text=text),
        voice=tts.VoiceSelectionParams(language_code="ko-KR", name=voice),
        audio_config=tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3))
    with open(dst, "wb") as f:
        f.write(resp.audio_content)


def synth_scene(project, scene, log=print):
    """장면 하나의 나레이션 → out/audio/<id>.wav. 반환: (경로, 길이초, 분당음절)."""
    cfg = project.cfg["tts"]
    provider = scene.get("tts_provider", cfg["provider"])
    audio_dir = os.path.join(project.out, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    sid = scene["id"]
    say = T.tts_text(scene.get("say", scene["narration"]), cfg.get("pronunciation"))
    syl = T.syllables(scene["narration"])
    key = hashlib.sha1(json.dumps([provider, cfg["voice"], say, cfg["target_spm"]]).encode()).hexdigest()[:12]
    final = os.path.join(audio_dir, f"{sid}.wav")
    stamp = final + ".key"
    if os.path.exists(final) and os.path.exists(stamp) and open(stamp).read() == key:
        d = ffprobe_duration(final)
        return final, d, syl / d * 60

    raw = os.path.join(audio_dir, f"{sid}.raw.mp3")
    if provider == "silent":
        _silent(syl / cfg["target_spm"] * 60, final)
    else:
        if provider == "edge":
            _edge(say, cfg["voice"], raw)
        elif provider == "google":
            _google(say, cfg["voice"], raw)
        elif provider == "file":
            for ext in ("wav", "mp3", "m4a"):
                cand = project.path(f"voice/{sid}.{ext}")
                if os.path.exists(cand):
                    shutil.copy(cand, raw)
                    break
            else:
                raise FileNotFoundError(f"voice/{sid}.wav|mp3|m4a 가 없습니다")
        else:
            raise ValueError(f"알 수 없는 TTS provider: {provider}")
        d = ffprobe_duration(raw)
        spm = syl / d * 60
        tempo = 1.0
        target = cfg["target_spm"]
        if provider != "file" and abs(spm - target) / target > cfg["tolerance"]:
            lo, hi = cfg["tempo_range"]
            tempo = min(hi, max(lo, target / spm))
            log(f"  {sid}: {spm:.0f}음절/분 → atempo {tempo:.2f} 보정")
        _to_wav(raw, final, tempo)
        os.remove(raw)
    with open(stamp, "w") as f:
        f.write(key)
    d = ffprobe_duration(final)
    return final, d, syl / d * 60
