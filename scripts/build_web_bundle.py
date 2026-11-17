"""Pack data/ JSON artifacts into netlify/functions/data/archive.json.gz for serverless deployment."""

from __future__ import annotations

import glob
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_FILE = ROOT / "netlify" / "functions" / "data" / "archive.json.gz"


def build_bundle() -> dict[str, int]:
    docs = []
    for p in sorted(glob.glob(str(DATA_DIR / "protocol" / "*.json"))):
        if p.endswith("index.json"):
            continue
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        docs.append({
            "id": d["id"],
            "tier": 1,
            "source_type": "official_protocol",
            "title": d["title"],
            "url": d["url"],
            "channel": "protocol.bryanjohnson.com",
            "published_at": d.get("published_at", ""),
            "updated_at": d.get("updated_at", ""),
            "duration_sec": 0,
            "content": d["markdown"],
        })

    articles_path = DATA_DIR / "articles" / "articles.json"
    if articles_path.exists():
        for d in json.loads(articles_path.read_text(encoding="utf-8")):
            docs.append({
                "id": d["id"],
                "tier": 2,
                "source_type": "official_article",
                "title": d["title"],
                "url": d["url"],
                "channel": "blueprint.bryanjohnson.com",
                "published_at": d.get("published_at", ""),
                "updated_at": d.get("updated_at", ""),
                "duration_sec": 0,
                "content": d["markdown"],
            })

    segs = []
    for p in sorted(glob.glob(str(DATA_DIR / "transcripts" / "*.json"))):
        if p.endswith("manifest.json"):
            continue
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        docs.append({
            "id": d["id"],
            "tier": int(d.get("tier", 2)),
            "source_type": d.get("source_type", "official_video"),
            "title": d["title"],
            "url": d["url"],
            "channel": d.get("channel", "YouTube"),
            "published_at": d.get("published_at", ""),
            "updated_at": d.get("published_at", ""),
            "duration_sec": int(d.get("duration_sec", 0)),
            "content": (d.get("description") or "")[:900],
        })
        for s in d.get("segments", []):
            segs.append([d["id"], int(s["start_sec"]), s["text"]])

    stances = []
    stances_path = DATA_DIR / "stances.json"
    if stances_path.exists():
        stances = json.loads(stances_path.read_text(encoding="utf-8"))

    payload = json.dumps({"docs": docs, "segs": segs, "stances": stances}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_bytes(gzip.compress(payload, compresslevel=9))
    return {"docs": len(docs), "segs": len(segs), "stances": len(stances), "bytes": OUT_FILE.stat().st_size}


if __name__ == "__main__":
    print(json.dumps(build_bundle(), indent=2))
