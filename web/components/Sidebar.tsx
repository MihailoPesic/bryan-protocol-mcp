import { ArrowUpRight } from "lucide-react";

interface SidebarProps {
  activeQuery: string;
  onSelectQuery: (q: string) => void;
  onOpenMcp: () => void;
}

const GROUPS = [
  {
    heading: "Stopped / Changed",
    items: [
      { label: "Rapamycin", q: "rapamycin", dot: "bg-amber-600" },
      { label: "HGH (Thymus)", q: "human growth hormone HGH", dot: "bg-amber-600" },
      { label: "Donor Young Plasma", q: "plasma exchange", dot: "bg-violet-600" },
      { label: "Testosterone / TRT", q: "testosterone trt", dot: "bg-amber-600" },
      { label: "Project Baby Face", q: "donor fat baby face", dot: "bg-amber-600" },
      { label: "Cerebrolysin", q: "cerebrolysin", dot: "bg-amber-600" },
    ],
  },
  {
    heading: "Avoids / Nuanced",
    items: [
      { label: "Coffee & Caffeine", q: "coffee caffeine", dot: "bg-rose-600" },
      { label: "Cold Plunge", q: "cold plunge", dot: "bg-rose-600" },
      { label: "Seed Oils vs. EVOO", q: "seed oils", dot: "bg-sky-600" },
      { label: "Sun & UV Exposure", q: "sun exposure", dot: "bg-sky-600" },
      { label: "Social Media", q: "social media fast", dot: "bg-sky-600" },
    ],
  },
  {
    heading: "Active Regimen",
    items: [
      { label: "Sleep Schedule", q: "sleep", dot: "bg-emerald-600" },
      { label: "Daily Routine", q: "my daily routine", dot: "bg-emerald-600" },
      { label: "Nutrition & Macros", q: "nutrition macros", dot: "bg-emerald-600" },
      { label: "Rx Prescriptions", q: "acarbose metformin", dot: "bg-emerald-600" },
      { label: "Dry Sauna + Ice", q: "dry sauna", dot: "bg-emerald-600" },
      { label: "HBOT Protocol", q: "hbot hyperbaric", dot: "bg-emerald-600" },
      { label: "Psilocybin Trial", q: "psilocybin", dot: "bg-violet-600" },
    ],
  },
];

export function Sidebar({ activeQuery, onSelectQuery, onOpenMcp }: SidebarProps) {
  const normalized = activeQuery.trim().toLowerCase();

  return (
    <aside className="hidden w-56 shrink-0 lg:block">
      <div className="sticky top-20 space-y-6">
        {GROUPS.map((group) => (
          <div key={group.heading}>
            <div className="mb-2 px-2 font-mono text-[11px] font-medium uppercase tracking-wider text-[#6F6E69]">
              {group.heading}
            </div>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const isActive = normalized === item.q.toLowerCase();
                return (
                  <li key={item.q}>
                    <button
                      type="button"
                      onClick={() => onSelectQuery(item.q)}
                      className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] transition-colors ${
                        isActive
                          ? "bg-[#EFECE6] font-medium text-[#141413]"
                          : "text-[#4A4945] hover:bg-[#F2F0EA] hover:text-[#141413]"
                      }`}
                    >
                      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${item.dot}`} />
                      <span className="truncate">{item.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}

        <div className="border-t border-[#E6E4DD] pt-4">
          <button
            type="button"
            onClick={onOpenMcp}
            className="flex w-full items-center justify-between rounded-md border border-[#E6E4DD] bg-white px-2.5 py-2 text-left text-[12px] text-[#3A3935] hover:border-[#C9C6BD]"
          >
            <div>
              <div className="font-medium text-[#141413]">MCP Endpoint</div>
              <div className="font-mono text-[11px] text-[#6F6E69]">/mcp · Streamable HTTP</div>
            </div>
            <ArrowUpRight className="h-3.5 w-3.5 text-[#6F6E69]" />
          </button>
        </div>
      </div>
    </aside>
  );
}
