"""화면 요소(모션그래픽). 각 요소는 content(t) 로 RGBA 이미지와 위치를 돌려주고,
등장/퇴장(페이드+이동)은 render.py 가 공통 가속·감속 곡선으로 처리한다."""
import os

from PIL import Image, ImageDraw

from . import draw as D
from . import easing as E
from .text import _words_with_emphasis


class Ctx:
    def __init__(self, project, W, H):
        self.p = project
        self.W, self.H = W, H
        self.s = min(W, H) / 1080
        self.portrait = H > W
        self.accent = tuple(project.accent)
        pal = project.cfg["palette"]
        self.ink, self.paper, self.white, self.muted = (tuple(pal[k]) for k in ("ink", "paper", "white", "muted"))
        m = project.cfg["layout"]["margin"] * self.s
        if self.portrait:
            self.box = (m * 0.6, H * 0.17, W - m * 0.6, H * 0.66)
        else:
            self.box = (m, 150 * self.s, W - m, H - 250 * self.s)
        self.motion = project.cfg["motion"]

    def f(self, key, size):
        return D.font(self.p.font(key), size * self.s)

    @property
    def cx(self):
        return (self.box[0] + self.box[2]) / 2

    @property
    def cy(self):
        return (self.box[1] + self.box[3]) / 2

    @property
    def bw(self):
        return self.box[2] - self.box[0]


def fmt_num(v, decimals=0):
    return f"{v:,.{decimals}f}"


class Element:
    static = True

    def __init__(self, spec, ctx, scene_dur):
        self.spec, self.c, self.dur = spec, ctx, scene_dur
        self.at = float(spec.get("at", 0.2))
        self.until = float(spec["until"]) if "until" in spec else scene_dur
        self._cache = None

    def content(self, t):
        """t = 요소 등장 후 경과 시간. 반환 (img, (x, y))"""
        raise NotImplementedError

    def get(self, t):
        if self.static:
            if self._cache is None:
                self._cache = self.content(0)
            return self._cache
        return self.content(t)


def centered(img, cx, cy):
    return img, (int(cx - img.width / 2), int(cy - img.height / 2))


class Keyword(Element):
    static = False

    def content(self, t):
        c = self.c
        fnt = c.f("black", self.spec.get("size", 110))
        line = D.rich_line(_words_with_emphasis(self.spec["text"]), fnt, c.white, c.accent, stroke=int(4 * c.s))
        sub = self.spec.get("sub")
        subimg = D.text_image(sub, c.f("medium", 44), c.white) if sub else None
        bar_h = int(10 * c.s)
        p = E.get(c.motion["move"]["easing"])(E.progress(t, 0.25, 0.6))
        w = max(line.width, subimg.width if subimg else 0)
        h = line.height + bar_h + int(24 * c.s) + ((subimg.height + int(20 * c.s)) if subimg else 0)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        img.alpha_composite(line, ((w - line.width) // 2, 0))
        bw = int(line.width * 0.6 * p)
        if bw > 0:
            ImageDraw.Draw(img).rectangle([(w - bw) // 2, line.height + int(10 * c.s),
                                           (w + bw) // 2, line.height + int(10 * c.s) + bar_h], fill=D.rgba(c.accent))
        if subimg:
            img.alpha_composite(subimg, ((w - subimg.width) // 2, h - subimg.height))
        return centered(img, c.cx, self.spec.get("y", 0.5) * (c.box[3] - c.box[1]) + c.box[1])


class Number(Element):
    static = False

    def content(self, t):
        c, sp = self.c, self.spec
        m = c.motion["count"]
        p = E.get(m["easing"])(E.progress(t, 0, sp.get("count_dur", m["dur"])))
        val = float(sp["value"]) * p
        big = c.f("black", sp.get("size", 170))
        small = c.f("bold", sp.get("size", 170) * 0.42)
        parts = []
        if sp.get("prefix"):
            parts.append(D.text_image(sp["prefix"], small, c.white))
        parts.append(D.text_image(fmt_num(val, sp.get("decimals", 0)), big, c.accent))
        if sp.get("suffix"):
            parts.append(D.text_image(sp["suffix"], small, c.white))
        gap = int(14 * c.s)
        w = sum(i.width for i in parts) + gap * (len(parts) - 1)
        h = max(i.height for i in parts)
        row = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        x = 0
        for i in parts:
            row.alpha_composite(i, (x, h - i.height))
            x += i.width + gap
        label = sp.get("label")
        if not label:
            return centered(row, c.cx, c.cy)
        lab = D.text_image(label, c.f("bold", 50), c.white)
        img = Image.new("RGBA", (max(w, lab.width), h + lab.height + int(30 * c.s)), (0, 0, 0, 0))
        img.alpha_composite(row, ((img.width - w) // 2, 0))
        img.alpha_composite(lab, ((img.width - lab.width) // 2, img.height - lab.height))
        return centered(img, c.cx, c.cy)


class Bars(Element):
    static = False

    def content(self, t):
        c, sp = self.c, self.spec
        items = sp["items"][:6]
        vmax = max(float(i["value"]) for i in items) or 1
        lab_f, val_f = c.f("bold", 44), c.f("black", 46)
        row_h = int(min(110 * c.s, (c.box[3] - c.box[1]) / (len(items) + 0.5)))
        label_w = int(max(D.text_size(lab_f, str(i["label"]))[0] for i in items) + 30 * c.s)
        full = int(c.bw - label_w - 220 * c.s)
        img = Image.new("RGBA", (int(c.bw), row_h * len(items)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        ease = E.get(c.motion["move"]["easing"])
        for k, it in enumerate(items):
            p = ease(E.progress(t, k * c.motion["stagger"], 0.7))
            y = k * row_h
            col = c.accent if k == sp.get("highlight", -1) else c.muted
            d.text((label_w - 20 * c.s, y + row_h / 2), str(it["label"]), font=lab_f, anchor="rm", fill=D.rgba(c.white))
            bw = int(full * float(it["value"]) / vmax * p)
            bh = int(row_h * 0.55)
            if bw > 0:
                d.rounded_rectangle([label_w, y + (row_h - bh) / 2, label_w + bw, y + (row_h + bh) / 2],
                                    radius=int(8 * c.s), fill=D.rgba(col))
            if p > 0.05:
                txt = fmt_num(float(it["value"]), sp.get("decimals", 0)) + sp.get("unit", "")
                d.text((label_w + bw + 20 * c.s, y + row_h / 2), txt, font=val_f, anchor="lm",
                       fill=D.rgba(c.white, int(255 * min(1, p * 1.5))))
        return centered(img, c.cx, c.cy)


class Flow(Element):
    static = False

    def content(self, t):
        c, sp = self.c, self.spec
        steps = sp["steps"]
        n = len(steps)
        gap = sp.get("gap") or max(0.6, (self.until - self.at - 1.0) / max(1, n))
        fnt = c.f("bold", 46 if n <= 3 else 38)
        ease = E.get(c.motion["enter"]["easing"])
        if c.portrait:
            bw, bh = int(c.bw * 0.86), int(140 * c.s)
            img = Image.new("RGBA", (int(c.bw), int(n * bh + (n - 1) * 60 * c.s)), (0, 0, 0, 0))
        else:
            arrow = int(70 * c.s)
            bw = int((c.bw - arrow * (n - 1)) / n)
            bh = int(220 * c.s)
            img = Image.new("RGBA", (int(c.bw), bh), (0, 0, 0, 0))
        latest = max([k for k in range(n) if t >= k * gap] or [0])
        for k, s in enumerate(steps):
            p = ease(E.progress(t, k * gap, c.motion["enter"]["dur"]))
            if p <= 0:
                continue
            box = D.rounded((bw, bh), int(18 * c.s), D.rgba(c.paper))
            bd = ImageDraw.Draw(box)
            if k == latest:
                bd.rounded_rectangle([0, 0, bw - 1, bh - 1], int(18 * c.s), outline=D.rgba(c.accent), width=int(7 * c.s))
            lines = D.wrap(s, fnt, bw - 40 * c.s)
            lh = fnt.size * 1.25
            y0 = bh / 2 - lh * len(lines) / 2 + lh / 2
            for i, ln in enumerate(lines):
                bd.text((bw / 2, y0 + i * lh), ln, font=fnt, anchor="mm", fill=D.rgba(c.ink))
            box = D.with_opacity(box, p)
            off = int((1 - p) * 30 * c.s)
            if c.portrait:
                pos = ((img.width - bw) // 2, int(k * (bh + 60 * c.s)) + off)
            else:
                pos = (int(k * (bw + 70 * c.s)), off)
            img.alpha_composite(box, pos)
            if k > 0:
                d = ImageDraw.Draw(img)
                col = D.rgba(c.accent, int(255 * p))
                if c.portrait:
                    ax, ay = img.width // 2, pos[1] - int(30 * c.s)
                    d.polygon([(ax - 18 * c.s, ay - 12 * c.s), (ax + 18 * c.s, ay - 12 * c.s), (ax, ay + 12 * c.s)], fill=col)
                else:
                    ax, ay = pos[0] - int(35 * c.s), bh // 2
                    d.polygon([(ax - 12 * c.s, ay - 18 * c.s), (ax - 12 * c.s, ay + 18 * c.s), (ax + 14 * c.s, ay)], fill=col)
        return centered(img, c.cx, c.cy)


class Headline(Element):
    """기사·문서 요지 카드. 원문 캡처 대신 직접 요약한 문장 + 출처를 쓴다."""
    static = False

    def content(self, t):
        c, sp = self.c, self.spec
        fnt = c.f("bold", 58)
        pad = int(46 * c.s)
        width = int(min(c.bw, 1300 * c.s) * sp.get("width", 1.0))
        lines = D.wrap(sp["text"], fnt, width - pad * 2)
        lh = int(fnt.size * 1.35)
        src = sp.get("source")
        sf = c.f("medium", 32)
        h = pad * 2 + lh * len(lines) + (int(50 * c.s) if src else 0)
        card = D.rounded((width, h), int(14 * c.s), D.rgba(c.paper))
        d = ImageDraw.Draw(card)
        hl = sp.get("highlight")
        p = E.get(c.motion["move"]["easing"])(E.progress(t, 0.35, 0.7))
        for i, ln in enumerate(lines):
            y = pad + i * lh
            if hl and hl in ln and p > 0:
                x0 = pad + d.textlength(ln[:ln.index(hl)], font=fnt)
                x1 = x0 + d.textlength(hl, font=fnt)
                d.rectangle([x0 - 4, y + lh * 0.45, x0 + (x1 - x0) * p + 4, y + lh * 0.92],
                            fill=D.rgba(c.accent, 200))
            d.text((pad, y), ln, font=fnt, fill=D.rgba(c.ink))
        if src:
            d.text((pad, h - pad - 10 * c.s), src, font=sf, fill=D.rgba(c.muted), anchor="ls")
        cy = c.box[1] + (c.box[3] - c.box[1]) * sp.get("y", 0.5)
        return centered(card, c.box[0] + c.bw * sp.get("x", 0.5), cy)


class Compare(Element):
    static = False

    def content(self, t):
        c, sp = self.c, self.spec
        ease = E.get(c.motion["enter"]["easing"])
        col_w = int(c.bw / 2)
        lab_f, val_f = c.f("bold", 50), c.f("black", 120)
        h = int(330 * c.s)
        img = Image.new("RGBA", (int(c.bw), h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for k, side in enumerate(("left", "right")):
            it = sp[side]
            p = ease(E.progress(t, k * 0.35, c.motion["enter"]["dur"]))
            if p <= 0:
                continue
            a = int(255 * p)
            cx = col_w * k + col_w / 2
            dy = (1 - p) * 30 * c.s
            col = c.accent if it.get("accent", k == 1) else c.white
            d.text((cx, 70 * c.s + dy), str(it["label"]), font=lab_f, anchor="mm", fill=D.rgba(c.white, a))
            d.text((cx, 210 * c.s + dy), str(it["value"]), font=val_f, anchor="mm", fill=D.rgba(col, a))
        d.line([(col_w, 30 * c.s), (col_w, h - 30 * c.s)], fill=D.rgba(c.muted, 160), width=int(3 * c.s))
        return centered(img, c.cx, c.cy)


class Timeline(Element):
    static = False

    def content(self, t):
        c, sp = self.c, self.spec
        items = sp["items"]
        n = len(items)
        ease = E.get(c.motion["move"]["easing"])
        h = int(330 * c.s)
        img = Image.new("RGBA", (int(c.bw), h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        y = h // 2
        p_line = ease(E.progress(t, 0, 0.9))
        d.line([(0, y), (c.bw * p_line, y)], fill=D.rgba(c.muted), width=int(5 * c.s))
        df, tf = c.f("black", 44), c.f("bold", 36)
        for k, it in enumerate(items):
            x = c.bw * (k + 0.5) / n
            p = E.get(c.motion["enter"]["easing"])(E.progress(t, 0.3 + k * c.motion["stagger"] * 3, 0.4))
            if p <= 0:
                continue
            a = int(255 * p)
            r = 14 * c.s * p
            d.ellipse([x - r, y - r, x + r, y + r], fill=D.rgba(c.accent, a))
            d.text((x, y - 50 * c.s), str(it["date"]), font=df, anchor="mm", fill=D.rgba(c.accent, a))
            for i, ln in enumerate(D.wrap(str(it["text"]), tf, c.bw / n - 20 * c.s)[:2]):
                d.text((x, y + 60 * c.s + i * 46 * c.s), ln, font=tf, anchor="mm", fill=D.rgba(c.white, a))
        return centered(img, c.cx, c.cy)


class Title(Element):
    def content(self, t):
        c, sp = self.c, self.spec
        fnt = c.f("black", sp.get("size", 120))
        lines = [D.rich_line(_words_with_emphasis(l), fnt, c.white, c.accent, stroke=int(5 * c.s))
                 for l in sp["text"].split("\n")]
        sub = D.text_image(sp["sub"], c.f("bold", 48), c.accent) if sp.get("sub") else None
        w = max([l.width for l in lines] + ([sub.width] if sub else []))
        h = sum(l.height for l in lines) + ((sub.height + int(36 * c.s)) if sub else 0)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        y = 0
        if sub:
            img.alpha_composite(sub, ((w - sub.width) // 2, 0))
            y = sub.height + int(36 * c.s)
        for l in lines:
            img.alpha_composite(l, ((w - l.width) // 2, y))
            y += l.height
        return centered(img, c.cx, c.cy)


class Photo(Element):
    """둥근 모서리 사진 카드 (라이선스 확인된 이미지만)."""

    def content(self, t):
        c, sp = self.c, self.spec
        src = Image.open(c.p.path(sp["src"])).convert("RGBA")
        w = int(c.bw * sp.get("width", 0.6))
        h = int(w * sp.get("ratio", 9 / 16))
        img = D.cover(src, (w, h))
        mask = D.rounded((w, h), int(20 * c.s), (255, 255, 255, 255)).getchannel("A")
        img.putalpha(mask)
        cx = c.box[0] + c.bw * sp.get("x", 0.5)
        return centered(img, cx, c.cy)


class Cutout(Element):
    """누끼(배경 제거) 피사체. 옆에서 미끄러져 들어온다."""

    def content(self, t):
        from .cutout import cutout
        c, sp = self.c, self.spec
        img = cutout(c.p, sp["src"], outline=int(sp.get("outline", 0) * c.s))
        # 자막 영역을 침범하지 않도록 콘텐츠 영역 하단에 맞춘다
        h = int((c.box[3] - c.box[1]) * sp.get("height", 0.9))
        img = img.resize((max(1, int(img.width * h / img.height)), h), Image.LANCZOS)
        side = sp.get("side", "right")
        x = int(c.box[2] - img.width) if side == "right" else int(c.box[0])
        return img, (x, int(c.box[3] - img.height))


TYPES = {
    "keyword": Keyword, "number": Number, "bars": Bars, "flow": Flow, "headline": Headline,
    "compare": Compare, "timeline": Timeline, "title": Title, "photo": Photo, "cutout": Cutout,
}


def make(spec, ctx, scene_dur):
    t = spec.get("type")
    if t not in TYPES:
        raise ValueError(f"알 수 없는 visual type: {t} (사용 가능: {', '.join(TYPES)})")
    return TYPES[t](spec, ctx, scene_dur)
