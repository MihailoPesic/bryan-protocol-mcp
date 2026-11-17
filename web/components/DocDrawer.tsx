import { ExternalLink, X } from "lucide-react";
import type { DocumentDetail } from "../types";

interface DocDrawerProps {
  doc: DocumentDetail | null;
  loading: boolean;
  onClose: () => void;
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
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-[#262624]">
              {doc?.content}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
