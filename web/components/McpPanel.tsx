import { Check, Copy } from "lucide-react";
import { useState } from "react";

function CopyBlock({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs font-medium text-[#57564F]">{label}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1 rounded border border-[#E6E4DD] bg-white px-2 py-0.5 font-mono text-[11px] text-[#3A3935] hover:border-[#C9C6BD]"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-700" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto rounded-md border border-[#E6E4DD] bg-white p-3 font-mono text-xs text-[#141413]">
        {value}
      </pre>
    </div>
  );
}

const TOOLS = [
  ["what_would_bryan_do", "Returns matching stances plus Tier 1 protocol, Tier 2 articles/videos, and Tier 3 podcast timestamps."],
  ["check_stance_and_changes", "Checks if Bryan currently takes, stopped, or avoids a specific item with chronological mentions."],
  ["get_official_protocol", "Looks up authoritative sections from protocol.bryanjohnson.com."],
  ["search_archive", "Full-text search across all documents and 11,870 timestamped transcript segments."],
  ["get_document", "Fetches full Markdown or transcript text for a document ID."],
  ["list_sources", "Paginated catalog of indexed protocol pages, articles, videos, and podcasts."],
  ["get_protocol_overview", "Archive counts, source tiers, and Tier 1 page index."],
];

export function McpPanel() {
  const origin = typeof window !== "undefined" ? window.location.origin : "https://bryan-protocol-mcp.netlify.app";
  const endpoint = `${origin}/mcp`;

  const cursorConfig = JSON.stringify(
    {
      mcpServers: {
        "bryan-protocol": {
          url: endpoint,
        },
      },
    },
    null,
    2,
  );

  return (
    <div className="space-y-8">
      <div className="border-b border-[#E6E4DD] pb-4">
        <h2 className="text-xl font-semibold tracking-tight text-[#141413]">
          Connect via Model Context Protocol (MCP)
        </h2>
        <p className="mt-1 text-sm text-[#57564F]">
          Read-only Streamable HTTP server backed by the same 266-source index. No API key required.
        </p>
      </div>

      <div className="space-y-4">
        <CopyBlock label="Streamable HTTP Endpoint" value={endpoint} />
        <CopyBlock
          label="Claude Code CLI"
          value={`claude mcp add --transport http bryan-protocol ${endpoint}`}
        />
        <CopyBlock label="Cursor / MCP Client JSON" value={cursorConfig} />
        <CopyBlock
          label="Local offline Python (SQLite + FTS5 via stdio)"
          value={`git clone https://github.com/MihailoPesic/bryan-protocol-mcp.git\ncd bryan-protocol-mcp\nPYTHONPATH=src python3 -m bryan_protocol_mcp serve`}
        />
      </div>

      <div>
        <h3 className="mb-3 font-mono text-xs font-medium uppercase tracking-wider text-[#6F6E69]">
          Exposed Tools
        </h3>
        <div className="overflow-hidden rounded-md border border-[#E6E4DD] bg-white">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-[#E6E4DD] bg-[#FAF9F6] font-mono text-[11px] uppercase text-[#6F6E69]">
                <th className="px-4 py-2.5 font-medium">Tool</th>
                <th className="px-4 py-2.5 font-medium">Behavior</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EFECE6]">
              {TOOLS.map(([name, desc]) => (
                <tr key={name}>
                  <td className="px-4 py-2.5 align-top font-mono text-xs font-medium text-[#141413]">
                    {name}
                  </td>
                  <td className="px-4 py-2.5 text-xs leading-relaxed text-[#4A4945]">{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
