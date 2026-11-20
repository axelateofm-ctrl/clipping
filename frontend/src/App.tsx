import { useCallback, useEffect, useRef, useState } from "react";
import { RotateCcw, X } from "lucide-react";
import { api } from "./api";
import type {
  ExportSettings,
  SplitParams,
  UploadEntry,
  VideoState,
} from "./types";
import Header from "./components/Header";
import ImportZone from "./components/ImportZone";
import VideoCard from "./components/VideoCard";
import LoginGate from "./components/LoginGate";
import ProgressBar from "./components/ProgressBar";
import { formatBytes } from "./utils";

const DEFAULT_PARAMS: SplitParams = {
  target: 70,
  window: 10,
  smart: true,
  silence_db: -35,
  silence_min: 0.25,
};

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [health, setHealth] = useState<Awaited<ReturnType<typeof api.health>> | null>(null);
  const [videos, setVideos] = useState<VideoState[]>([]);
  const [uploads, setUploads] = useState<UploadEntry[]>([]);
  const uploadXhrs = useRef<Record<string, { xhr?: XMLHttpRequest }>>({});

  // --- bootstrap --------------------------------------------------------
  useEffect(() => {
    (async () => {
      try {
        setHealth(await api.health());
      } catch {
        /* ignore */
      }
      try {
        const status = await api.authStatus();
        if (!status.protected) {
          setAuthed(true);
          return;
        }
        // Protégé : on teste l'accès.
        try {
          await api.listVideos();
          setAuthed(true);
        } catch {
          setAuthed(false);
        }
      } catch {
        setAuthed(true); // en cas de doute, on laisse l'UI s'afficher
      }
    })();
  }, []);

  // --- polling de l'état ------------------------------------------------
  const refresh = useCallback(async () => {
    try {
      const list = await api.listVideos();
      list.sort((a, b) => a.created_at - b.created_at);
      setVideos(list);
    } catch {
      /* ignore transient errors */
    }
  }, []);

  useEffect(() => {
    if (!authed) return;
    refresh();
    const id = setInterval(refresh, 1000);
    return () => clearInterval(id);
  }, [authed, refresh]);

  // --- upload -----------------------------------------------------------
  const uploadOne = useCallback(
    async (file: File) => {
      const localId = `${file.name}-${file.size}-${Date.now()}-${Math.random()
        .toString(36)
        .slice(2, 7)}`;
      setUploads((u) => [
        ...u,
        { localId, filename: file.name, size: file.size, progress: 0 },
      ]);
      const sig: { xhr?: XMLHttpRequest } = {};
      uploadXhrs.current[localId] = sig;
      try {
        const state = await api.uploadVideo(
          file,
          (frac) =>
            setUploads((u) =>
              u.map((e) => (e.localId === localId ? { ...e, progress: frac } : e))
            ),
          sig
        );
        setVideos((v) => [...v.filter((x) => x.id !== state.id), state]);
        setUploads((u) => u.filter((e) => e.localId !== localId));
        delete uploadXhrs.current[localId];
      } catch (err) {
        setUploads((u) =>
          u.map((e) =>
            e.localId === localId ? { ...e, error: (err as Error).message } : e
          )
        );
      }
    },
    []
  );

  const handleFiles = useCallback(
    (files: File[]) => {
      files.forEach((f) => uploadOne(f));
    },
    [uploadOne]
  );

  const retryUpload = useCallback(
    (entry: UploadEntry) => {
      setUploads((u) => u.filter((e) => e.localId !== entry.localId));
      // On ne peut pas relire le File d'origine ici sans le reconserver ;
      // l'utilisateur ré-importe le fichier. On retire simplement l'entrée.
    },
    []
  );

  const cancelUpload = useCallback((entry: UploadEntry) => {
    uploadXhrs.current[entry.localId]?.xhr?.abort();
    setUploads((u) => u.filter((e) => e.localId !== entry.localId));
    delete uploadXhrs.current[entry.localId];
  }, []);

  // --- actions vidéo ----------------------------------------------------
  const onAnalyze = useCallback(
    async (id: string, params: SplitParams) => {
      try {
        const s = await api.analyze(id, params);
        setVideos((v) => v.map((x) => (x.id === id ? s : x)));
      } catch (err) {
        alert((err as Error).message);
      }
    },
    []
  );

  const onExport = useCallback(async (id: string, settings: ExportSettings) => {
    try {
      const s = await api.exportVideo(id, settings);
      setVideos((v) => v.map((x) => (x.id === id ? s : x)));
    } catch (err) {
      alert((err as Error).message);
    }
  }, []);

  const onCancel = useCallback(async (id: string) => {
    try {
      const s = await api.cancel(id);
      setVideos((v) => v.map((x) => (x.id === id ? s : x)));
    } catch {
      /* ignore */
    }
  }, []);

  const onRemove = useCallback(async (id: string) => {
    setVideos((v) => v.filter((x) => x.id !== id));
    try {
      await api.remove(id);
    } catch {
      /* ignore */
    }
  }, []);

  if (authed === null) {
    return (
      <div className="min-h-screen grid place-items-center text-slate-500 text-sm">
        Chargement…
      </div>
    );
  }
  if (authed === false) {
    return <LoginGate onSuccess={() => setAuthed(true)} />;
  }

  const anyBusy = videos.some(
    (v) => v.status === "analyzing" || v.status === "exporting"
  );

  return (
    <div className="min-h-screen max-w-5xl mx-auto px-4 sm:px-6 py-8">
      <Header health={health} />

      <ImportZone onFiles={handleFiles} />

      {/* Uploads en cours */}
      {uploads.length > 0 && (
        <div className="mt-4 space-y-2">
          {uploads.map((u) => (
            <div key={u.localId} className="card p-4 flex items-center gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex justify-between text-sm mb-1">
                  <span className="truncate">{u.filename}</span>
                  <span className="text-slate-500 text-xs ml-2 shrink-0">
                    {formatBytes(u.size)}
                  </span>
                </div>
                {u.error ? (
                  <p className="text-xs text-red-400">{u.error}</p>
                ) : (
                  <ProgressBar value={u.progress} label="Envoi vers le serveur…" />
                )}
              </div>
              {u.error ? (
                <button
                  onClick={() => retryUpload(u)}
                  className="btn-ghost !px-2.5 !py-2"
                  title="Fermer (ré-importez le fichier pour réessayer)"
                >
                  <RotateCcw className="h-4 w-4" />
                </button>
              ) : (
                <button
                  onClick={() => cancelUpload(u)}
                  className="btn-ghost !px-2.5 !py-2"
                  title="Annuler l'envoi"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Liste des vidéos */}
      <div className="mt-6 space-y-5">
        {videos.length === 0 && uploads.length === 0 && (
          <div className="text-center text-slate-500 text-sm py-12">
            Aucune vidéo pour le moment. Importez un ou plusieurs MP4 pour commencer.
          </div>
        )}
        {videos.map((v) => (
          <VideoCard
            key={v.id}
            video={v}
            defaults={DEFAULT_PARAMS}
            onAnalyze={onAnalyze}
            onExport={onExport}
            onCancel={onCancel}
            onRemove={onRemove}
          />
        ))}
      </div>

      <footer className="mt-12 text-center text-[11px] text-slate-600">
        AXIE Video Splitter — traitement serveur FFmpeg · {anyBusy ? "traitement en cours…" : "prêt"}
      </footer>
    </div>
  );
}
