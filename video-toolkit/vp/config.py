"""preset.yaml + project.yaml 로드 및 병합."""
import copy
import csv
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESET_PATH = os.path.join(ROOT, "config", "preset.yaml")


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
