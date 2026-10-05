"""장면 → 프레임 → ffmpeg. 진행률바·마지막 화면 관련영상 프레임은 의도적으로 구현하지 않는다."""
import os
import subprocess

from PIL import Image, ImageDraw

from . import draw as D
from . import easing as E
from . import elements as EL
from . import text as T


def build_timeline(project, audio):
    """audio: [(wav, dur)] → 장면별 {start, dur, narr_dur} 와 자막 큐."""
    pad = project.cfg["video"]["scene_pad"]
    aspect = project.meta.get("aspect", "16:9")
    sub = project.cfg["subtitle"]
    timeline, cues, t = [], [], 0.0
    for scene, (_, narr) in zip(project.scenes, audio):
        dur = narr + pad + float(scene.get("hold", 0))
        timeline.append({"scene": scene, "start": t, "dur": dur, "narr": narr})
        sc = T.split_cues(scene["narration"], sub["max_chars"][aspect], sub["max_lines"])
        weights = [max(1.0, sum(T.syllables(w) for line in cue for w, _ in line)) for cue in sc]
        total = sum(weights) or 1
        ct = t
        for cue, w in zip(sc, weights):
            d = narr * w / total
            cues.append({"start": ct, "end": ct + max(d, 0.01), "cue": cue})
            ct += d
        t += dur
    # 최소 노출 시간 보정(다음 큐와 겹치지 않는 범위에서)
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else t
        if c["end"] - c["start"] < sub["min_cue_sec"]:
            c["end"] = min(nxt, c["start"] + sub["min_cue_sec"])
    return timeline, cues, t


class SceneRenderer:
    def __init__(self, project, ctx, item):
        self.p, self.c = project, ctx
        self.scene, self.dur = item["scene"], item["dur"]
        sc = self.scene
        self.elements = [EL.make(v, ctx, self.dur) for v in sc.get("visuals", [])]
        self.bg_spec = sc.get("bg", {})
        self.bg_img = None
        if self.bg_spec.get("src"):
            k = project.cfg["motion"]["kenburns"]["scale"]
            src = Image.open(project.path(self.bg_spec["src"])).convert("RGB")
            self.bg_img = D.cover(src, (int(ctx.W * k), int(ctx.H * k)))
        self.static_overlay = self._static_overlay()

    def _static_overlay(self):
        c, sc, cfg = self.c, self.scene, self.p.cfg
        ov = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 0))
        if self.bg_img is not None:
            dim = self.bg_spec.get("dim", 0.5 if sc.get("visuals") else 0.15)
            ov.alpha_composite(Image.new("RGBA", (c.W, c.H), (0, 0, 0, int(255 * dim))))
        # 자막 가독성용 하단 그라데이션
        gh = int(c.H * (0.38 if c.portrait else 0.32))
        ov.alpha_composite(D.vgradient((c.W, gh), (0, 0, 0, 0), (0, 0, 0, 170)), (0, c.H - gh))
        m = int(cfg["layout"]["margin"] * c.s * (0.6 if c.portrait else 1))
        top = int(48 * c.s) if not c.portrait else int(c.H * 0.06)
        if cfg["layout"]["chapter_tag"] and sc.get("chapter"):
            f = c.f("bold", 34)
            tw, th = D.text_size(f, sc["chapter"])
            pill = D.rounded((tw + int(44 * c.s), th + int(26 * c.s)), int(30 * c.s), D.rgba(c.accent))
            ImageDraw.Draw(pill).text((pill.width / 2, pill.height / 2), sc["chapter"], font=f, anchor="mm",
                                      fill=D.rgba(c.ink))
            ov.alpha_composite(pill, (m, top))
        if cfg["layout"]["logo_watermark"]:
            logo = cfg["channel"].get("logo")
            if logo and os.path.exists(self.p.path(logo)):
                li = Image.open(self.p.path(logo)).convert("RGBA")
                h = int(60 * c.s)
                li = li.resize((int(li.width * h / li.height), h), Image.LANCZOS)
                ov.alpha_composite(D.with_opacity(li, 0.85), (c.W - m - li.width, top))
            else:
                f = c.f("black", 30)
                tw, _ = D.text_size(f, cfg["channel"]["name"])
                ImageDraw.Draw(ov).text((c.W - m, top + int(14 * c.s)), cfg["channel"]["name"], font=f, anchor="ra",
                                        fill=D.rgba(c.white, 200))
        if cfg["layout"]["source_caption"] and sc.get("source"):
            f = c.f("medium", 28)
            bm = cfg["subtitle"]["bottom_margin"][self.p.meta.get("aspect", "16:9")] * c.s
            y = c.H - bm - cfg["subtitle"]["size"] * c.s * 3.3 - int(36 * c.s)   # 자막 2줄 위
            ImageDraw.Draw(ov).text((m, y), "출처: " + sc["source"], font=f, fill=D.rgba(c.white, 190))
        return ov

    def background(self, t):
        c = self.c
        if self.bg_img is None:
            col = self.bg_spec.get("color", "ink")
            col = tuple(self.p.cfg["palette"].get(col, col)) if isinstance(col, str) else tuple(col)
            return Image.new("RGBA", (c.W, c.H), D.rgba(col))
        kb = self.bg_spec.get("kenburns", "in")
        p = E.get(self.p.cfg["motion"]["kenburns"]["easing"])(t / max(0.01, self.dur))
        bw, bh = self.bg_img.size
        if kb == "in":
            ww = E.lerp(bw, c.W, p)
        elif kb == "out":
            ww = E.lerp(c.W, bw, p)
        else:
            ww = (bw + c.W) / 2
        wh = min(bh, ww * c.H / c.W)
        ww = min(bw, ww)
        fx, fy = self.bg_spec.get("focus", [0.5, 0.5])
        x = max(0, min(fx * bw - ww / 2, bw - ww))
        y = max(0, min(fy * bh - wh / 2, bh - wh))
        return self.bg_img.resize((c.W, c.H), Image.BILINEAR, box=(x, y, x + ww, y + wh)).convert("RGBA")

    def frame(self, t):
        c, mo = self.c, self.p.cfg["motion"]
        img = self.background(t)
        img.alpha_composite(self.static_overlay)
        ein, eout = E.get(mo["enter"]["easing"]), E.get(mo["exit"]["easing"])
        for el in self.elements:
            if t < el.at:
                continue
            end = min(el.until, self.dur)
            if t > end:
                continue
            pin = ein(E.progress(t, el.at, mo["enter"]["dur"]))
            pout = eout(E.progress(t, end - mo["exit"]["dur"], mo["exit"]["dur"])) if el.until < self.dur else 0
            op = pin * (1 - pout)
            if op <= 0.003:
                continue
            content, (x, y) = el.get(t - el.at)
            dy = int(mo["enter"]["dy"] * c.s * (1 - pin))
            if el.spec.get("type") == "cutout":
                side = el.spec.get("side", "right")
                x += int((1 - pin) * 160 * c.s * (1 if side == "right" else -1))
                dy = 0
            _paste_clipped(img, D.with_opacity(content, op), x, y + dy)
        return img


def _paste_clipped(base, im, x, y):
    """화면 밖으로 나가는 부분을 잘라서 합성."""
    l, t = max(0, -x), max(0, -y)
    r, b = min(im.width, base.width - x), min(im.height, base.height - y)
    if l >= r or t >= b:
        return
    base.alpha_composite(im.crop((l, t, r, b)), (max(0, x), max(0, y)))


class SubtitleLayer:
    def __init__(self, project, ctx, cues):
        self.p, self.c, self.cues = project, ctx, cues
        self.cache = {}
        sub = project.cfg["subtitle"]
        self.fnt = ctx.f("bold", sub["size"])
        self.stroke = int(sub["stroke"] * ctx.s)
        self.bm = int(sub["bottom_margin"][project.meta.get("aspect", "16:9")] * ctx.s)
        self.box = sub.get("box_opacity", 0)
        self.i = 0

    def image(self, idx):
        if idx not in self.cache:
            c = self.c
            lines = [D.rich_line(l, self.fnt, c.white, c.accent, self.stroke) for l in self.cues[idx]["cue"]]
            gap = int(6 * c.s)
            w = max(l.width for l in lines)
            h = sum(l.height for l in lines) + gap * (len(lines) - 1)
            pad = int(18 * c.s) if self.box else 0
            img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
            if self.box:
                img = D.rounded(img.size, int(12 * c.s), (0, 0, 0, int(255 * self.box)))
            y = pad
            for l in lines:
                img.alpha_composite(l, ((img.width - l.width) // 2, y))
                y += l.height + gap
            self.cache = {idx: img}
        return self.cache[idx]

    def draw(self, frame, t):
        while self.i < len(self.cues) and self.cues[self.i]["end"] <= t:
            self.i += 1
        if self.i >= len(self.cues) or self.cues[self.i]["start"] > t:
            return
        im = self.image(self.i)
        frame.alpha_composite(im, ((self.c.W - im.width) // 2, self.c.H - self.bm - im.height))


def render(project, audio, audio_path, out_path, preview=False, log=print):
    W, H = project.canvas(preview)
    fps = project.cfg["video"]["fps"] // (2 if preview else 1)
    ctx = EL.Ctx(project, W, H)
    timeline, cues, total = build_timeline(project, audio)
    subs = SubtitleLayer(project, ctx, cues) if project.cfg["subtitle"]["burn_in"] else None
    v = project.cfg["video"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-i", audio_path, "-c:v", "libx264",
           "-preset", "veryfast" if preview else v["preset"], "-crf", str(28 if preview else v["crf"]),
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n_total = int(total * fps)
    fade = v["end_fade"]
    frame_no = 0
    for item in timeline:
        sr = SceneRenderer(project, ctx, item)
        end_frame = int(round((item["start"] + item["dur"]) * fps))
        while frame_no < end_frame:
            gt = frame_no / fps
            img = sr.frame(gt - item["start"])
            if subs:
                subs.draw(img, gt)
            if gt > total - fade:   # 마지막 페이드아웃 (관련 영상 프레임 없이 검은 화면으로 종료)
                k = E.ease_in_out_cubic((gt - (total - fade)) / fade)
                img.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, int(255 * k))))
            proc.stdin.write(img.convert("RGB").tobytes())
            frame_no += 1
        log(f"  장면 {item['scene']['id']} 완료 ({frame_no}/{n_total} 프레임)")
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg 인코딩 실패")
    return timeline, cues, total
