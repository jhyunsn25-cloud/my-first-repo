"""제작 전 검사: 팩트 검증 상태, 출처, 자산 라이선스, 자막 길이, 과장 표현, 예상 길이, 제목·썸네일."""
import os
import re

from . import text as T

NUM = re.compile(r"\d")


def run(project, allow_unverified=False):
    errors, warns = [], []
    cfg = project.cfg
    src = project.sources()
    lic = project.licenses()
    spm = cfg["tts"]["target_spm"]
    total = 0.0
    used_claims = set()

    for sc in project.scenes:
        sid = sc.get("id", "?")
        narr = sc.get("narration", "")
        if not narr.strip():
            errors.append(f"[{sid}] narration 이 비어 있음")
            continue
        total += T.syllables(narr) / spm * 60 + cfg["video"]["scene_pad"]
        claims = sc.get("claims", [])
        used_claims.update(claims)
        if NUM.search(T.plain(narr)) and not claims and not sc.get("no_claim"):
            errors.append(f"[{sid}] 숫자가 있는 문장에 claims(출처 ID)가 없음 → sources.csv 에 등록 후 claims: [C1] 추가")
        for cid in claims:
            r = src.get(cid)
            if not r:
                errors.append(f"[{sid}] claim {cid} 가 sources.csv 에 없음")
                continue
            if not r.get("url", "").strip():
                errors.append(f"[{cid}] 출처 URL 없음")
            status = r.get("status", "").strip()
            if status != "verified":
                (warns if allow_unverified else errors).append(f"[{cid}] 검증 상태 '{status or '빈칸'}' (verified 여야 함)")
            if r.get("kind") == "number" and not r.get("second_source", "").strip():
                warns.append(f"[{cid}] 수치 claim 은 교차 출처(second_source) 권장")
        for w in cfg["check"]["caution_words"]:
            if w in narr:
                warns.append(f"[{sid}] 과장 우려 표현 '{w}'")
        for sent in T.sentences(T.plain(narr)):
            if len(sent) > 70:
                warns.append(f"[{sid}] 긴 문장({len(sent)}자) — 한 문장 한 정보로 나누기: {sent[:30]}…")
        for v in sc.get("visuals", []) + ([sc["bg"]] if sc.get("bg", {}).get("src") else []):
            p = v.get("src")
            if p:
                if not os.path.exists(project.path(p)):
                    errors.append(f"[{sid}] 파일 없음: {p}")
                elif os.path.relpath(project.path(p), project.path("assets")).replace("\\", "/") not in lic:
                    warns.append(f"[{sid}] assets/licenses.csv 에 라이선스 기록 없음: {p}")
        if len(sc.get("visuals", [])) > 3:
            warns.append(f"[{sid}] 한 장면 요소 {len(sc['visuals'])}개 — 3개 이하 권장")
        ats = sorted(float(v.get("at", 0.2)) for v in sc.get("visuals", []))
        if any(b - a < cfg["motion"]["enter"]["dur"] for a, b in zip(ats, ats[1:])):
            n = sum(1 for a, b in zip(ats, ats[1:]) if b - a < cfg["motion"]["enter"]["dur"]) + 1
            if n > cfg["motion"]["max_simultaneous"]:
                warns.append(f"[{sid}] 동시에 움직이는 요소가 {n}개 — at 간격을 벌리기")

    for cid in src:
        if cid not in used_claims:
            warns.append(f"[{cid}] sources.csv 에 있지만 대본에서 쓰이지 않음")

    lo, hi = project.format_cfg["target_sec"]
    if not lo <= total <= hi:
        warns.append(f"예상 길이 {total/60:.1f}분 — {project.format_cfg['label']} 권장 {lo/60:.0f}~{hi/60:.0f}분")

    t = project.meta.get("title", "")
    if not t:
        errors.append("meta.title 없음")
    elif len(t) > cfg["check"]["title_max"]:
        warns.append(f"제목 {len(t)}자 — {cfg['check']['title_max']}자 이하 권장")
    th = project.thumbnail
    if th:
        lines = th.get("lines", [])
        if len(lines) != 2:
            warns.append("썸네일 카피는 2줄 권장")
        for l in lines:
            if len(T.plain(l)) > cfg["thumbnail"]["max_line_chars"]:
                warns.append(f"썸네일 줄 '{T.plain(l)}' {len(T.plain(l))}자 — {cfg['thumbnail']['max_line_chars']}자 이하 권장")
        if t and any(T.plain(l).strip() == t.strip() for l in lines):
            warns.append("썸네일 카피가 제목과 같음 — 다른 표현으로")
        if not th.get("subjects"):
            warns.append("썸네일 subjects(누끼 피사체)가 없음 — 주요 인물·피사체는 누끼 합성이 원칙")
    dedup = lambda xs: list(dict.fromkeys(xs))
    return dedup(errors), dedup(warns), total
