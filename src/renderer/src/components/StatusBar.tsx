// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/components/StatusBar.tsx
// Shows sidecar connection status + start/stop button.
// ─────────────────────────────────────────────────────────────────────────────

import { Mic, Radio } from 'lucide-react'
import { clsx } from 'clsx'
import { useAppStore } from '../store'
import type { CaptureMode } from '@shared/types'

interface Props {
  onStart: () => Promise<void>
  onStop: () => Promise<void>
}

const MODES: { value: CaptureMode; label: string }[] = [
  { value: 'sermon', label: 'Sermon' },
  { value: 'worship', label: 'Worship' },
]

export function StatusBar({ onStart, onStop }: Props): React.ReactElement {
  const { status, isListening, captureMode, setCaptureMode } = useAppStore()

  const handleToggle = (): void => {
    if (isListening) {
      onStop().catch(console.error)
    } else {
      onStart().catch(console.error)
    }
  }

  const handleModeChange = (mode: CaptureMode): void => {
    setCaptureMode(mode)
    window.verseflow.setMode(mode).catch(console.error)
  }

  return (
    <div className="flex flex-col border-b border-[var(--color-glass-border)]">
      {/* Top row: connection + mic button */}
      <div className="flex items-center gap-3 px-4 pt-3 pb-2">
        <span
          className={clsx(
            'size-2 rounded-full shrink-0',
            status.connected ? 'bg-emerald-400 shadow-[0_0_6px_theme(colors.emerald.400)]' : 'bg-zinc-500',
          )}
        />
        <span className="flex-1 text-xs text-zinc-400 truncate">{status.message}</span>
        <button
          type="button"
          onClick={handleToggle}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
            isListening
              ? 'bg-rose-500/20 text-rose-300 hover:bg-rose-500/30'
              : 'bg-brand-500/20 text-brand-300 hover:bg-brand-500/30',
          )}
        >
          {isListening ? (
            <>
              <Radio size={12} className="animate-pulse" />
              Stop
            </>
          ) : (
            <>
              <Mic size={12} />
              Listen
            </>
          )}
        </button>
      </div>

      {/* Mode toggle pill */}
      <div className="flex items-center px-4 pb-2.5">
        <div className="flex rounded-md overflow-hidden border border-[var(--color-glass-border)] text-[11px]">
          {MODES.map((m) => (
            <button
              key={m.value}
              type="button"
              onClick={() => handleModeChange(m.value)}
              className={clsx(
                'px-3 py-1 transition-colors',
                captureMode === m.value
                  ? 'bg-brand-500/30 text-brand-300'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5',
              )}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
