"""부드러운 가속·감속 곡선. 모든 모션은 여기 함수만 사용한다(linear 금지)."""
import math


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out_cubic(t):
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_in_cubic(t):
    t = clamp01(t)
    return t ** 3


def ease_in_out_cubic(t):
    t = clamp01(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_quint(t):
    t = clamp01(t)
    return 1 - (1 - t) ** 5


def ease_in_out_sine(t):
    t = clamp01(t)
    return -(math.cos(math.pi * t) - 1) / 2


EASINGS = {
    "out_cubic": ease_out_cubic,
    "in_cubic": ease_in_cubic,
    "in_out_cubic": ease_in_out_cubic,
    "out_quint": ease_out_quint,
    "in_out_sine": ease_in_out_sine,
}


def get(name):
    if name not in EASINGS:
        raise ValueError(f"알 수 없는 easing: {name} (사용 가능: {', '.join(EASINGS)})")
    return EASINGS[name]


def progress(t, start, dur):
    """구간 [start, start+dur]에서의 0~1 진행도."""
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return clamp01((t - start) / dur)


def lerp(a, b, p):
    return a + (b - a) * p
