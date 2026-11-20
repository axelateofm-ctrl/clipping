import { Play, Film } from "lucide-react";
import { api } from "../api";
import type { SegmentOut } from "../types";
import { formatClock, formatDuration } from "../utils";

interface Props {
  videoId: string;
  duration: number;
  segments: SegmentOut[];
  onPreview: (seg: SegmentOut) => void;
  activeIndex?: number | null;
}

function cutColor(t: SegmentOut["cut_type"]): string {
  if (t === "silence") return "bg-accent-silence";
  if (t === "final") return "bg-brand-500";
  return "bg-accent-time";
}

export default function SegmentTimeline({
  videoId,
  duration,
  segments,
  onPreview,
  activeIndex,
}: Props) {
  if (!segments.length) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
          <Film className="h-4 w-4 text-brand-400" />
          {segments.length} séquence{segments.length > 1 ? "s" : ""} prévue
          {segments.length > 1 ? "s" : ""}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-accent-silence" /> Silence
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-accent-time" /> Durée
          </span>
        </div>
      </div>

      {/* Timeline proportionnelle */}
      <div className="flex h-8 w-full overflow-hidden rounded-lg border border-white/5 bg-ink-900">
        {segments.map((s) => {
          const w = duration > 0 ? (s.duration / duration) * 100 : 0;
          return (
            <button
              key={s.index}
              title={`Séquence ${s.index} — ${formatClock(s.start)} → ${formatClock(s.end)}`}
              onClick={() => onPreview(s)}
              style={{ width: `${w}%` }}
              className={`group relative h-full border-r border-ink-950/60 last:border-r-0 ${cutColor(
                s.cut_type
              )} ${activeIndex === s.index ? "ring-2 ring-white/70 ring-inset z-10" : "opacity-80 hover:opacity-100"}`}
            >
              <span className="absolute inset-0 grid place-items-center text-[10px] font-bold text-black/70">
                {w > 4 ? s.index : ""}
              </span>
            </button>
          );
        })}
      </div>

      {/* Grille des séquences */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {segments.map((s) => (
          <div
            key={s.index}
            className={`rounded-xl border bg-ink-900/60 overflow-hidden transition-colors ${
              activeIndex === s.index ? "border-brand-500/60" : "border-white/5"
            }`}
          >
            <div className="relative aspect-video bg-ink-950">
              <img
                src={api.thumbUrl(videoId, s.start + Math.min(0.5, s.duration / 2))}
                alt={`Miniature séquence ${s.index}`}
                loading="lazy"
                className="h-full w-full object-cover"
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).style.visibility = "hidden";
                }}
              />
              <button
                onClick={() => onPreview(s)}
                className="absolute inset-0 grid place-items-center bg-black/30 opacity-0 hover:opacity-100 transition-opacity"
              >
                <span className="grid place-items-center h-10 w-10 rounded-full bg-white/90 text-black">
                  <Play className="h-4 w-4 translate-x-0.5" />
                </span>
              </button>
              <span
                className={`absolute top-1.5 left-1.5 chip ${
                  s.cut_type === "silence"
                    ? "bg-emerald-500/80 text-black"
                    : s.cut_type === "final"
                    ? "bg-brand-500/80 text-white"
                    : "bg-amber-400/80 text-black"
                }`}
              >
                #{s.index}
              </span>
            </div>
            <div className="p-2.5 text-xs">
              <div className="flex justify-between text-slate-300">
                <span>{formatClock(s.start)}</span>
                <span className="text-slate-500">→</span>
                <span>{formatClock(s.end)}</span>
              </div>
              <div className="mt-1 flex items-center justify-between">
                <span className="text-slate-400">
                  {formatDuration(s.duration)}
                </span>
                <span
                  className={`text-[10px] font-medium ${
                    s.cut_type === "silence"
                      ? "text-emerald-400"
                      : s.cut_type === "final"
                      ? "text-brand-400"
                      : "text-amber-400"
                  }`}
                >
                  {s.cut_type === "silence"
                    ? "pause"
                    : s.cut_type === "final"
                    ? "fin"
                    : "temps"}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
