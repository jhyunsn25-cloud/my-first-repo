"""TTS 합성 + 목표 속도(분당 음절) 보정.

provider:
  typecast — 타입캐스트 API (TYPECAST_API_KEY 필요, 크레딧 차감). 감정 표현 지원.
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
import urllib.error
import urllib.parse
import urllib.request

from . import text as T

TYPECAST_HOST = os.environ.get("TYPECAST_API_HOST", "https://api.typecast.ai")


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


def typecast_request(method, path, body=None, params=None, raw=False):
    key = os.environ.get("TYPECAST_API_KEY")
    if not key:
        raise SystemExit("TYPECAST_API_KEY 환경변수가 없습니다 → typecast.ai/developers/api 에서 API 키 발급 후\n"
                         "  export TYPECAST_API_KEY=발급받은키   (Windows: set TYPECAST_API_KEY=...)")
    url = TYPECAST_HOST + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "X-API-KEY": key, "Content-Type": "application/json", "User-Agent": "video-toolkit"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            content = r.read()
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:300]
        hint = {401: "API 키 확인", 402: "크레딧 부족 — 플랜·잔여 크레딧 확인", 422: "요청 값 확인(voice_id, model, 감정 등)",
                429: "요청 한도 초과 — 잠시 후 다시"}.get(e.code, "")
        raise SystemExit(f"타입캐스트 API 오류 {e.code} {hint}: {msg}") from e
    return content if raw else json.loads(content)


def _typecast(text, tc, dst, prev_text=None, next_text=None):
    if not tc.get("voice_id"):
        raise SystemExit("preset.yaml(또는 overrides) 의 tts.typecast.voice_id 가 비어 있습니다 → python make.py voices 로 찾기")
    model = tc.get("model", "ssfm-v30")
    body = {"voice_id": tc["voice_id"], "text": text, "model": model, "language": "kor",
            "output": {"audio_format": "wav", "audio_tempo": float(tc.get("tempo", 1.0))}}
    emo = tc.get("emotion")
    if emo == "smart" and model == "ssfm-v30":
        body["prompt"] = {"emotion_type": "smart"}
        if prev_text:
            body["prompt"]["previous_text"] = prev_text[-500:]
        if next_text:
            body["prompt"]["next_text"] = next_text[:500]
    elif emo in ("preset", "smart"):     # v21 은 smart 미지원 → preset 으로
        preset = {"emotion_preset": tc.get("emotion_preset", "normal"),
                  "emotion_intensity": float(tc.get("emotion_intensity", 1.0))}
        body["prompt"] = {"emotion_type": "preset", **preset} if model == "ssfm-v30" else preset
    with open(dst, "wb") as f:
        f.write(typecast_request("POST", "/v1/text-to-speech", body, raw=True))


def synth_scene(project, scene, log=print, prev_text=None, next_text=None):
    """장면 하나의 나레이션 → out/audio/<id>.wav. 반환: (경로, 길이초, 분당음절)."""
    cfg = project.cfg["tts"]
    provider = scene.get("tts_provider", cfg["provider"])
    audio_dir = os.path.join(project.out, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    sid = scene["id"]
    say = T.tts_text(scene.get("say", scene["narration"]), cfg.get("pronunciation"))
    syl = T.syllables(scene["narration"])
    extra = cfg.get("typecast") if provider == "typecast" else None
    key = hashlib.sha1(json.dumps([provider, cfg["voice"], say, cfg["target_spm"], extra],
                                  sort_keys=True).encode()).hexdigest()[:12]
    final = os.path.join(audio_dir, f"{sid}.wav")
    stamp = final + ".key"
    if os.path.exists(final) and os.path.exists(stamp) and open(stamp).read() == key:
        d = ffprobe_duration(final)
        return final, d, syl / d * 60

    raw = os.path.join(audio_dir, f"{sid}.raw.mp3")
    if provider == "silent":
        _silent(syl / cfg["target_spm"] * 60, final)
    else:
        if provider == "typecast":
            _typecast(say, cfg["typecast"], raw, prev_text, next_text)
        elif provider == "edge":
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
            if tempo != target / spm and provider == "typecast":
                sug = float(cfg["typecast"].get("tempo", 1.0)) * target / spm
                log(f"  ※ 보정 한계를 넘음 → tts.typecast.tempo: {sug:.2f} 로 설정 후 다시 합성 권장")
        _to_wav(raw, final, tempo)
        os.remove(raw)
    with open(stamp, "w") as f:
        f.write(key)
    d = ffprobe_duration(final)
    return final, d, syl / d * 60
