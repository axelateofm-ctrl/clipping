import { useEffect, useRef, useState } from "react";
import {
  Trash2,
  Wand2,
  Download,
  Ban,
  RefreshCw,
  AlertTriangle,
  FileVideo,
  Volume2,
  VolumeX,
  Package,
} from "lucide-react";
import type { ExportSettings, SegmentOut, SplitParams, VideoState } from "../types";
import { api } from "../api";
import {
  estimateRemaining,
  formatBytes,
  formatDuration,
  statusLabel,
  statusTone,
} from "../utils";
import SettingsPanel from "./SettingsPanel";
import SegmentTimeline from "./SegmentTimeline";
import ProgressBar from "./ProgressBar";
import ExportModal from "./ExportModal";

interface Props {
  video: VideoState;
  defaults: SplitParams;
  onAnalyze: (id: string, params: SplitParams) => void;
  onExport: (id: string, settings: ExportSettings) => void;
  onCancel: (id: string) => void;
  onRemove: (id: string) => void;
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-ink-900/60 px-3 py-2">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="text-sm font-medium text-slate-200 truncate">{value}</div>
    </div>
  );
}

export default function VideoCard({
  video,
  defaults,
  onAnalyze,
  onExport,
  onCancel,
  onRemove,
}: Props) {
  const [params, setParams] = useState<SplitParams>(video.params ?? defaults);
  const [showExport, setShowExport] = useState(false);
  const [activeSeg, setActiveSeg] = useState<SegmentOut | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const stageStart = useRef<number>(Date.now());
  const lastStage = useRef<string | null>(null);

  const m = video.meta;
  const busy = video.status === "analyzing" || video.status === "exporting";

  // Réinitialise le chrono quand une étape démarre.
  useEffect(() => {
    const stage = video.progress_stage ?? video.status;
    if (stage !== lastStage.current) {
      lastStage.current = stage;
      stageStart.current = Date.now();
    }
  }, [video.progress_stage, video.status]);

  // Prévisualisation d'une séquence : lecture bornée [start, end].
  function previewSegment(seg: SegmentOut) {
    const v = videoRef.current;
    if (!v) return;
    setActiveSeg(seg);
    v.currentTime = seg.start;
    v.play().catch(() => undefined);
  }

  function onTimeUpdate() {
    const v = videoRef.current;
    if (!v || !activeSeg) return;
    if (v.currentTime >= activeSeg.end) {
      v.pause();
      setActiveSeg(null);
    }
  }

  const eta =
    busy && video.progress > 0
      ? estimateRemaining(video.progress, Date.now() - stageStart.current)
      : null;

  const resolution = m.width && m.height ? `${m.width} × ${m.height}` : "—";

  return (
    <div className="card p-5 animate-fade-in">
      {/* En-tête */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="grid place-items-center h-10 w-10 rounded-lg bg-ink-800 shrink-0">
            <FileVideo className="h-5 w-5 text-brand-400" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold truncate" title={m.filename}>
              {m.filename}
            </h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`chip ${statusTone(video.status)}`}>
                {statusLabel(video.status)}
              </span>
              {m.has_audio ? (
                <span className="chip bg-ink-800 text-slate-400">
                  <Volume2 className="h-3 w-3" /> audio
                </span>
              ) : (
                <span className="chip bg-ink-800 text-slate-500">
                  <VolumeX className="h-3 w-3" /> muet
                </span>
              )}
            </div>
          </div>
        </div>
        <button
          onClick={() => onRemove(video.id)}
          className="btn-ghost !px-2.5 !py-2 shrink-0"
          title="Retirer"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        {/* Lecteur */}
        <div>
          <video
            ref={videoRef}
            src={api.sourceUrl(video.id)}
            controls
            onTimeUpdate={onTimeUpdate}
            className="w-full rounded-xl bg-black aspect-video"
          />
          {activeSeg && (
            <p className="text-[11px] text-brand-400 mt-1.5">
              Lecture de la séquence #{activeSeg.index}…
            </p>
          )}
        </div>

        {/* Métadonnées */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 content-start">
          <MetaItem label="Taille" value={formatBytes(m.size_bytes)} />
          <MetaItem label="Durée" value={formatDuration(m.duration)} />
          <MetaItem label="Résolution" value={resolution} />
          <MetaItem label="Format" value={m.aspect_ratio ?? "—"} />
          <MetaItem label="Images/s" value={m.fps ? `${m.fps}` : "—"} />
          <MetaItem label="Codec vidéo" value={m.video_codec ?? "—"} />
          <MetaItem label="Codec audio" value={m.audio_codec ?? "—"} />
        </div>
      </div>

      {/* Paramètres de découpage */}
      <div className="mt-6 pt-5 border-t border-white/5">
        <SettingsPanel params={params} onChange={setParams} disabled={busy} />
      </div>

      {/* Actions principales */}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        {video.status === "analyzing" ? (
          <>
            <div className="flex-1 min-w-[200px]">
              <ProgressBar
                value={video.progress}
                tone="brand"
                label={m.has_audio && params.smart ? "Analyse des silences…" : "Analyse…"}
                indeterminate={!m.has_audio || !params.smart}
              />
            </div>
            <button onClick={() => onCancel(video.id)} className="btn-danger">
              <Ban className="h-4 w-4" /> Annuler
            </button>
          </>
        ) : video.status === "exporting" ? (
          <>
            <div className="flex-1 min-w-[200px]">
              <ProgressBar
                value={video.progress}
                tone="amber"
                label={`Export — séquence ${video.current_segment}/${video.total_segments}${
                  eta ? ` · ~${eta} restant` : ""
                }`}
              />
            </div>
            <button onClick={() => onCancel(video.id)} className="btn-danger">
              <Ban className="h-4 w-4" /> Annuler
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => onAnalyze(video.id, params)}
              className={video.segments.length ? "btn-ghost" : "btn-primary"}
            >
              {video.segments.length ? (
                <>
                  <RefreshCw className="h-4 w-4" /> Relancer l'analyse
                </>
              ) : (
                <>
                  <Wand2 className="h-4 w-4" /> Analyser et calculer les séquences
                </>
              )}
            </button>
            {video.segments.length > 0 && (
              <button onClick={() => setShowExport(true)} className="btn-primary">
                <Download className="h-4 w-4" /> Exporter les vidéos
              </button>
            )}
          </>
        )}
      </div>

      {/* Erreur */}
      {video.status === "error" && video.error && (
        <div className="mt-4 flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-300">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{video.error}</span>
        </div>
      )}

      {/* Séquences */}
      {video.segments.length > 0 && (
        <div className="mt-6 pt-5 border-t border-white/5">
          <SegmentTimeline
            videoId={video.id}
            duration={m.duration}
            segments={video.segments}
            onPreview={previewSegment}
            activeIndex={activeSeg?.index ?? null}
          />
        </div>
      )}

      {/* Résultats / téléchargements */}
      {video.export_ready && video.status === "done" && (
        <div className="mt-6 pt-5 border-t border-white/5">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-300">
              <Package className="h-4 w-4" />
              Export terminé et vérifié — {video.segments.length} fichiers prêts.
            </div>
            <a href={api.downloadZipUrl(video.id)} className="btn-primary" download>
              <Download className="h-4 w-4" /> Télécharger le ZIP
            </a>
          </div>
          <details className="mt-3">
            <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-200">
              Téléchargements individuels
            </summary>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {video.segments.map((s) => {
                const pad = Math.max(2, String(video.segments.length).length);
                const name = `${video.zip_name?.replace(/\.zip$/, "") ?? "Sequence"}_${String(
                  s.index
                ).padStart(pad, "0")}.mp4`;
                return (
                  <a
                    key={s.index}
                    href={api.downloadSegmentUrl(video.id, name)}
                    download
                    className="flex items-center justify-between rounded-lg bg-ink-900/60 px-3 py-2 text-xs hover:bg-ink-800"
                  >
                    <span className="font-mono truncate text-slate-300">{name}</span>
                    <Download className="h-3.5 w-3.5 text-slate-400 shrink-0 ml-2" />
                  </a>
                );
              })}
            </div>
          </details>
        </div>
      )}

      {showExport && (
        <ExportModal
          video={video}
          onClose={() => setShowExport(false)}
          onLaunch={(settings) => {
            setShowExport(false);
            onExport(video.id, settings);
          }}
        />
      )}
    </div>
  );
}
