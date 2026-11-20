interface Props {
  value: number; // 0..1
  tone?: "brand" | "amber" | "emerald";
  label?: string;
  indeterminate?: boolean;
}

const toneMap = {
  brand: "bg-brand-500",
  amber: "bg-amber-400",
  emerald: "bg-emerald-400",
};

export default function ProgressBar({ value, tone = "brand", label, indeterminate }: Props) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div className="w-full">
      {label && (
        <div className="flex justify-between text-xs text-slate-400 mb-1.5">
          <span>{label}</span>
          {!indeterminate && <span className="tabular-nums">{pct}%</span>}
        </div>
      )}
      <div className="h-2 w-full rounded-full bg-ink-700 overflow-hidden">
        <div
          className={`h-full rounded-full ${toneMap[tone]} transition-[width] duration-300 ease-out ${
            indeterminate ? "animate-pulse w-1/3" : ""
          }`}
          style={indeterminate ? undefined : { width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
