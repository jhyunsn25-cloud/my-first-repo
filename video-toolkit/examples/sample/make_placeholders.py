"""샘플 프로젝트용 임시 이미지 생성(실제 제작 시에는 라이선스 확인된 사진으로 교체)."""
import os
import random

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "assets")
os.makedirs(A, exist_ok=True)


def bg(name, c1, c2, seed):
    random.seed(seed)
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), c1)
    d = ImageDraw.Draw(img)
    for _ in range(40):
        x, y, r = random.randint(0, W), random.randint(0, H), random.randint(60, 260)
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * random.random()) for i in range(3)))
    img = img.filter(ImageFilter.GaussianBlur(30))
    ImageDraw.Draw(img).text((40, 40), "PLACEHOLDER — 실제 사진으로 교체", fill=(255, 255, 255))
    img.save(os.path.join(A, name), quality=90)


def subject(name):
    """흰 배경 위 컵 모양 피사체 (누끼 테스트용)."""
    W, H = 900, 1100
    img = Image.new("RGB", (W, H), (236, 236, 232))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([220, 330, 680, 1000], 40, fill=(120, 72, 40))
    d.rounded_rectangle([200, 280, 700, 360], 20, fill=(245, 245, 245))
    d.ellipse([640, 520, 820, 760], outline=(120, 72, 40), width=40)
    d.rectangle([260, 520, 640, 700], fill=(250, 230, 200))
    img.save(os.path.join(A, name), quality=92)


bg("bg_cafe.jpg", (70, 45, 30), (190, 140, 90), 1)
bg("bg_farm.jpg", (30, 70, 40), (140, 190, 90), 2)
bg("bg_city.jpg", (25, 35, 60), (90, 120, 180), 3)
bg("bg_shop.jpg", (60, 30, 50), (200, 120, 140), 4)
subject("cup.jpg")
print("placeholders →", A)
