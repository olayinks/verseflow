# VerseFlow

**Real-time Bible verse and worship lyric suggestions for church services.**

VerseFlow listens to your pastor or worship leader and automatically suggests relevant Bible verses and song lyrics — displayed in a floating overlay that sits on top of your presentation software (ProPresenter, PowerPoint, EasyWorship, and more).

---

## What You Need

Before you start, make sure your computer has the following. Don't worry — the instructions below walk you through installing each one.

| Requirement | Why |
|---|---|
| Windows 10/11 or macOS 12+ | Supported operating systems |
| [Node.js 20+](https://nodejs.org) | Runs the app |
| [Python 3.11+](https://www.python.org/downloads/) | Runs the audio and AI engine |
| [VS Code](https://code.visualstudio.com) | Free code editor — used to open and run the project |
| A microphone | Captures the speaker's voice |
| ~2 GB free disk space | For the AI models |

---

## Step-by-Step Setup

### Step 1 — Install VS Code

1. Go to **https://code.visualstudio.com**
2. Click the big download button for your operating system
3. Run the installer and follow the prompts
4. Once installed, open VS Code

### Step 2 — Install Node.js

1. Go to **https://nodejs.org**
2. Download the **LTS** version (the left button — recommended for most users)
3. Run the installer — click Next through all the steps
4. When it asks about "Tools for Native Modules", tick that box
5. Restart your computer after installation

### Step 3 — Install Python

1. Go to **https://www.python.org/downloads/**
2. Download the latest **Python 3.x** installer
3. Run the installer — **important:** tick "Add Python to PATH" at the bottom before clicking Install
4. Click "Install Now"

### Step 4 — Get the VerseFlow Code

**Option A — Download as a ZIP (easiest):**
1. Go to the VerseFlow GitHub page
2. Click the green **Code** button → **Download ZIP**
3. Unzip the folder somewhere easy to find (e.g. your Desktop)

**Option B — Use Git (if you have it installed):**
```
git clone https://github.com/YOUR-USERNAME/verseflow.git
```

### Step 5 — Open the Project in VS Code

1. Open VS Code
2. Click **File → Open Folder**
3. Browse to the `verseflow` folder you downloaded and click **Select Folder**
4. VS Code will open the project

### Step 6 — Run the One-Click Setup

This step downloads all the required libraries and AI models. It only needs to be done once and takes about 5–15 minutes depending on your internet speed.

**On Windows:**
1. In VS Code, press `Ctrl + `` ` ` (that's the backtick key, top-left of keyboard) to open the Terminal
2. Type the following and press Enter:
   ```
   .\setup.bat
   ```

**On macOS:**
1. Press `Cmd + `` ` ` ` to open the Terminal
2. Type the following and press Enter:
   ```
   bash setup.sh
   ```

Wait for it to finish. You'll see "Setup complete!" at the end.

> **Note:** The first run downloads about 1.5 GB of AI models. Make sure you're on a good internet connection.

### Step 7 — Start the App

You need two terminals running at the same time.

**Terminal 1 — Start the audio engine:**
```
npm run sidecar:dev
```

**Terminal 2 — Start the app:**
```
npm run dev
```

The VerseFlow overlay window will appear. A loading indicator shows while the AI engines initialise — the **Listen** button enables automatically once they are ready (typically 10–30 seconds on first launch).

> **Shortcut:** In VS Code, go to **Terminal → New Terminal** to open a second terminal alongside the first.

---

## Using VerseFlow

1. **Settings (first launch):** The settings panel opens automatically. Choose your presentation software from the dropdown and browse to its location on your computer.

2. **Choose a capture mode:** Use the **Sermon / Worship** toggle below the status bar to switch modes.
   - **Sermon** — optimised for spoken word. Longer audio windows for better word accuracy, prioritises Bible verse detection.
   - **Worship** — optimised for singing. Shorter windows for faster response, prioritises song lyric matching.

3. **Start listening:** Click the **Listen** button (or press `Space`). VerseFlow will start listening to your microphone.

4. **Suggestions appear automatically:** As the speaker talks, Bible verses and song lyrics are suggested in real time in the panel below the transcript.

5. **Send to presentation:** Hover over any suggestion card and click the **Send** button that appears — or use arrow keys to select a card and press `Enter`. You don't need to expand the card first.

6. **Stop listening:** Click the **Stop** button (or press `Space` again).

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `Space` | Start / stop listening |
| `↑` / `↓` | Move between suggestions |
| `Enter` | Send selected suggestion to presentation |
| `Escape` | Deselect suggestion / close settings |

### Testing Your Audio Input

Before a service, verify VerseFlow is capturing the right microphone:

1. Open **Settings** (gear icon, top right)
2. Select your audio input device from the dropdown
3. Click **Test mic** — a level meter appears showing real-time audio
4. Speak into the microphone and watch the bar move
5. Use the **Monitor vol** slider to hear your own audio played back through your speakers/headphones
6. Click **Stop test** when done

> If you are using speakers (not headphones), keep the monitor volume low to avoid feedback.

---

## Supported Presentation Software

| Software | Platform |
|---|---|
| ProPresenter 7 | Windows & macOS |
| EasyWorship | Windows & macOS |
| Microsoft PowerPoint | Windows & macOS |
| Apple Keynote | macOS only |
| OpenLP | Windows & macOS |

> VerseFlow works by typing into the presentation software's search box. The presentation software must be open and have slides/songs already in its library.

---

---

## Speaker Training (Improve Accuracy for Your Speaker)

Out of the box VerseFlow uses the `small.en` Whisper model with biblical vocabulary hints. For speakers with strong accents or unusual pronunciation of scripture terms, you can fine-tune the model on their voice in a few steps.

### How training works in packaged vs development builds

VerseFlow's normal audio engine runs as a self-contained binary — no Python required. Training is different: it uses your **system Python** and several large ML packages that are not bundled with the app (they would add 2–4 GB to the installer and most users never need them).

| | Normal operation | Speaker training |
|---|---|---|
| Python required? | No — bundled binary | Yes — system Python 3.11+ |
| Extra packages? | No | Yes — see below |
| Works in packaged app? | Yes | Yes, once packages are installed |

### Step 1 — Install training dependencies (once)

```
pip install -r sidecar/requirements-training.txt
```

If training packages are missing when you click Train, the app will display an error with this exact command rather than failing silently.

> A GPU (NVIDIA with CUDA) is strongly recommended. Training on CPU works but takes 30–60 minutes. With a GPU it finishes in under 5 minutes.

### Step 2 — Collect voice samples (in the app)

1. Open **Settings → Speaker Training**
2. Click **Record sample** and speak a Bible verse clearly
3. Click **Stop recording**, then type exactly what you said into the transcript box
4. Click **Save sample**
5. Repeat for at least **10 samples** — vary the books, chapters and speaking pace

**Tips for good samples:**
- Use a mix of short references ("John 3:16") and longer passages
- Include book names that are hard to pronounce (Deuteronomy, Thessalonians, Habakkuk)
- Record in the same room and with the same microphone you use during services

### Step 3 — Train the model

Once 10 or more samples are saved, a **Train** button appears in the settings panel. Click it — training runs in the background and a progress bar updates as it goes.

When complete, the fine-tuned model is saved to `data/models/custom-whisper-ct2/` and VerseFlow automatically uses it on the next sidecar restart.

---

## Adding Your Own Worship Songs

Drop plain `.txt` files into the `data/lyrics/source/` folder — one song per file. Each line is a lyric line. Then rebuild the lyrics index:

```
npm run scripts:build-lyrics
```

---

## Troubleshooting

**"Python is not recognized"**
→ Re-run the Python installer and make sure "Add Python to PATH" is ticked.

**"npm is not recognized"**
→ Re-run the Node.js installer and restart your computer.

**The overlay doesn't appear**
→ Make sure you ran both terminal commands in Step 7.

**No suggestions are appearing**
→ Check that your microphone is selected in Settings and use **Test mic** to confirm audio is being captured. Also check that the audio engine terminal shows activity.

**Suggestions seem unrelated to what was said**
→ Try lowering the Semantic Threshold slider in Settings (towards "Broad"). The semantic search uses `multi-qa-MiniLM-L6-cos-v1`, a retrieval-optimised model — if you rebuilt the index with the old `all-MiniLM-L6-v2` model, re-run `npm run scripts:build-bible` to get the matching index. If the speaker has a strong accent, collect voice samples and run Speaker Training.

**The Listen button stays greyed out**
→ The engines are still loading. Watch the status bar — the amber pulse and loading message will clear when ready. If it stays grey indefinitely, check the sidecar terminal for errors.

**Training fails with a missing module error**
→ Run `pip install -r sidecar/requirements-training.txt` and try again.

**ProPresenter / PowerPoint doesn't respond**
→ Make sure the presentation software is open and focused before clicking Send. The app needs accessibility permissions on macOS — go to System Settings → Privacy & Security → Accessibility.

---

## System Requirements (Full)

| | Minimum | Recommended |
|---|---|---|
| OS | Windows 10, macOS 12 | Windows 11, macOS 14 |
| RAM | 4 GB | 8 GB+ |
| CPU | Any modern dual-core | Quad-core or better |
| GPU | Not required | NVIDIA GPU speeds up transcription |
| Disk | 2 GB free | 4 GB free |
| Internet | Required for setup | Not needed after setup |

---

## License

MIT — free to use in your church or ministry.
