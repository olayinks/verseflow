// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/hooks/useKeyboard.ts
//
// Global keyboard shortcuts for the overlay.
//
//   ArrowDown / ArrowUp  — cycle through suggestion cards
//   Enter                — send the active suggestion to presentation
//   Escape               — deselect active card, or close settings panel
//
// Registered once in App.tsx. Reads store state at event time via getState()
// so the listener never needs re-registration when suggestions change.
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect } from 'react'
import { useAppStore } from '../store'
import type { LyricSuggestion, VerseSuggestion } from '@shared/types'

export function useKeyboard(): void {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      const {
        suggestions,
        activeSuggestion,
        setActiveSuggestion,
        settingsPanelOpen,
        setSettingsPanelOpen,
        helpPanelOpen,
        setHelpPanelOpen,
      } = useAppStore.getState()

      if (e.key === 'Escape') {
        if (helpPanelOpen) {
          setHelpPanelOpen(false)
        } else if (settingsPanelOpen) {
          setSettingsPanelOpen(false)
        } else {
          setActiveSuggestion(null)
        }
        return
      }

      // Remaining shortcuts only apply when no panel is open.
      if (settingsPanelOpen || helpPanelOpen || suggestions.length === 0) return

      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        const currentIdx = activeSuggestion
          ? suggestions.findIndex((s) => s.id === activeSuggestion.id)
          : -1
        const next =
          e.key === 'ArrowDown'
            ? (currentIdx + 1) % suggestions.length
            : (currentIdx - 1 + suggestions.length) % suggestions.length
        setActiveSuggestion(suggestions[next])
        return
      }

      if (e.key === 'Enter' && activeSuggestion) {
        e.preventDefault()
        const text =
          activeSuggestion.kind === 'lyric'
            ? (activeSuggestion as LyricSuggestion).lines.join('\n')
            : (activeSuggestion as VerseSuggestion).verse.text
        window.verseflow.sendToPresentation(text).catch(console.error)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])
}
