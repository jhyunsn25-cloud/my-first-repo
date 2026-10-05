"""썸네일: 배경(1장 또는 2~4장 콜라주) + 주요 인물·피사체 누끼 합성 + 하단 2줄 카피."""
import os

from PIL import Image, ImageDraw

from . import draw as D
from .cutout import cutout
from .text import _words_with_emphasis


def _collage(project, srcs, W, H, accent):
    n = len(srcs)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    if n == 1:
        canvas.alpha_composite(D.cover(Image.open(project.path(srcs[0])).convert("RGBA"), (W, H)))
        return canvas
    # 자체 스타일: 기울어진 직선 분할 + 강조색 얇은 틈 (찢어진 종이 효과는 사용하지 않음)
    cols = 2 if n >= 2 else 1
    rows = 2 if n >= 3 else 1
    slant = int(W * 0.04)
    gap = 8
    cells = []
    for i in range(n):
        r, c = divmod(i, cols)
        if n == 3 and i == 2:
            cells.append((0, 1, cols, 1))
        else:
            cells.append((c, r, 1, 1))
    for i, (c, r, cw, rh) in enumerate(cells):
        x0, x1 = W * c / cols, W * (c + cw) / cols
        y0, y1 = H * r / rows, H * (r + rh) / rows
        poly = [(x0 + (slant if c > 0 else 0), y0), (x1 + (slant if c + cw < cols else 0), y0),
                (x1 - (slant if c + cw < cols else 0), y1), (x0 - (slant if c > 0 else 0), y1)]
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon(poly, fill=255)
        img = D.cover(Image.open(project.path(srcs[i])).convert("RGBA"), (W, H))
        canvas.paste(img, (0, 0), mask)
        ImageDraw.Draw(canvas).line(poly + [poly[0]], fill=D.rgba(accent), width=gap)
    return canvas


def make(project, out_path=None):
    th, cfg = project.thumbnail, project.cfg
    tc = cfg["thumbnail"]
    W, H = tc["size"]
    s = H / 720
    accent = tuple(project.accent)
    img = _collage(project, th["backgrounds"], W, H, accent)
    img.alpha_composite(D.vgradient((W, int(H * 0.55)), (0, 0, 0, 0), (0, 0, 0, 215)), (0, H - int(H * 0.55)))

    # 주요 인물·피사체: 배경 제거(누끼) 후 테두리·그림자 넣어 합성
    for sub in th.get("subjects", []):
        cut = cutout(project, sub["src"], outline=int(sub.get("outline", tc["outline"]) * s),
                     shadow=int(sub.get("shadow", tc["shadow"]) * s))
        h = int(H * sub.get("height", 0.85))
        cut = cut.resize((max(1, int(cut.width * h / cut.height)), h), Image.LANCZOS)
        cx, by = sub.get("x", 0.75) * W, sub.get("y", 1.0) * H
        x, y = int(cx - cut.width / 2), int(by - cut.height)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.alpha_composite(cut, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))
        img.alpha_composite(layer)

    m = int(48 * s)
    # 코너 라벨(선택)
    y_text = H - m
    lines = th.get("lines", [])
    sizes = tc["line_size"]
    fnt = [D.font(project.font("display"), sizes[i] * s) for i in range(min(2, len(lines)))]
    rendered = []
    for i, l in enumerate(lines[:2]):
        words = _words_with_emphasis(l)
        if i == 1:
            words = [(w, True) for w, _ in words]   # 2줄은 강조색
        rendered.append(D.rich_line(words, fnt[i], (255, 255, 255), accent, stroke=int(6 * s)))
    for im in reversed(rendered):
        y_text -= im.height
        img.alpha_composite(im, (m, y_text))
        y_text -= int(6 * s)
    if th.get("label"):
        f = D.font(project.font("black"), 38 * s)
        tw, tht = D.text_size(f, th["label"])
        pill = D.rounded((tw + int(36 * s), tht + int(24 * s)), int(8 * s), D.rgba(accent))
        ImageDraw.Draw(pill).text((pill.width / 2, pill.height / 2), th["label"], font=f, anchor="mm", fill=(17, 20, 24, 255))
        img.alpha_composite(pill, (m, y_text - pill.height - int(10 * s)))
    # 채널 표시: 좌상단 (우하단은 재생시간 배지에 가려지므로 비움)
    logo = cfg["channel"].get("logo")
    if logo and os.path.exists(project.path(logo)):
        li = Image.open(project.path(logo)).convert("RGBA")
        h = int(80 * s)
        li = li.resize((int(li.width * h / li.height), h), Image.LANCZOS)
        img.alpha_composite(li, (m, m))
    else:
        f = D.font(project.font("black"), 34 * s)
        tw, tht = D.text_size(f, cfg["channel"]["name"])
        pill = D.rounded((tw + int(30 * s), tht + int(22 * s)), int(6 * s), (17, 20, 24, 230))
        ImageDraw.Draw(pill).text((pill.width / 2, pill.height / 2), cfg["channel"]["name"], font=f, anchor="mm",
                                  fill=D.rgba(accent))
        img.alpha_composite(pill, (m, m))
    out_path = out_path or os.path.join(project.out, "thumbnail.jpg")
    img.convert("RGB").save(out_path, quality=92)
    return out_path
