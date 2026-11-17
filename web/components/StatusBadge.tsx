const STYLES: Record<string, { label: string; classes: string; dot: string }> = {
  active: {
    label: "Active",
    classes: "bg-emerald-50 text-emerald-900 border-emerald-200",
    dot: "bg-emerald-600",
  },
  stopped: {
    label: "Stopped",
    classes: "bg-amber-50 text-amber-900 border-amber-200",
    dot: "bg-amber-600",
  },
  avoid: {
    label: "Avoids",
    classes: "bg-rose-50 text-rose-900 border-rose-200",
    dot: "bg-rose-600",
  },
  conditional: {
    label: "Nuanced",
    classes: "bg-sky-50 text-sky-900 border-sky-200",
    dot: "bg-sky-600",
  },
  experimental: {
    label: "Experimental",
    classes: "bg-violet-50 text-violet-900 border-violet-200",
    dot: "bg-violet-600",
  },
};

export function StatusBadge({ status }: { status: string }) {
  const cfg = STYLES[status.toLowerCase()] ?? STYLES.conditional;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wide ${cfg.classes}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}
