// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/components/StatusBar.tsx
// Shows sidecar connection status + start/stop button.
// ─────────────────────────────────────────────────────────────────────────────

import { Mic, Radio } from 'lucide-react'
import { clsx } from 'clsx'
import { useAppStore } from '../store'

interface Props {
  onStart: () => Promise<void>
  onStop: () => Promise<void>
}

export function StatusBar({ onStart, onStop }: Props): React.ReactElement {
  const { status, isListening } = useAppStore()

  const handleToggle = (): void => {
    if (isListening) {
      onStop().catch(console.error)
    } else {
      onStart().catch(console.error)
    }
  }

  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-glass-border)]">
      {/* Connection dot */}
      <span
        className={clsx(
          'size-2 rounded-full shrink-0',
          status.connected ? 'bg-emerald-400 shadow-[0_0_6px_theme(colors.emerald.400)]' : 'bg-zinc-500',
        )}
      />

      {/* Status message */}
      <span className="flex-1 text-xs text-zinc-400 truncate">{status.message}</span>

      {/* Mic toggle button */}
      <button
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
  )
}
