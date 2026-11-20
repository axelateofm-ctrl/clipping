import { useRef, useState } from "react";
import { UploadCloud, FilePlus2 } from "lucide-react";

interface Props {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

export default function ImportZone({ onFiles, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  function handleFiles(list: FileList | null) {
    if (!list) return;
    const files = Array.from(list).filter(
      (f) => f.type === "video/mp4" || f.name.toLowerCase().endsWith(".mp4")
    );
    if (files.length) onFiles(files);
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        if (!disabled) handleFiles(e.dataTransfer.files);
      }}
      className={`card relative overflow-hidden transition-colors ${
        drag ? "border-brand-500/70 bg-brand-500/5" : ""
      }`}
    >
      <div className="p-10 text-center">
        <div
          className={`mx-auto mb-4 grid place-items-center h-16 w-16 rounded-2xl transition-colors ${
            drag ? "bg-brand-500/20" : "bg-ink-800"
          }`}
        >
          <UploadCloud className={`h-8 w-8 ${drag ? "text-brand-400" : "text-slate-400"}`} />
        </div>
        <p className="text-base font-semibold">
          Glissez-déposez vos vidéos MP4 ici
        </p>
        <p className="text-sm text-slate-400 mt-1 mb-5">
          Plusieurs fichiers acceptés. Traitement 100&nbsp;% côté serveur.
        </p>
        <button
          type="button"
          className="btn-primary mx-auto"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
        >
          <FilePlus2 className="h-4 w-4" />
          Importer des vidéos
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="video/mp4,.mp4"
          multiple
          hidden
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}
