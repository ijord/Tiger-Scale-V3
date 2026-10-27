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

- The browser installer and firmware update channel use the fork's releases
  and Pages site, with explicit repository/site arguments in the deployment
  workflow. The release includes all three supported boards, including
  JC3248W535, and deployment verification checks each board's served binary
  against its release asset. The installer identifies the community fork and
  links the JC3248 wiring guide in every language
  (`.github/workflows/pages.yml`, `.github/workflows/release.yml`,
  `scripts/fetch-published-site.py`, `scripts/make-manifest.py`,
  `scripts/verify-published-site.py`, `TigerTagSplashESP32/TigerTagSplashESP32.ino`,
  `platformio.ini`, `web-installer/`, `docs/INSTALLATION.md`,
  `docs/JC3248W535.md`).

## Changed

- Prepared the first fork release, v3.11.0, with release notes covering the
  inventory/tag workflow, Bambu import, weight handling and supported boards
  (`TigerTagSplashESP32/TigerTagSplashESP32.ino`, `CHANGELOG.md`,
  `docs/release-notes/v3.11.0.md`, `llms.txt`, `scripts/check-llms-txt.py`,
  `docs/INSTALLATION.md`).

- The README's Onshape logo displays at 400 pixels wide and its browser-install
  button opens the fork's installer (`README.md`).
