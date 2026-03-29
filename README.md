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
Wait until you see: `Sidecar ready — waiting for Electron to connect`

**Terminal 2 — Start the app:**
```
npm run dev
```

The VerseFlow overlay window will appear on your screen.

> **Shortcut:** In VS Code, go to **Terminal → New Terminal** to open a second terminal alongside the first.

---

## Using VerseFlow

1. **Settings (first launch):** The settings panel opens automatically. Choose your presentation software from the dropdown and browse to its location on your computer.

2. **Start listening:** Click the **Listen** button (or press `Space`). VerseFlow will start listening to your microphone.

3. **Suggestions appear automatically:** As the speaker talks, Bible verses and song lyrics are suggested in real time in the panel below the transcript.

4. **Send to presentation:** Click any suggestion card (or use arrow keys to select, then press `Enter`) to send it to your presentation software.

5. **Stop listening:** Click the **Stop** button (or press `Space` again).

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `↑` / `↓` | Move between suggestions |
| `Enter` | Send selected suggestion to presentation |
| `Escape` | Deselect suggestion / close settings |

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
→ Check that your microphone is selected in Settings and that the audio engine terminal shows activity.

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
