// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/components/StatusBar.tsx
// Shows sidecar connection / engine-load state + start/stop button.
// ─────────────────────────────────────────────────────────────────────────────

import { Loader2, Mic, Radio, WifiOff } from 'lucide-react'
import { clsx } from 'clsx'
import { useAppStore } from '../store'
import type { EngineState } from '../store'
import type { CaptureMode } from '@shared/types'

interface Props {
  onStart: () => Promise<void>
  onStop: () => Promise<void>
}

const MODES: { value: CaptureMode; label: string }[] = [
  { value: 'sermon', label: 'Sermon' },
  { value: 'worship', label: 'Worship' },
]

// ── Status dot ────────────────────────────────────────────────────────────────

function StatusDot({ state }: { state: EngineState }): React.ReactElement {
  return (
    <span
      className={clsx('size-2 rounded-full shrink-0', {
        'bg-zinc-600':                                   state === 'disconnected',
        'bg-amber-400 animate-pulse shadow-[0_0_6px_theme(colors.amber.400)]': state === 'loading',
        'bg-emerald-400 shadow-[0_0_6px_theme(colors.emerald.400)]':           state === 'ready',
        'bg-rose-500 shadow-[0_0_6px_theme(colors.rose.500)]':                 state === 'error',
      })}
    />
  )
}

// ── Loading bar shown while engines initialise ─────────────────────────────

function LoadingBar(): React.ReactElement {
  return <div className="h-0.5 w-full bg-amber-400/50 animate-pulse" />
}

// ── Main component ────────────────────────────────────────────────────────────

export function StatusBar({ onStart, onStop }: Props): React.ReactElement {
  const { status, engineState, isListening, captureMode, setCaptureMode } = useAppStore()

  const canListen = engineState === 'ready'

  const handleToggle = (): void => {
    if (!canListen) return
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
      {/* Top row: status dot + message + mic button */}
      <div className="flex items-center gap-3 px-4 pt-3 pb-2">
        <StatusDot state={engineState} />

        <span className="flex items-center gap-1.5 flex-1 text-xs truncate">
          {engineState === 'loading' && (
            <Loader2 size={11} className="shrink-0 text-amber-400 animate-spin" />
          )}
          {engineState === 'disconnected' && (
            <WifiOff size={11} className="shrink-0 text-zinc-500" />
          )}
          <span
            className={clsx('truncate', {
              'text-zinc-400':  engineState === 'ready' || engineState === 'disconnected',
              'text-amber-300': engineState === 'loading',
              'text-rose-400':  engineState === 'error',
            })}
          >
            {status.message}
          </span>
        </span>

        <button
          type="button"
          onClick={handleToggle}
          disabled={!canListen}
          title={!canListen ? 'Waiting for engines to load…' : undefined}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
            !canListen && 'opacity-40 cursor-not-allowed',
            canListen && isListening && 'bg-rose-500/20 text-rose-300 hover:bg-rose-500/30',
            canListen && !isListening && 'bg-brand-500/20 text-brand-300 hover:bg-brand-500/30',
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

      {/* Indeterminate progress bar while engines load */}
      {engineState === 'loading' && <LoadingBar />}

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
