// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/components/SettingsPanel.tsx
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useRef, useState } from 'react'
import { FolderOpen, X } from 'lucide-react'
import { clsx } from 'clsx'
import { useAppStore } from '../store'
import type { AppSettings, AudioDevice, AppLaunchStatus, PresentationDriver } from '@shared/types'

const DRIVERS: { value: PresentationDriver; label: string }[] = [
  { value: 'none', label: 'None (disabled)' },
  { value: 'propresenter', label: 'ProPresenter' },
  { value: 'easyworship', label: 'EasyWorship' },
  { value: 'powerpoint', label: 'PowerPoint' },
  { value: 'keynote', label: 'Keynote' },
  { value: 'openlp', label: 'OpenLP' },
]

function Label({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <p className="text-[11px] uppercase tracking-widest text-zinc-500 mb-1.5">{children}</p>
  )
}

const inputCls =
  'w-full rounded-lg px-3 py-2 text-sm bg-[var(--color-surface-2)] border border-[var(--color-glass-border)] text-zinc-100 focus:outline-none focus:border-brand-400 transition-colors'

type LaunchState = 'idle' | 'checking' | 'running' | 'launched' | 'error'

const LAUNCH_LABEL: Record<LaunchState, string> = {
  idle: 'Check status',
  checking: 'Checking…',
  running: 'Running',
  launched: 'Launching…',
  error: 'Could not launch',
}

const LAUNCH_DOT: Record<LaunchState, string> = {
  idle: 'bg-zinc-500',
  checking: 'bg-yellow-400 animate-pulse',
  running: 'bg-green-400',
  launched: 'bg-yellow-400 animate-pulse',
  error: 'bg-red-400',
}

export function SettingsPanel(): React.ReactElement {
  const { settingsPanelOpen, setSettingsPanelOpen, settings, setSettings } = useAppStore()
  const [audioDevices, setAudioDevices] = useState<AudioDevice[]>([])
  const [devicesLoading, setDevicesLoading] = useState(false)
  const [launchState, setLaunchState] = useState<LaunchState>('idle')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Fetch audio devices the first time the panel opens.
  useEffect(() => {
    if (!settingsPanelOpen || audioDevices.length > 0) return
    setDevicesLoading(true)
    window.verseflow
      .getAudioDevices()
      .then(setAudioDevices)
      .catch(console.error)
      .finally(() => setDevicesLoading(false))
  }, [settingsPanelOpen])

  // Auto-check app status whenever the panel opens with a path configured.
  useEffect(() => {
    if (!settingsPanelOpen || !settings?.presentationAppPath) return
    checkLaunch()
  }, [settingsPanelOpen])

  // Cleanup pending debounce on unmount.
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  if (!settings) return <></>

  const save = (partial: Partial<AppSettings>): void => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      window.verseflow
        .setSettings(partial)
        .then(setSettings)
        .catch(console.error)
    }, 400)
  }

  const close = (): void => {
    // Mark setup as completed the first time the user closes the panel.
    if (!settings.setupCompleted) {
      window.verseflow.setSettings({ setupCompleted: true }).then(setSettings).catch(console.error)
    }
    setSettingsPanelOpen(false)
  }

  const handleBrowse = async (): Promise<void> => {
    const path = await window.verseflow.pickAppPath()
    if (!path) return
    const updated = await window.verseflow.setSettings({ presentationAppPath: path })
    setSettings(updated)
    setLaunchState('idle')
    // Auto-check after picking a new path.
    checkLaunchFor(path)
  }

  const checkLaunch = (): void => checkLaunchFor(settings.presentationAppPath)

  const checkLaunchFor = (appPath: string): void => {
    if (!appPath) return
    setLaunchState('checking')
    window.verseflow
      .checkAndLaunchApp()
      .then((status: AppLaunchStatus) => {
        setLaunchState(status.running ? 'running' : 'launched')
      })
      .catch(() => setLaunchState('error'))
  }

  const showAppPath = settings.presentationDriver !== 'none'

  return (
    <div
      className={clsx(
        'absolute inset-0 z-20 flex flex-col transition-transform duration-300 ease-in-out',
        settingsPanelOpen ? 'translate-x-0' : 'translate-x-full',
      )}
      style={{
        background: 'var(--color-glass-bg)',
        backdropFilter: 'var(--blur-glass)',
        WebkitBackdropFilter: 'var(--blur-glass)',
      }}
      aria-hidden={settingsPanelOpen ? undefined : 'true'}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-3 pb-2 border-b border-[var(--color-glass-border)]">
        <span className="text-sm font-semibold text-zinc-100">Settings</span>
        <button
          type="button"
          onClick={close}
          className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-white/10 transition-colors"
          aria-label="Close settings"
        >
          <X size={14} />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-5">

        {/* Audio device */}
        <div>
          <Label>Audio Input Device</Label>
          <select
            aria-label="Audio input device"
            className={inputCls}
            value={settings.audioDevice}
            onChange={(e) => save({ audioDevice: e.target.value })}
            disabled={devicesLoading}
          >
            <option value="">
              {devicesLoading ? 'Loading devices…' : 'System default'}
            </option>
            {audioDevices.map((d) => (
              <option key={d.index} value={d.name}>
                {d.name}
              </option>
            ))}
          </select>
        </div>

        {/* Presentation driver */}
        <div>
          <Label>Presentation Software</Label>
          <select
            aria-label="Presentation software"
            className={inputCls}
            value={settings.presentationDriver}
            onChange={(e) => {
              save({ presentationDriver: e.target.value as PresentationDriver })
              setLaunchState('idle')
            }}
          >
            {DRIVERS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </div>

        {/* Application path — only shown when a driver is selected */}
        {showAppPath && (
          <div>
            <Label>Application Path</Label>
            <div className="flex gap-2">
              <input
                type="text"
                readOnly
                className={clsx(inputCls, 'flex-1 truncate cursor-default text-zinc-400')}
                value={settings.presentationAppPath}
                placeholder="No application selected"
              />
              <button
                type="button"
                onClick={handleBrowse}
                aria-label="Browse for application"
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-[var(--color-surface-2)] border border-[var(--color-glass-border)] text-zinc-300 hover:text-zinc-100 hover:border-brand-400 transition-colors shrink-0"
              >
                <FolderOpen size={13} />
                Browse
              </button>
            </div>

            {/* Launch status */}
            {settings.presentationAppPath && (
              <div className="mt-2 flex items-center gap-2">
                <span className={clsx('size-2 rounded-full shrink-0', LAUNCH_DOT[launchState])} />
                <span className="text-xs text-zinc-400 flex-1">{LAUNCH_LABEL[launchState]}</span>
                {(launchState === 'idle' || launchState === 'error') && (
                  <button
                    type="button"
                    onClick={checkLaunch}
                    className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
                  >
                    {launchState === 'error' ? 'Retry' : 'Launch'}
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Semantic threshold */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <Label>Semantic Threshold</Label>
            <span className="text-xs text-zinc-400 tabular-nums">
              {settings.semanticThreshold.toFixed(2)}
            </span>
          </div>
          <input
            type="range"
            aria-label="Semantic threshold"
            min="0"
            max="1"
            step="0.05"
            value={settings.semanticThreshold}
            onChange={(e) => save({ semanticThreshold: parseFloat(e.target.value) })}
            className="w-full accent-brand-400 cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-zinc-600 mt-0.5">
            <span>Broad</span>
            <span>Precise</span>
          </div>
        </div>

        {/* Max suggestions */}
        <div>
          <Label>Max Suggestions</Label>
          <input
            type="number"
            aria-label="Max suggestions"
            min={1}
            max={20}
            className={inputCls}
            value={settings.maxSuggestions}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10)
              if (v >= 1 && v <= 20) save({ maxSuggestions: v })
            }}
          />
        </div>

        {/* Lyrics toggle */}
        <div>
          <Label>Lyric Suggestions</Label>
          <button
            type="button"
            role="switch"
            aria-label="Toggle lyric suggestions"
            aria-checked={settings.lyricsEnabled ? 'true' : 'false'}
            onClick={() => {
              const next = !settings.lyricsEnabled
              if (debounceRef.current) clearTimeout(debounceRef.current)
              window.verseflow
                .setSettings({ lyricsEnabled: next })
                .then(setSettings)
                .catch(console.error)
            }}
            className={clsx(
              'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none',
              settings.lyricsEnabled ? 'bg-brand-500' : 'bg-zinc-600',
            )}
          >
            <span
              className={clsx(
                'inline-block size-4 rounded-full bg-white shadow transition-transform',
                settings.lyricsEnabled ? 'translate-x-6' : 'translate-x-1',
              )}
            />
          </button>
        </div>

      </div>
    </div>
  )
}
