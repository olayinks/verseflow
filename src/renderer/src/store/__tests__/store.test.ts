import { describe, it, expect, beforeEach } from 'vitest'
import { useAppStore } from '../index'
import type { VerseSuggestion, LyricSuggestion, AppSettings } from '@shared/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SETTINGS: AppSettings = {
  sidecarPort: 8765,
  presentationDriver: 'none',
  presentationAppPath: '',
  translations: ['KJV'],
  maxSuggestions: 3,
  semanticThreshold: 0.6,
  lyricsEnabled: true,
  audioDevice: '',
  setupCompleted: false,
}

const makeVerse = (id: string): VerseSuggestion => ({
  id,
  kind: 'explicit',
  score: 1.0,
  triggerText: 'John 3:16',
  verse: {
    reference: { book: 'John', chapter: 3, verse: 16 },
    translation: 'KJV',
    text: 'For God so loved the world',
  },
})

const makeLyric = (id: string): LyricSuggestion => ({
  id,
  kind: 'lyric',
  songTitle: 'Amazing Grace',
  lines: ['Amazing grace how sweet the sound'],
  score: 0.9,
  triggerText: 'amazing grace',
})

// ---------------------------------------------------------------------------
// Reset store before each test
// ---------------------------------------------------------------------------

beforeEach(() => {
  useAppStore.setState({
    status: { connected: false, message: 'Initialising…' },
    isListening: false,
    transcript: null,
    suggestions: [],
    activeSuggestion: null,
    settings: null,
    settingsPanelOpen: false,
  })
})

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

describe('setStatus', () => {
  it('updates connected and message', () => {
    useAppStore.getState().setStatus({ connected: true, message: 'Ready' })
    const { status } = useAppStore.getState()
    expect(status.connected).toBe(true)
    expect(status.message).toBe('Ready')
  })
})

// ---------------------------------------------------------------------------
// Listening
// ---------------------------------------------------------------------------

describe('setListening', () => {
  it('sets isListening true', () => {
    useAppStore.getState().setListening(true)
    expect(useAppStore.getState().isListening).toBe(true)
  })

  it('clears suggestions and transcript when stopping', () => {
    useAppStore.setState({ suggestions: [makeVerse('v1')], transcript: { text: 'hi', isFinal: true, fullText: 'hi' } })
    useAppStore.getState().setListening(false)
    const { suggestions, transcript } = useAppStore.getState()
    expect(suggestions).toHaveLength(0)
    expect(transcript).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Suggestions
// ---------------------------------------------------------------------------

describe('addSuggestion', () => {
  beforeEach(() => {
    useAppStore.setState({ settings: SETTINGS })
  })

  it('adds a verse suggestion', () => {
    useAppStore.getState().addSuggestion(makeVerse('v1'))
    expect(useAppStore.getState().suggestions).toHaveLength(1)
  })

  it('adds a lyric suggestion', () => {
    useAppStore.getState().addSuggestion(makeLyric('l1'))
    expect(useAppStore.getState().suggestions).toHaveLength(1)
  })

  it('does not add duplicate ids', () => {
    useAppStore.getState().addSuggestion(makeVerse('v1'))
    useAppStore.getState().addSuggestion(makeVerse('v1'))
    expect(useAppStore.getState().suggestions).toHaveLength(1)
  })

  it('prepends new suggestions (newest first)', () => {
    useAppStore.getState().addSuggestion(makeVerse('v1'))
    useAppStore.getState().addSuggestion(makeVerse('v2'))
    expect(useAppStore.getState().suggestions[0].id).toBe('v2')
  })

  it('respects maxSuggestions cap', () => {
    // maxSuggestions = 3
    for (let i = 0; i < 5; i++) useAppStore.getState().addSuggestion(makeVerse(`v${i}`))
    expect(useAppStore.getState().suggestions).toHaveLength(3)
  })

  it('falls back to 5 when settings is null', () => {
    useAppStore.setState({ settings: null })
    for (let i = 0; i < 7; i++) useAppStore.getState().addSuggestion(makeVerse(`v${i}`))
    expect(useAppStore.getState().suggestions).toHaveLength(5)
  })
})

describe('clearSuggestions', () => {
  it('empties the list', () => {
    useAppStore.setState({ suggestions: [makeVerse('v1'), makeVerse('v2')] })
    useAppStore.getState().clearSuggestions()
    expect(useAppStore.getState().suggestions).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// Active suggestion
// ---------------------------------------------------------------------------

describe('setActiveSuggestion', () => {
  it('sets a suggestion as active', () => {
    const s = makeVerse('v1')
    useAppStore.getState().setActiveSuggestion(s)
    expect(useAppStore.getState().activeSuggestion?.id).toBe('v1')
  })

  it('clears active suggestion', () => {
    useAppStore.setState({ activeSuggestion: makeVerse('v1') })
    useAppStore.getState().setActiveSuggestion(null)
    expect(useAppStore.getState().activeSuggestion).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Settings panel
// ---------------------------------------------------------------------------

describe('setSettingsPanelOpen', () => {
  it('opens the panel', () => {
    useAppStore.getState().setSettingsPanelOpen(true)
    expect(useAppStore.getState().settingsPanelOpen).toBe(true)
  })

  it('closes the panel', () => {
    useAppStore.setState({ settingsPanelOpen: true })
    useAppStore.getState().setSettingsPanelOpen(false)
    expect(useAppStore.getState().settingsPanelOpen).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

describe('setSettings', () => {
  it('stores the full settings object', () => {
    useAppStore.getState().setSettings(SETTINGS)
    expect(useAppStore.getState().settings?.presentationDriver).toBe('none')
    expect(useAppStore.getState().settings?.maxSuggestions).toBe(3)
  })
})
