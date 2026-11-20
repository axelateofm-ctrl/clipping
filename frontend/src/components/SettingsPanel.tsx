import { useState } from "react";
import { SlidersHorizontal, ChevronDown, Sparkles } from "lucide-react";
import type { SplitParams } from "../types";

interface Props {
  params: SplitParams;
  onChange: (p: SplitParams) => void;
  disabled?: boolean;
}

export default function SettingsPanel({ params, onChange, disabled }: Props) {
  const [advanced, setAdvanced] = useState(false);
  const [unit, setUnit] = useState<"s" | "min">("s");

  const set = (patch: Partial<SplitParams>) => onChange({ ...params, ...patch });

  const targetDisplay = unit === "s" ? params.target : +(params.target / 60).toFixed(2);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
        <SlidersHorizontal className="h-4 w-4 text-brand-400" />
        Paramètres de découpage
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="field-label">Durée cible par séquence</label>
          <div className="flex gap-2">
            <input
              type="number"
              min={unit === "s" ? 5 : 0.1}
              step={unit === "s" ? 1 : 0.1}
              className="input"
              value={targetDisplay}
              disabled={disabled}
              onChange={(e) => {
                const v = parseFloat(e.target.value) || 0;
                set({ target: unit === "s" ? v : v * 60 });
              }}
            />
            <select
              className="input w-24"
              value={unit}
              disabled={disabled}
              onChange={(e) => setUnit(e.target.value as "s" | "min")}
            >
              <option value="s">secondes</option>
              <option value="min">minutes</option>
            </select>
          </div>
        </div>

        <div>
          <label className="field-label">Découpage intelligent (silences)</label>
          <button
            type="button"
            disabled={disabled}
            onClick={() => set({ smart: !params.smart })}
            className={`btn w-full justify-between ${
              params.smart ? "bg-brand-500/15 text-brand-300" : "bg-white/5 text-slate-300"
            }`}
          >
            <span className="flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              {params.smart ? "Activé" : "Désactivé"}
            </span>
            <span
              className={`h-5 w-9 rounded-full relative transition-colors ${
                params.smart ? "bg-brand-500" : "bg-ink-600"
              }`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
                  params.smart ? "left-4" : "left-0.5"
                }`}
              />
            </span>
          </button>
        </div>
      </div>

      <button
        type="button"
        className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200"
        onClick={() => setAdvanced((v) => !v)}
      >
        <ChevronDown className={`h-4 w-4 transition-transform ${advanced ? "rotate-180" : ""}`} />
        Réglages avancés
      </button>

      {advanced && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 animate-fade-in">
          <div>
            <label className="field-label">Fenêtre de recherche (s)</label>
            <input
              type="number"
              min={0}
              step={1}
              className="input"
              value={params.window}
              disabled={disabled || !params.smart}
              onChange={(e) => set({ window: parseFloat(e.target.value) || 0 })}
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Recherche un silence entre {Math.max(0, params.target - params.window)}&nbsp;s et{" "}
              {params.target}&nbsp;s.
            </p>
          </div>
          <div>
            <label className="field-label">Seuil de silence (dB)</label>
            <input
              type="number"
              step={1}
              className="input"
              value={params.silence_db}
              disabled={disabled || !params.smart}
              onChange={(e) => set({ silence_db: parseFloat(e.target.value) || -35 })}
            />
          </div>
          <div>
            <label className="field-label">Durée mini de silence (s)</label>
            <input
              type="number"
              min={0.05}
              step={0.05}
              className="input"
              value={params.silence_min}
              disabled={disabled || !params.smart}
              onChange={(e) => set({ silence_min: parseFloat(e.target.value) || 0.25 })}
            />
          </div>
          <p className="sm:col-span-3 text-[11px] text-slate-500">
            Un silence détecté ne garantit pas la fin d'une phrase : si aucun silence
            pertinent n'est trouvé, une coupe à la durée cible est appliquée.
          </p>
        </div>
      )}
    </div>
  );
}
