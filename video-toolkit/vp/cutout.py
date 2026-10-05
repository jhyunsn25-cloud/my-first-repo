"""누끼: rembg 로 배경 제거 → 여백 자르기 → (선택) 흰 테두리. 결과는 out/cutouts 에 캐시."""
import hashlib
import os

from PIL import Image, ImageFilter

_sessions = {}


def _remove_bg(img, model):
    from rembg import new_session, remove
    if model not in _sessions:
        _sessions[model] = new_session(model)
    return remove(img, session=_sessions[model])


def has_alpha(img):
    return img.mode == "RGBA" and img.getchannel("A").getextrema()[0] < 250


def cutout(project, rel, outline=0, shadow=0):
    src = project.path(rel)
    model = project.cfg["thumbnail"]["rembg_model"]
    key = hashlib.sha1(f"{os.path.abspath(src)}:{os.path.getmtime(src)}:{model}".encode()).hexdigest()[:12]
    cache_dir = os.path.join(project.out, "cutouts")
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, f"{key}.png")
    if os.path.exists(cache):
        img = Image.open(cache).convert("RGBA")
    else:
        img = Image.open(src)
        img = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
        if not has_alpha(img.convert("RGBA")):     # 이미 투명 배경 PNG 면 그대로 사용
            img = _remove_bg(img, model)
        img = img.convert("RGBA")
        bbox = img.getchannel("A").point(lambda v: 255 if v > 16 else 0).getbbox()
        if bbox:
            img = img.crop(bbox)
        img.save(cache)
    if outline or shadow:
        img = decorate(img, outline, shadow)
    return img


def decorate(img, outline, shadow):
    pad = outline + shadow * 2 + 4
    big = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    a = Image.new("L", big.size, 0)
    a.paste(img.getchannel("A"), (pad, pad))
    if shadow:
        sh = a.filter(ImageFilter.GaussianBlur(shadow)).point(lambda v: int(v * 0.55))
        layer = Image.new("RGBA", big.size, (0, 0, 0, 255))
        layer.putalpha(sh)
        big.alpha_composite(layer, (shadow // 2, shadow // 2))
    if outline:
        ring = a.filter(ImageFilter.MaxFilter(outline * 2 + 1))
        layer = Image.new("RGBA", big.size, (255, 255, 255, 255))
        layer.putalpha(ring)
        big.alpha_composite(layer)
    big.alpha_composite(img, (pad, pad))
    return big
