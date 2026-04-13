// ─────────────────────────────────────────────────────────────────────────────
// src/shared/types.ts
//
// Types shared between the Electron main process and the renderer (React UI).
// Also consumed by the preload bridge and the Python sidecar via the WS API.
// ─────────────────────────────────────────────────────────────────────────────

// ---------------------------------------------------------------------------
// Sidecar / WebSocket message shapes
// ---------------------------------------------------------------------------

/** Every message on the WebSocket wire has a `type` discriminant. */
export type WsMessageType =
  | 'transcript'
  | 'verse_suggestion'
  | 'lyric_suggestion'
  | 'status'
  | 'error'

export interface WsMessage<T = unknown> {
  type: WsMessageType
  payload: T
}

/** A partial or final transcript chunk from the STT engine. */
export interface TranscriptPayload {
  text: string
  /** true = this chunk is stable; false = still being refined */
  isFinal: boolean
  /** Cumulative session transcript so far */
  fullText: string
}

// ---------------------------------------------------------------------------
// Suggestions
// ---------------------------------------------------------------------------

export type SuggestionKind = 'explicit' | 'semantic' | 'lyric'

export interface VerseReference {
  book: string
  chapter: number
  verse: number
  /** Optional end verse for ranges, e.g. John 3:16-17 */
  verseEnd?: number
}

export interface VerseText {
  reference: VerseReference
  /** Translation identifier, e.g. "KJV", "NIV", "ESV" */
  translation: string
  text: string
}

export interface VerseSuggestion {
  id: string
  kind: SuggestionKind
  /** The verse reference + text */
  verse: VerseText
  /** Similarity score 0–1 (1 = exact match / highest semantic similarity) */
  score: number
  /** Snippet of transcript that triggered this suggestion */
  triggerText: string
}

export interface LyricSuggestion {
  id: string
  kind: 'lyric'
  songTitle: string
  artist?: string
  /** The matched lyric lines */
  lines: string[]
  score: number
  triggerText: string
}

export type Suggestion = VerseSuggestion | LyricSuggestion

// ---------------------------------------------------------------------------
// IPC channel names (keep in sync with preload/index.ts)
// ---------------------------------------------------------------------------

export type CaptureMode = 'sermon' | 'worship'

// ---------------------------------------------------------------------------
// Speaker training
// ---------------------------------------------------------------------------

export interface TrainingStatus {
  sampleCount: number
  isTraining: boolean
  progress: number        // 0–100
  hasCustomModel: boolean
  lastError: string | null
}

export const IPC = {
  // Renderer → Main
  START_LISTENING: 'sidecar:start-listening',
  STOP_LISTENING: 'sidecar:stop-listening',
  SET_MODE: 'sidecar:set-mode',
  TRAINING_SAVE_SAMPLE: 'training:save-sample',
  TRAINING_GET_STATUS: 'training:get-status',
  TRAINING_START: 'training:start',
  // Main → Renderer (push)
  TRAINING_ON_PROGRESS: 'training:on-progress',
  SEND_TO_PRESENTATION: 'presentation:send',
  GET_SETTINGS: 'settings:get',
  SET_SETTINGS: 'settings:set',
  GET_AUDIO_DEVICES: 'sidecar:get-audio-devices',
  APP_PICK_PATH: 'app:pick-path',
  APP_CHECK_LAUNCH: 'app:check-launch',

  // Main → Renderer (push events)
  ON_TRANSCRIPT: 'sidecar:on-transcript',
  ON_SUGGESTION: 'sidecar:on-suggestion',
  ON_STATUS: 'sidecar:on-status',
  ON_ERROR: 'sidecar:on-error',
  GET_STATUS: 'sidecar:get-status',
} as const

/** Result returned by the app:check-launch IPC call. */
export interface AppLaunchStatus {
  /** The app was already running before we checked. */
  running: boolean
  /** We just launched it (it was not running before). */
  launched: boolean
}

/** Audio input device descriptor returned by get_audio_devices. */
export interface AudioDevice {
  index: number
  name: string
  channels: number
  sampleRate: number
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export type PresentationDriver =
  | 'propresenter'
  | 'easyworship'
  | 'powerpoint'
  | 'keynote'
  | 'openlp'
  | 'none'

export interface AppSettings {
  /** WebSocket port the Python sidecar listens on */
  sidecarPort: number
  /** Which presentation software to drive */
  presentationDriver: PresentationDriver
  /** Absolute path to the presentation app executable / .app bundle */
  presentationAppPath: string
  /** Bible translations to show, in preference order */
  translations: string[]
  /** Max number of suggestions to display */
  maxSuggestions: number
  /** Min semantic similarity score to surface a suggestion (0–1) */
  semanticThreshold: number
  /** Show lyric suggestions */
  lyricsEnabled: boolean
  /** Audio input device label (empty = system default) */
  audioDevice: string
  /** True once the user has closed the settings panel at least once */
  setupCompleted: boolean
}

export const DEFAULT_SETTINGS: AppSettings = {
  sidecarPort: 8765,
  presentationDriver: 'none',
  presentationAppPath: '',
  translations: ['KJV'],
  maxSuggestions: 5,
  semanticThreshold: 0.45,
  lyricsEnabled: true,
  audioDevice: '',
  setupCompleted: false,
}
