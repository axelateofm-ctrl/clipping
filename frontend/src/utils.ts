import type { VideoStatus } from "./types";

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 o";
  const units = ["o", "Ko", "Mo", "Go", "To"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatDuration(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "—";
  const s = Math.floor(seconds % 60);
  const m = Math.floor((seconds / 60) % 60);
  const h = Math.floor(seconds / 3600);
  const pad = (n: number) => String(n).padStart(2, "0");
  if (h > 0) return `${h}:${pad(m)}:${pad(s)}`;
  return `${m}:${pad(s)}`;
}

export function formatClock(seconds: number): string {
  const ms = Math.round((seconds % 1) * 10);
  return `${formatDuration(seconds)}.${ms}`;
}

export function statusLabel(status: VideoStatus): string {
  const map: Record<VideoStatus, string> = {
    uploaded: "Importée",
    analyzing: "Analyse en cours",
    ready: "Prête à exporter",
    exporting: "Export en cours",
    done: "Terminée",
    error: "Erreur",
    canceled: "Annulée",
  };
  return map[status];
}

export function statusTone(status: VideoStatus): string {
  const map: Record<VideoStatus, string> = {
    uploaded: "bg-slate-500/15 text-slate-300",
    analyzing: "bg-brand-500/15 text-brand-400",
    ready: "bg-emerald-500/15 text-emerald-300",
    exporting: "bg-amber-500/15 text-amber-300",
    done: "bg-emerald-500/20 text-emerald-300",
    error: "bg-red-500/15 text-red-300",
    canceled: "bg-slate-600/20 text-slate-400",
  };
  return map[status];
}

export function estimateRemaining(
  progress: number,
  elapsedMs: number
): string | null {
  if (progress <= 0.02 || progress >= 1) return null;
  const totalMs = elapsedMs / progress;
  const remainingMs = totalMs - elapsedMs;
  if (!isFinite(remainingMs) || remainingMs < 0) return null;
  return formatDuration(remainingMs / 1000);
}
