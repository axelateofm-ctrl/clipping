import type {
  ExportSettings,
  SplitParams,
  VideoState,
} from "./types";

const BASE = "/api";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Erreur ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  async authStatus(): Promise<{ protected: boolean }> {
    return jsonOrThrow(await fetch(`${BASE}/auth/status`));
  },

  async login(password: string): Promise<{ ok: boolean; detail?: string }> {
    const res = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (res.status === 401) return { ok: false, detail: "Mot de passe incorrect." };
    return jsonOrThrow(res);
  },

  async health(): Promise<{
    status: string;
    ffmpeg: boolean;
    ffprobe: boolean;
    version: string;
    disk_free_mb?: number;
  }> {
    return jsonOrThrow(await fetch(`${BASE}/health`));
  },

  async listVideos(): Promise<VideoState[]> {
    return jsonOrThrow(await fetch(`${BASE}/videos`));
  },

  async getVideo(id: string): Promise<VideoState> {
    return jsonOrThrow(await fetch(`${BASE}/videos/${id}`));
  },

  /** Upload avec suivi de progression réel via XMLHttpRequest. */
  uploadVideo(
    file: File,
    onProgress: (fraction: number) => void,
    signal?: { xhr?: XMLHttpRequest }
  ): Promise<VideoState> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      if (signal) signal.xhr = xhr;
      xhr.open("POST", `${BASE}/videos`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(e.loaded / e.total);
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            reject(new Error("Réponse serveur illisible."));
          }
        } else {
          let detail = `Erreur ${xhr.status}`;
          try {
            const body = JSON.parse(xhr.responseText);
            if (body?.detail) detail = body.detail;
          } catch {
            /* ignore */
          }
          reject(new Error(detail));
        }
      };
      xhr.onerror = () => reject(new Error("Échec réseau pendant l'envoi."));
      xhr.onabort = () => reject(new Error("Envoi annulé."));
      const form = new FormData();
      form.append("file", file, file.name);
      xhr.send(form);
    });
  },

  async analyze(id: string, params: SplitParams): Promise<VideoState> {
    return jsonOrThrow(
      await fetch(`${BASE}/videos/${id}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ params }),
      })
    );
  },

  async exportVideo(id: string, settings: ExportSettings): Promise<VideoState> {
    return jsonOrThrow(
      await fetch(`${BASE}/videos/${id}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings }),
      })
    );
  },

  async cancel(id: string): Promise<VideoState> {
    return jsonOrThrow(
      await fetch(`${BASE}/videos/${id}/cancel`, { method: "POST" })
    );
  },

  async remove(id: string): Promise<void> {
    await fetch(`${BASE}/videos/${id}`, { method: "DELETE" });
  },

  sourceUrl(id: string): string {
    return `${BASE}/videos/${id}/source`;
  },
  thumbUrl(id: string, t: number, w = 240): string {
    return `${BASE}/videos/${id}/thumb?t=${t.toFixed(2)}&w=${w}`;
  },
  downloadZipUrl(id: string): string {
    return `${BASE}/videos/${id}/download`;
  },
  downloadSegmentUrl(id: string, name: string): string {
    return `${BASE}/videos/${id}/download/${encodeURIComponent(name)}`;
  },
};
