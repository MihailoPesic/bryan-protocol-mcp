import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

export interface ArchiveDoc {
  id: string;
  tier: number;
  source_type: string;
  title: string;
  url: string;
  channel: string;
  published_at: string;
  updated_at: string;
  duration_sec: number;
  content: string;
}

export interface ArchiveStance {
  id: string;
  topic: string;
  category: string;
  status: string;
  summary: string;
  dosage_or_rule: string;
  rationale: string;
  changed_at: string;
  sources: Array<{ title: string; url: string }>;
}

interface RawBundle {
  docs: ArchiveDoc[];
  segs: Array<[string, number, string]>;
  stances: ArchiveStance[];
}

interface IndexedSegment {
  doc_id: string;
  start_sec: number;
  text: string;
  lower: string;
  deep_link: string;
}

interface IndexedDoc extends ArchiveDoc {
  lowerTitle: string;
  lowerContent: string;
}

interface IndexedStance extends ArchiveStance {
  lowerBlob: string;
}

const STOPWORDS = new Set([
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
]);

export function formatTimestamp(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const hrs = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return hrs > 0 ? `${hrs}:${pad(mins)}:${pad(secs)}` : `${mins}:${pad(secs)}`;
}

export function extractTokens(raw: string): string[] {
  const all = (raw.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter((t) => t.length >= 2);
  const filtered = all.filter((t) => !STOPWORDS.has(t));
  const chosen = filtered.length > 0 ? filtered : all;
  return Array.from(new Set(chosen)).slice(0, 12);
}

function stripInlineHtmlTags(text: string): string {
  return text
    .replace(/<\/?(?:b|i|em|strong|u|s|br|p|span|font)[^>]*>/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function cleanMarkdownText(text: string): string {
  return stripInlineHtmlTags(text)
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_`~#>]+/g, " ")
    .replace(/\|/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function makeExcerpt(text: string, tokens: string[], maxLen = 400): string {
  const clean = cleanMarkdownText(text);
  if (clean.length <= maxLen) return clean;
  const lower = clean.toLowerCase();
  let bestPos = -1;
  for (const tok of tokens) {
    const pos = lower.indexOf(tok);
    if (pos !== -1 && (bestPos === -1 || pos < bestPos)) bestPos = pos;
  }
  if (bestPos <= Math.floor(maxLen / 3)) return `${clean.slice(0, maxLen).trimEnd()}...`;
  const start = Math.max(0, bestPos - Math.floor(maxLen / 3));
  const end = Math.min(clean.length, start + maxLen);
  return `${start > 0 ? "..." : ""}${clean.slice(start, end).trim()}${end < clean.length ? "..." : ""}`;
}

function countTermHits(haystack: string, tok: string): number {
  let count = 0;
  let pos = 0;
  while (true) {
    const idx = haystack.indexOf(tok, pos);
    if (idx === -1) break;
    count += 1;
    pos = idx + tok.length;
    if (count >= 12) break;
  }
  return count;
}

function scoreTokens(text: string, tokens: string[], weight = 1): number {
  let matched = 0;
  let hits = 0;
  for (const tok of tokens) {
    const c = countTermHits(text, tok);
    if (c > 0) {
      matched += 1;
      hits += c;
    }
  }
  if (matched === 0) return 0;
  return matched * 20 * weight + hits * 2 * weight;
}

function resolveBundlePath(): string {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const candidates = [
    path.resolve(process.cwd(), "netlify/functions/data/archive.json.gz"),
    path.resolve(here, "../functions/data/archive.json.gz"),
    path.resolve(here, "data/archive.json.gz"),
    path.resolve(process.cwd(), "data/archive.json.gz"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  throw new Error(`archive.json.gz not found. Checked: ${candidates.join(", ")}`);
}

class ProtocolEngine {
  readonly docs: IndexedDoc[];
  readonly docById: Map<string, IndexedDoc>;
  readonly segs: IndexedSegment[];
  readonly segsByDoc: Map<string, IndexedSegment[]>;
  readonly stances: IndexedStance[];

  constructor(bundle: RawBundle) {
    this.docById = new Map();
    this.docs = bundle.docs.map((d) => {
      const idx: IndexedDoc = {
        ...d,
        lowerTitle: d.title.toLowerCase(),
        lowerContent: d.content.toLowerCase(),
      };
      this.docById.set(idx.id, idx);
      return idx;
    });

    this.segsByDoc = new Map();
    this.segs = bundle.segs.map(([doc_id, start_sec, text]) => {
      const doc = this.docById.get(doc_id);
      const baseUrl = doc?.url ?? `https://www.youtube.com/watch?v=${doc_id.replace(/^yt:/, "")}`;
      const cleanText = stripInlineHtmlTags(text);
      const seg: IndexedSegment = {
        doc_id,
        start_sec,
        text: cleanText,
        lower: cleanText.toLowerCase(),
        deep_link: `${baseUrl}&t=${start_sec}s`,
      };
      let list = this.segsByDoc.get(doc_id);
      if (!list) {
        list = [];
        this.segsByDoc.set(doc_id, list);
      }
      list.push(seg);
      return seg;
    });

    this.stances = bundle.stances.map((s) => ({
      ...s,
      lowerBlob: [s.topic, s.category, s.status, s.summary, s.dosage_or_rule, s.rationale]
        .join(" ")
        .toLowerCase(),
    }));
  }

  getProtocolOverview() {
    const countsMap = new Map<string, { tier: number; source_type: string; count: number }>();
    for (const d of this.docs) {
      const key = `${d.tier}:${d.source_type}`;
      const prev = countsMap.get(key);
      if (prev) prev.count += 1;
      else countsMap.set(key, { tier: d.tier, source_type: d.source_type, count: 1 });
    }
    const stanceMap = new Map<string, number>();
    for (const s of this.stances) {
      stanceMap.set(s.status, (stanceMap.get(s.status) ?? 0) + 1);
    }
    return {
      document_counts: Array.from(countsMap.values()).sort((a, b) => a.tier - b.tier || a.source_type.localeCompare(b.source_type)),
      segment_count: this.segs.length,
      stance_counts: Array.from(stanceMap.entries()).map(([status, count]) => ({ status, count })),
      tier1_official_pages: this.docs
        .filter((d) => d.tier === 1)
        .map((d) => ({ id: d.id, title: d.title, url: d.url, updated_at: d.updated_at }))
        .sort((a, b) => a.title.localeCompare(b.title)),
      source_tier_hierarchy: {
        "1": "Official Blueprint Protocol (protocol.bryanjohnson.com): highest ground truth for current daily regimen",
        "2": "Blueprint Official Articles (blueprint.bryanjohnson.com) & Bryan Johnson YouTube (@BryanJohnson): explanations, experiments, updates",
        "3": "External Podcast & Interview Appearances: long-form reasoning and Q&A with timestamped citations",
      },
    };
  }

  private searchStances(query: string, limit = 8): ArchiveStance[] {
    const tokens = extractTokens(query);
    if (tokens.length === 0) return [];

    const strictHits: Array<{ score: number; stance: IndexedStance }> = [];
    const broadHits: Array<{ score: number; stance: IndexedStance }> = [];

    for (const s of this.stances) {
      const topicLower = s.topic.toLowerCase();
      const matchedCount = tokens.filter((t) => s.lowerBlob.includes(t)).length;
      if (matchedCount === 0) continue;
      const score = scoreTokens(topicLower, tokens, 6) + scoreTokens(s.lowerBlob, tokens, 1);
      if (matchedCount === tokens.length) strictHits.push({ score, stance: s });
      else broadHits.push({ score, stance: s });
    }

    const chosen = strictHits.length > 0 ? strictHits : broadHits;
    chosen.sort((a, b) => b.score - a.score);
    return chosen.slice(0, limit).map(({ stance: { lowerBlob: _lb, ...rest } }) => rest);
  }

  private searchDocs(
    query: string,
    opts: { tier?: number; source_type?: string; limit?: number } = {},
  ) {
    const tokens = extractTokens(query);
    if (tokens.length === 0) return [];
    const limit = opts.limit ?? 10;

    const scored: Array<{ matched: number; score: number; doc: IndexedDoc }> = [];
    for (const d of this.docs) {
      if (opts.tier !== undefined && d.tier !== opts.tier) continue;
      if (opts.source_type && d.source_type !== opts.source_type) continue;
      const titleScore = scoreTokens(d.lowerTitle, tokens, 5);
      const bodyScore = scoreTokens(d.lowerContent, tokens, 1);
      const total = titleScore + bodyScore;
      if (total <= 0) continue;
      const matched = tokens.filter((t) => d.lowerTitle.includes(t) || d.lowerContent.includes(t)).length;
      scored.push({ matched, score: total + (4 - d.tier) * 4, doc: d });
    }

    scored.sort(
      (a, b) =>
        b.matched - a.matched ||
        b.score - a.score ||
        a.doc.tier - b.doc.tier ||
        b.doc.published_at.localeCompare(a.doc.published_at),
    );

    return scored.slice(0, limit).map(({ doc }) => ({
      doc_id: doc.id,
      tier: doc.tier,
      source_type: doc.source_type,
      title: doc.title,
      url: doc.url,
      channel_or_site: doc.channel,
      published_at: doc.published_at,
      updated_at: doc.updated_at,
      duration_sec: doc.duration_sec,
      excerpt: makeExcerpt(doc.content, tokens),
    }));
  }

  private searchSegments(
    query: string,
    opts: { tier?: number; source_type?: string; limit?: number } = {},
  ) {
    const tokens = extractTokens(query);
    if (tokens.length === 0) return [];
    const limit = opts.limit ?? 10;

    const scored: Array<{ matched: number; score: number; seg: IndexedSegment; doc: IndexedDoc }> = [];
    for (const seg of this.segs) {
      const doc = this.docById.get(seg.doc_id);
      if (!doc) continue;
      if (opts.tier !== undefined && doc.tier !== opts.tier) continue;
      if (opts.source_type && doc.source_type !== opts.source_type) continue;

      const textMatched = tokens.filter((t) => seg.lower.includes(t)).length;
      if (textMatched === 0) continue;
      const titleBonus = scoreTokens(doc.lowerTitle, tokens, 1.5);
      const segScore = scoreTokens(seg.lower, tokens, 3);
      scored.push({
        matched: textMatched,
        score: segScore + titleBonus + (4 - doc.tier) * 3,
        seg,
        doc,
      });
    }

    scored.sort(
      (a, b) =>
        b.matched - a.matched ||
        b.score - a.score ||
        a.doc.tier - b.doc.tier ||
        b.doc.published_at.localeCompare(a.doc.published_at),
    );

    const out = [];
    const seen = new Set<string>();
    for (const { seg, doc } of scored) {
      const key = `${doc.id}:${seg.start_sec}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({
        doc_id: doc.id,
        tier: doc.tier,
        source_type: doc.source_type,
        title: doc.title,
        channel: doc.channel,
        published_at: doc.published_at,
        timestamp: formatTimestamp(seg.start_sec),
        start_sec: seg.start_sec,
        deep_link: seg.deep_link,
        text: seg.text,
      });
      if (out.length >= limit) break;
    }
    return out;
  }

  getOfficialProtocol(topic: string, includeFullContent = true, limit = 5) {
    const matches = this.searchDocs(topic, { tier: 1, limit }).map((m, idx) => {
      if (includeFullContent && idx < 2) {
        const full = this.docById.get(m.doc_id);
        return { ...m, content: full?.content.slice(0, 16000) ?? m.excerpt };
      }
      return m;
    });
    return {
      topic,
      tier1_pages: matches,
      related_stances: this.searchStances(topic, 5),
    };
  }

  checkStanceAndChanges(topic: string) {
    const docHits = this.searchDocs(topic, { limit: 10 }).filter(
      (d) => d.tier === 1 || d.source_type === "official_article",
    );
    return {
      topic,
      stances: this.searchStances(topic, 8),
      protocol_and_article_mentions: docHits,
      video_and_podcast_mentions: this.searchSegments(topic, { limit: 10 }),
    };
  }

  whatWouldBryanDo(question: string, includeTranscripts = true, maxPerTier = 5) {
    return {
      question,
      ground_truth_guidance:
        "Prioritize Tier 1 (protocol.bryanjohnson.com) and explicit stopped/avoid stances over older videos or interviews. Always cite URLs, dates, and video timestamps.",
      explicit_stances: this.searchStances(question, 6),
      tier1_official_protocol: this.searchDocs(question, { tier: 1, limit: maxPerTier }),
      tier2_official_articles_and_videos: {
        documents: this.searchDocs(question, { tier: 2, limit: maxPerTier }),
        timestamped_quotes: includeTranscripts ? this.searchSegments(question, { tier: 2, limit: maxPerTier }) : [],
      },
      tier3_external_podcasts: includeTranscripts ? this.searchSegments(question, { tier: 3, limit: maxPerTier }) : [],
    };
  }

  searchArchive(query: string, tier?: number, sourceType?: string, limit = 10) {
    return {
      query,
      documents: this.searchDocs(query, { tier, source_type: sourceType, limit }),
      timestamped_segments: this.searchSegments(query, { tier, source_type: sourceType, limit }),
    };
  }

  getDocument(docId: string, includeSegments = false, maxChars = 25000) {
    const doc = this.docById.get(docId);
    if (!doc) return null;
    const segs = this.segsByDoc.get(docId) ?? [];
    const rawContent =
      doc.content ||
      segs.map((s) => `[${formatTimestamp(s.start_sec)}] ${s.text}`).join("\n");
    return {
      id: doc.id,
      tier: doc.tier,
      source_type: doc.source_type,
      title: doc.title,
      url: doc.url,
      channel_or_site: doc.channel,
      published_at: doc.published_at,
      updated_at: doc.updated_at,
      duration_sec: doc.duration_sec,
      content: rawContent.slice(0, maxChars),
      truncated: rawContent.length > maxChars,
      total_chars: rawContent.length,
      ...(includeSegments
        ? {
            segments: segs.map((s, seq) => ({
              seq,
              timestamp: formatTimestamp(s.start_sec),
              start_sec: s.start_sec,
              deep_link: s.deep_link,
              text: s.text,
            })),
          }
        : {}),
    };
  }

  listSources(tier?: number, sourceType?: string, limit = 50, offset = 0) {
    const filtered = this.docs
      .filter((d) => (tier === undefined || d.tier === tier) && (!sourceType || d.source_type === sourceType))
      .sort((a, b) => a.tier - b.tier || b.published_at.localeCompare(a.published_at) || a.title.localeCompare(b.title));
    return {
      total: filtered.length,
      limit,
      offset,
      items: filtered.slice(offset, offset + limit).map((d) => ({
        id: d.id,
        tier: d.tier,
        source_type: d.source_type,
        title: d.title,
        url: d.url,
        channel_or_site: d.channel,
        published_at: d.published_at,
        updated_at: d.updated_at,
        duration_sec: d.duration_sec,
      })),
    };
  }

  listAllStances(): ArchiveStance[] {
    return this.stances.map(({ lowerBlob: _lb, ...rest }) => rest);
  }
}

let cachedEngine: ProtocolEngine | null = null;

export function getEngine(): ProtocolEngine {
  if (cachedEngine) return cachedEngine;
  const bundlePath = resolveBundlePath();
  const gz = fs.readFileSync(bundlePath);
  const jsonText = zlib.gunzipSync(gz).toString("utf-8");
  const bundle = JSON.parse(jsonText) as RawBundle;
  cachedEngine = new ProtocolEngine(bundle);
  return cachedEngine;
}
