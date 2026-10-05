#!/usr/bin/env python3
"""video-preset 제작 CLI.

  python make.py check     <프로젝트폴더> [--allow-unverified]
  python make.py tts       <프로젝트폴더>
  python make.py render    <프로젝트폴더> [--preview] [--allow-unverified]
  python make.py thumb     <프로젝트폴더>
  python make.py publish   <프로젝트폴더>        # 제목·설명란·SRT 만 다시 생성
  python make.py all       <프로젝트폴더> [--preview] [--allow-unverified]
"""
import argparse
import os
import sys
import time

from vp import audio as A
from vp import check as C
from vp import publish as P
from vp import render as R
from vp import thumbnail as TH
from vp import tts as TTS
from vp.config import Project


def do_check(p, allow):
    errors, warns, total = C.run(p, allow)
    print(f"■ 검사: {p.meta.get('title', '')}  ({p.format_cfg['label']}, 예상 {total/60:.1f}분)")
    for w in warns:
        print("  경고:", w)
    for e in errors:
        print("  오류:", e)
    if errors:
        print(f"→ 오류 {len(errors)}개. 수정 후 다시 실행하세요.")
        return False
    print("→ 통과" + (" (경고 확인 필요)" if warns else ""))
    return True


def do_tts(p):
    print("■ TTS")
    res = []
    for sc in p.scenes:
        path, d, spm = TTS.synth_scene(p, sc)
        print(f"  {sc['id']}: {d:.1f}초, {spm:.0f}음절/분")
        res.append((path, d))
    return res


def do_render(p, preview):
    audio = do_tts(p)
    narr = os.path.join(p.out, "narration.wav")
    _, total = A.concat_narration(audio, p.cfg["video"]["scene_pad"], narr)
    mixed = os.path.join(p.out, "mix.wav")
    A.mix(narr, total, p.cfg, p.path(p.cfg["audio"].get("bgm")), mixed)
    out = os.path.join(p.out, "preview.mp4" if preview else "video.mp4")
    print(f"■ 렌더 → {out}")
    t0 = time.time()
    timeline, cues, _ = R.render(p, audio, mixed, out, preview=preview)
    print(f"  {time.time()-t0:.0f}초 소요")
    P.write_publish(p, timeline, cues)
    print("■ 제목·설명란·자막 → out/title.txt, out/description.txt, out/subtitles.srt")
    return timeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "tts", "render", "thumb", "publish", "all"])
    ap.add_argument("project")
    ap.add_argument("--preview", action="store_true", help="절반 해상도·15fps 빠른 미리보기")
    ap.add_argument("--allow-unverified", action="store_true", help="검증 안 된 claim 을 경고로만 처리(미리보기 전용)")
    a = ap.parse_args()
    p = Project(a.project)
    if a.cmd == "check":
        sys.exit(0 if do_check(p, a.allow_unverified) else 1)
    if a.cmd == "tts":
        do_tts(p)
        return
    if a.cmd in ("render", "all"):
        if not do_check(p, a.allow_unverified):
            sys.exit(1)
        if a.allow_unverified and not a.preview:
            print("※ --allow-unverified 로 만든 영상은 업로드하지 마세요.")
        do_render(p, a.preview)
    if a.cmd == "publish":
        audio = [(None, TTS.ffprobe_duration(os.path.join(p.out, "audio", f"{s['id']}.wav"))) for s in p.scenes]
        timeline, cues, _ = R.build_timeline(p, audio)
        P.write_publish(p, timeline, cues)
        print("■ out/title.txt, description.txt, subtitles.srt 갱신")
    if a.cmd in ("thumb", "all") and p.thumbnail:
        print("■ 썸네일 →", TH.make(p))


if __name__ == "__main__":
    main()
