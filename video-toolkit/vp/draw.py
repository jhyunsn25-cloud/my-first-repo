"""Pillow 그리기 도우미: 폰트 캐시, 외곽선 텍스트, 둥근 상자, 그라데이션, 알파 조절."""
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont


@lru_cache(maxsize=256)
def font(path, size):
    try:
        return ImageFont.truetype(path, max(1, int(size)))
    except OSError as e:
        raise SystemExit(f"폰트를 열 수 없습니다: {path}\n→ bash scripts/setup_fonts.sh 를 먼저 실행하세요") from e


def text_size(fnt, s):
    l, t, r, b = fnt.getbbox(s)
    return r - l, b - t


def rgba(c, a=255):
    return (c[0], c[1], c[2], a)


def with_opacity(img, op):
    if op >= 0.999:
        return img
    a = img.getchannel("A").point(lambda v: int(v * max(0.0, op)))
    img = img.copy()
    img.putalpha(a)
    return img


def text_image(s, fnt, fill, stroke=0, stroke_fill=(0, 0, 0)):
    """문자열 하나를 딱 맞는 RGBA 이미지로."""
    l, t, r, b = fnt.getbbox(s, stroke_width=stroke)
    img = Image.new("RGBA", (r - l + 2, b - t + 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((-l + 1, -t + 1), s, font=fnt, fill=rgba(fill),
                             stroke_width=stroke, stroke_fill=rgba(stroke_fill))
    return img


def rich_line(words, fnt, color, accent, stroke=0, stroke_fill=(0, 0, 0)):
    """[(단어, 강조)] 한 줄 → 이미지 (강조 단어는 accent 색). 기준선 정렬."""
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    space = probe.textlength(" ", font=fnt)
    asc, desc = fnt.getmetrics()
    widths = [probe.textlength(w, font=fnt) for w, _ in words]
    w = int(sum(widths) + space * max(0, len(words) - 1)) + stroke * 2 + 2
    h = asc + desc + stroke * 2
    img = Image.new("RGBA", (max(1, w), h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = stroke + 1
    for (word, e), ww in zip(words, widths):
        d.text((x, stroke + asc), word, font=fnt, anchor="ls", fill=rgba(accent if e else color),
               stroke_width=stroke, stroke_fill=rgba(stroke_fill))
        x += ww + space
    return img


def rounded(size, radius, fill):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius, fill=fill)
    return img


def vgradient(size, top_rgba, bottom_rgba):
    w, h = size
    col = Image.new("RGBA", (1, h))
    for y in range(h):
        p = y / max(1, h - 1)
        col.putpixel((0, y), tuple(int(top_rgba[i] + (bottom_rgba[i] - top_rgba[i]) * p) for i in range(4)))
    return col.resize((w, h))


def cover(img, size):
    """비율 유지하며 size 를 꽉 채우도록 자르기."""
    w, h = size
    s = max(w / img.width, h / img.height)
    img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def wrap(s, fnt, max_w):
    words, lines, cur = s.split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if cur and text_size(fnt, nxt)[0] > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines
