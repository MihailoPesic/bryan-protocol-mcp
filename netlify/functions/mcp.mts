import type { Config, Context } from "@netlify/functions";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { z } from "zod";
import { getEngine } from "../lib/engine.ts";

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Mcp-Session-Id",
};

function withCors(res: Response): Response {
  const headers = new Headers(res.headers);
  for (const [k, v] of Object.entries(CORS_HEADERS)) headers.set(k, v);
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
}

const SOURCE_TYPES = z.enum([
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
]);

function buildServer(): McpServer {
  const engine = getEngine();
  const server = new McpServer({
    name: "bryan-protocol-mcp",
    version: "0.1.0",
  });

  server.tool(
    "get_protocol_overview",
    "Get database stats, source tiers, and the index of all official Tier 1 protocol.bryanjohnson.com sections.",
    {},
    async () => ({
      content: [{ type: "text", text: JSON.stringify(engine.getProtocolOverview(), null, 2) }],
    }),
  );

  server.tool(
    "get_official_protocol",
    "Look up authoritative Tier 1 sections from protocol.bryanjohnson.com for a given topic.",
    {
      topic: z.string().describe("Protocol topic or keyword (e.g. sleep, nutrition, exercise, skin, rx)"),
      include_full_content: z.boolean().default(true).describe("Include full Markdown text of top official matches"),
      limit: z.number().int().min(1).max(20).default(5),
    },
    async ({ topic, include_full_content, limit }) => ({
      content: [{ type: "text", text: JSON.stringify(engine.getOfficialProtocol(topic, include_full_content, limit), null, 2) }],
    }),
  );

  server.tool(
    "what_would_bryan_do",
    "Retrieve a tiered Ground Truth Dossier (explicit stances, Tier 1 protocol pages, Tier 2 Bryan videos/articles, Tier 3 podcast timestamped quotes) to answer what Bryan Johnson would or wouldn't do.",
    {
      question: z.string().describe("Scenario, habit, food, supplement, or question"),
      include_transcripts: z.boolean().default(true).describe("Include timestamped video and podcast quotes"),
      max_per_tier: z.number().int().min(1).max(15).default(5),
    },
    async ({ question, include_transcripts, max_per_tier }) => ({
      content: [{ type: "text", text: JSON.stringify(engine.whatWouldBryanDo(question, include_transcripts, max_per_tier), null, 2) }],
    }),
  );

  server.tool(
    "check_stance_and_changes",
    "Check whether Bryan actively uses/does something, stopped doing it, or avoids it, with rationale and chronological mentions.",
    {
      topic: z.string().describe("Supplement, food, habit, or therapy (e.g. rapamycin, coffee, cold plunge, seed oils)"),
    },
    async ({ topic }) => ({
      content: [{ type: "text", text: JSON.stringify(engine.checkStanceAndChanges(topic), null, 2) }],
    }),
  );

  server.tool(
    "search_archive",
    "Full-text search across all official protocol pages, Blueprint articles, @BryanJohnson videos/streams, and external podcast transcripts.",
    {
      query: z.string().describe("Search query"),
      tier: z.number().int().min(1).max(3).optional().describe("Optional tier filter (1=official protocol, 2=articles/videos, 3=podcasts)"),
      source_type: SOURCE_TYPES.optional(),
      limit: z.number().int().min(1).max(30).default(10),
    },
    async ({ query, tier, source_type, limit }) => ({
      content: [{ type: "text", text: JSON.stringify(engine.searchArchive(query, tier, source_type, limit), null, 2) }],
    }),
  );

  server.tool(
    "get_document",
    "Fetch full text and optional timestamped segments for a document ID returned by search or list_sources.",
    {
      doc_id: z.string().describe("Document ID (e.g. protocol:sleep, article:why-i-avoid-the-sun, yt:coU8aHzTvpk)"),
      include_segments: z.boolean().default(false),
      max_chars: z.number().int().min(500).max(100000).default(25000),
    },
    async ({ doc_id, include_segments, max_chars }) => {
      const doc = engine.getDocument(doc_id, include_segments, max_chars);
      if (!doc) {
        return {
          content: [{ type: "text", text: JSON.stringify({ error: `Document not found: ${doc_id}` }) }],
          isError: true,
        };
      }
      return { content: [{ type: "text", text: JSON.stringify(doc, null, 2) }] };
    },
  );

  server.tool(
    "list_sources",
    "List ingested pages, articles, videos, and podcasts with pagination and optional tier/source_type filters.",
    {
      tier: z.number().int().min(1).max(3).optional(),
      source_type: SOURCE_TYPES.optional(),
      limit: z.number().int().min(1).max(200).default(50),
      offset: z.number().int().min(0).default(0),
    },
    async ({ tier, source_type, limit, offset }) => ({
      content: [{ type: "text", text: JSON.stringify(engine.listSources(tier, source_type, limit, offset), null, 2) }],
    }),
  );

  return server;
}

export default async (req: Request, _context: Context) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }
  if (req.method !== "POST") {
    return withCors(
      Response.json(
        {
          error: "Method not allowed. Send Streamable HTTP MCP JSON-RPC POST requests to /mcp, or visit / for the web UI.",
        },
        { status: 405 },
      ),
    );
  }

  const server = buildServer();
  const transport = new WebStandardStreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
    enableJsonResponse: true,
  });

  await server.connect(transport);
  const response = await transport.handleRequest(req);
  return withCors(response);
};

export const config: Config = {
  path: "/mcp",
  rateLimit: {
    windowSize: 60,
    windowLimit: 100,
    aggregateBy: ["ip", "domain"],
  },
};
