// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/components/HelpPanel.tsx
// Slide-in help overlay — mirrors the layout of SettingsPanel.
// ─────────────────────────────────────────────────────────────────────────────

import { X } from 'lucide-react'
import { clsx } from 'clsx'
import { useAppStore } from '../store'

function Section({ title, children }: { title: string; children: React.ReactNode }): React.ReactElement {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-[11px] uppercase tracking-widest text-zinc-500">{title}</p>
      {children}
    </div>
  )
}

function P({ children }: { children: React.ReactNode }): React.ReactElement {
  return <p className="text-xs text-zinc-400 leading-relaxed">{children}</p>
}

function KbRow({ keys, action }: { keys: string[]; action: string }): React.ReactElement {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-zinc-400">{action}</span>
      <div className="flex items-center gap-1">
        {keys.map((k) => (
          <kbd
            key={k}
            className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-700/60 border border-zinc-600 text-zinc-300"
          >
            {k}
          </kbd>
        ))}
      </div>
    </div>
  )
}

function Step({ n, children }: { n: number; children: React.ReactNode }): React.ReactElement {
  return (
    <div className="flex gap-2.5">
      <span className="shrink-0 size-4 rounded-full bg-brand-500/20 text-brand-400 text-[10px] font-semibold flex items-center justify-center mt-0.5">
        {n}
      </span>
      <p className="text-xs text-zinc-400 leading-relaxed">{children}</p>
    </div>
  )
}

export function HelpPanel(): React.ReactElement {
  const { helpPanelOpen, setHelpPanelOpen } = useAppStore()

  return (
    <div
      className={clsx(
        'settings-panel absolute inset-0 z-20 flex flex-col transition-transform duration-300 ease-in-out',
        helpPanelOpen ? 'translate-x-0' : 'translate-x-full',
      )}
      aria-hidden={helpPanelOpen ? undefined : true}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-3 pb-2 border-b border-[var(--color-glass-border)]">
        <span className="text-sm font-semibold text-zinc-100">Help</span>
        <button
          type="button"
          onClick={() => setHelpPanelOpen(false)}
          className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-white/10 transition-colors"
          aria-label="Close help"
        >
          <X size={14} />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-5">

        {/* Basic usage */}
        <Section title="Getting Started">
          <Step n={1}>Open <strong className="text-zinc-300">Settings</strong> (gear icon) and select your audio input device and presentation software.</Step>
          <Step n={2}>Choose a <strong className="text-zinc-300">capture mode</strong> using the Sermon / Worship toggle.</Step>
          <Step n={3}>Click <strong className="text-zinc-300">Listen</strong> (or press Space) to start capturing audio.</Step>
          <Step n={4}>Suggestions appear automatically as the speaker talks. Click a card (or press Enter) to send it to your presentation software.</Step>
          <Step n={5}>Click <strong className="text-zinc-300">Stop</strong> (or press Space) when done.</Step>
        </Section>

        {/* Capture modes */}
        <Section title="Capture Modes">
          <P>
            <strong className="text-zinc-300">Sermon</strong> — optimised for spoken word. Uses a longer audio window for better word accuracy and prioritises Bible verse detection.
          </P>
          <P>
            <strong className="text-zinc-300">Worship</strong> — optimised for singing. Uses a shorter window for faster response and prioritises song lyric matching.
          </P>
          <P>Switch modes at any time using the toggle below the status bar — even mid-session.</P>
        </Section>

        {/* Audio test */}
        <Section title="Testing Your Microphone">
          <P>Before a service, confirm VerseFlow is capturing the right audio source:</P>
          <Step n={1}>Open Settings and select your device from the <strong className="text-zinc-300">Audio Input Device</strong> dropdown.</Step>
          <Step n={2}>Click <strong className="text-zinc-300">Test mic</strong> — a level meter shows real-time audio activity.</Step>
          <Step n={3}>Speak into the microphone and watch the bar move. Use the <strong className="text-zinc-300">Monitor vol</strong> slider to hear the audio played back.</Step>
          <Step n={4}>Click <strong className="text-zinc-300">Stop test</strong> when satisfied.</Step>
          <P>If using speakers (not headphones), keep monitor volume low to avoid feedback.</P>
        </Section>

        {/* Speaker training */}
        <Section title="Speaker Training">
          <P>
            Fine-tune the speech recognition model on the speaker's own voice to improve accuracy — especially for unusual diction, accents, or scripture-specific terms like Thessalonians or Habakkuk.
          </P>
          <P>
            Training uses your <strong className="text-zinc-300">system Python</strong>, not the bundled audio engine. Install the extra packages once before your first training run:
          </P>
          <Step n={1}>
            Open a terminal and run:{' '}
            <code className="text-[10px] font-mono bg-zinc-800 px-1 py-0.5 rounded text-zinc-300">
              pip install -r sidecar/requirements-training.txt
            </code>
            {' '}(If packages are missing, the app will show this message automatically when you click Train.)
          </Step>
          <Step n={2}>Go to <strong className="text-zinc-300">Settings → Speaker Training</strong>. Click <strong className="text-zinc-300">Record sample</strong>, speak a Bible verse clearly, then stop.</Step>
          <Step n={3}>Type exactly what you said into the transcript box and click <strong className="text-zinc-300">Save sample</strong>.</Step>
          <Step n={4}>Repeat for at least <strong className="text-zinc-300">10 samples</strong>. Vary the books, chapters, and pace. Include hard-to-pronounce names.</Step>
          <Step n={5}>Once 10 samples are saved, click <strong className="text-zinc-300">Train</strong>. A progress bar tracks the process. The custom model is used automatically after restarting.</Step>
          <P>A GPU shortens training from ~45 minutes to under 5 minutes.</P>
        </Section>

        {/* Keyboard shortcuts */}
        <Section title="Keyboard Shortcuts">
          <div className="flex flex-col gap-2">
            <KbRow keys={['Space']} action="Start / stop listening" />
            <KbRow keys={['↑', '↓']} action="Navigate suggestions" />
            <KbRow keys={['Enter']} action="Send to presentation" />
            <KbRow keys={['Esc']} action="Deselect / close panel" />
          </div>
        </Section>

        {/* Troubleshooting */}
        <Section title="Troubleshooting">
          <div className="flex flex-col gap-3">
            <div>
              <p className="text-xs font-medium text-zinc-300 mb-0.5">No suggestions appearing</p>
              <P>Use Test mic to confirm audio is being captured. Lower the Semantic Threshold slider in Settings towards "Broad".</P>
            </div>
            <div>
              <p className="text-xs font-medium text-zinc-300 mb-0.5">Wrong words in transcript</p>
              <P>Collect voice samples and run Speaker Training to personalise the model for your speaker's diction.</P>
            </div>
            <div>
              <p className="text-xs font-medium text-zinc-300 mb-0.5">Presentation software not responding</p>
              <P>Ensure the software is open before clicking Send. On macOS, grant Accessibility permissions in System Settings → Privacy & Security.</P>
            </div>
            <div>
              <p className="text-xs font-medium text-zinc-300 mb-0.5">Training fails with a missing module error</p>
              <P>
                Run{' '}
                <code className="text-[10px] font-mono bg-zinc-800 px-1 py-0.5 rounded text-zinc-300">
                  pip install -r sidecar/requirements-training.txt
                </code>{' '}
                and try again.
              </P>
            </div>
          </div>
        </Section>

      </div>
    </div>
  )
}
