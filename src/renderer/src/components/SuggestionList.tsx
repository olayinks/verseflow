// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/components/SuggestionList.tsx
// Scrollable list of SuggestionCards.
// ─────────────────────────────────────────────────────────────────────────────

import { useAppStore } from '../store'
import { SuggestionCard } from './SuggestionCard'
import type { Suggestion } from '@shared/types'

interface Props {
  onSend: (text: string) => void
}

export function SuggestionList({ onSend }: Props): React.ReactElement {
  const { suggestions, activeSuggestion, setActiveSuggestion } = useAppStore()

  const handleClick = (s: Suggestion): void => {
    setActiveSuggestion(activeSuggestion?.id === s.id ? null : s)
  }

  if (suggestions.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-600 text-sm italic px-4 text-center">
        Suggestions will appear here as the sermon progresses.
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto px-2 py-2 flex flex-col gap-1">
      {suggestions.map((s) => (
        <SuggestionCard
          key={s.id}
          suggestion={s}
          isActive={activeSuggestion?.id === s.id}
          onClick={handleClick}
          onSend={onSend}
        />
      ))}
    </div>
  )
}
