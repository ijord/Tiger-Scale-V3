# Worklog — since the last checkpoint

The single source of truth for everything done since the last commit. Read it at
the start of a session; append to it the moment a change is done, never in a
batch at the end.

The headings match [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), so
at release time this file is synthesised into the `CHANGELOG.md` entry and the
release note in `docs/release-notes/` without being re-derived from the diff.

Keep it clean as you go: describe the **end state**, not the journey. An "Added
X" and a later "Fixed X" from the same cycle collapse into one entry. Anything
reverted disappears entirely — it never shipped. One bullet, one logical change,
always naming the files touched.

Reset this file to the header above at each checkpoint. Nothing is lost: the raw
log lives in git history and the synthesised entry lives in the changelog.

---

## Added

- Guition JC3248W535C_I_Y support through `jc3248w535_hsu`: board-specific QSPI
  display and AXS15231B touch pins/protocol, two UART/HSU PN532 readers, HX711
  connector wiring, and direct I2S speaker output with software volume. The
  owner confirmed working display, touch, and speaker output after USB
  installation; HX711 and NFC readers remain unverified. The
  board has its own OTA identity with no Waveshare fallback; AXP2101 battery
  telemetry and software power-off are unavailable on this hardware.
  The PN532 guide identifies both 115200-baud UARTs, four required wires per
  reader, and optional reset wiring only to `RSTPD_N`; `RSTO` stays unconnected.
  Hardware reset recovery and power-down isolation require the reset input.
  CODEMAP notes cover the Guition touch protocol and OTA selection.
  CI and local `--all` verification include the dedicated environment.
  Files: `platformio.ini`, `TigerTagSplashESP32/TigerTagSplashESP32.ino`,
  `docs/JC3248W535.md`, `docs/HARDWARE.md`, `.github/workflows/build.yml`,
  `scripts/verify.sh`, and regenerated `CODEMAP.md`/firmware TOC.

## Fixed

- Calibration preserves load-cell polarity: the on-device wizard saves a signed
  factor and checks its magnitude, while web calibration accepts finite nonzero
  factors of either sign. Recalibrating a cell whose raw counts decrease under
  load now produces a positive weight without swapping signal wires.
  Files: `TigerTagSplashESP32/TigerTagSplashESP32.ino`, `data/www/script.js`,
  `data/www/index.html`.

## Removed

- **Forty dead translation keys**, 480 lines out of `i18n.h`. `I18N_LAN_TITLE`
  went with the Live view rename; the other thirty-nine were left behind by
  screens that were rewritten and never referenced again — most of the
  calibration wizard's step strings, three of the five sleep ones, four OTA
  states, and a scattering of singles. 157 keys became 117, in eleven languages
  each. Files: `i18n.h`, and the key count in `CLAUDE.md`, `AGENTS.md` and
  `docs/FIRMWARE.md`, which said 158, 103 and 88 — the last two had been wrong
  for a long time and in a different language count.
