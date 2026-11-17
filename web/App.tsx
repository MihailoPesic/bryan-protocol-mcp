import {
  Check,
  Copy,
  ExternalLink,
  FileText,
  Play,
  Search,
  Share2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { DocDrawer } from "./components/DocDrawer";
import { McpPanel } from "./components/McpPanel";
import { Sidebar } from "./components/Sidebar";
import { StatusBadge } from "./components/StatusBadge";
import type {
  DocumentDetail,
  OverviewResponse,
  QueryDossier,
  SourceItem,
  Stance,
} from "./types";

type ViewTab = "search" | "changelog" | "sources" | "mcp";

const FEATURED_LEDGER_IDS = [
  "stance:rapamycin",
  "stance:coffee-caffeine",
  "stance:cold-plunge",
  "stance:seed-oils-vs-evoo",
  "stance:testosterone-trt",
  "stance:hgh-thymus",
  "stance:plasma-exchange",
  "stance:psilocybin",
];

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export function App() {
  const [tab, setTab] = useState<ViewTab>("search");
  const [inputValue, setInputValue] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [dossier, setDossier] = useState<QueryDossier | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [stances, setStances] = useState<Stance[]>([]);
  const [stanceFilter, setStanceFilter] = useState("all");

  const [sources, setSources] = useState<SourceItem[]>([]);
  const [sourcesLoaded, setSourcesLoaded] = useState(false);
  const [sourceTierFilter, setSourceTierFilter] = useState("all");
  const [sourceSearch, setSourceSearch] = useState("");

  const [drawerDoc, setDrawerDoc] = useState<DocumentDetail | null>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  const copyText = async (key: string, value: string) => {
    await navigator.clipboard.writeText(value);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey((prev) => (prev === key ? null : prev)), 1500);
  };

  const openDocument = async (docId: string) => {
    setDrawerLoading(true);
    setDrawerDoc(null);
    try {
      const detail = await fetchJson<DocumentDetail>(
        `/api/document?id=${encodeURIComponent(docId)}`,
      );
      setDrawerDoc(detail);
    } finally {
      setDrawerLoading(false);
    }
  };

  const runSearch = async (rawQuery: string, pushHistory = true) => {
    const clean = rawQuery.trim();
    setTab("search");
    setInputValue(clean);
    setActiveQuery(clean);
    setSearchError(null);

    if (!clean) {
      setDossier(null);
      if (pushHistory) window.history.replaceState(null, "", window.location.pathname);
      return;
    }

    if (pushHistory) {
      window.history.replaceState(
        null,
        "",
        `${window.location.pathname}?q=${encodeURIComponent(clean)}`,
      );
    }

    setSearching(true);
    try {
      const data = await fetchJson<QueryDossier>(
        `/api/query?q=${encodeURIComponent(clean)}`,
      );
      setDossier(data);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Failed to query archive");
    } finally {
      setSearching(false);
    }
  };

  const loadSources = async () => {
    if (sourcesLoaded) return;
    const page1 = await fetchJson<{ total: number; items: SourceItem[] }>(
      "/api/sources?limit=200&offset=0",
    );
    let combined = page1.items;
    if (page1.total > combined.length) {
      const page2 = await fetchJson<{ total: number; items: SourceItem[] }>(
        `/api/sources?limit=200&offset=${combined.length}`,
      );
      combined = combined.concat(page2.items);
    }
    setSources(combined);
    setSourcesLoaded(true);
  };

  useEffect(() => {
    Promise.all([
      fetchJson<OverviewResponse>("/api/overview"),
      fetchJson<{ stances: Stance[] }>("/api/stances"),
    ])
      .then(([ov, st]) => {
        setOverview(ov);
        setStances(st.stances || []);
      })
      .catch(() => {});

    const urlQ = new URLSearchParams(window.location.search).get("q");
    if (urlQ) {
      void runSearch(urlQ, false);
    }
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.key === "/" &&
        document.activeElement !== inputRef.current &&
        !(document.activeElement instanceof HTMLInputElement)
      ) {
        e.preventDefault();
        inputRef.current?.focus();
      } else if (e.key === "Escape") {
        setDrawerDoc(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (tab === "sources" && !sourcesLoaded) {
      void loadSources();
    }
  }, [tab, sourcesLoaded]);

  const totalDocs = useMemo(
    () => (overview?.document_counts || []).reduce((acc, r) => acc + r.count, 0),
    [overview],
  );

  const featuredLedger = useMemo(() => {
    const map = new Map(stances.map((s) => [s.id, s]));
    return FEATURED_LEDGER_IDS.map((id) => map.get(id)).filter((s): s is Stance => Boolean(s));
  }, [stances]);

  const filteredStances = useMemo(() => {
    if (stanceFilter === "all") return stances;
    return stances.filter((s) => s.status === stanceFilter);
  }, [stances, stanceFilter]);

  const filteredSources = useMemo(() => {
    const q = sourceSearch.trim().toLowerCase();
    return sources.filter((s) => {
      if (sourceTierFilter !== "all" && String(s.tier) !== sourceTierFilter) return false;
      if (!q) return true;
      return (
        s.title.toLowerCase().includes(q) ||
        s.channel_or_site.toLowerCase().includes(q) ||
        s.source_type.toLowerCase().includes(q)
      );
    });
  }, [sources, sourceTierFilter, sourceSearch]);

  const allTranscriptQuotes = useMemo(() => {
    if (!dossier) return [];
    return [
      ...(dossier.tier2_official_articles_and_videos?.timestamped_quotes || []),
      ...(dossier.tier3_external_podcasts || []),
    ];
  }, [dossier]);

  return (
    <div className="min-h-screen bg-[#FAF9F6] text-[#141413]">
      {/* Minimal Header */}
      <header className="sticky top-0 z-30 border-b border-[#E6E4DD] bg-[#FAF9F6]/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => void runSearch("")}
              className="flex items-center gap-2.5 text-left"
            >
              <span className="flex h-7 w-7 items-center justify-center rounded bg-[#141413] font-mono text-[11px] font-semibold text-[#FAF9F6]">
                BP
              </span>
              <span className="text-sm font-semibold tracking-tight text-[#141413]">
                bryan.protocol
              </span>
            </button>
            <span className="hidden rounded border border-[#E6E4DD] bg-white px-1.5 py-0.5 font-mono text-[10px] text-[#6F6E69] sm:inline-block">
              {totalDocs || 266} sources · {(overview?.segment_count || 11870).toLocaleString()} timestamps
            </span>
          </div>

          <nav className="flex items-center gap-1 sm:gap-2">
            {(
              [
                ["search", "Search"],
                ["changelog", "Stopped & Avoided"],
                ["sources", `Sources (${totalDocs || 266})`],
                ["mcp", "MCP"],
              ] as Array<[ViewTab, string]>
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors sm:text-[13px] ${
                  tab === key
                    ? "bg-[#EFECE6] text-[#141413]"
                    : "text-[#57564F] hover:bg-[#F2F0EA] hover:text-[#141413]"
                }`}
              >
                {label}
              </button>
            ))}
            <a
              href="https://github.com/MihailoPesic/bryan-protocol-mcp"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden items-center gap-1 rounded-md px-2.5 py-1.5 text-[13px] font-medium text-[#57564F] hover:bg-[#F2F0EA] hover:text-[#141413] sm:inline-flex"
            >
              GitHub
              <ExternalLink className="h-3 w-3" />
            </a>
          </nav>
        </div>
      </header>

      {/* Main Split Workspace */}
      <div className="mx-auto flex max-w-6xl gap-10 px-4 py-8 sm:px-6">
        <Sidebar
          activeQuery={activeQuery}
          onSelectQuery={(q) => void runSearch(q)}
          onOpenMcp={() => setTab("mcp")}
        />

        <main className="min-w-0 flex-1 max-w-3xl">
          {tab === "search" && (
            <div className="space-y-6">
              {/* Compact Search Input */}
              <div>
                <h1 className="text-2xl font-semibold tracking-tight text-[#141413] sm:text-[28px]">
                  Bryan Johnson Protocol Index
                </h1>
                <p className="mt-1 text-sm text-[#57564F]">
                  Cross-references{" "}
                  <a
                    href="https://protocol.bryanjohnson.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline decoration-[#D2CFC6] underline-offset-2 hover:text-[#141413]"
                  >
                    protocol.bryanjohnson.com
                  </a>
                  , 69 Blueprint essays, and 166 captioned videos &amp; podcasts.
                </p>

                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void runSearch(inputValue);
                  }}
                  className="mt-4 flex gap-2"
                >
                  <div className="relative flex-1">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6F6E69]" />
                    <input
                      ref={inputRef}
                      type="text"
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      placeholder="Search any supplement, habit, or video quote (e.g. rapamycin, seed oils, coffee)..."
                      className="w-full rounded-md border border-[#D8D5CD] bg-white py-2.5 pl-9 pr-14 text-sm text-[#141413] placeholder:text-[#8E8C84] focus:border-[#141413] focus:outline-none"
                    />
                    {inputValue ? (
                      <button
                        type="button"
                        onClick={() => void runSearch("")}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-[#6F6E69] hover:bg-[#F2F0EA]"
                        aria-label="Clear search"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    ) : (
                      <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border border-[#E6E4DD] bg-[#FAF9F6] px-1.5 py-0.5 font-mono text-[10px] text-[#6F6E69] sm:inline-block">
                        /
                      </kbd>
                    )}
                  </div>
                  <button
                    type="submit"
                    className="shrink-0 rounded-md bg-[#141413] px-4 py-2.5 text-sm font-medium text-[#FAF9F6] hover:bg-[#2B2B28]"
                  >
                    Search
                  </button>
                </form>

                {/* Mobile quick pills */}
                <div className="mt-3 flex flex-wrap gap-1.5 lg:hidden">
                  {["rapamycin", "seed oils", "coffee", "cold plunge", "psilocybin", "sleep"].map(
                    (term) => (
                      <button
                        key={term}
                        type="button"
                        onClick={() => void runSearch(term)}
                        className="rounded border border-[#E6E4DD] bg-white px-2.5 py-1 text-xs text-[#4A4945] hover:border-[#141413]"
                      >
                        {term}
                      </button>
                    ),
                  )}
                </div>
              </div>

              {/* Loading / Error */}
              {searching && (
                <div className="rounded-md border border-[#E6E4DD] bg-white p-4 text-sm text-[#57564F]">
                  Querying 266 sources and 11,870 timestamps...
                </div>
              )}

              {searchError && (
                <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
                  {searchError}
                </div>
              )}

              {/* Landing Ledger when no active query */}
              {!searching && !dossier && (
                <div className="space-y-8">
                  <section>
                    <div className="mb-3 flex items-baseline justify-between">
                      <h2 className="font-mono text-xs font-medium uppercase tracking-wider text-[#6F6E69]">
                        Frequently Misquoted / Changed Positions
                      </h2>
                      <button
                        type="button"
                        onClick={() => setTab("changelog")}
                        className="text-xs font-medium text-[#1D4ED8] hover:underline"
                      >
                        View all {stances.length} entries →
                      </button>
                    </div>

                    <div className="overflow-hidden rounded-md border border-[#E6E4DD] bg-white">
                      <div className="divide-y divide-[#EFECE6]">
                        {featuredLedger.map((item) => (
                          <div
                            key={item.id}
                            className="flex flex-col gap-2 p-4 transition-colors hover:bg-[#FAF9F6] sm:flex-row sm:items-start sm:justify-between sm:gap-4"
                          >
                            <div className="min-w-0 flex-1 space-y-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => void runSearch(item.topic)}
                                  className="text-left text-sm font-semibold text-[#141413] hover:text-[#1D4ED8] hover:underline"
                                >
                                  {item.topic}
                                </button>
                                <StatusBadge status={item.status} />
                                <span className="font-mono text-[11px] text-[#6F6E69]">
                                  {item.changed_at}
                                </span>
                              </div>
                              <p className="text-[13px] leading-relaxed text-[#4A4945]">
                                {item.summary}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => void runSearch(item.topic)}
                              className="shrink-0 self-start rounded border border-[#E6E4DD] bg-[#FAF9F6] px-2.5 py-1 font-mono text-[11px] text-[#3A3935] hover:border-[#141413]"
                            >
                              Receipts
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </section>

                  {overview && overview.tier1_official_pages.length > 0 && (
                    <section>
                      <h2 className="mb-3 font-mono text-xs font-medium uppercase tracking-wider text-[#6F6E69]">
                        Official Sections (protocol.bryanjohnson.com)
                      </h2>
                      <div className="grid grid-cols-1 gap-px overflow-hidden rounded-md border border-[#E6E4DD] bg-[#E6E4DD] sm:grid-cols-2">
                        {overview.tier1_official_pages.map((page) => (
                          <button
                            key={page.id}
                            type="button"
                            onClick={() => void openDocument(page.id)}
                            className="flex items-center justify-between bg-white px-3.5 py-2.5 text-left hover:bg-[#FAF9F6]"
                          >
                            <span className="truncate text-[13px] font-medium text-[#141413]">
                              {page.title}
                            </span>
                            <span className="ml-2 shrink-0 font-mono text-[11px] text-[#8E8C84]">
                              {page.updated_at}
                            </span>
                          </button>
                        ))}
                      </div>
                    </section>
                  )}
                </div>
              )}

              {/* Search Results Dossier */}
              {!searching && dossier && (
                <div className="space-y-7">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E6E4DD] pb-3">
                    <div className="font-mono text-xs text-[#57564F]">
                      Results for <span className="font-semibold text-[#141413]">"{dossier.question}"</span>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        void copyText(
                          "share-url",
                          `${window.location.origin}/?q=${encodeURIComponent(dossier.question)}`,
                        )
                      }
                      className="inline-flex items-center gap-1.5 rounded border border-[#E6E4DD] bg-white px-2.5 py-1 text-xs font-medium text-[#3A3935] hover:border-[#141413]"
                    >
                      {copiedKey === "share-url" ? (
                        <Check className="h-3.5 w-3.5 text-emerald-700" />
                      ) : (
                        <Share2 className="h-3.5 w-3.5" />
                      )}
                      {copiedKey === "share-url" ? "Link copied" : "Share query link"}
                    </button>
                  </div>

                  {/* Stance Monographs */}
                  {dossier.explicit_stances.length > 0 && (
                    <section className="space-y-3">
                      <h2 className="font-mono text-xs font-medium uppercase tracking-wider text-[#6F6E69]">
                        Documented Position
                      </h2>
                      {dossier.explicit_stances.map((st) => (
                        <article
                          key={st.id}
                          className="rounded-md border border-[#D8D5CD] bg-white p-5"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-2.5">
                              <h3 className="text-base font-semibold text-[#141413]">
                                {st.topic}
                              </h3>
                              <StatusBadge status={st.status} />
                            </div>
                            <span className="font-mono text-xs text-[#6F6E69]">
                              {st.changed_at}
                            </span>
                          </div>
                          <p className="mt-2.5 text-sm leading-relaxed text-[#262624]">
                            {st.summary}
                          </p>
                          {st.dosage_or_rule && (
                            <div className="mt-3 rounded border border-[#EFECE6] bg-[#FAF9F6] px-3 py-2 text-xs text-[#3A3935]">
                              <span className="font-mono font-semibold text-[#141413]">
                                Protocol / Rule:{" "}
                              </span>
                              {st.dosage_or_rule}
                            </div>
                          )}
                          {st.rationale && (
                            <p className="mt-2.5 text-xs leading-relaxed text-[#57564F]">
                              {st.rationale}
                            </p>
                          )}
                          <div className="mt-3 flex flex-wrap items-center gap-2 pt-1">
                            {st.sources.map((src) => (
                              <a
                                key={src.url}
                                href={src.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 rounded border border-[#E6E4DD] bg-[#FAF9F6] px-2 py-1 font-mono text-[11px] text-[#1D4ED8] hover:border-[#1D4ED8]"
                              >
                                {src.title}
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            ))}
                            <button
                              type="button"
                              onClick={() =>
                                void copyText(
                                  st.id,
                                  `${st.topic} [${st.status.toUpperCase()}]: ${st.summary}${st.sources[0] ? ` (${st.sources[0].url})` : ""}`,
                                )
                              }
                              className="ml-auto inline-flex items-center gap-1 font-mono text-[11px] text-[#57564F] hover:text-[#141413]"
                            >
                              {copiedKey === st.id ? (
                                <Check className="h-3 w-3 text-emerald-700" />
                              ) : (
                                <Copy className="h-3 w-3" />
                              )}
                              {copiedKey === st.id ? "Copied" : "Copy summary"}
                            </button>
                          </div>
                        </article>
                      ))}
                    </section>
                  )}

                  {/* Official Protocol Pages */}
                  {dossier.tier1_official_protocol.length > 0 && (
                    <section className="space-y-2.5">
                      <h2 className="font-mono text-xs font-medium uppercase tracking-wider text-[#6F6E69]">
                        Official Protocol (protocol.bryanjohnson.com)
                      </h2>
                      <div className="divide-y divide-[#EFECE6] overflow-hidden rounded-md border border-[#E6E4DD] bg-white">
                        {dossier.tier1_official_protocol.map((doc) => (
                          <div key={doc.doc_id} className="p-4">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="text-sm font-semibold text-[#141413]">
                                {doc.title}
                              </span>
                              <span className="font-mono text-[11px] text-[#6F6E69]">
                                Updated {doc.updated_at || "n/a"}
                              </span>
                            </div>
                            <p className="mt-1.5 text-[13px] leading-relaxed text-[#4A4945]">
                              {doc.excerpt}
                            </p>
                            <div className="mt-2.5 flex items-center gap-3 text-xs">
                              <button
                                type="button"
                                onClick={() => void openDocument(doc.doc_id)}
                                className="inline-flex items-center gap-1 font-medium text-[#141413] hover:underline"
                              >
                                <FileText className="h-3.5 w-3.5" />
                                Read full section
                              </button>
                              <a
                                href={doc.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 font-mono text-[11px] text-[#1D4ED8] hover:underline"
                              >
                                protocol.bryanjohnson.com
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}

                  {/* Blueprint Articles & Official Videos */}
                  {dossier.tier2_official_articles_and_videos.documents.length > 0 && (
                    <section className="space-y-2.5">
                      <h2 className="font-mono text-xs font-medium uppercase tracking-wider text-[#6F6E69]">
                        Articles &amp; @BryanJohnson Videos
                      </h2>
                      <div className="divide-y divide-[#EFECE6] overflow-hidden rounded-md border border-[#E6E4DD] bg-white">
                        {dossier.tier2_official_articles_and_videos.documents.map((doc) => (
                          <div key={doc.doc_id} className="p-4">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="text-sm font-medium text-[#141413]">
                                {doc.title}
                              </span>
                              <span className="font-mono text-[11px] text-[#6F6E69]">
                                {doc.channel_or_site} · {doc.published_at || "n/a"}
                              </span>
                            </div>
                            <p className="mt-1.5 text-[13px] leading-relaxed text-[#4A4945]">
                              {doc.excerpt}
                            </p>
                            <div className="mt-2.5 flex items-center gap-3 text-xs">
                              <button
                                type="button"
                                onClick={() => void openDocument(doc.doc_id)}
                                className="inline-flex items-center gap-1 font-medium text-[#141413] hover:underline"
                              >
                                <FileText className="h-3.5 w-3.5" />
                                Read text
                              </button>
                              <a
                                href={doc.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 font-mono text-[11px] text-[#1D4ED8] hover:underline"
                              >
                                Open original
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}

                  {/* Timestamped Quotes */}
                  {allTranscriptQuotes.length > 0 && (
                    <section className="space-y-2.5">
                      <h2 className="font-mono text-xs font-medium uppercase tracking-wider text-[#6F6E69]">
                        Timestamped Video &amp; Podcast Quotes
                      </h2>
                      <div className="divide-y divide-[#EFECE6] overflow-hidden rounded-md border border-[#E6E4DD] bg-white">
                        {allTranscriptQuotes.map((q) => {
                          const key = `${q.doc_id}:${q.start_sec}`;
                          const quotePayload = `"${q.text}" - Bryan Johnson (${q.channel}, ${q.published_at}) ${q.deep_link}`;
                          return (
                            <div key={key} className="p-4">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="text-xs font-medium text-[#57564F]">
                                  {q.channel} · {q.title}
                                </span>
                                <span className="font-mono text-[11px] text-[#6F6E69]">
                                  {q.published_at}
                                </span>
                              </div>
                              <blockquote className="mt-2 border-l-2 border-[#D8D5CD] pl-3 text-[13px] leading-relaxed text-[#141413]">
                                "{q.text}"
                              </blockquote>
                              <div className="mt-2.5 flex flex-wrap items-center gap-3 text-xs">
                                <a
                                  href={q.deep_link}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 rounded bg-[#141413] px-2 py-0.5 font-mono text-[11px] text-[#FAF9F6] hover:bg-[#2B2B28]"
                                >
                                  <Play className="h-2.5 w-2.5 fill-current" />
                                  {q.timestamp}
                                </a>
                                <button
                                  type="button"
                                  onClick={() => void openDocument(q.doc_id)}
                                  className="font-medium text-[#4A4945] hover:text-[#141413] hover:underline"
                                >
                                  Full transcript
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void copyText(key, quotePayload)}
                                  className="ml-auto inline-flex items-center gap-1 font-mono text-[11px] text-[#57564F] hover:text-[#141413]"
                                >
                                  {copiedKey === key ? (
                                    <Check className="h-3 w-3 text-emerald-700" />
                                  ) : (
                                    <Copy className="h-3 w-3" />
                                  )}
                                  {copiedKey === key ? "Copied" : "Copy quote"}
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </section>
                  )}

                  {dossier.explicit_stances.length === 0 &&
                    dossier.tier1_official_protocol.length === 0 &&
                    dossier.tier2_official_articles_and_videos.documents.length === 0 &&
                    allTranscriptQuotes.length === 0 && (
                      <div className="rounded-md border border-[#E6E4DD] bg-white p-6 text-sm text-[#57564F]">
                        No direct matches found for "{dossier.question}". Try keywords like{" "}
                        <button
                          type="button"
                          onClick={() => void runSearch("olive oil")}
                          className="underline"
                        >
                          olive oil
                        </button>
                        ,{" "}
                        <button
                          type="button"
                          onClick={() => void runSearch("metformin")}
                          className="underline"
                        >
                          metformin
                        </button>
                        , or{" "}
                        <button
                          type="button"
                          onClick={() => void runSearch("sauna")}
                          className="underline"
                        >
                          sauna
                        </button>
                        .
                      </div>
                    )}
                </div>
              )}
            </div>
          )}

          {/* Changelog / Stopped & Avoided Ledger */}
          {tab === "changelog" && (
            <div className="space-y-5">
              <div className="border-b border-[#E6E4DD] pb-4">
                <h1 className="text-2xl font-semibold tracking-tight text-[#141413]">
                  Protocol Changelog &amp; Avoided List
                </h1>
                <p className="mt-1 text-sm text-[#57564F]">
                  Every documented compound, therapy, and habit Bryan actively follows, changed, stopped, or avoids.
                </p>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {(
                  [
                    ["all", `All (${stances.length})`],
                    ["stopped", "Stopped"],
                    ["avoid", "Avoids"],
                    ["conditional", "Nuanced"],
                    ["experimental", "Experimental"],
                    ["active", "Active"],
                  ] as const
                ).map(([status, label]) => (
                  <button
                    key={status}
                    type="button"
                    onClick={() => setStanceFilter(status)}
                    className={`rounded border px-3 py-1 text-xs font-medium ${
                      stanceFilter === status
                        ? "border-[#141413] bg-[#141413] text-[#FAF9F6]"
                        : "border-[#E6E4DD] bg-white text-[#4A4945] hover:border-[#C9C6BD]"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <div className="divide-y divide-[#EFECE6] overflow-hidden rounded-md border border-[#E6E4DD] bg-white">
                {filteredStances.map((st) => (
                  <div key={st.id} className="p-4 sm:p-5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold text-[#141413] sm:text-base">
                          {st.topic}
                        </h3>
                        <StatusBadge status={st.status} />
                      </div>
                      <span className="font-mono text-xs text-[#6F6E69]">{st.changed_at}</span>
                    </div>
                    <p className="mt-2 text-sm text-[#262624]">{st.summary}</p>
                    {st.dosage_or_rule && (
                      <p className="mt-1.5 text-xs text-[#57564F]">
                        <span className="font-mono font-medium text-[#141413]">Rule:</span>{" "}
                        {st.dosage_or_rule}
                      </p>
                    )}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {st.sources.map((src) => (
                        <a
                          key={src.url}
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 font-mono text-[11px] text-[#1D4ED8] hover:underline"
                        >
                          {src.title}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sources Table */}
          {tab === "sources" && (
            <div className="space-y-4">
              <div className="border-b border-[#E6E4DD] pb-4">
                <h1 className="text-2xl font-semibold tracking-tight text-[#141413]">
                  Indexed Sources ({sources.length || totalDocs || 266})
                </h1>
                <p className="mt-1 text-sm text-[#57564F]">
                  Click any row to read the extracted Markdown or timestamped transcript.
                </p>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-wrap gap-1.5">
                  {(
                    [
                      ["all", "All Tiers"],
                      ["1", "Tier 1 · Official Protocol"],
                      ["2", "Tier 2 · Articles & YouTube"],
                      ["3", "Tier 3 · Podcasts"],
                    ] as const
                  ).map(([tier, label]) => (
                    <button
                      key={tier}
                      type="button"
                      onClick={() => setSourceTierFilter(tier)}
                      className={`rounded border px-2.5 py-1 text-xs font-medium ${
                        sourceTierFilter === tier
                          ? "border-[#141413] bg-[#141413] text-[#FAF9F6]"
                          : "border-[#E6E4DD] bg-white text-[#4A4945] hover:border-[#C9C6BD]"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <input
                  type="search"
                  value={sourceSearch}
                  onChange={(e) => setSourceSearch(e.target.value)}
                  placeholder="Filter titles or channels..."
                  className="rounded border border-[#D8D5CD] bg-white px-3 py-1.5 text-xs text-[#141413] placeholder:text-[#8E8C84] focus:border-[#141413] focus:outline-none sm:w-56"
                />
              </div>

              <div className="overflow-x-auto rounded-md border border-[#E6E4DD] bg-white">
                <table className="w-full border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b border-[#E6E4DD] bg-[#FAF9F6] font-mono text-[11px] uppercase text-[#6F6E69]">
                      <th className="px-3.5 py-2.5 font-medium">Title</th>
                      <th className="px-3.5 py-2.5 font-medium">Source</th>
                      <th className="px-3.5 py-2.5 font-medium">Date</th>
                      <th className="px-3.5 py-2.5 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#EFECE6]">
                    {filteredSources.map((src) => (
                      <tr key={src.id} className="hover:bg-[#FAF9F6]">
                        <td className="px-3.5 py-2.5 font-medium text-[#141413]">
                          <button
                            type="button"
                            onClick={() => void openDocument(src.id)}
                            className="text-left hover:text-[#1D4ED8] hover:underline"
                          >
                            {src.title}
                          </button>
                        </td>
                        <td className="px-3.5 py-2.5 font-mono text-[11px] text-[#57564F]">
                          T{src.tier} · {src.channel_or_site}
                        </td>
                        <td className="whitespace-nowrap px-3.5 py-2.5 font-mono text-[11px] text-[#6F6E69]">
                          {src.published_at || src.updated_at || "-"}
                        </td>
                        <td className="whitespace-nowrap px-3.5 py-2.5 text-right">
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 font-mono text-[11px] text-[#1D4ED8] hover:underline"
                          >
                            Link
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* MCP Docs View */}
          {tab === "mcp" && <McpPanel />}
        </main>
      </div>

      <footer className="mx-auto max-w-6xl border-t border-[#E6E4DD] px-4 py-6 text-xs text-[#6F6E69] sm:px-6">
        Independent archive of Bryan Johnson's public Blueprint protocols, articles, videos, and
        interviews. Not affiliated with Blueprint or Bryan Johnson, and not medical advice.
      </footer>

      <DocDrawer
        doc={drawerDoc}
        loading={drawerLoading}
        onClose={() => {
          setDrawerDoc(null);
          setDrawerLoading(false);
        }}
      />
    </div>
  );
}
