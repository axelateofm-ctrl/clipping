import { useMemo, useState } from "react";
import { X, Download, Film, Info } from "lucide-react";
import type { ExportSettings, VideoState } from "../types";

interface Props {
  video: VideoState;
  onClose: () => void;
  onLaunch: (settings: ExportSettings) => void;
}

function sanitizePreview(name: string): string {
  const cleaned = name
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/\s+/g, "_")
    .replace(/[^A-Za-z0-9._-]+/g, "_")
    .replace(/_{2,}/g, "_")
    .replace(/^[._-]+|[._-]+$/g, "");
  return cleaned || "Sequence";
}

export default function ExportModal({ video, onClose, onLaunch }: Props) {
  const [settings, setSettings] = useState<ExportSettings>({
    aspect_ratio: "16:9",
    quality: "original",
    precise: false,
    base_name: "Podcast",
  });

  const base = sanitizePreview(settings.base_name);
  const total = video.segments.length;
  const pad = Math.max(2, String(total).length);
  const examples = useMemo(() => {
    return [1, 2, 3]
      .filter((n) => n <= total || total === 0)
      .map((n) => `${base}_${String(n).padStart(pad, "0")}.mp4`);
  }, [base, pad, total]);

  const vertical = settings.aspect_ratio === "9:16";
  const sameRatio =
    video.meta.width && video.meta.height
      ? Math.abs(
          video.meta.width / video.meta.height -
            (vertical ? 9 / 16 : 16 / 9)
        ) <= 0.02
      : false;

  const set = (patch: Partial<ExportSettings>) =>
    setSettings((s) => ({ ...s, ...patch }));

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-2xl animate-fade-in max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b border-white/5">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Film className="h-5 w-5 text-brand-400" />
            Exporter les séquences
          </h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5">
            <X className="h-5 w-5 text-slate-400" />
          </button>
        </div>

        <div className="p-5 space-y-6">
          {/* Format */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <label className="field-label">Format de l'image</label>
              <select
                className="input"
                value={settings.aspect_ratio}
                onChange={(e) =>
                  set({ aspect_ratio: e.target.value as ExportSettings["aspect_ratio"] })
                }
              >
                <option value="16:9">Paysage 16:9</option>
                <option value="9:16">Vertical 9:16</option>
              </select>
              <p className="text-[11px] text-slate-500 mt-2 flex gap-1.5">
                <Info className="h-3.5 w-3.5 shrink-0 mt-px" />
                {sameRatio
                  ? "La vidéo possède déjà ce ratio : aucun recadrage inutile."
                  : "L'image sera adaptée sans déformation (marges neutres centrées), via un ré-encodage."}
              </p>
            </div>

            {/* Prévisualisation du format */}
            <div className="grid place-items-center">
              <div className="text-[11px] text-slate-400 mb-2">Aperçu du cadre</div>
              <div
                className={`border-2 border-brand-500/50 bg-ink-900 grid place-items-center rounded-md ${
                  vertical ? "w-[54px] h-[96px]" : "w-[128px] h-[72px]"
                }`}
              >
                <span className="text-[10px] text-slate-500">{settings.aspect_ratio}</span>
              </div>
            </div>
          </div>

          {/* Qualité */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <label className="field-label">Qualité d'export</label>
              <select
                className="input"
                value={settings.quality}
                onChange={(e) =>
                  set({ quality: e.target.value as ExportSettings["quality"] })
                }
              >
                <option value="original">Qualité d'origine privilégiée</option>
                <option value="high">Haute qualité (ré-encodage soigné)</option>
              </select>
            </div>
            <div>
              <label className="field-label">Découpage</label>
              <button
                type="button"
                onClick={() => set({ precise: !settings.precise })}
                className={`btn w-full justify-between ${
                  settings.precise ? "bg-brand-500/15 text-brand-300" : "bg-white/5 text-slate-300"
                }`}
              >
                <span>{settings.precise ? "Précis (ré-encodage)" : "Rapide (copie directe)"}</span>
                <span
                  className={`h-5 w-9 rounded-full relative transition-colors ${
                    settings.precise ? "bg-brand-500" : "bg-ink-600"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
                      settings.precise ? "left-4" : "left-0.5"
                    }`}
                  />
                </span>
              </button>
              <p className="text-[11px] text-slate-500 mt-1.5">
                {sameRatio
                  ? settings.precise
                    ? "Coupes à l'image près (plus lent)."
                    : "Rapide, qualité d'origine conservée (coupe aux images clés)."
                  : "Le changement de format impose un ré-encodage précis."}
              </p>
            </div>
          </div>

          {/* Nommage */}
          <div>
            <label className="field-label">Nom des vidéos</label>
            <input
              className="input"
              value={settings.base_name}
              onChange={(e) => set({ base_name: e.target.value })}
              placeholder="Podcast_Omar_Sy"
            />
            <div className="mt-2 flex flex-wrap gap-2">
              {examples.map((ex) => (
                <span key={ex} className="chip bg-ink-800 text-slate-400 font-mono text-[11px]">
                  {ex}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 p-5 border-t border-white/5">
          <p className="text-xs text-slate-500">
            {total} séquence{total > 1 ? "s" : ""} seront générées puis réunies dans un ZIP.
          </p>
          <div className="flex gap-2">
            <button onClick={onClose} className="btn-ghost">
              Annuler
            </button>
            <button onClick={() => onLaunch({ ...settings, base_name: base })} className="btn-primary">
              <Download className="h-4 w-4" />
              Lancer l'exportation
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
