"""SQLite + FTS5 ground-truth database builder and query engine."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bryan_protocol_mcp.html_utils import format_timestamp

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "bryan_protocol.db"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_STOPWORDS = frozenset({
    "a", "about", "an", "and", "any", "are", "as", "at", "be",
    "because", "been", "between", "bryan", "but", "by", "can",
    "could", "did", "do", "does", "doing", "for", "from", "get", "had",
    "has", "have", "he", "her", "his", "how", "i", "if", "in", "into",
    "is", "it", "its", "johnson", "just", "know", "like", "make", "me",
    "more", "my", "of", "on", "or", "other", "our", "out", "over",
    "protocol", "really", "say", "said", "says", "should", "so", "some",
    "still", "such", "take", "taking", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "thing", "think", "this",
    "through", "to", "under", "up", "use", "using", "very", "want", "was",
    "we", "were", "what", "when", "where", "whether", "which", "who",
    "why", "will", "with", "would", "you", "your",
})

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    tier INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    channel_or_site TEXT NOT NULL,
    published_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    duration_sec INTEGER DEFAULT 0,
    summary TEXT DEFAULT '',
    content TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_documents_tier_type ON documents(tier, source_type);
CREATE INDEX IF NOT EXISTS idx_documents_published ON documents(published_at DESC);

CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    start_sec INTEGER NOT NULL,
    end_sec INTEGER NOT NULL,
    text TEXT NOT NULL,
    deep_link TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_segments_doc_seq ON segments(doc_id, seq);

CREATE TABLE IF NOT EXISTS stances (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    dosage_or_rule TEXT DEFAULT '',
    rationale TEXT DEFAULT '',
    changed_at TEXT DEFAULT '',
    sources_json TEXT DEFAULT '[]'
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    doc_id UNINDEXED,
    tier UNINDEXED,
    source_type UNINDEXED,
    title,
    summary,
    content,
    tokenize='porter unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5(
    doc_id UNINDEXED,
    start_sec UNINDEXED,
    deep_link UNINDEXED,
    doc_title,
    text,
    tokenize='porter unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS stances_fts USING fts5(
    stance_id UNINDEXED,
    topic,
    category,
    status,
    summary,
    dosage_or_rule,
    rationale,
    tokenize='porter unicode61'
);
"""


def build_fts_queries(raw_query: str) -> tuple[str, str, list[str]]:
    """Convert arbitrary user text into safe FTS5 (AND, OR) queries and tokens."""
    all_tokens = re.findall(r"[a-zA-Z0-9]+", raw_query.lower())
    filtered = [t for t in all_tokens if t not in _STOPWORDS and len(t) >= 2]
    tokens = filtered if filtered else [t for t in all_tokens if len(t) >= 2]
    if not tokens:
        return "", "", []
    # Deduplicate preserving order
    unique = list(dict.fromkeys(tokens))[:12]
    quoted = [f'"{tok}"' for tok in unique]
    strict_q = " AND ".join(quoted)
    broad_q = " OR ".join(quoted)
    return strict_q, broad_q, unique


def _excerpt(text: str, tokens: list[str], max_len: int = 420) -> str:
    """Return a readable excerpt centered on the first query token match."""
    clean = " ".join(text.split())
    if len(clean) <= max_len:
        return clean
    lower = clean.lower()
    best_pos = -1
    for tok in tokens:
        pos = lower.find(tok.lower())
        if pos != -1 and (best_pos == -1 or pos < best_pos):
            best_pos = pos
    if best_pos <= max_len // 3:
        return clean[:max_len].rstrip() + "..."
    start = max(0, best_pos - max_len // 3)
    end = min(len(clean), start + max_len)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean) else ""
    return f"{prefix}{clean[start:end].strip()}{suffix}"


class ProtocolDatabase:
    """Read/write wrapper around the Bryan Protocol SQLite + FTS5 database."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    def _connect(self, readonly: bool = True) -> sqlite3.Connection:
        if readonly:
            if not self.db_path.exists():
                raise FileNotFoundError(
                    f"Database not found at {self.db_path}. Run `python3 -m bryan_protocol_mcp build-db` first."
                )
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def rebuild_from_data_dir(self, data_dir: Path | str = DEFAULT_DATA_DIR) -> dict[str, int]:
        """Rebuild the SQLite database cleanly from JSON files in `data_dir`."""
        data_root = Path(data_dir)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "bryan_protocol.db"
            conn = sqlite3.connect(tmp_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=OFF;")
            conn.execute("PRAGMA synchronous=OFF;")
            conn.executescript(SCHEMA_SQL)

            doc_count = 0
            seg_count = 0
            stance_count = 0

            # 1. Tier 1: Official protocol.bryanjohnson.com pages
            protocol_dir = data_root / "protocol"
            if protocol_dir.exists():
                for pfile in sorted(protocol_dir.glob("*.json")):
                    if pfile.name == "index.json":
                        continue
                    item = json.loads(pfile.read_text(encoding="utf-8"))
                    doc_id = item["id"]
                    self._insert_document(conn, {
                        "id": doc_id,
                        "tier": 1,
                        "source_type": "official_protocol",
                        "title": item["title"],
                        "url": item["url"],
                        "channel_or_site": "protocol.bryanjohnson.com",
                        "published_at": item.get("published_at", ""),
                        "updated_at": item.get("updated_at", ""),
                        "duration_sec": 0,
                        "summary": item.get("summary", ""),
                        "content": item.get("markdown", ""),
                        "metadata_json": json.dumps(item.get("metadata", {})),
                    })
                    doc_count += 1

            # 2. Tier 2: Blueprint official blog articles
            articles_file = data_root / "articles" / "articles.json"
            if articles_file.exists():
                articles = json.loads(articles_file.read_text(encoding="utf-8"))
                for item in articles:
                    self._insert_document(conn, {
                        "id": item["id"],
                        "tier": 2,
                        "source_type": "official_article",
                        "title": item["title"],
                        "url": item["url"],
                        "channel_or_site": "blueprint.bryanjohnson.com",
                        "published_at": item.get("published_at", ""),
                        "updated_at": item.get("updated_at", ""),
                        "duration_sec": 0,
                        "summary": item.get("summary", ""),
                        "content": item.get("markdown", ""),
                        "metadata_json": json.dumps(item.get("metadata", {})),
                    })
                    doc_count += 1

            # 3. Tier 2 & 3: YouTube transcripts (@BryanJohnson + external podcasts)
            transcripts_dir = data_root / "transcripts"
            if transcripts_dir.exists():
                for tfile in sorted(transcripts_dir.glob("*.json")):
                    if tfile.name == "manifest.json":
                        continue
                    item = json.loads(tfile.read_text(encoding="utf-8"))
                    doc_id = item["id"]
                    tier = int(item.get("tier", 2))
                    source_type = item.get("source_type", "official_video")
                    segments = item.get("segments", [])
                    full_text = item.get("full_text") or "\n".join(
                        f"[{format_timestamp(s['start_sec'])}] {s['text']}" for s in segments
                    )
                    self._insert_document(conn, {
                        "id": doc_id,
                        "tier": tier,
                        "source_type": source_type,
                        "title": item["title"],
                        "url": item["url"],
                        "channel_or_site": item.get("channel", "YouTube"),
                        "published_at": item.get("published_at", ""),
                        "updated_at": item.get("updated_at", item.get("published_at", "")),
                        "duration_sec": int(item.get("duration_sec", 0)),
                        "summary": item.get("description", "")[:500],
                        "content": full_text,
                        "metadata_json": json.dumps(item.get("metadata", {})),
                    })
                    doc_count += 1

                    for idx, seg in enumerate(segments):
                        start_sec = int(seg["start_sec"])
                        end_sec = int(seg.get("end_sec", start_sec))
                        text = seg["text"].strip()
                        if not text:
                            continue
                        deep_link = seg.get("deep_link") or f"{item['url']}&t={start_sec}s"
                        conn.execute(
                            "INSERT INTO segments (doc_id, seq, start_sec, end_sec, text, deep_link) VALUES (?, ?, ?, ?, ?, ?)",
                            (doc_id, idx, start_sec, end_sec, text, deep_link),
                        )
                        conn.execute(
                            "INSERT INTO segments_fts (doc_id, start_sec, deep_link, doc_title, text) VALUES (?, ?, ?, ?, ?)",
                            (doc_id, start_sec, deep_link, item["title"], text),
                        )
                        seg_count += 1

            # 4. Curated ground-truth stances & anti-protocol rules
            stances_file = data_root / "stances.json"
            if stances_file.exists():
                stances = json.loads(stances_file.read_text(encoding="utf-8"))
                for st in stances:
                    conn.execute(
                        """
                        INSERT INTO stances (id, topic, category, status, summary, dosage_or_rule, rationale, changed_at, sources_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            st["id"],
                            st["topic"],
                            st["category"],
                            st["status"],
                            st["summary"],
                            st.get("dosage_or_rule", ""),
                            st.get("rationale", ""),
                            st.get("changed_at", ""),
                            json.dumps(st.get("sources", [])),
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO stances_fts (stance_id, topic, category, status, summary, dosage_or_rule, rationale)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            st["id"],
                            st["topic"],
                            st["category"],
                            st["status"],
                            st["summary"],
                            st.get("dosage_or_rule", ""),
                            st.get("rationale", ""),
                        ),
                    )
                    stance_count += 1

            built_at = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("built_at", built_at))
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("schema_version", "1"))
            conn.commit()
            conn.execute("PRAGMA journal_mode=DELETE;")
            conn.close()

            dest_tmp = self.db_path.with_suffix(".db.staging")
            shutil.copyfile(tmp_path, dest_tmp)
            if self.db_path.exists():
                self.db_path.unlink()
            dest_tmp.replace(self.db_path)

        return {"documents": doc_count, "segments": seg_count, "stances": stance_count}

    @staticmethod
    def _insert_document(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO documents (
                id, tier, source_type, title, url, channel_or_site,
                published_at, updated_at, duration_sec, summary, content, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["tier"],
                row["source_type"],
                row["title"],
                row["url"],
                row["channel_or_site"],
                row["published_at"],
                row["updated_at"],
                row["duration_sec"],
                row["summary"],
                row["content"],
                row["metadata_json"],
            ),
        )
        conn.execute(
            """
            INSERT INTO documents_fts (doc_id, tier, source_type, title, summary, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["tier"],
                row["source_type"],
                row["title"],
                row["summary"],
                row["content"],
            ),
        )

    def get_protocol_overview(self) -> dict[str, Any]:
        """Return archive statistics, source breakdown, and Tier 1 protocol index."""
        with self._connect(readonly=True) as conn:
            meta = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM meta").fetchall()}
            doc_counts = [
                dict(r)
                for r in conn.execute(
                    "SELECT tier, source_type, COUNT(*) AS count FROM documents GROUP BY tier, source_type ORDER BY tier, source_type"
                ).fetchall()
            ]
            stance_counts = [
                dict(r)
                for r in conn.execute(
                    "SELECT status, COUNT(*) AS count FROM stances GROUP BY status ORDER BY count DESC"
                ).fetchall()
            ]
            seg_total = conn.execute("SELECT COUNT(*) AS c FROM segments").fetchone()["c"]
            tier1_pages = [
                dict(r)
                for r in conn.execute(
                    "SELECT id, title, url, updated_at FROM documents WHERE tier = 1 ORDER BY title"
                ).fetchall()
            ]
        return {
            "meta": meta,
            "document_counts": doc_counts,
            "segment_count": seg_total,
            "stance_counts": stance_counts,
            "tier1_official_pages": tier1_pages,
            "source_tier_hierarchy": {
                "1": "Official Blueprint Protocol (protocol.bryanjohnson.com): highest ground truth for current daily regimen",
                "2": "Blueprint Official Articles (blueprint.bryanjohnson.com) & Bryan Johnson YouTube (@BryanJohnson): explanations, experiments, updates",
                "3": "External Podcast & Interview Appearances: long-form reasoning and Q&A with timestamped citations",
            },
        }

    def _fts_search_documents(
        self,
        conn: sqlite3.Connection,
        query: str,
        tier: int | None = None,
        source_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        strict_q, broad_q, tokens = build_fts_queries(query)
        if not strict_q:
            return []

        results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for fts_q in (strict_q, broad_q):
            if len(results) >= limit:
                break
            if fts_q == strict_q and strict_q == broad_q and seen_ids:
                break
            where = ["documents_fts MATCH ?"]
            params: list[Any] = [fts_q]
            if tier is not None:
                where.append("d.tier = ?")
                params.append(tier)
            if source_type:
                where.append("d.source_type = ?")
                params.append(source_type)
            params.append(limit * 2)

            sql = f"""
                SELECT d.id, d.tier, d.source_type, d.title, d.url, d.channel_or_site,
                       d.published_at, d.updated_at, d.duration_sec, d.content,
                       bm25(documents_fts, 0.0, 0.0, 0.0, 6.0, 3.0, 1.0) AS score
                FROM documents_fts
                JOIN documents d ON d.id = documents_fts.doc_id
                WHERE {' AND '.join(where)}
                ORDER BY score ASC, d.tier ASC, d.published_at DESC
                LIMIT ?
            """
            for r in conn.execute(sql, params).fetchall():
                if r["id"] in seen_ids:
                    continue
                seen_ids.add(r["id"])
                results.append({
                    "doc_id": r["id"],
                    "tier": r["tier"],
                    "source_type": r["source_type"],
                    "title": r["title"],
                    "url": r["url"],
                    "channel_or_site": r["channel_or_site"],
                    "published_at": r["published_at"],
                    "updated_at": r["updated_at"],
                    "duration_sec": r["duration_sec"],
                    "excerpt": _excerpt(r["content"], tokens),
                })
                if len(results) >= limit:
                    break
        return results

    def _fts_search_segments(
        self,
        conn: sqlite3.Connection,
        query: str,
        tier: int | None = None,
        source_type: str | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        strict_q, broad_q, _ = build_fts_queries(query)
        if not strict_q:
            return []

        results: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, int]] = set()

        for fts_q in (strict_q, broad_q):
            if len(results) >= limit:
                break
            where = ["segments_fts MATCH ?"]
            params: list[Any] = [fts_q]
            if tier is not None:
                where.append("d.tier = ?")
                params.append(tier)
            if source_type:
                where.append("d.source_type = ?")
                params.append(source_type)
            params.append(limit * 3)

            sql = f"""
                SELECT s.doc_id, d.tier, d.source_type, d.title, d.channel_or_site,
                       d.published_at, s.start_sec, s.text, s.deep_link,
                       bm25(segments_fts, 0.0, 0.0, 0.0, 2.0, 5.0) AS score
                FROM segments_fts
                JOIN documents d ON d.id = segments_fts.doc_id
                JOIN segments s ON s.doc_id = segments_fts.doc_id AND s.start_sec = segments_fts.start_sec
                WHERE {' AND '.join(where)}
                ORDER BY score ASC, d.tier ASC, d.published_at DESC
                LIMIT ?
            """
            for r in conn.execute(sql, params).fetchall():
                key = (r["doc_id"], r["start_sec"])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                results.append({
                    "doc_id": r["doc_id"],
                    "tier": r["tier"],
                    "source_type": r["source_type"],
                    "title": r["title"],
                    "channel": r["channel_or_site"],
                    "published_at": r["published_at"],
                    "timestamp": format_timestamp(r["start_sec"]),
                    "start_sec": r["start_sec"],
                    "deep_link": r["deep_link"],
                    "text": r["text"],
                })
                if len(results) >= limit:
                    break
        return results

    def _search_stances(self, conn: sqlite3.Connection, query: str, limit: int = 8) -> list[dict[str, Any]]:
        strict_q, broad_q, tokens = build_fts_queries(query)
        rows_by_id: dict[str, dict[str, Any]] = {}

        if strict_q:
            strict_sql = """
                SELECT st.*, bm25(stances_fts, 0.0, 8.0, 4.0, 2.0, 4.0, 3.0, 2.0) AS score
                FROM stances_fts
                JOIN stances st ON st.id = stances_fts.stance_id
                WHERE stances_fts MATCH ?
                ORDER BY score ASC
                LIMIT ?
            """
            for r in conn.execute(strict_sql, (strict_q, limit)).fetchall():
                rows_by_id[r["id"]] = self._format_stance(r)

            # Only broaden to OR when strict AND found nothing (e.g., multi-topic questions)
            if not rows_by_id and broad_q != strict_q:
                for r in conn.execute(strict_sql, (broad_q, limit)).fetchall():
                    if r["id"] not in rows_by_id:
                        rows_by_id[r["id"]] = self._format_stance(r)

        # Substring fallback only when FTS found nothing (e.g., partial terms)
        if not rows_by_id and tokens:
            for tok in tokens[:4]:
                like = f"%{tok}%"
                for r in conn.execute(
                    "SELECT * FROM stances WHERE LOWER(topic) LIKE ? OR LOWER(summary) LIKE ? OR LOWER(category) LIKE ? LIMIT ?",
                    (like, like, like, limit),
                ).fetchall():
                    if r["id"] not in rows_by_id:
                        rows_by_id[r["id"]] = self._format_stance(r)
        return list(rows_by_id.values())[:limit]

    @staticmethod
    def _format_stance(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "topic": row["topic"],
            "category": row["category"],
            "status": row["status"],
            "summary": row["summary"],
            "dosage_or_rule": row["dosage_or_rule"],
            "rationale": row["rationale"],
            "changed_at": row["changed_at"],
            "sources": json.loads(row["sources_json"] or "[]"),
        }

    def get_official_protocol(self, topic: str, include_full_content: bool = True, limit: int = 5) -> dict[str, Any]:
        """Fetch authoritative Tier 1 protocol.bryanjohnson.com pages matching `topic`."""
        with self._connect(readonly=True) as conn:
            matches = self._fts_search_documents(conn, topic, tier=1, limit=limit)
            if include_full_content and matches:
                for item in matches[:2]:
                    row = conn.execute("SELECT content FROM documents WHERE id = ?", (item["doc_id"],)).fetchone()
                    if row:
                        item["content"] = row["content"][:16000]
            stances = self._search_stances(conn, topic, limit=5)
        return {
            "topic": topic,
            "tier1_pages": matches,
            "related_stances": stances,
        }

    def check_stance_and_changes(self, topic: str) -> dict[str, Any]:
        """Check whether Bryan actively does, stopped, or avoids `topic` with chronological mentions."""
        with self._connect(readonly=True) as conn:
            stances = self._search_stances(conn, topic, limit=8)
            doc_hits = self._fts_search_documents(conn, topic, limit=10)
            seg_hits = self._fts_search_segments(conn, topic, limit=10)
        return {
            "topic": topic,
            "stances": stances,
            "protocol_and_article_mentions": [d for d in doc_hits if d["tier"] in (1, 2) and d["source_type"] != "official_video"],
            "video_and_podcast_mentions": seg_hits,
        }

    def what_would_bryan_do(
        self,
        question: str,
        include_transcripts: bool = True,
        max_per_tier: int = 5,
    ) -> dict[str, Any]:
        """Build a tiered Ground Truth Dossier to answer what Bryan would or wouldn't do."""
        with self._connect(readonly=True) as conn:
            stances = self._search_stances(conn, question, limit=6)
            tier1 = self._fts_search_documents(conn, question, tier=1, limit=max_per_tier)
            tier2_docs = self._fts_search_documents(conn, question, tier=2, limit=max_per_tier)
            tier2_segs = self._fts_search_segments(conn, question, tier=2, limit=max_per_tier) if include_transcripts else []
            tier3_segs = self._fts_search_segments(conn, question, tier=3, limit=max_per_tier) if include_transcripts else []

        return {
            "question": question,
            "ground_truth_guidance": (
                "Prioritize Tier 1 (protocol.bryanjohnson.com) and explicit `stopped`/`avoid` stances over older videos or interviews. "
                "Always cite URLs, dates, and video timestamps when answering. If Bryan stopped or changed something (e.g. rapamycin), state the update explicitly."
            ),
            "explicit_stances": stances,
            "tier1_official_protocol": tier1,
            "tier2_official_articles_and_videos": {
                "documents": tier2_docs,
                "timestamped_quotes": tier2_segs,
            },
            "tier3_external_podcasts": tier3_segs,
        }

    def search_archive(
        self,
        query: str,
        tier: int | None = None,
        source_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search documents and timestamped segments across the archive."""
        with self._connect(readonly=True) as conn:
            docs = self._fts_search_documents(conn, query, tier=tier, source_type=source_type, limit=limit)
            segs = self._fts_search_segments(conn, query, tier=tier, source_type=source_type, limit=limit)
        return {
            "query": query,
            "documents": docs,
            "timestamped_segments": segs,
        }

    def get_document(self, doc_id: str, include_segments: bool = False, max_chars: int = 25000) -> dict[str, Any] | None:
        """Retrieve a full document by ID with optional timestamped transcript segments."""
        with self._connect(readonly=True) as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                return None
            out = {
                "id": row["id"],
                "tier": row["tier"],
                "source_type": row["source_type"],
                "title": row["title"],
                "url": row["url"],
                "channel_or_site": row["channel_or_site"],
                "published_at": row["published_at"],
                "updated_at": row["updated_at"],
                "duration_sec": row["duration_sec"],
                "content": row["content"][:max_chars],
                "truncated": len(row["content"]) > max_chars,
                "total_chars": len(row["content"]),
                "metadata": json.loads(row["metadata_json"] or "{}"),
            }
            if include_segments:
                segs = conn.execute(
                    "SELECT seq, start_sec, end_sec, text, deep_link FROM segments WHERE doc_id = ? ORDER BY seq",
                    (doc_id,),
                ).fetchall()
                out["segments"] = [
                    {
                        "seq": s["seq"],
                        "timestamp": format_timestamp(s["start_sec"]),
                        "start_sec": s["start_sec"],
                        "deep_link": s["deep_link"],
                        "text": s["text"],
                    }
                    for s in segs
                ]
            return out

    def list_sources(
        self,
        tier: int | None = None,
        source_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List ingested documents with optional tier/source_type filtering."""
        where: list[str] = []
        params: list[Any] = []
        if tier is not None:
            where.append("tier = ?")
            params.append(tier)
        if source_type:
            where.append("source_type = ?")
            params.append(source_type)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect(readonly=True) as conn:
            total = conn.execute(f"SELECT COUNT(*) AS c FROM documents {where_sql}", params).fetchone()["c"]
            rows = conn.execute(
                f"""
                SELECT id, tier, source_type, title, url, channel_or_site, published_at, updated_at, duration_sec
                FROM documents {where_sql}
                ORDER BY tier ASC, published_at DESC, title ASC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [dict(r) for r in rows],
        }

    def list_all_stances(self) -> list[dict[str, Any]]:
        """Return every curated ground-truth stance entry."""
        with self._connect(readonly=True) as conn:
            rows = conn.execute("SELECT * FROM stances ORDER BY category, topic").fetchall()
            return [self._format_stance(r) for r in rows]
