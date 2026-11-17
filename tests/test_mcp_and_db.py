"""Unit and integration tests for bryan-protocol-mcp."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bryan_protocol_mcp.db import ProtocolDatabase, build_fts_queries  # noqa: E402
from bryan_protocol_mcp.html_utils import format_timestamp, html_to_markdown, youtube_timestamp_url  # noqa: E402
from bryan_protocol_mcp.server import BryanProtocolMCPServer  # noqa: E402


def _seed_sample_data(data_dir: Path) -> None:
    (data_dir / "protocol").mkdir(parents=True, exist_ok=True)
    (data_dir / "articles").mkdir(parents=True, exist_ok=True)
    (data_dir / "transcripts").mkdir(parents=True, exist_ok=True)

    (data_dir / "protocol" / "sleep.json").write_text(
        json.dumps({
            "id": "protocol:sleep",
            "title": "Sleep",
            "url": "https://protocol.bryanjohnson.com/#sleep",
            "published_at": "2026-01-21",
            "updated_at": "2026-01-21",
            "summary": "Bedtime 8:30 pm, screens off 60 minutes before bed, no caffeine 8-10 hours before sleep.",
            "markdown": "# Sleep\n\nBedtime 8:30 pm. Avoid caffeine 8-10 hours before sleep. Final meal 4 hours before bed.",
            "metadata": {"slug": "sleep"},
        }),
        encoding="utf-8",
    )

    (data_dir / "articles" / "articles.json").write_text(
        json.dumps([
            {
                "id": "article:why-i-stopped-rapamycin",
                "title": "Why I Stopped Taking Rapamycin",
                "url": "https://blueprint.bryanjohnson.com/blogs/news/why-i-stopped-rapamycin",
                "published_at": "2024-09-28",
                "updated_at": "2024-09-28",
                "summary": "Discontinued rapamycin due to elevated lipids, glucose, resting heart rate, and skin infections.",
                "markdown": "# Why I Stopped Taking Rapamycin\n\nI stopped taking rapamycin on September 28, 2024 after nearly five years.",
                "metadata": {"author": "Bryan Johnson"},
            }
        ]),
        encoding="utf-8",
    )

    (data_dir / "transcripts" / "abc123def45.json").write_text(
        json.dumps({
            "id": "yt:abc123def45",
            "video_id": "abc123def45",
            "tier": 3,
            "source_type": "external_podcast",
            "title": "Bryan Johnson on Longevity Podcast",
            "url": "https://www.youtube.com/watch?v=abc123def45",
            "channel": "Example Podcast",
            "published_at": "2025-05-01",
            "duration_sec": 3600,
            "description": "Long-form interview about sleep and nutrition.",
            "segments": [
                {
                    "start_sec": 125,
                    "end_sec": 160,
                    "text": "I never eat after noon and prioritize eight hours of consistent sleep.",
                    "deep_link": "https://www.youtube.com/watch?v=abc123def45&t=125s",
                }
            ],
            "metadata": {"view_count": 10000},
        }),
        encoding="utf-8",
    )

    (data_dir / "stances.json").write_text(
        json.dumps([
            {
                "id": "stance:rapamycin",
                "topic": "Rapamycin",
                "category": "rx_prescriptions",
                "status": "stopped",
                "summary": "Bryan Johnson discontinued rapamycin in September 2024.",
                "dosage_or_rule": "Stopped (previously experimented with weekly/biweekly dosing).",
                "rationale": "Side effects including elevated resting heart rate, lipid/glucose elevations, skin infections, and epigenetic clock data.",
                "changed_at": "2024-09-28",
                "sources": [{"title": "Official Blueprint Update", "url": "https://protocol.bryanjohnson.com/#rx-prescriptions"}],
            },
            {
                "id": "stance:caffeine",
                "topic": "Caffeine & Coffee",
                "category": "sleep_and_stimulants",
                "status": "conditional",
                "summary": "Avoid caffeine at least 8-10 hours before bedtime to keep resting heart rate low.",
                "dosage_or_rule": "None within 8-10 hours of sleep; avoid acidic coffee lingering on teeth.",
                "rationale": "Caffeine has a ~6 hour half-life and raises pre-bed RHR by 2-5 bpm.",
                "changed_at": "2026-01-21",
                "sources": [{"title": "Sleep Protocol", "url": "https://protocol.bryanjohnson.com/#sleep"}],
            },
        ]),
        encoding="utf-8",
    )


class TestUtilsAndDatabase(unittest.TestCase):
    def test_html_to_markdown_and_timestamps(self) -> None:
        raw = "<h2>Routine</h2><p>Eat <strong>veggies</strong>.</p><script>bad()</script><ul><li>Item 1</li><li>Item 2</li></ul>"
        md = html_to_markdown(raw)
        self.assertIn("## Routine", md)
        self.assertIn("**veggies**", md)
        self.assertIn("- Item 1", md)
        self.assertNotIn("bad()", md)
        self.assertEqual(format_timestamp(65), "1:05")
        self.assertEqual(format_timestamp(3661), "1:01:01")
        self.assertEqual(youtube_timestamp_url("xyz12345678", 92.8), "https://www.youtube.com/watch?v=xyz12345678&t=92s")

    def test_fts_query_sanitizer(self) -> None:
        strict_q, broad_q, toks = build_fts_queries("What would Bryan NOT do with 'rapamycin' & sleep-tracking?")
        self.assertEqual(toks, ["not", "rapamycin", "sleep", "tracking"])
        self.assertIn('"rapamycin"', strict_q)
        self.assertIn(" OR ", broad_q)

        # All-stopwords fallback
        strict2, _, toks2 = build_fts_queries("Bryan protocol")
        self.assertTrue(len(toks2) == 2 and '"bryan"' in strict2)

    def test_db_queries_and_mcp_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir = tmp_path / "data"
            db_path = tmp_path / "test.db"
            _seed_sample_data(data_dir)

            db = ProtocolDatabase(db_path)
            counts = db.rebuild_from_data_dir(data_dir)
            self.assertEqual(counts, {"documents": 3, "segments": 1, "stances": 2})

            overview = db.get_protocol_overview()
            self.assertEqual(overview["segment_count"], 1)
            self.assertEqual(len(overview["tier1_official_pages"]), 1)

            wwbd = db.what_would_bryan_do("Does Bryan still take rapamycin?")
            self.assertEqual(wwbd["explicit_stances"][0]["status"], "stopped")
            self.assertTrue(any("Rapamycin" in d["title"] for d in wwbd["tier2_official_articles_and_videos"]["documents"]))

            pod = db.search_archive("consistent sleep", tier=3)
            self.assertEqual(len(pod["timestamped_segments"]), 1)
            self.assertEqual(pod["timestamped_segments"][0]["deep_link"], "https://www.youtube.com/watch?v=abc123def45&t=125s")

            # MCP server JSON-RPC unit tests
            srv = BryanProtocolMCPServer(db)
            self.assertIsNone(srv.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))

            init_resp = srv.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
            assert init_resp is not None
            self.assertEqual(init_resp["result"]["protocolVersion"], "2025-03-26")

            tools_resp = srv.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            assert tools_resp is not None
            self.assertGreaterEqual(len(tools_resp["result"]["tools"]), 7)

            call_resp = srv.handle_message({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "check_stance_and_changes", "arguments": {"topic": "caffeine"}},
            })
            assert call_resp is not None
            parsed = json.loads(call_resp["result"]["content"][0]["text"])
            self.assertEqual(parsed["stances"][0]["status"], "conditional")

            res_resp = srv.handle_message({"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "bryan://protocol/stances"}})
            assert res_resp is not None
            stances_data = json.loads(res_resp["result"]["contents"][0]["text"])
            self.assertEqual(len(stances_data), 2)

            # Ensure strict AND stance match avoids unrelated partial-token matches
            stances_file = data_dir / "stances.json"
            stances_list = json.loads(stances_file.read_text(encoding="utf-8"))
            stances_list.append({
                "id": "stance:seed-oils",
                "topic": "Seed Oils vs Extra Virgin Olive Oil",
                "category": "nutrition",
                "status": "conditional",
                "summary": "Loves EVOO; cold-pressed seed oils are fine while fried oils are harmful.",
                "dosage_or_rule": "Avoid fried high-heat oils.",
                "rationale": "Biomarker testing.",
                "changed_at": "2026-03-05",
                "sources": [],
            })
            stances_list.append({
                "id": "stance:tea-tree-oil",
                "topic": "Tea Tree Oil Rinse",
                "category": "oral_care",
                "status": "stopped",
                "summary": "Discontinued tea tree oil rinse.",
                "dosage_or_rule": "Stopped.",
                "rationale": "Baseline normalized.",
                "changed_at": "2026-01-21",
                "sources": [],
            })
            stances_file.write_text(json.dumps(stances_list), encoding="utf-8")
            db.rebuild_from_data_dir(data_dir)
            seed_check = db.check_stance_and_changes("What does Bryan say about seed oils?")
            self.assertEqual([s["id"] for s in seed_check["stances"]], ["stance:seed-oils"])

            # End-to-end stdio subprocess handshake
            env = dict(os.environ, PYTHONPATH=str(SRC))
            requests_payload = "\n".join([
                json.dumps({"jsonrpc": "2.0", "id": 10, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}}),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                json.dumps({"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "get_official_protocol", "arguments": {"topic": "sleep"}}}),
            ]) + "\n"
            proc = subprocess.run(
                [sys.executable, "-m", "bryan_protocol_mcp", "serve", "--db", str(db_path)],
                input=requests_payload,
                text=True,
                capture_output=True,
                env=env,
                timeout=15,
                check=True,
            )
            lines = [json.loads(line) for line in proc.stdout.strip().splitlines() if line.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["id"], 10)
            self.assertEqual(lines[1]["id"], 11)
            body = json.loads(lines[1]["result"]["content"][0]["text"])
            self.assertEqual(body["tier1_pages"][0]["doc_id"], "protocol:sleep")


if __name__ == "__main__":
    unittest.main()
