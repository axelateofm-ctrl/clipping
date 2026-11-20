export type VideoStatus =
  | "uploaded"
  | "analyzing"
  | "ready"
  | "exporting"
  | "done"
  | "error"
  | "canceled";

export interface VideoMeta {
  filename: string;
  size_bytes: number;
  duration: number;
  width?: number | null;
  height?: number | null;
  aspect_ratio?: string | null;
  fps?: number | null;
  video_codec?: string | null;
  audio_codec?: string | null;
  has_audio: boolean;
}

export interface SegmentOut {
  index: number;
  start: number;
  end: number;
  duration: number;
  cut_type: "silence" | "time" | "final";
}

export interface SplitParams {
  target: number;
  window: number;
  smart: boolean;
  silence_db: number;
  silence_min: number;
}

export interface ExportSettings {
  aspect_ratio: "16:9" | "9:16";
  quality: "original" | "high";
  precise: boolean;
  base_name: string;
}

export interface VideoState {
  id: string;
  status: VideoStatus;
  meta: VideoMeta;
  params?: SplitParams | null;
  segments: SegmentOut[];
  error?: string | null;
  progress: number;
  progress_stage?: "analyze" | "export" | null;
  current_segment: number;
  total_segments: number;
  export_ready: boolean;
  zip_name?: string | null;
  created_at: number;
  updated_at: number;
}

/** Entrée locale pendant l'upload (avant réponse serveur). */
export interface UploadEntry {
  localId: string;
  filename: string;
  size: number;
  progress: number; // 0..1
  error?: string;
}
