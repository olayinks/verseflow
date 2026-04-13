// ─────────────────────────────────────────────────────────────────────────────
// src/main/index.ts
//
// Electron main process entry point.
//
// Responsibilities:
//   1. Create and configure BrowserWindows (main overlay + optional settings).
//   2. Spawn and manage the Python sidecar process.
//   3. Maintain a WebSocket CLIENT connection to the sidecar.
//   4. Bridge sidecar events → renderer via IPC.
//   5. Handle IPC calls from the renderer.
// ─────────────────────────────────────────────────────────────────────────────

import { app, BrowserWindow, shell, ipcMain, nativeTheme } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { registerIpcHandlers } from './ipc/handlers'
import { SidecarManager } from './sidecar-manager'
import { settingsStore } from './settings-store'
import { isAppRunning, launchApp } from './app-launcher'

// Keep a global reference so the GC doesn't close the window.
let mainWindow: BrowserWindow | null = null
let sidecarManager: SidecarManager | null = null

// ---------------------------------------------------------------------------
// Window creation
// ---------------------------------------------------------------------------

function createMainWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 480,
    height: 700,
    minWidth: 360,
    minHeight: 500,
    show: false,
    autoHideMenuBar: true,
    // Always on top so it floats over presentation software.
    // Level is set to 'floating' which sits above normal windows but below
    // system overlays — ideal for a live helper panel.
    alwaysOnTop: true,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'hidden',
    frame: false,
    transparent: true,
    vibrancy: 'under-window', // macOS frosted-glass effect
    backgroundMaterial: 'acrylic', // Windows 11 acrylic effect
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  // Show the window gracefully once the renderer is ready.
  win.on('ready-to-show', () => {
    win.show()
    // Auto-launch the presentation app if one is configured and not yet running.
    const { presentationDriver, presentationAppPath } = settingsStore.store
    if (presentationDriver !== 'none' && presentationAppPath) {
      isAppRunning(presentationAppPath).then((running) => {
        if (!running) {
          launchApp(presentationAppPath).catch((e) => {
            console.error('[main] Failed to auto-launch presentation app:', e)
          })
        }
      })
    }
  })

  // Open DevTools links in the system browser, not Electron.
  win.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // In dev: load from Vite dev server. In prod: load built HTML.
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    win.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    win.loadFile(join(__dirname, '../renderer/index.html'))
  }

  return win
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(() => {
  // Set the app user model ID (Windows taskbar grouping).
  electronApp.setAppUserModelId('com.verseflow.app')

  // Open/close DevTools with F12 in dev.
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // Honour the OS dark/light mode preference.
  nativeTheme.themeSource = 'system'

  // Boot the Python sidecar process.
  sidecarManager = new SidecarManager()

  // Create the main overlay window.
  mainWindow = createMainWindow()

  // Register all IPC handlers, injecting references they need.
  registerIpcHandlers({ mainWindow, sidecarManager })

  // Connect sidecar WebSocket and pipe events to the renderer.
  sidecarManager.connect(mainWindow)

  app.on('activate', () => {
    // macOS: re-open the window when the dock icon is clicked.
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createMainWindow()
    }
  })
})

app.on('window-all-closed', () => {
  sidecarManager?.shutdown()
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  sidecarManager?.shutdown()
})

// Suppress the default Electron menu in production.
if (!is.dev) {
  ipcMain.on('disable-default-menu', () => {
    /* handled by autoHideMenuBar above */
  })
}
