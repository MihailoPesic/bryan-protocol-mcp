import type { Config, Context } from "@netlify/functions";
import { getEngine } from "../lib/engine.ts";

export default async (req: Request, _context: Context) => {
  if (req.method !== "GET") {
    return Response.json({ error: "Method not allowed" }, { status: 405 });
  }

  const url = new URL(req.url);
  const path = url.pathname;
  const engine = getEngine();

  if (path.endsWith("/overview")) {
    return Response.json(engine.getProtocolOverview(), {
      headers: { "Cache-Control": "public, max-age=300" },
    });
  }

  if (path.endsWith("/stances")) {
    return Response.json({ stances: engine.listAllStances() }, {
      headers: { "Cache-Control": "public, max-age=300" },
    });
  }

  if (path.endsWith("/document")) {
    const docId = url.searchParams.get("id") ?? "";
    const includeSegs = url.searchParams.get("segments") === "1";
    if (!docId) return Response.json({ error: "Missing id query parameter" }, { status: 400 });
    const doc = engine.getDocument(docId, includeSegs, 40000);
    if (!doc) return Response.json({ error: `Document not found: ${docId}` }, { status: 404 });
    return Response.json(doc, { headers: { "Cache-Control": "public, max-age=300" } });
  }

  if (path.endsWith("/sources")) {
    const tierRaw = url.searchParams.get("tier");
    const tier = tierRaw ? Number(tierRaw) : undefined;
    const sourceType = url.searchParams.get("source_type") || undefined;
    const limit = Math.min(200, Math.max(1, Number(url.searchParams.get("limit") ?? 50)));
    const offset = Math.max(0, Number(url.searchParams.get("offset") ?? 0));
    return Response.json(engine.listSources(tier, sourceType, limit, offset), {
      headers: { "Cache-Control": "public, max-age=300" },
    });
  }

  // Default: /api/query?q=...
  const q = (url.searchParams.get("q") ?? "").trim();
  if (!q) {
    return Response.json({ error: "Missing q parameter" }, { status: 400 });
  }
  return Response.json(engine.whatWouldBryanDo(q, true, 6), {
    headers: { "Cache-Control": "public, max-age=120" },
  });
};

export const config: Config = {
  path: ["/api/query", "/api/stances", "/api/overview", "/api/document", "/api/sources"],
  rateLimit: {
    windowSize: 60,
    windowLimit: 120,
    aggregateBy: ["ip", "domain"],
  },
};
