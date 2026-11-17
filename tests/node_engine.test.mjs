import assert from "node:assert/strict";
import test from "node:test";
import mcpHandler from "../netlify/functions/mcp.mts";
import apiHandler from "../netlify/functions/api.mts";

const dummyCtx = {};

test("API handler serves overview, stances, query, and document", async () => {
  const ovRes = await apiHandler(new Request("https://example.test/api/overview"), dummyCtx);
  assert.equal(ovRes.status, 200);
  const ov = await ovRes.json();
  assert.ok(ov.segment_count >= 13000);

  const stRes = await apiHandler(new Request("https://example.test/api/stances"), dummyCtx);
  assert.equal(stRes.status, 200);
  const st = await stRes.json();
  assert.ok(st.stances.length >= 35);

  const ktRes = await apiHandler(new Request("https://example.test/api/query?q=kate+tolo"), dummyCtx);
  assert.equal(ktRes.status, 200);
  const kt = await ktRes.json();
  assert.equal(kt.explicit_stances[0].id, "stance:kate-tolo-female-protocol");

  const qRes = await apiHandler(new Request("https://example.test/api/query?q=seed+oils"), dummyCtx);
  assert.equal(qRes.status, 200);
  const q = await qRes.json();
  assert.equal(q.explicit_stances[0].id, "stance:seed-oils-vs-evoo");
  assert.ok(q.tier3_external_podcasts.some((seg) => seg.deep_link.includes("l8IHPKv7OCw")));

  const docRes = await apiHandler(new Request("https://example.test/api/document?id=protocol:sleep"), dummyCtx);
  assert.equal(docRes.status, 200);
  const doc = await docRes.json();
  assert.equal(doc.tier, 1);
  assert.ok(doc.content.includes("8:30"));
});

test("MCP Streamable HTTP handler handles CORS, 405, initialize, tools/list, and tools/call", async () => {
  const optRes = await mcpHandler(new Request("https://example.test/mcp", { method: "OPTIONS" }), dummyCtx);
  assert.equal(optRes.status, 204);
  assert.equal(optRes.headers.get("access-control-allow-origin"), "*");

  const getRes = await mcpHandler(new Request("https://example.test/mcp", { method: "GET" }), dummyCtx);
  assert.equal(getRes.status, 405);

  const initRes = await mcpHandler(
    new Request("https://example.test/mcp", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocolVersion: "2025-03-26",
          capabilities: {},
          clientInfo: { name: "test", version: "1.0.0" },
        },
      }),
    }),
    dummyCtx,
  );
  assert.equal(initRes.status, 200);
  const initJson = await initRes.json();
  assert.equal(initJson.result.serverInfo.name, "bryan-protocol-mcp");

  const listRes = await mcpHandler(
    new Request("https://example.test/mcp", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
      },
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list" }),
    }),
    dummyCtx,
  );
  assert.equal(listRes.status, 200);
  const listJson = await listRes.json();
  assert.equal(listJson.result.tools.length, 7);

  const callRes = await mcpHandler(
    new Request("https://example.test/mcp", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 3,
        method: "tools/call",
        params: {
          name: "what_would_bryan_do",
          arguments: { question: "Does Bryan still take rapamycin?" },
        },
      }),
    }),
    dummyCtx,
  );
  assert.equal(callRes.status, 200);
  const callJson = await callRes.json();
  const payload = JSON.parse(callJson.result.content[0].text);
  assert.equal(payload.explicit_stances[0].status, "stopped");
});
