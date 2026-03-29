// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/App.tsx
//
// Root component.  Mounts all sub-panels and wires up the sidecar hook.
//
// Layout (top-to-bottom):
//   ┌─────────────────────────────┐
//   │  Title bar (drag handle)    │
//   ├─────────────────────────────┤
//   │  StatusBar  [Listen btn]    │
//   ├─────────────────────────────┤
//   │  TranscriptPane             │
//   ├─────────────────────────────┤
//   │  SuggestionList  (scroll)   │
//   └─────────────────────────────┘
//   SettingsPanel (absolute overlay, slides in from right)
// ─────────────────────────────────────────────────────────────────────────────

import { useCallback } from 'react'
import { Minus, Settings, X } from 'lucide-react'
import { useSidecar } from './hooks/useSidecar'
import { useKeyboard } from './hooks/useKeyboard'
import { useAppStore } from './store'
import { StatusBar } from './components/StatusBar'
import { TranscriptPane } from './components/TranscriptPane'
import { SuggestionList } from './components/SuggestionList'
import { SettingsPanel } from './components/SettingsPanel'

// Detect Windows — show custom close/minimize buttons on frameless window.
// macOS renders native traffic lights automatically.
const isWindows = navigator.userAgent.includes('Windows')

export default function App(): React.ReactElement {
  const { startListening, stopListening } = useSidecar()
  const { setSettingsPanelOpen } = useAppStore()

  useKeyboard()

  const handleSend = useCallback(async (text: string) => {
    await window.verseflow.sendToPresentation(text)
  }, [])

  const iconBtnCls =
    'p-1.5 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-white/10 transition-colors'

  return (
    <div
      className="relative flex flex-col h-full rounded-[var(--radius-panel)] overflow-hidden"
      style={{
        background: 'var(--color-glass-bg)',
        backdropFilter: 'var(--blur-glass)',
        WebkitBackdropFilter: 'var(--blur-glass)',
        border: '1px solid var(--color-glass-border)',
      }}
    >
      {/* ── Drag handle / title bar ─────────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-4 pt-3 pb-2"
        style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
      >
        <div className="flex items-center gap-2">
          <span className="text-brand-400 font-bold text-sm tracking-tight">VerseFlow</span>
        </div>

        {/* Window controls — no-drag so clicks register */}
        <div
          className="flex items-center gap-0.5"
          style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        >
          <button
            onClick={() => setSettingsPanelOpen(true)}
            className={iconBtnCls}
            aria-label="Open settings"
          >
            <Settings size={13} />
          </button>

          {isWindows && (
            <>
              <button
                onClick={() => window.verseflow.minimizeWindow()}
                className={iconBtnCls}
                aria-label="Minimize"
              >
                <Minus size={13} />
              </button>
              <button
                onClick={() => window.verseflow.closeWindow()}
                className="p-1.5 rounded-md text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                aria-label="Close"
              >
                <X size={13} />
              </button>
            </>
          )}
        </div>
      </div>

      {/* ── Status + mic control ────────────────────────────────────────── */}
      <StatusBar onStart={startListening} onStop={stopListening} />

      {/* ── Live transcript ─────────────────────────────────────────────── */}
      <TranscriptPane />

      {/* ── Divider ─────────────────────────────────────────────────────── */}
      <div className="mx-4 h-px bg-[var(--color-glass-border)]" />

      {/* ── Suggestion list ─────────────────────────────────────────────── */}
      <SuggestionList onSend={handleSend} />

      {/* ── Settings panel (absolute overlay) ───────────────────────────── */}
      <SettingsPanel />
    </div>
  )
}
