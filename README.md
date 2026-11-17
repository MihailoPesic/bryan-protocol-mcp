# bryan-protocol-mcp

A searchable ground-truth database and Model Context Protocol (MCP) server for Bryan Johnson's Blueprint Protocol.

- **Live Web App:** https://bryan-protocol-mcp.netlify.app
- **Public Streamable HTTP MCP:** `https://bryan-protocol-mcp.netlify.app/mcp`

It indexes his official protocol pages, Blueprint blog posts, YouTube videos/livestreams, and full-length podcast appearances into a local SQLite FTS5 archive, alongside a curated stance matrix tracking what he actively does, what he stopped doing, and what he avoids.

Runs on Python 3.10+ stdlib and SQLite FTS5 with zero external runtime dependencies.

## Why build this?

Several RAG demos and static trackers exist around Blueprint (such as `BlueprintAI`, `agent-bryan`, `OpenLongevity`, and `nutrimetrics`), mostly built as standalone web chatbots over a single snapshot of the site.

This repo focuses on being a clean, citation-first MCP data source for tools like Claude Desktop, Cursor, or VS Code, with three goals:

1. **Tiered source priority:** Official `protocol.bryanjohnson.com` rules take precedence over older podcast clips or exploratory experiments.
2. **Tracking what changed or stopped:** Explicit entries for things Bryan dropped or avoids (like stopping rapamycin in Sept 2024, stopping HGH after 100 days, skipping cold plunges, avoiding caffeinated coffee, and his nuanced take on cold-pressed vs. high-heat seed oils).
3. **Timestamped primary citations:** Every video and podcast match includes a `?t=...s` YouTube link to the exact moment he said it.

## Dataset

Everything is pre-indexed in `data/bryan_protocol.db` (**266 documents**, **11,870 timestamped segments**, **25 structured stances**):

| Tier | Source Type | Count | Notes |
| --- | --- | ---: | --- |
| Tier 1 | `official_protocol` | 29 | Pages from `protocol.bryanjohnson.com` (Daily Routine, Sleep, Nutrition, Exercise, Rx, Skin, Hair, Oral Care, HBOT, Sauna, Clean Water, Biomarkers, etc.) |
| Tier 2 | `official_article` | 69 | Articles from `blueprint.bryanjohnson.com/blogs/news` |
| Tier 2 | `official_video` & `official_stream` | 148 | 139 videos and 9 livestreams from `@BryanJohnson` on YouTube |
| Tier 3 | `external_podcast` | 20 | Full-length appearances (Modern Wisdom, Rich Roll, Theo Von #644, Diary of a CEO x2, Lex Fridman #186, Impact Theory x3, FULL SEND, Jubilee, Doctor Mike, FLAGRANT, IMPAULSIVE, Jay Shetty, Mark Hyman, The Knowledge Project, Tim Ferriss, Piers Morgan, Axios) |
| Stances | `stances.json` | 25 | Active, stopped, avoided, conditional, and experimental positions with dates and links |

## Quick Start

### Run locally from the CLI

```bash
git clone https://github.com/MihailoPesic/bryan-protocol-mcp.git
cd bryan-protocol-mcp

PYTHONPATH=src python3 -m bryan_protocol_mcp stats
PYTHONPATH=src python3 -m bryan_protocol_mcp query "Does Bryan still take rapamycin?"
PYTHONPATH=src python3 -m bryan_protocol_mcp query "Should I cold plunge or drink coffee?"
```

### Use with an MCP client (Claude Desktop, Cursor, VS Code)

Add the server to your MCP config (see `mcp_config_examples.json`):

```json
{
  "mcpServers": {
    "bryan-protocol": {
      "command": "python3",
      "args": ["-m", "bryan_protocol_mcp", "serve"],
      "env": {
        "PYTHONPATH": "/path/to/bryan-protocol-mcp/src"
      }
    }
  }
}
```

Or install in editable mode so `bryan-protocol-mcp` is on your `PATH`:

```bash
pip install -e .
bryan-protocol-mcp serve
```

### Optional HTTP JSON-RPC server (Python)

```bash
PYTHONPATH=src python3 -m bryan_protocol_mcp serve --transport http --host 127.0.0.1 --port 8000
```

## Public Web UI & Hosted Streamable HTTP MCP (Netlify)

In addition to the local Python stdio server, this repo includes a zero-API-key web frontend (`public/`) and serverless Streamable HTTP MCP endpoint (`netlify/functions/mcp.mts`) ready to deploy on Netlify:

- `GET /`: Interactive "What Would Bryan Do?" search, shareable `?q=...` verdict links, "Stopped & Avoided" matrix, timestamped video/podcast jump links, and one-click quote/receipt copy buttons.
- `POST /mcp`: Public Streamable HTTP MCP server built on `@modelcontextprotocol/sdk` (`WebStandardStreamableHTTPServerTransport`), backed by a compressed 2.1 MB archive bundle (`netlify/functions/data/archive.json.gz`).
- `GET /api/query`, `/api/stances`, `/api/overview`, `/api/document`, `/api/sources`: JSON endpoints powering the web UI.

Deploy straight to Netlify by linking the GitHub repository (build command `python3 scripts/build_web_bundle.py`, publish directory `public`).

## Available MCP Tools & Resources

**Tools**
- `what_would_bryan_do`: Pulls matching stances (`active`, `stopped`, `avoid`), Tier 1 official protocol pages, Tier 2 articles/videos, and Tier 3 podcast quotes with timestamps.
- `check_stance_and_changes`: Checks whether Bryan uses, stopped, or avoids a specific compound, food, or habit along with chronological mentions.
- `get_official_protocol`: Searches Tier 1 `protocol.bryanjohnson.com` sections directly.
- `search_archive`: Full-text BM25 search across documents and transcript segments (filterable by `tier` and `source_type`).
- `get_document`: Retrieves full text and optional timestamped segments for any document ID.
- `list_sources`: Paginated listing of indexed documents and podcasts.
- `get_protocol_overview`: Returns database counts, build timestamp, and Tier 1 page index.

**Resources & Prompts**
- `bryan://protocol/index`: Official protocol index and counts.
- `bryan://protocol/stances`: Full JSON stance matrix.
- Prompt `evaluate_against_blueprint`: Evaluates a food, habit, or supplement against cited Blueprint sources.

## Updating the Archive

The scrapers run using Python's standard library (WordPress REST API, Shopify sitemap/JSON-LD, and YouTube Innertube endpoints):

```bash
# Refresh official pages, articles, @BryanJohnson videos, and external podcasts
PYTHONPATH=src python3 -m bryan_protocol_mcp ingest --all

# Rebuild SQLite FTS5 and the Netlify bundle after editing data/stances.json or data/external_podcasts.json
PYTHONPATH=src python3 -m bryan_protocol_mcp build-db
python3 scripts/build_web_bundle.py
```

To index additional YouTube interviews or podcast appearances, add their video IDs to `data/external_podcasts.json` and run `ingest --youtube`.

## Tests

```bash
python3 -m unittest discover -s tests -v
node --test tests/node_engine.test.mjs
```

## Disclaimer

Independent archive of Bryan Johnson's publicly shared Blueprint protocols, articles, videos, and interviews. Not affiliated with Bryan Johnson or Blueprint, and not medical advice.
