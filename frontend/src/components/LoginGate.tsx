import { useState } from "react";
import { Lock } from "lucide-react";
import { api } from "../api";

interface Props {
  onSuccess: () => void;
}

export default function LoginGate({ onSuccess }: Props) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.login(password);
      if (res.ok) onSuccess();
      else setError(res.detail || "Accès refusé.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <form onSubmit={submit} className="card p-8 w-full max-w-sm animate-fade-in">
        <div className="grid place-items-center h-12 w-12 rounded-xl bg-brand-500/15 mb-5 mx-auto">
          <Lock className="h-6 w-6 text-brand-400" />
        </div>
        <h1 className="text-lg font-bold text-center">AXIE Video Splitter</h1>
        <p className="text-sm text-slate-400 text-center mb-6">
          Accès protégé. Saisissez le mot de passe.
        </p>
        <input
          type="password"
          className="input mb-3"
          placeholder="Mot de passe"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
        />
        {error && <p className="text-sm text-red-400 mb-3">{error}</p>}
        <button type="submit" className="btn-primary w-full" disabled={busy || !password}>
          {busy ? "Connexion…" : "Entrer"}
        </button>
      </form>
    </div>
  );
}
