import { ExternalLink, X } from "lucide-react";
import type { ReactNode } from "react";
import type { DocumentDetail } from "../types";

interface DocDrawerProps {
  doc: DocumentDetail | null;
  loading: boolean;
  onClose: () => void;
}

function renderInline(rawText: string): ReactNode[] {
  const text = rawText.replace(/<\/?(?:b|i|em|strong|u|s|br|p|span|font)[^>]*>/gi, "");
  const parts: ReactNode[] = [];
  const pattern = /(\[([^\]]+)\]\(([^)]*)\)|\*\*([^*]+)\*\*|\*([^*]+)\*)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(text.slice(last, match.index));
    }
    if (match[2] !== undefined && match[3] !== undefined) {
      const target = match[3].trim();
      if (/^(https?:\/\/|mailto:)/i.test(target)) {
        parts.push(
          <a
            key={key++}
            href={target}
            target={target.startsWith("mailto:") ? undefined : "_blank"}
            rel={target.startsWith("mailto:") ? undefined : "noopener noreferrer"}
            className="text-[#1D4ED8] underline decoration-[#BFCFF6] underline-offset-2 hover:decoration-[#1D4ED8]"
          >
            {match[2]}
          </a>,
        );
      } else {
        parts.push(<span key={key++}>{match[2]}</span>);
      }
    } else if (match[4]) {
      parts.push(
        <strong key={key++} className="font-semibold text-[#141413]">
          {match[4]}
        </strong>,
      );
    } else if (match[5]) {
      parts.push(
        <em key={key++} className="italic">
          {match[5]}
        </em>,
      );
    }
    last = pattern.lastIndex;
  }

  if (last < text.length) {
    parts.push(text.slice(last));
  }
  return parts;
}

function FormattedBody({ content }: { content: string }) {
  const blocks = content.split(/\n{2,}/);
  return (
    <div className="space-y-3.5 text-sm leading-relaxed text-[#262624]">
      {blocks.map((block, idx) => {
        const trimmed = block.trim();
        if (!trimmed || /^\*{3,}$|^-{3,}$/.test(trimmed)) return null;
        if (trimmed.startsWith("### ")) {
          return (
            <h4 key={idx} className="pt-2 text-sm font-semibold text-[#141413]">
              {renderInline(trimmed.slice(4))}
            </h4>
          );
        }
        if (trimmed.startsWith("## ")) {
          return (
            <h3 key={idx} className="pt-3 text-base font-semibold text-[#141413]">
              {renderInline(trimmed.slice(3))}
            </h3>
          );
        }
        if (trimmed.startsWith("# ")) {
          return (
            <h2 key={idx} className="text-lg font-semibold text-[#141413]">
              {renderInline(trimmed.slice(2))}
            </h2>
          );
        }

        const lines = trimmed.split("\n");
        if (lines.every((l) => /^[-*+]\s+|^\d+\.\s+/.test(l.trim()))) {
          return (
            <ul key={idx} className="list-disc space-y-1.5 pl-5">
              {lines.map((l, li) => (
                <li key={li}>{renderInline(l.trim().replace(/^[-*+]\s+|^\d+\.\s+/, ""))}</li>
              ))}
            </ul>
          );
        }

        return (
          <p key={idx} className="whitespace-pre-line">
            {renderInline(trimmed)}
          </p>
        );
      })}
    </div>
  );
}

export function DocDrawer({ doc, loading, onClose }: DocDrawerProps) {
  if (!doc && !loading) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/25 backdrop-blur-[1px]"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-2xl flex-col border-l border-[#E6E4DD] bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-[#E6E4DD] px-6 py-4">
          <div className="min-w-0">
            {doc ? (
              <>
                <div className="mb-1 flex flex-wrap items-center gap-2 font-mono text-[11px] text-[#6F6E69]">
                  <span className="rounded bg-[#F2F0EA] px-1.5 py-0.5 text-[#141413]">
                    Tier {doc.tier}
                  </span>
                  <span>{doc.channel_or_site}</span>
                  {(doc.published_at || doc.updated_at) && (
                    <span>· {doc.published_at || doc.updated_at}</span>
                  )}
                </div>
                <h2 className="text-lg font-semibold leading-snug text-[#141413]">
                  {doc.title}
                </h2>
              </>
            ) : (
              <div className="text-sm text-[#6F6E69]">Loading document...</div>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-[#6F6E69] hover:bg-[#F2F0EA] hover:text-[#141413]"
            aria-label="Close reader"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {doc && (
          <div className="flex items-center justify-between border-b border-[#EFECE6] bg-[#FAF9F6] px-6 py-2.5 text-xs">
            <a
              href={doc.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-mono text-[#1D4ED8] hover:underline"
            >
              Open original source
              <ExternalLink className="h-3 w-3" />
            </a>
            {doc.truncated && (
              <span className="font-mono text-[#6F6E69]">
                Showing first {doc.content.length.toLocaleString()} of{" "}
                {doc.total_chars.toLocaleString()} chars
              </span>
            )}
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="space-y-3">
              <div className="h-4 w-3/4 animate-pulse rounded bg-[#EFECE6]" />
              <div className="h-4 w-full animate-pulse rounded bg-[#EFECE6]" />
              <div className="h-4 w-5/6 animate-pulse rounded bg-[#EFECE6]" />
            </div>
          ) : (
            doc && <FormattedBody content={doc.content} />
          )}
        </div>
      </div>
    </div>
  );
}
