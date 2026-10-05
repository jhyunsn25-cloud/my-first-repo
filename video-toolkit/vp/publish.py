"""SRT 자막 파일과 YouTube 설명란(챕터·출처 포함) 생성."""
import os

from . import text as T


def ts_srt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ts_chapter(t):
    t = int(t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def write_srt(cues, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, c in enumerate(cues, 1):
            f.write(f"{i}\n{ts_srt(c['start'])} --> {ts_srt(c['end'])}\n{T.cue_text(c['cue'])}\n\n")


def chapters(timeline):
    out, last = [], None
    for it in timeline:
        ch = it["scene"].get("chapter")
        if ch and ch != last:
            out.append((it["start"], ch))
            last = ch
    if out:
        out[0] = (0.0, out[0][1])     # YouTube 챕터는 00:00 으로 시작해야 함
    ok = len(out) >= 3 and all(b[0] - a[0] >= 10 for a, b in zip(out, out[1:]))
    return out, ok


def title(project):
    t = project.meta["title"]
    if project.cfg["channel"]["title_suffix"] and project.format != "bundle":
        t += f" / {project.cfg['channel']['name']}"
    return t


def description(project, timeline):
    m, cfg = project.meta, project.cfg
    lines = [*m.get("summary", []), ""]
    chs, ok = chapters(timeline)
    if ok:
        lines += ["[목차]"] + [f"{ts_chapter(t)} {name}" for t, name in chs] + [""]
    src = project.sources()
    if src:
        lines.append("[출처]")
        for cid, r in src.items():
            lines.append(f"- [{cid}] {r.get('publisher', '')}, {r.get('title', '')} ({r.get('date', '')}) {r.get('url', '')}".strip())
        lines.append("")
    if m.get("basis_date"):
        lines.append(f"※ 이 영상은 {m['basis_date']} 기준 정보입니다.")
    lines.append("※ 내용 오류 제보는 댓글로 남겨 주세요. 확인 후 고정 댓글로 정정합니다.")
    if cfg["tts"]["provider"] in ("edge", "google"):
        lines.append("※ 이 영상의 나레이션은 AI 합성 음성입니다.")
    if m.get("sponsored"):
        lines.append(f"※ 유료 광고 포함: {m['sponsored']}")
    if m.get("hashtags"):
        lines += ["", " ".join("#" + h.lstrip("#") for h in m["hashtags"][:5])]
    return "\n".join(lines).strip() + "\n"


def write_publish(project, timeline, cues):
    write_srt(cues, os.path.join(project.out, "subtitles.srt"))
    with open(os.path.join(project.out, "description.txt"), "w", encoding="utf-8") as f:
        f.write(description(project, timeline))
    with open(os.path.join(project.out, "title.txt"), "w", encoding="utf-8") as f:
        f.write(title(project) + "\n")
