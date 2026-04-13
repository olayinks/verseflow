// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/components/SuggestionCard.tsx
//
// Renders a single verse or lyric suggestion.
// Clicking the card sends it to the active presentation driver.
// ─────────────────────────────────────────────────────────────────────────────

import { clsx } from 'clsx'
import { BookOpen, Music, Send, Zap } from 'lucide-react'
import type { Suggestion, VerseSuggestion, LyricSuggestion } from '@shared/types'

interface Props {
  suggestion: Suggestion
  isActive: boolean
  onClick: (s: Suggestion) => void
  onSend: (text: string) => void
}

function kindIcon(kind: Suggestion['kind']): React.ReactElement {
  switch (kind) {
    case 'explicit':
      return <Zap size={11} className="text-amber-400" />
    case 'semantic':
      return <BookOpen size={11} className="text-brand-400" />
    case 'lyric':
      return <Music size={11} className="text-fuchsia-400" />
  }
}

function kindLabel(kind: Suggestion['kind']): string {
  switch (kind) {
    case 'explicit':
      return 'Explicit match'
    case 'semantic':
      return 'Semantic match'
    case 'lyric':
      return 'Lyric match'
  }
}

function renderVerse(s: VerseSuggestion): React.ReactElement {
  const { book, chapter, verse, verseEnd } = s.verse.reference
  const ref = verseEnd ? `${book} ${chapter}:${verse}–${verseEnd}` : `${book} ${chapter}:${verse}`
  return (
    <>
      <div className="flex items-center justify-between mb-1">
        <span className="font-semibold text-zinc-100 text-sm">{ref}</span>
        <span className="text-[10px] text-zinc-500 uppercase tracking-wider">{s.verse.translation}</span>
      </div>
      <p className="text-xs text-zinc-300 leading-relaxed selectable line-clamp-3">{s.verse.text}</p>
    </>
  )
}

function renderLyric(s: LyricSuggestion): React.ReactElement {
  return (
    <>
      <div className="flex items-center justify-between mb-1">
        <span className="font-semibold text-zinc-100 text-sm">{s.songTitle}</span>
        {s.artist && <span className="text-[10px] text-zinc-500 truncate ml-2">{s.artist}</span>}
      </div>
      <p className="text-xs text-zinc-300 leading-relaxed selectable line-clamp-3 italic">
        {s.lines.join(' / ')}
      </p>
    </>
  )
}

export function SuggestionCard({ suggestion: s, isActive, onClick, onSend }: Props): React.ReactElement {
  const scorePercent = Math.round(s.score * 100)

  const sendText =
    s.kind === 'lyric'
      ? (s as LyricSuggestion).lines.join('\n')
      : (s as VerseSuggestion).verse.text

  const handleSend = (e: React.MouseEvent): void => {
    e.stopPropagation()
    onSend(sendText)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onClick(s)}
      onKeyDown={(e) => e.key === 'Enter' && onClick(s)}
      className={clsx(
        'group rounded-[var(--radius-card)] p-3 cursor-pointer transition-all',
        'border border-transparent',
        isActive
          ? 'bg-[var(--color-surface-2)] border-[var(--color-glass-border)]'
          : 'hover:bg-[var(--color-surface-1)]',
      )}
    >
      {/* Header row — send icon appears on hover */}
      <div className="flex items-center gap-1.5 mb-2">
        {kindIcon(s.kind)}
        <span className="text-[10px] text-zinc-500">{kindLabel(s.kind)}</span>
        <span className="text-[10px] text-zinc-600">{scorePercent}%</span>
        <button
          type="button"
          onClick={handleSend}
          title="Send to presentation"
          className={clsx(
            'ml-auto flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium transition-all',
            'bg-brand-500/20 text-brand-300 hover:bg-brand-500/40',
            'opacity-0 group-hover:opacity-100',
            isActive && 'opacity-100',
          )}
        >
          <Send size={9} />
          Send
        </button>
      </div>

      {/* Content */}
      {s.kind === 'lyric' ? renderLyric(s as LyricSuggestion) : renderVerse(s as VerseSuggestion)}
    </div>
  )
}
