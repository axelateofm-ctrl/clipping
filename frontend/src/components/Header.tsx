import { Scissors, Server, CircleCheck, CircleAlert } from "lucide-react";

interface Props {
  health?: {
    status: string;
    ffmpeg: boolean;
    ffprobe: boolean;
    version: string;
    disk_free_mb?: number;
  } | null;
}

export default function Header({ health }: Props) {
  const ok = health?.ffmpeg && health?.ffprobe;
  return (
    <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
      <div className="flex items-center gap-3">
        <div className="grid place-items-center h-11 w-11 rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 shadow-lg shadow-brand-600/30">
          <Scissors className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight">
            AXIE <span className="text-brand-400">Video Splitter</span>
          </h1>
          <p className="text-xs text-slate-400">
            Découpe automatique en séquences de ~70&nbsp;s, au plus près des silences.
          </p>
        </div>
      </div>

      {health && (
        <div className="flex items-center gap-2 text-xs">
          <span className="chip bg-ink-800 text-slate-400">
            <Server className="h-3.5 w-3.5" /> Serveur v{health.version}
          </span>
          {ok ? (
            <span className="chip bg-emerald-500/10 text-emerald-300">
              <CircleCheck className="h-3.5 w-3.5" /> FFmpeg prêt
            </span>
          ) : (
            <span className="chip bg-red-500/10 text-red-300">
              <CircleAlert className="h-3.5 w-3.5" /> FFmpeg indisponible
            </span>
          )}
          {typeof health.disk_free_mb === "number" && health.disk_free_mb >= 0 && (
            <span className="chip bg-ink-800 text-slate-400 hidden md:inline-flex">
              {Math.round(health.disk_free_mb / 1024)} Go libres
            </span>
          )}
        </div>
      )}
    </header>
  );
}
