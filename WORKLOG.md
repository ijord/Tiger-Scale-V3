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

- Blank NTAG213/215/216 pairs can be assigned to untagged inventory from the
  scale. The horizontal picker wraps, sorts neutral colors first, offers
  mutually exclusive hue and black/white rails, and filters by available
  material. Clear filament is neutral; changing material resets color filters.
  The picker's Validate action is the final write confirmation. Exiting or
  finishing requires lifting the spool before another prompt.
- Two-tag erase with confirmation, full verification and atomic inventory
  unlinking. Previously tagged inventory is preserved as an untagged spool.
  Erase is disabled without two eligible tags or when both are already blank.
- Unknown spool containers can be selected during assignment or normal reads,
  with account-specific empty weights and conditional twin updates.
- Original Bambu tags are read-only. Matching native pairs import as stable
  `TigerData_Bambu_<UID>` inventory records; unique non-refill catalog matches
  become TigerData+. Existing pairs upgrade in place, preserving account edits.
  Unknown or ambiguous catalog matches remain TigerData. Generic unrecognized
  tags cannot create weight-only inventory records.
- Native regression suites cover inventory transactions, codecs, RFID retries,
  picker behavior using LVGL, display filtering and bounded automatic zero.
  CI runs these on the reference HSU build; fixtures use synthetic tag IDs.

  Files: `TigerTagSplashESP32/TigerTagSplashESP32.ino`, `i18n.h`,
  `bambu_catalog.h`, generated `font_cjk_*.c`, `include/lv_conf.h`,
  `scripts/test-inventory.py`, `scripts/test-picker.py`, `scripts/test-zero.py`,
  `scripts/fixtures/`, `scripts/generate-bambu-catalog.py`,
  `.github/workflows/build.yml`, `scripts/verify.sh`, `CONTRIBUTING.md`,
  `README.md`, `docs/FIRMWARE.md`.

## Changed

- Zero Scale and Erase tag share the home control area. Per-reader tag icons
  distinguish missing, unidentified and identified tags. Successful reads beep
  once per distinct tag per placement. Successful writes and erases return
  without a final OK dialog; assignment restarts normal reading automatically.
- Inventory loading retries transient failures and avoids duplicate full-list
  downloads. Writes/erases recover individual pages and verify both original
  UIDs; pending account saves survive restarts without rewriting tags. Preparing
  and writing screens transition without briefly exposing the home screen.
- RFID reduced-drive settings remain available alongside the factory analog
  profile for weak coupling. Display filtering resets on confirmed large steps,
  while small changes receive stronger smoothing and stable rounding.
- Automatic zero uses fresh, steady raw samples within ±2 g for at least three
  seconds, with a 30-second cooldown and ±5 g cumulative cap from explicit zero.
  Large negative offsets require Zero Scale and block weight uploads. Removal
  releases the session independently. Startup restores the saved baseline;
  absent/invalid baselines require manual zero. Firebase login never tares.
- Public source preparation removes machine paths from generated font headers
  and uses example network details in API documentation. The font generator
  performs this cleanup automatically. Source maps and technical docs reflect
  the completed implementation.

  Files: firmware and tests above, `scripts/make-cjk-font.sh`, `docs/API.md`,
  `AGENTS.md`, `CLAUDE.md`, `CODEMAP.md`, `llms.txt`, `.gitattributes`
  (collapse generated fonts/catalog data in review).

**Validation scope:**

Hardware testing during development confirmed blank-pair assignment, erase and
inventory unlinking, two read beeps, automatic reread, picker controls and the
Clear filter on JC3248W535 HSU. Original Bambu import, repeat recognition and
TigerData+ upgrade were confirmed with one PLA Basic Jade White spool. Bounded zero was USB-installed and checked on the same board: startup
restored its baseline, a 1.02 g empty-platform drift was corrected, placement and
removal preserved the offset, and a deliberate loaded zero produced a held
negative reading with the required warning. Explicit empty-platform zero cleared
the warning and returned to 0 g. No tag writes or inventory assignments were
performed during these zero checks. No claim is made of hardware coverage for
the other board variants or transports. Current build/test results are recorded with the local review
package; no release or pull request has been published.
