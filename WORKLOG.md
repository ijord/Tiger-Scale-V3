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

- Normal tag programming and pair verification use only pages 0x04–0x17,
  preserving signature pages through retries and recovery. Explicit erase clears
  all 144 bytes to zero, matching Tiger Studio, and blank detection accepts
  all-zero 80-byte records while rejecting partially erased data. Message
  encoding copies exactly the first 28 UTF-8 bytes, matching the official SDKs.
  Added pinned upstream encoding vectors and signature/erase regression checks
  (`TigerTagSplashESP32/TigerTagSplashESP32.ino`, `scripts/test-inventory.py`,
  `scripts/fixtures/tigertag-encoding.json`, `scripts/fixtures/README.md`,
  `docs/FIRMWARE.md`).

- Bambu inventory creation releases its HTTPS connection before verification,
  avoiding overlapping TLS clients after a successful save. It retries
  transient save failures up to three times,
  checks for an already-created pair before retrying, and refreshes expired
  authentication. Incomplete or conflicting account pairs stop recovery without
  overwriting existing data. Added regression coverage for transient failures,
  retry limits, lost replies, TLS client lifetime, and permanent refusals
  (`TigerTagSplashESP32/TigerTagSplashESP32.ino`, `scripts/test-inventory.py`).
