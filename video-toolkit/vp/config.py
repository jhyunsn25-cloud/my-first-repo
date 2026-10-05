"""preset.yaml + project.yaml 로드 및 병합."""
import copy
import csv
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESET_PATH = os.path.join(ROOT, "config", "preset.yaml")
LIB = os.path.join(ROOT, "assets")          # 프로젝트 공용 자산(효과음 등). 경로에 lib: 접두어로 참조


def load_dotenv(path=os.path.join(ROOT, ".env")):
    """video-toolkit/.env 의 KEY=VALUE 를 환경변수로 (이미 설정된 값은 유지). .env 는 git 에 올리지 않는다."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()


def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Project:
    def __init__(self, project_dir):
        self.dir = os.path.abspath(project_dir)
        with open(PRESET_PATH, encoding="utf-8") as f:
            preset = yaml.safe_load(f)
        with open(os.path.join(self.dir, "project.yaml"), encoding="utf-8") as f:
            self.data = yaml.safe_load(f)
        self.cfg = deep_merge(preset, self.data.get("overrides", {}))
        self.meta = self.data.get("meta", {})
        self.scenes = self.data.get("scenes", [])
        self.thumbnail = self.data.get("thumbnail", {})
        fmt = self.meta.get("format", "explainer")
        if fmt not in self.cfg["formats"]:
            raise ValueError(f"meta.format '{fmt}' 이 preset.yaml formats에 없습니다")
        self.format = fmt
        self.format_cfg = self.cfg["formats"][fmt]
        self.out = os.path.join(self.dir, "out")
        os.makedirs(self.out, exist_ok=True)

    def path(self, rel):
        if rel is None:
            return None
        if rel.startswith("lib:"):
            return os.path.join(LIB, rel[4:])
        return rel if os.path.isabs(rel) else os.path.join(self.dir, rel)

    def font(self, key):
        p = self.cfg["fonts"][key]
        return p if os.path.isabs(p) else os.path.join(ROOT, p)

    @property
    def accent(self):
        return self.cfg["palette"]["accents"][self.format_cfg["accent"]]

    def canvas(self, preview=False):
        w, h = self.cfg["video"]["sizes"][self.meta.get("aspect", "16:9")]
        if preview:
            w, h = w // 2, h // 2
        return w, h

    def sources(self):
        path = os.path.join(self.dir, "sources.csv")
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8-sig") as f:
            return {r["claim_id"].strip(): r for r in csv.DictReader(f) if r.get("claim_id")}

    def licenses(self):
        path = os.path.join(self.dir, "assets", "licenses.csv")
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8-sig") as f:
            return {r["file"].strip(): r for r in csv.DictReader(f) if r.get("file")}
