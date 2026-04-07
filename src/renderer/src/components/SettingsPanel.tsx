// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/components/SettingsPanel.tsx
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useRef, useState } from 'react'
import { FolderOpen, Mic, MicOff, Circle, Square, Brain, X } from 'lucide-react'
import { clsx } from 'clsx'
import { useAppStore } from '../store'
import type { AppSettings, AudioDevice, AppLaunchStatus, PresentationDriver, TrainingStatus } from '@shared/types'

// ── WAV encoding helpers ──────────────────────────────────────────────────────

function writeString(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
}

function encodeWav(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const buf = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buf)
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)   // PCM
  view.setUint16(22, 1, true)   // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, samples.length * 2, true)
  let off = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    off += 2
  }
  return buf
}

async function resampleTo16k(blob: Blob): Promise<Float32Array> {
  const arrayBuf = await blob.arrayBuffer()
  const ctx = new OfflineAudioContext(1, 1, 16_000)
  const decoded = await new AudioContext().decodeAudioData(arrayBuf)
  const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * 16_000), 16_000)
  const src = offline.createBufferSource()
  src.buffer = decoded
  src.connect(offline.destination)
  src.start(0)
  const rendered = await offline.startRendering()
  return rendered.getChannelData(0)
}

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
  const [testState, setTestState] = useState<'idle' | 'testing' | 'error'>('idle')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Speaker training state ──────────────────────────────────────────────
  const [trainingStatus, setTrainingStatus] = useState<TrainingStatus | null>(null)
  const [recordState, setRecordState] = useState<'idle' | 'recording' | 'recorded'>('idle')
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)
  const [transcript, setTranscript] = useState('')
  const [savingState, setSavingState] = useState<'idle' | 'saving' | 'saved'>('idle')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const recordChunksRef = useRef<BlobPart[]>([])
  const [monitorVolume, setMonitorVolume] = useState(0.8)
  const audioTestRef = useRef<{
    stream: MediaStream
    ctx: AudioContext
    gain: GainNode
    animFrame: number
  } | null>(null)
  const levelBarRef = useRef<HTMLDivElement>(null)

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

  // Stop audio test when panel closes or component unmounts.
  useEffect(() => {
    if (!settingsPanelOpen) stopAudioTest()
  }, [settingsPanelOpen])

  useEffect(() => {
    return () => stopAudioTest()
  }, [])

  const stopAudioTest = (): void => {
    if (audioTestRef.current) {
      cancelAnimationFrame(audioTestRef.current.animFrame)
      audioTestRef.current.stream.getTracks().forEach((t) => t.stop())
      audioTestRef.current.ctx.close()
      audioTestRef.current = null
    }
    setTestState('idle')
    if (levelBarRef.current) levelBarRef.current.style.width = '0%'
  }

  // ── Training logic ────────────────────────────────────────────────────────

  // Load training status whenever the panel opens.
  useEffect(() => {
    if (!settingsPanelOpen) return
    window.verseflow.getTrainingStatus().then(setTrainingStatus).catch(console.error)
    const unsub = window.verseflow.onTrainingProgress(setTrainingStatus)
    return unsub
  }, [settingsPanelOpen])

  const startRecording = async (): Promise<void> => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      recordChunksRef.current = []
      const mr = new MediaRecorder(stream)
      mr.ondataavailable = (e) => { if (e.data.size > 0) recordChunksRef.current.push(e.data) }
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(recordChunksRef.current, { type: 'audio/webm' })
        setRecordedBlob(blob)
        setRecordState('recorded')
      }
      mediaRecorderRef.current = mr
      mr.start()
      setRecordState('recording')
    } catch {
      setRecordState('idle')
    }
  }

  const stopRecording = (): void => {
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current = null
  }

  const discardRecording = (): void => {
    setRecordedBlob(null)
    setTranscript('')
    setRecordState('idle')
    setSavingState('idle')
  }

  const saveSample = async (): Promise<void> => {
    if (!recordedBlob || !transcript.trim()) return
    setSavingState('saving')
    try {
      const pcm = await resampleTo16k(recordedBlob)
      const wav = encodeWav(pcm, 16_000)
      await window.verseflow.saveSample(wav, transcript.trim())
      const status = await window.verseflow.getTrainingStatus()
      setTrainingStatus(status)
      discardRecording()
      setSavingState('saved')
      setTimeout(() => setSavingState('idle'), 2000)
    } catch {
      setSavingState('idle')
    }
  }

  const startTraining = (): void => {
    window.verseflow.startTraining().catch(console.error)
    setTrainingStatus((s) => s ? { ...s, isTraining: true, progress: 0 } : s)
  }

  const MIN_TRAINING_SAMPLES = 10

  const startAudioTest = async (): Promise<void> => {
    if (testState === 'testing') {
      stopAudioTest()
      return
    }
    try {
      setTestState('testing')
      if (levelBarRef.current) levelBarRef.current.style.width = '0%'

      // Match the selected device name to a browser MediaDeviceInfo deviceId.
      let deviceId: string | undefined
      if (settings.audioDevice) {
        const mediaDevices = await navigator.mediaDevices.enumerateDevices()
        const match = mediaDevices.find(
          (d) => d.kind === 'audioinput' && d.label.includes(settings.audioDevice),
        )
        deviceId = match?.deviceId
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
      })

      const ctx = new AudioContext()
      const source = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      const gain = ctx.createGain()
      gain.gain.value = monitorVolume

      // Meter: source → analyser (no output)
      source.connect(analyser)
      // Playback: source → gain → speakers
      source.connect(gain)
      gain.connect(ctx.destination)

      analyser.fftSize = 512
      const data = new Uint8Array(analyser.frequencyBinCount)
      const tick = (): void => {
        analyser.getByteTimeDomainData(data)
        let sum = 0
        for (const v of data) {
          const norm = (v - 128) / 128
          sum += norm * norm
        }
        const level = Math.min(1, Math.sqrt(sum / data.length) * 6)
        if (levelBarRef.current) {
          levelBarRef.current.style.width = `${Math.round(level * 100)}%`
          levelBarRef.current.className =
            level > 0.7
              ? 'h-full rounded-full bg-red-400'
              : level > 0.4
                ? 'h-full rounded-full bg-yellow-400'
                : 'h-full rounded-full bg-brand-400'
        }
        audioTestRef.current!.animFrame = requestAnimationFrame(tick)
      }

      audioTestRef.current = { stream, ctx, gain, animFrame: requestAnimationFrame(tick) }
    } catch {
      stopAudioTest()
      setTestState('error')
    }
  }

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
        'settings-panel absolute inset-0 z-20 flex flex-col transition-transform duration-300 ease-in-out',
        settingsPanelOpen ? 'translate-x-0' : 'translate-x-full',
      )}
      aria-hidden={!settingsPanelOpen}
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
            onChange={(e) => {
              stopAudioTest()
              save({ audioDevice: e.target.value })
            }}
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

          {/* Microphone test */}
          <div className="mt-2 flex flex-col gap-2">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={startAudioTest}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border transition-colors shrink-0',
                  testState === 'testing'
                    ? 'bg-red-500/20 border-red-500/50 text-red-300 hover:bg-red-500/30'
                    : 'bg-[var(--color-surface-2)] border-[var(--color-glass-border)] text-zinc-300 hover:text-zinc-100 hover:border-brand-400',
                )}
              >
                {testState === 'testing' ? <MicOff size={12} /> : <Mic size={12} />}
                {testState === 'testing' ? 'Stop test' : 'Test mic'}
              </button>

              {/* Level meter */}
              <div className="flex-1">
                <div className="h-2 w-full rounded-full overflow-hidden bg-zinc-700/60">
                  <div ref={levelBarRef} className="h-full rounded-full bg-brand-400" />
                </div>
              </div>
            </div>

            {/* Playback volume — only shown while testing */}
            {testState === 'testing' && (
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-zinc-500 shrink-0 w-16">Monitor vol</span>
                <input
                  type="range"
                  aria-label="Monitor playback volume"
                  min="0"
                  max="1"
                  step="0.05"
                  value={monitorVolume}
                  onChange={(e) => {
                    const v = parseFloat(e.target.value)
                    setMonitorVolume(v)
                    if (audioTestRef.current) audioTestRef.current.gain.gain.value = v
                  }}
                  className="flex-1 accent-brand-400 cursor-pointer"
                />
                <span className="text-[10px] text-zinc-500 tabular-nums w-6 text-right">
                  {Math.round(monitorVolume * 100)}%
                </span>
              </div>
            )}

            {testState === 'error' && (
              <p className="text-[10px] text-red-400">
                Microphone access denied or device unavailable.
              </p>
            )}
          </div>
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

        {/* ── Speaker Training ─────────────────────────────────────────── */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <Label>Speaker Training</Label>
            {trainingStatus && (
              <span className="text-[10px] text-zinc-500 tabular-nums">
                {trainingStatus.sampleCount} sample{trainingStatus.sampleCount !== 1 ? 's' : ''}
                {trainingStatus.hasCustomModel && ' · custom model active'}
              </span>
            )}
          </div>

          {/* Step 1 — record a sample */}
          {recordState === 'idle' && (
            <p className="text-[11px] text-zinc-500 mb-2">
              Record yourself saying a Bible verse or passage, then type what you said.
              Aim for 10+ samples across different books.
            </p>
          )}

          <div className="flex flex-col gap-2">
            {recordState !== 'recorded' && (
              <button
                type="button"
                onClick={recordState === 'idle' ? startRecording : stopRecording}
                className={clsx(
                  'flex items-center gap-2 px-3 py-2 rounded-lg text-xs border transition-colors',
                  recordState === 'recording'
                    ? 'bg-red-500/20 border-red-500/50 text-red-300 hover:bg-red-500/30'
                    : 'bg-[var(--color-surface-2)] border-[var(--color-glass-border)] text-zinc-300 hover:border-brand-400',
                )}
              >
                {recordState === 'recording'
                  ? <><Square size={11} className="fill-current" /> Stop recording</>
                  : <><Circle size={11} className="fill-red-400 text-red-400" /> Record sample</>}
              </button>
            )}

            {/* Step 2 — transcript + save */}
            {recordState === 'recorded' && (
              <>
                <textarea
                  aria-label="Transcript of recorded audio"
                  rows={2}
                  placeholder="Type exactly what you said…"
                  value={transcript}
                  onChange={(e) => setTranscript(e.target.value)}
                  className={clsx(inputCls, 'resize-none text-xs')}
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={saveSample}
                    disabled={!transcript.trim() || savingState === 'saving'}
                    className="flex-1 px-3 py-1.5 rounded-lg text-xs bg-brand-500/20 border border-brand-500/40 text-brand-300 hover:bg-brand-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {savingState === 'saving' ? 'Saving…' : savingState === 'saved' ? 'Saved ✓' : 'Save sample'}
                  </button>
                  <button
                    type="button"
                    onClick={discardRecording}
                    className="px-3 py-1.5 rounded-lg text-xs border border-[var(--color-glass-border)] text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    Discard
                  </button>
                </div>
              </>
            )}

            {/* Step 3 — train */}
            {trainingStatus && trainingStatus.sampleCount >= MIN_TRAINING_SAMPLES && !trainingStatus.isTraining && (
              <button
                type="button"
                onClick={startTraining}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs bg-brand-500/20 border border-brand-500/40 text-brand-300 hover:bg-brand-500/30 transition-colors"
              >
                <Brain size={12} />
                Train on {trainingStatus.sampleCount} samples
              </button>
            )}

            {/* Training progress */}
            {trainingStatus?.isTraining && (
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-[10px] text-zinc-500">
                  <span>Training…</span>
                  <span>{trainingStatus.progress}%</span>
                </div>
                <div className="h-1.5 w-full rounded-full overflow-hidden bg-zinc-700/60">
                  <div
                    className="h-full rounded-full bg-brand-400 transition-all duration-500"
                    style={{ width: `${trainingStatus.progress}%` }}
                  />
                </div>
              </div>
            )}

            {trainingStatus?.lastError && (
              <p className="text-[10px] text-red-400">{trainingStatus.lastError}</p>
            )}

            {trainingStatus && trainingStatus.sampleCount > 0 && trainingStatus.sampleCount < MIN_TRAINING_SAMPLES && !trainingStatus.isTraining && (
              <p className="text-[10px] text-zinc-600">
                {MIN_TRAINING_SAMPLES - trainingStatus.sampleCount} more sample{MIN_TRAINING_SAMPLES - trainingStatus.sampleCount !== 1 ? 's' : ''} needed before training
              </p>
            )}
          </div>
        </div>

        {/* Lyrics toggle */}
        <div>
          <Label>Lyric Suggestions</Label>
          <button
            type="button"
            role="switch"
            aria-label="Toggle lyric suggestions"
            aria-checked={settings.lyricsEnabled}
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
