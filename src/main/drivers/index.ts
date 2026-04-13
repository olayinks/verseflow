// ─────────────────────────────────────────────────────────────────────────────
// src/main/drivers/index.ts
//
// Factory that returns the correct PresentationDriver for the active setting.
// Each driver is implemented in its own file (Stage 9 will flesh them out).
// ─────────────────────────────────────────────────────────────────────────────

import type { PresentationDriver } from '../../shared/types'
import { ProPresenterDriver } from './propresenter'
import { EasyWorshipDriver } from './easyworship'
import { PowerPointDriver } from './powerpoint'
import { KeynoteDriver } from './keynote'
import { OpenLPDriver } from './openlp'

/** Every driver must implement this interface. */
export interface IPresentationDriver {
  /**
   * Send a text string (verse or lyric) to the active slide in the
   * presentation software.  Throws on failure.
   */
  send(text: string): Promise<void>
}

/** A no-op driver used when no presentation software is configured. */
class NoneDriver implements IPresentationDriver {
  async send(text: string): Promise<void> {
    console.log('[NoneDriver] Would send:', text)
  }
}


export function getDriver(driver: PresentationDriver): IPresentationDriver {
  switch (driver) {
    case 'none':
      return new NoneDriver()
    case 'propresenter':
      return new ProPresenterDriver()
    case 'easyworship':
      return new EasyWorshipDriver()
    case 'powerpoint':
      return new PowerPointDriver()
    case 'keynote':
      return new KeynoteDriver()
    case 'openlp':
      return new OpenLPDriver()
    default:
      return new NoneDriver()
  }
}
