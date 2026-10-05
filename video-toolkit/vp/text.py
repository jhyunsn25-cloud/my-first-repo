"""문장·음절·자막 분할. 대본의 *강조* 표시는 자막에서 강조색, TTS 에서는 제거."""
import re

HANGUL = re.compile(r"[가-힣]")


def plain(text):
    return text.replace("*", "")


def syllables(text):
    t = plain(text)
    n = len(HANGUL.findall(t))
    n += sum(len(m) * 1.6 for m in re.findall(r"\d+", t))   # 숫자는 자리수당 약 1.6음절로 근사
    n += sum(max(1, len(m) // 2) for m in re.findall(r"[A-Za-z]+", t))
    return n


def sentences(text):
    parts = re.split(r"(?<=[.?!])\s+", text.strip())
    return [p for p in parts if p]


def tts_text(text, pronunciation):
    t = plain(text)
    for k, v in (pronunciation or {}).items():
        t = t.replace(k, v)
    return t


def _words_with_emphasis(sentence):
    """단어 단위 (텍스트, 강조여부). *로 감싼 구간에 걸친 단어는 강조."""
    out, emph = [], False
    for tok in sentence.split():
        hit = emph
        for ch in tok:
            if ch == "*":
                emph = not emph
            elif emph:
                hit = True
        word = plain(tok)
        if word:
            out.append((word, hit))
    return out


def _len(words):
    return sum(len(w) for w, _ in words) + max(0, len(words) - 1)


def _best_split(words, max_chars):
    """두 줄로 나눌 때 가장 균형 잡히고 쉼표·조사 뒤에서 끊기는 위치."""
    best, best_score = None, None
    for i in range(1, len(words)):
        a, b = words[:i], words[i:]
        la, lb = _len(a), _len(b)
        if la > max_chars or lb > max_chars:
            continue
        score = abs(la - lb)
        if a[-1][0].endswith((",", "，")):
            score -= 6
        if best_score is None or score < best_score:
            best, best_score = i, score
    return best


def _chunks(words, max_chars, max_lines):
    """한 문장을 큐 단위로: 길면 쉼표 근처에서 먼저 자르고, 각 큐는 균형 잡힌 2줄."""
    cap = max_chars * max_lines
    if _len(words) <= max_chars:
        return [[words]]
    if _len(words) <= cap and max_lines >= 2:
        i = _best_split(words, max_chars)
        if i:
            return [[words[:i], words[i:]]]
    # 너무 길면 큐 개수를 정해 길이를 고르게 나누고, 목표 지점 근처 쉼표를 우선
    import math
    total = _len(words)
    target = total / math.ceil(total / cap)
    best, best_score, length = 1, None, 0
    for k in range(len(words) - 1):
        length += len(words[k][0]) + (1 if k else 0)
        if length > cap:
            break
        score = abs(length - target) - (8 if words[k][0].endswith(",") else 0)
        if best_score is None or score < best_score:
            best, best_score = k + 1, score
    return _chunks(words[:best], max_chars, max_lines) + _chunks(words[best:], max_chars, max_lines)


def split_cues(text, max_chars, max_lines):
    """나레이션을 자막 큐 리스트로. 큐 = 줄 리스트, 줄 = [(단어, 강조)]."""
    cues = []
    for sent in sentences(text):
        words = _words_with_emphasis(sent)
        if words:
            cues.extend(_chunks(words, max_chars, max_lines))
    return cues


def cue_text(cue):
    return "\n".join(" ".join(w for w, _ in line) for line in cue)
