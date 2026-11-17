"""Model Context Protocol (MCP) JSON-RPC 2.0 server over stdio and optional HTTP."""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from bryan_protocol_mcp import __version__
from bryan_protocol_mcp.db import DEFAULT_DB_PATH, ProtocolDatabase

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

SERVER_INSTRUCTIONS = (
    "You are querying the Bryan Johnson / Blueprint Ground Truth Archive. "
    "Always prioritize Tier 1 (protocol.bryanjohnson.com) and explicit `stopped` or `avoid` stances "
    "over older videos or external interviews. Always cite exact URLs, dates, and video timestamps."
)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_protocol_overview",
        "description": "Get database stats, source tiers, last-ingested metadata, and the index of all official Tier 1 protocol.bryanjohnson.com sections.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_official_protocol",
        "description": "Look up authoritative Tier 1 sections from protocol.bryanjohnson.com for a given topic (e.g. sleep, nutrition, exercise, skin, oral care, hair, biomarkers, rx).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Protocol topic or keyword to look up."},
                "include_full_content": {"type": "boolean", "default": True, "description": "Include full Markdown text of top official matches."},
                "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "what_would_bryan_do",
        "description": "Retrieve a tiered Ground Truth Dossier (explicit stances, Tier 1 protocol pages, Tier 2 Bryan videos/articles, Tier 3 external podcast timestamped quotes) to answer what Bryan Johnson would or wouldn't do in a scenario.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Scenario, habit, food, supplement, or question (e.g. 'Should I drink coffee after noon?', 'Does Bryan take rapamycin?')."},
                "include_transcripts": {"type": "boolean", "default": True, "description": "Include timestamped video and podcast quotes."},
                "max_per_tier": {"type": "integer", "default": 5, "minimum": 1, "maximum": 15},
            },
            "required": ["question"],
        },
    },
    {
        "name": "check_stance_and_changes",
        "description": "Check whether Bryan actively uses/does something, stopped doing it, or strictly avoids it, including rationale and chronological mentions across videos and articles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Supplement, food, habit, or therapy (e.g. 'rapamycin', 'alcohol', 'sunscreen', 'metformin')."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "search_archive",
        "description": "Full-text BM25 search across all official protocol pages, Blueprint blog articles, @BryanJohnson videos/streams, and external podcast transcripts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "tier": {"type": "integer", "enum": [1, 2, 3], "description": "Optional tier filter (1=official protocol, 2=official articles/videos, 3=external podcasts)."},
                "source_type": {
                    "type": "string",
                    "enum": [
                        "official_protocol",
                        "official_article",
                        "official_video",
                        "official_stream",
                        "official_short",
                        "historical_protocol",
                        "bryanjohnson_essay",
                        "blueprint_product",
                        "kate_tolo_profile",
                        "kate_tolo_video",
                        "kate_tolo_short",
                        "external_podcast",
                    ],
                    "description": "Optional source type filter.",
                },
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 30},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_document",
        "description": "Fetch the full text (and optionally timestamped segments) of any document ID returned by search or list_sources.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "Document ID (e.g. 'protocol:sleep', 'article:why-i-avoid-the-sun', 'yt:coU8aHzTvpk')."},
                "include_segments": {"type": "boolean", "default": False, "description": "Include individual timestamped video/podcast segments."},
                "max_chars": {"type": "integer", "default": 25000, "minimum": 500, "maximum": 100000},
            },
            "required": ["doc_id"],
        },
    },
    {
        "name": "list_sources",
        "description": "List ingested documents, articles, videos, and podcasts with pagination and optional tier/source_type filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tier": {"type": "integer", "enum": [1, 2, 3]},
                "source_type": {
                    "type": "string",
                    "enum": [
                        "official_protocol",
                        "official_article",
                        "official_video",
                        "official_stream",
                        "official_short",
                        "historical_protocol",
                        "bryanjohnson_essay",
                        "blueprint_product",
                        "kate_tolo_profile",
                        "kate_tolo_video",
                        "kate_tolo_short",
                        "external_podcast",
                    ],
                },
                "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 200},
                "offset": {"type": "integer", "default": 0, "minimum": 0},
            },
        },
    },
]

RESOURCES: list[dict[str, Any]] = [
    {
        "uri": "bryan://protocol/index",
        "name": "Official Protocol Index",
        "description": "Index of all Tier 1 protocol.bryanjohnson.com pages and archive statistics.",
        "mimeType": "application/json",
    },
    {
        "uri": "bryan://protocol/stances",
        "name": "Bryan Stances & Anti-Protocol Matrix",
        "description": "Structured ground-truth stances (active, stopped, avoid, experimental) with citations.",
        "mimeType": "application/json",
    },
]

PROMPTS: list[dict[str, Any]] = [
    {
        "name": "evaluate_against_blueprint",
        "description": "Evaluate a food, supplement, habit, or daily routine strictly against Bryan Johnson's documented Blueprint Protocol.",
        "arguments": [
            {"name": "subject", "description": "The food, supplement, or habit to evaluate.", "required": True}
        ],
    }
]


class BryanProtocolMCPServer:
    """Stateless JSON-RPC 2.0 MCP request router backed by ProtocolDatabase."""

    def __init__(self, db: ProtocolDatabase) -> None:
        self.db = db

    def handle_message(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        """Process a single JSON-RPC 2.0 message and return a response dict (or None for notifications)."""
        msg_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}

        # Notifications have no id and expect no response
        if msg_id is None:
            return None

        try:
            result = self._dispatch(method, params)
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except KeyError as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": f"Missing parameter: {exc}"},
            }
        except ValueError as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": str(exc)},
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": f"Internal error: {exc}"},
            }

    def _dispatch(self, method: str | None, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            req_ver = params.get("protocolVersion", "2025-03-26")
            proto = req_ver if req_ver in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
            return {
                "protocolVersion": proto,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "bryan-protocol-mcp",
                    "title": "Bryan Johnson Blueprint Ground Truth MCP",
                    "version": __version__,
                },
                "instructions": SERVER_INSTRUCTIONS,
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": TOOLS}
        if method == "tools/call":
            return self._call_tool(params["name"], params.get("arguments") or {})
        if method == "resources/list":
            return {"resources": RESOURCES}
        if method == "resources/read":
            return self._read_resource(params["uri"])
        if method == "prompts/list":
            return {"prompts": PROMPTS}
        if method == "prompts/get":
            return self._get_prompt(params["name"], params.get("arguments") or {})
        raise ValueError(f"Method not found: {method}")

    def _call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "get_protocol_overview":
                payload = self.db.get_protocol_overview()
            elif name == "get_official_protocol":
                payload = self.db.get_official_protocol(
                    topic=str(args["topic"]),
                    include_full_content=bool(args.get("include_full_content", True)),
                    limit=int(args.get("limit", 5)),
                )
            elif name == "what_would_bryan_do":
                payload = self.db.what_would_bryan_do(
                    question=str(args["question"]),
                    include_transcripts=bool(args.get("include_transcripts", True)),
                    max_per_tier=int(args.get("max_per_tier", 5)),
                )
            elif name == "check_stance_and_changes":
                payload = self.db.check_stance_and_changes(topic=str(args["topic"]))
            elif name == "search_archive":
                payload = self.db.search_archive(
                    query=str(args["query"]),
                    tier=int(args["tier"]) if args.get("tier") is not None else None,
                    source_type=str(args["source_type"]) if args.get("source_type") else None,
                    limit=int(args.get("limit", 10)),
                )
            elif name == "get_document":
                doc = self.db.get_document(
                    doc_id=str(args["doc_id"]),
                    include_segments=bool(args.get("include_segments", False)),
                    max_chars=int(args.get("max_chars", 25000)),
                )
                if doc is None:
                    return {
                        "content": [{"type": "text", "text": json.dumps({"error": f"Document not found: {args['doc_id']}"})}],
                        "isError": True,
                    }
                payload = doc
            elif name == "list_sources":
                payload = self.db.list_sources(
                    tier=int(args["tier"]) if args.get("tier") is not None else None,
                    source_type=str(args["source_type"]) if args.get("source_type") else None,
                    limit=int(args.get("limit", 50)),
                    offset=int(args.get("offset", 0)),
                )
            else:
                return {
                    "content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {name}"})}],
                    "isError": True,
                }
            return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}]}
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                "isError": True,
            }

    def _read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "bryan://protocol/index":
            text = json.dumps(self.db.get_protocol_overview(), indent=2, ensure_ascii=False)
        elif uri == "bryan://protocol/stances":
            text = json.dumps(self.db.list_all_stances(), indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unknown resource URI: {uri}")
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": text}]}

    def _get_prompt(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name != "evaluate_against_blueprint":
            raise ValueError(f"Unknown prompt: {name}")
        subject = str(args.get("subject", "")).strip() or "this habit/supplement"
        return {
            "description": "Evaluate a topic strictly against Bryan Johnson's Blueprint Protocol.",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Use `what_would_bryan_do` and `check_stance_and_changes` for '{subject}'. "
                            "Separate Tier 1 official protocol.bryanjohnson.com rules from historical changes or podcast remarks, "
                            "explicitly note if Bryan stopped or avoids it, and cite every URL, date, and video timestamp."
                        ),
                    },
                }
            ],
        }


def run_stdio_server(db_path: str | None = None) -> None:
    """Run the MCP server reading JSON-RPC lines from stdin and writing to stdout."""
    db = ProtocolDatabase(db_path or DEFAULT_DB_PATH)
    server = BryanProtocolMCPServer(db)
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer

    while True:
        raw_line = stdin.readline()
        if not raw_line:
            break
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}}
            stdout.write((json.dumps(err) + "\n").encode("utf-8"))
            stdout.flush()
            continue

        resp = server.handle_message(msg)
        if resp is not None:
            stdout.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
            stdout.flush()


def run_http_server(host: str = "127.0.0.1", port: int = 8000, db_path: str | None = None) -> None:
    """Run an HTTP JSON-RPC endpoint (`POST /mcp`, `GET /health`) for remote or local clients."""
    db = ProtocolDatabase(db_path or DEFAULT_DB_PATH)
    mcp = BryanProtocolMCPServer(db)

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            sys.stderr.write(f"[http] {format % args}\n")

        def _send_json(self, status: int, body: Any) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json(200, {"status": "ok", "overview": db.get_protocol_overview()})
            else:
                self._send_json(404, {"error": "Not found. POST JSON-RPC 2.0 payloads to /mcp or GET /health."})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/mcp":
                self._send_json(404, {"error": "POST JSON-RPC 2.0 payloads to /mcp"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as exc:
                self._send_json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}})
                return
            resp = mcp.handle_message(msg)
            if resp is None:
                self.send_response(202)
                self.end_headers()
                return
            self._send_json(200, resp)

    httpd = ThreadingHTTPServer((host, port), _Handler)
    sys.stderr.write(f"bryan-protocol-mcp HTTP server listening on http://{host}:{port}/mcp\n")
    httpd.serve_forever()
