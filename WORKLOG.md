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

## Fixed

- Known-tag admission refreshes physical weight after NFC reads and latches only
  accepted UIDs, preventing false no-tag timeouts after a beep/blue icon. Cached
  spool details appear before metadata refresh. Lookup precedes the single
  displayed weighing stage without discarding stability already earned. Erase
  stays disabled until the workflow and background work finish, with the same
  guard on the action (`TigerTagSplashESP32/TigerTagSplashESP32.ino`, `i18n.h`,
  `scripts/test-inventory.py`, `docs/FIRMWARE.md` and translation-count docs).

- Writes and erases offer direction-specific positioning and retry within the
  same session. Verified tags are not rewritten. Verification read failures
  recover with bounded same-UID retries, while removal, identity changes and
  cancellation remain safe exits. Logs identify the failing phase. Added native
  failure and real LVGL dialog coverage, translations and regenerated CJK fonts
  (`TigerTagSplashESP32/TigerTagSplashESP32.ino`, `i18n.h`, `font_cjk_*.c`,
  `scripts/test-inventory.py`, `scripts/test-picker.py`, `docs/FIRMWARE.md`).

- Tag erasure preserves one logical inventory spool. Differences in backup flags
  and remaining weight do not duplicate it; conflicting retained fields require
  choosing the entry to keep, checked against freshly read document versions.
- Nested inventory metadata uses the same parser depth for saved transactions
  as for live responses, preventing local parse errors being retried as network
  failures.
- Assignment recovery rebuilds conditional writes from current inventory data,
  preserving app edits that agree with the programmed tag payload. Permanent
  conflicts stop automatic resume prompts. The original tag pair can be erased
  to cancel recovery; partial physical writes retain their recovery record.
- Fresh empty-platform samples clear the displayed spool and session even while
  inventory recovery is pending. Reads without a physical load cannot restore
  stale material information.

Files: `TigerTagSplashESP32/TigerTagSplashESP32.ino`, `i18n.h`,
`scripts/test-inventory.py`, `scripts/test-picker.py`, `docs/FIRMWARE.md`,
`AGENTS.md`, `CLAUDE.md`, `CODEMAP.md` and regenerated source maps.

Validation: `scripts/verify.sh --all` passed all seven builds and 4,231 native checks
(1,473 inventory/reader/workflow, 2,677 picker/dialog, 81 zero). USB installation
was hash-verified. Hardware checks confirmed erase/reset clears recovery, both
tags erase and unlink successfully, and removal clears stale spool information.
A known-spool placement showed cached details with the first read, one weighing
stage, no false NFC timeout, and Erase disabled until sync completed. Automatic
RF retries recovered errors in the hardware erase test; the positioning prompt
was exercised in native LVGL tests rather than that hardware run.
