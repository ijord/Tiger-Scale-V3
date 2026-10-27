# Installation

Building and flashing TigerScale V3 firmware.

## Requirements

- **[PlatformIO Core](https://docs.platformio.org/en/latest/core/installation/)** —
  `pip install platformio`, or the PlatformIO IDE extension for VS Code
- A USB-C cable and the board
- Python 3 (only for `scripts/watch_logs.py`)

**The Arduino IDE cannot build this project.** LVGL's configuration is located
through `-I include` combined with `LV_CONF_INCLUDE_SIMPLE`, and the IDE provides
no equivalent include path. PlatformIO is the only supported toolchain.

## Which build do I need?

Two things are fixed at **compile time**: which display board you have, and how
your PN532 modules are wired. All three published builds use HSU / UART readers.
Follow the wiring guide for your board.

| Your board | Build env | Published |
|------------|-----------|-----------|
| ESP32-S3-Touch-LCD-3.5**B** | `esp32s3_hsu_b` | yes — the default in the web installer |
| ESP32-S3-Touch-LCD-3.5 (no B) | `esp32s3_hsu` | yes |
| JC3248W535 / JC3248W535C | `jc3248w535_hsu` | yes — [Guition wiring](JC3248W535.md) |

On a Waveshare board, read the white silkscreen under the ribbon connector: it
either ends with a B or it does not. The two are the same size and take the same
wiring, but their screen controllers differ (AXS15231B over QSPI on the B,
ST7796 over SPI on the other), so the wrong image leaves you with a board that
flashes fine and never lights its screen.

The other two transports are not published any more — every scale in the field
is wired HSU, and offering a choice whose failure mode is silent ("no readers",
no reason given) cost more than it helped. They still build from source:

| Your wiring | Build env | Readers |
|-------------|-----------|---------|
| SPI | `esp32s3` | 2 — compiles, not bench-verified |
| I²C on `Wire1` | `esp32s3_i2c` | 1 — the PN532's address is fixed |

Wiring diagrams for each: [HARDWARE.md](HARDWARE.md#nfc-wiring--pick-one-then-build-the-matching-env).

## First install on a new board

### Easiest: the web installer

<https://ijord.github.io/Tiger-Scale-V3/>

This installer serves **ijord's TigerScale V3+ fork**. Choose your exact board:
Waveshare -3.5B, Waveshare -3.5, or Guition JC3248W535 / JC3248W535C.
All three builds use two HSU (UART) readers; the Guition board has
[different wiring](JC3248W535.md).

Plug the board in, choose your board, click Install. It writes the bootloader,
partition table, firmware and web UI in one go. Chrome, Edge or Opera on a desktop —
Web Serial is not available in Safari, Firefox or on mobile.

Note it **erases the board**, saved WiFi included. That is right for new hardware; to
update a scale already in use, see [Updating later](#updating-later).

### Publishing this fork's installer

The browser installer uses release assets from `ijord/Tiger-Scale-V3`; it does
not fall back to official firmware. Before its first installation:

1. Enable GitHub Actions in the fork, then set **Settings → Pages → Source** to
   **GitHub Actions**.
2. Prepare a new release version and notes with `scripts/bump-version.sh`.
   Commit the changes and push a new `v<version>` tag for that commit. The tag
   must match `TIGERSCALE_FW_VERSION`; do not reuse an inherited upstream tag.
3. Wait for the `release` workflow to build all three boards and deploy Pages.
   Running `release` manually is a dry run and does not publish anything.

The `pages` workflow can then refresh the installer without rebuilding firmware.
It downloads this fork's latest release and verifies the served images against
that release. Newly built firmware also checks this fork's update manifest.

### From source

**One command.** On a board that has never been flashed, this is the whole job:

```bash
git clone https://github.com/ijord/Tiger-Scale-V3.git
cd Tiger-Scale-V3

bash scripts/flash.sh --fs
```

`--fs` matters on a first install and is easy to skip. Two separate things live in
flash and they are written by two separate steps:

| What | Where | Written by |
|---|---|---|
| Firmware (the app) | `app0` @ 0x10000 | every flash |
| Web UI (`data/`) | `spiffs` @ 0x650000 | **only** with `--fs` / `-t uploadfs` |

Flash without `--fs` and the scale works, but its web interface answers 404 —
which looks like a bug and is not one. If that happens, just run
`bash scripts/flash.sh --fs` again.

Add `--monitor` if you want to watch it boot:

```bash
bash scripts/flash.sh --fs --monitor
```

### If the board is not detected

The ESP32-S3 exposes a native USB-Serial/JTAG port, and esptool resets it for you —
on the reference unit no button press was needed. If your port never appears:

- Give it a few seconds. Enumeration can lag; a port scan run immediately after
  plugging in may show nothing, then succeed on a retry.
- Check the cable carries data, not just power.
- Force download mode: hold **BOOT**, tap **RESET**, release **BOOT**, then flash.
- Pass the port explicitly: `bash scripts/flash.sh --fs --port /dev/cu.usbmodem1101`
  (`pio device list` will show candidates).

A correctly-talking board answers like this:

```
Chip type:  ESP32-S3 (QFN56) (revision v0.2)
Features:   Wi-Fi, BT 5 (LE), Dual Core + LP Core, 240MHz, Embedded PSRAM 8MB
Detected flash size: 16MB
```

### Did it work?

The boot log should show, in this order:

```
[LCD] begin OK w=480 h=320
[TOUCH] Wire1 SDA=8 SCL=7 addr=0x3B probe=0 (ACK)
[I2C] Scan done. 6 device(s) found.
[RFID] PN532-1 ready
[RFID] PN532-2 ready
[LITTLEFS] Mounted OK
[DB] Brand DB loaded: 120 entries
```

`PN532-1 ready` / `PN532-2 ready` is the one to check. If you see no readers, you
almost certainly built the wrong transport env for your wiring — see the table
above, and [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Two boot messages look alarming and are expected on this board:
`perimanSetPinBus(): Invalid pin: 22` and a few `NULL TX buffer pointer` lines.
They come from a vendor I²C bus that cannot work on the ESP32-S3.
[HARDWARE.md](HARDWARE.md#ic-topology--read-this-before-adding-any-peripheral)
explains why.

## Updating later

### Over the air — for firmware and web UI

**Settings → Update** on the touchscreen checks this fork's published manifest
and installs the web UI filesystem followed by the firmware, with a progress
bar. Nothing to plug in once the fork and the current partition table are installed.

> [!WARNING]
> **Older single-slot partition tables need a USB reflash first.** The current
> table has `ota_0` and `ota_1` application slots. A device still using the old
> single `factory` slot has nowhere to write a firmware update; the updater
> shows "Update over USB". Flash the partition table, firmware and filesystem
> over USB using `scripts/flash.sh --fs` for the correct board. An OTA update
> cannot replace the partition table.

Two further details:

- **Firmware and web UI are separate images.** This fork publishes both in its
  manifest. The updater writes the filesystem first, then the firmware before
  restarting. Older manifests without a filesystem URL update only firmware.
- **Published builds assume the HSU wiring** — one per board, and nothing for SPI
  or I²C. A unit wired either way that takes a published update comes back on the
  HSU build and loses its reader until reflashed over USB.

OTA also needs a published release to exist. Until the first version is tagged,
Settings → Update will simply report that it cannot reach the manifest.

### Over USB — for everything

```bash
bash scripts/flash.sh              # firmware only, keeps your settings
bash scripts/flash.sh --fs         # firmware + web UI
```

Your WiFi credentials, TigerTag session and calibration survive both — see below.

## Why your settings survive a reflash

PlatformIO writes each image at its own offset:

```
 0x0000  bootloader.bin
 0x8000  partitions.bin
 0xE000  boot_app0.bin
0x10000  firmware.bin
```

NVS lives at 0x9000–0xE000, in none of those ranges. WiFi credentials, the TigerTag
session and the calibration factor all survive. This is verified, not assumed: NVS
was read out of the reference unit before and after a reflash, and the saved SSID,
tare factor and settings were all still there.

**The trap:** flashing `.pio/build/<env>/firmware.factory.bin` at `0x0000` as a
single blob. That file is a *merged* image spanning 0x0000 upward continuously, so
it does overwrite NVS — which is why credentials used to disappear on every reflash
during development. Neither `scripts/flash.sh` nor `pio run -t upload` does this.

For a genuine clean slate, `bash scripts/flash.sh --erase` wipes everything
including calibration, after asking for confirmation.

Flash mode is fixed to **DIO** by the board configuration. QIO produces a boot crash
loop in `ets_loader.c` on this board — do not "optimise" it.

## Driving PlatformIO directly

```bash
pio run -e esp32s3_hsu_b              # build
pio run -e esp32s3_hsu_b -t upload    # flash firmware
pio run -e esp32s3_hsu_b -t uploadfs  # flash the web UI (LittleFS)
pio device monitor                  # serial console
```

## First boot

1. The TigerTag splash appears, then a WiFi setup screen.
2. Pick your network on the touchscreen and enter the password.
3. Sign in to your TigerTag account from **Settings → Cloud**.
4. Calibrate the scale: **Settings → Calibration**, then follow the wizard with a
   known reference weight.
5. Place a spool carrying a TigerTag tag. The scale reads it, weighs it, and syncs.

The device's own web UI is reachable at `http://<device-ip>/` — the address is
shown under **Settings → WiFi** — and at `http://tigerscale-XXXX.local/` (the four hex digits are shown on that same screen) where mDNS
resolves.

## Troubleshooting

Start with [TROUBLESHOOTING.md](TROUBLESHOOTING.md). The single most common cause
of "no readers detected" is having built the wrong transport env.
