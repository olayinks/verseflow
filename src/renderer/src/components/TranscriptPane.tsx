// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/components/TranscriptPane.tsx
// Shows the rolling live transcript from the STT engine.
// ─────────────────────────────────────────────────────────────────────────────

import { clsx } from 'clsx'
import { useAppStore } from '../store'

export function TranscriptPane(): React.ReactElement {
  const transcript = useAppStore((s) => s.transcript)

  return (
    <div className="px-4 py-3 min-h-[64px]">
      <p className="text-[11px] uppercase tracking-widest text-zinc-500 mb-1">Live transcript</p>
      {transcript ? (
        <p
          className={clsx(
            'text-sm leading-snug selectable',
            transcript.isFinal ? 'text-zinc-100' : 'text-zinc-400 italic',
          )}
        >
          {transcript.text || <span className="opacity-40">Listening…</span>}
        </p>
      ) : (
        <p className="text-sm text-zinc-600 italic">Transcript will appear here.</p>
      )}
    </div>
  )
}
