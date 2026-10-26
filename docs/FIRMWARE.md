# Firmware internals

How the firmware is organised, and the traps that have already cost this project
debugging time. If you are making a change, read [CODEMAP.md](../CODEMAP.md)
first — it maps every section and function, and its "Landmines" table is the
short version of what follows.

## Shape of the code

One Arduino C++ file, **about 17 500 lines**, divided into 26 numbered sections plus
`§AUDIO` and `§LVGL`. The table of contents at the top of the file is generated
by `bash scripts/update_toc.sh` from the `// §N — TITLE` banners, so it cannot
silently disagree with the file.

`i18n.h` holds every on-device string: **164 keys × 11 languages**
(EN/PT/FR/ES/DE/ZH/IT/PL). The web UI's translations are separate, under
`data/www/locales/`.

Why one file: it started as an Arduino sketch and grew. Splitting it is a real
option but a large, behaviour-risky change on hardware that cannot be
regression-tested automatically — hence the navigation tooling instead.

## The weighing pipeline

Supported blank generic NTAG213/215/216 tags are detected during
normal scanning, even without a spool on the scale or an account connection.
The detector checks a seven-byte NXP UID, the Type 2 Capability Container, and
the initialized empty-NDEF header from [NXP's datasheet, section 8.5.6](https://www.nxp.com/docs/en/data-sheet/NTAG213_215_216.pdf).
NTAG213's Lock Control TLV and the simpler NTAG215/216 header are supported.
The empty NDEF record `03 04 D8 00 00 00 FE 00` observed after a phone erase is
also recognized, with Capability Container versions 1.0 and 1.1.
This recognizes an initialized empty tag; it cannot establish that a tag has
never been used, or prove that it is writable. Read failures and TigerTag Init
markers do not trigger the notice. Detection itself does not write tag memory.

For a bench check, place a spool with two erased tags on the scale. With one
blank tag the badge says it is waiting for two; scanning continues. Two distinct
blank UIDs must both have been seen within 500 ms throughout a one-second
settling window, and the spool must weigh at least 20 g. The picker opens once
per physical load. Exit, declining a confirmation, reader dropouts and RF-cache
expiry do not re-arm it. After exiting, the badge requests a lift; a loaded
platform must become empty (within 5 g for 700 ms with fresh HX711 samples, independently of display filtering)
before another placement can reopen it. A missing HX711 cannot count as removal.
`[RFID] Blank NTAG21x` logs the detected UID and reader. Blank UIDs stay out of
normal metadata and inventory weight uploads; Hardware Test still shows raw UIDs.
A failed NTAG header read is unknown, never a written-tag result. A valid NTAG
header must identify an empty format or one of the three supported TigerTag
markers before it enters the corresponding workflow. Confirmed blanks evict
old metadata from RAM/NVS and clear stale UID/display fields, so erasing a
previously written tag cannot resurrect its cached brand.

```
HX711 → readWeight() → median + EMA filter → handleWeighWorkflow() → cloud
```

`handleWeighWorkflow()` is a state machine:

```
WF_IDLE → WF_SCANNING → WF_STABLE_WAIT → WF_SENDING → WF_DONE → WF_IDLE
```

Known-tag admission samples the load cell again after NFC work; a rejected or
stale read does not enter the UID dedup/latch cache or delay the next poll.
This prevents a blue recognized-tag icon and beep from being followed by a
false no-UID timeout. Cached identity is painted before metadata refresh.
Blue means the tag format was recognized, not that its inventory lookup finished.

Normal status progresses through Checking tag pair, Loading spool, Weighing,
Sending, Synced, then Remove. Inventory/container lookup finishes before the
weighing phase is shown, while the stability window continues in parallel.
Erase remains disabled throughout identification, lookup, weighing and sending,
including the normal reread after assigning tags. Completed sessions and idle
recovery/erase retries can enable it once background work is finished; both the
button and action use the same eligibility check.

- **`readWeight()`** applies a median filter then an exponential moving average.
  Small fluctuations use a fine EMA alpha of 0.04; the fast path requires both
  a rapid change in g/s and at least 5 g between the median and EMA. Confirmed
  load steps still restart the filters at the latest sample. The 0.5 g display
  hysteresis compares readings after the dead-zone offset, holding small changes
  without applying that offset twice.
- **`WF_STABLE_WAIT`** requires the reading to stay within `±STABLE_EPSILON_G` for
  `STABLE_WINDOW_MS`, with a 15 s ceiling after which the best candidate is sent
  anyway rather than hanging forever.
- **The settle window is tracked from `WF_SCANNING`, not from `WF_STABLE_WAIT`.**
  `updateStableWindow()` runs in both phases. The load cell reads throughout the
  scan, so a spool that settled while the readers were working has already
  earned the window by the time the workflow asks for it: measured, a scan that
  ran to its 8 s timeout now leaves `WF_STABLE_WAIT` after **14 ms** instead of a
  fresh 1.2 s. A scan that exits early — both tags read in under a second — still
  waits the full window, because the weight genuinely has not settled yet. The
  change removes a double count; it does not shorten the measurement.
  That function also refuses to call the weight steady until the slope ring
  buffer has filled: `wfCurrentSlope` is 0.0 until then, and 0.0 otherwise means
  "perfectly steady", which would read as stable at exactly the moment a spool
  is being placed.
- **Net weight** is gross minus the spool's container weight, fetched from the
  user's inventory. If that fetch fails the send still proceeds with net = 0
  rather than being blocked.
- **It is not clamped to `measure_gr`**, the manufacturer's nominal fill. Spools
  routinely leave the factory holding a little more than the label says, and the
  scale reports what is on it. The clamp that used to be there was also the
  source of a race: `measure_gr` is only read on the path that fetches the
  inventory record inline, never on the one that uses the value prefetched
  during `WF_SCANNING`, so the same spool at the same gross weight was sent as
  524.8 g or 500.0 g depending on whether the prefetch beat the settling time.
  Making the workflow faster made the wrong value win more often.

### Automatic zero and drift

`processAutoTare()` uses fresh HX711 samples, independently of display filtering.
It corrects only an idle, untagged platform within ±2 g after at least three
seconds and ten samples with a total range no greater than 1 g. Samples more
than 300 ms old, gaps, ongoing inventory work and detected tags interrupt
qualification. Corrections smaller than 0.5 g are ignored; corrections have a
30-second cooldown and a cumulative ±5 g limit from the last explicit zero.

Stable negative readings below -2 g, or idle readings between +2 g and the
20 g scan threshold, require **Zero Scale**. Exceeding the cumulative limit
also latches this warning. Weight uploads and new assignments are blocked
until the user zeros the scale. A larger positive reading can be a real load
and cannot safely be classified as an offset from weight alone.

Startup restores the saved explicit baseline; an absent or invalid baseline
requires an empty-platform Zero Scale. Firebase login never changes the zero.
Manual zero averages ten fresh ADC readings, persists the baseline and resets
the display filters. Drift corrections are not persisted. Every adjustment
logs its reason, reading and old/new offset. A failed manual sample set leaves
the offset unchanged and asks for zero again.

Spool removal clears the session separately, including when a negative offset
remains. Missing sensor samples cannot qualify removal. The prior unbounded
negative-drift tare and login-triggered tare must not be restored: they could
hide errors or zero a spool already on the platform.

### If the scale reads 0 g or inverted "no matter what"

Check the **sign** of raw `scale.get_units()` first, before touching filters or
auto-tare logic. A swapped load-cell wire produces exactly this symptom, because
the downstream `if (weight < 0) weight = 0` clamp makes a hardware polarity fault
look identical to a software bug. This has already happened once.

### Unrecognized RFID tags

A UID alone is not a TigerTag. Unrecognized tags remain grey on the home screen
and are excluded from metadata and automatic weight uploads. In particular,
four-byte MIFARE Classic UIDs must not bypass the NTAG header check. HSU reader
logs report UID, ATQA and SAK on detection; these identify chip characteristics,
not a filament brand. For four-byte Classic 1K candidates, a read-only probe
authenticates sectors 0/1 and decodes blocks 1, 2, 4 and 5, with up to three attempts
per placement. It checks the documented GF material identifier; this is format
recognition, not verification of Bambu's RSA signature. The derivation and layout
follow [Bambu-Research-Group](https://github.com/Bambu-Research-Group/RFID-Tag-Guide).
Unassociated candidates cannot upload weights. Original Bambu tags remain
unchanged throughout import and subsequent weighing.
Weight updates require an existing inventory document rather than creating a
weight-only record for an unknown UID.

### Importing original Bambu tags

On HSU readers, a first import requires two distinct native tags with matching
decoded material, variant, color, nominal weight and diameter. The scale asks
whether to add the spool, then asks for its container type. Exit cancels import;
lift and replace to retry. Both tags are freshly authenticated before saving.

Each native UID maps deterministically to `TigerData_Bambu_<uppercase UID>`.
The two inventory documents have reciprocal twin links, so Studio groups them
as one spool. Creation is atomic and requires both documents to be absent;
reconciliation after a lost response preserves existing data. Later placements
can recognize the saved pair from either tag. Normal weighing updates these
records, while the scale's Erase control remains disabled for native Bambu tags.

The conversion uses decoded material/color/capacity and Bambu's brand ID, with
the selected container tare and measured remaining weight. A unique non-refill
SKU match promotes it to TigerData+: the tag's variant, diameter and capacity
select a product from `bambu_catalog.h`, and the public product API must confirm
the exact SKU, product ID, brand, diameter, capacity and non-refill status before
the catalog fields are saved. New imports receive the name, image, print
settings, document links and complete `catalogProduct` metadata. Unknown or
ambiguous SKUs remain TigerData; an API failure leaves the inventory unchanged.

Existing generic Bambu pairs upgrade on their next read with an atomic masked
update to both documents. Version preconditions and reconciliation preserve
concurrent changes and recover lost responses. Weight, container, identities,
tag links and unrelated account fields are excluded from the update. Pairs
already carrying a product ID skip the catalog request and preserve edits.
The conversion does not merge an existing manually entered inventory spool.
Unknown material mappings and non-1.75 mm diameters are rejected. This is a
scale-side TigerData conversion, not official native-tag support in Studio;
external readers still see the original Bambu format.

Regenerate the compact SKU index from Studio's public
`assets/db/tigertag/id_catalog.json` using
`python scripts/generate-bambu-catalog.py path/to/id_catalog.json`. The generated
header records the source SHA256 and excludes duplicate SKUs and refills. It is
part of the application image, so updating it needs no filesystem flash.

### Assigning inventory to a blank tag pair

Before opening the picker, both blank tags must remain freshly readable for one
second. The home badge says "Waiting for 2 tags" until both are detected, then
"Checking tag pair..." with a spinner during this check. Intermittent reads can
restart the check even after both read beeps.

The picker loads the signed-in account's inventory in pages, selecting active
filament records (`id_type=142`) whose IDs start with `TigerData_` or legacy
`CLOUD_` (case-insensitive, preserving the exact document ID for later reads).
Physical-tag inventory records are excluded. A load or memory failure
rejects the list instead of displaying a partial inventory. Cards show brand,
material, color and remaining grams. All spools appear initially, neutrals first
(white to black), then colors in hue order. Like Studio, HSL saturation below
15% means neutral; the Clear aspect (21) or an explicit color name of Clear also
belongs in this group, retaining its original swatch. This includes catalogue
Clear colors marked Basic. Colored Translucent aspects remain subject to the HSL threshold.
Touching either rail activates only that group; the upper
rail navigates lightness, the lower rail hue. Manual scrolling updates the active
marker to the leftmost card. Material opens an alphabetical list of available
types, with ALL first to clear that material filter. Choosing a material or ALL
resets both color rails and shows every matching spool. Exiting the material menu
preserves the existing filters. The list wraps in both
directions using three virtual copies, recentring after each gesture. Five reusable
card objects bound LVGL memory use and only change their text when recycled.
The full inventory list is fetched once on entry. "Preparing tags" before the
write fetches only the selected full record and checks the two UID assignments;
the later save updates the account and does not reload the list.
HTTP response bodies are received through HTTPClient (including chunk decoding)
into a bounded 1 MiB PSRAM buffer before JSON parsing. This avoids stream reads
ending between TLS packets. Transient failures get three attempts with backoff;
401 gets one token refresh. Other client errors and memory exhaustion stop
immediately. Failed listing offers Retry without lifting; partial results are
discarded before a new attempt.
Exit is always available in the picker. Selecting a card enables Validate,
which confirms the selection and starts tag preparation directly.
Before either tag is changed, selection and header reads get up to six attempts
per reader with RF field reselection. A different UID or incompatible header
stops immediately. Logs distinguish failed selection from failed header reads.

If the selected inventory spool has no `container_id`, the scale asks which empty
spool it uses before preparing tags. The list comes from Studio's shared
`spools_filament.json`, with the filament's brand first (MasterSpools first for
refills) and any account `containerOverrides.containerWeight` corrections applied.
The chosen `container_id` and `container_weight` are saved on both new tag records
in the same assignment commit. Existing Firestore value types are replaced when
setting these fields, including integer weights and explicit nulls. Pending
assignments from older firmware recover their selected container from the saved
batch. Retries keep the original tag identities but rebuild the batch from current
inventory data with fresh version preconditions.
A failed save keeps the recovery record; server error details are logged. Erasing
tags preserves these fields.

A normal tagged-spool read also asks when the existing record has no container.
The choice updates only those two fields on reciprocal twins in one conditional
commit, then the current weighing uses the selected empty weight. Known types are
preserved. Exit, removal or failure stops that weighing cycle from uploading gross
weight as remaining filament; lift and replace to retry. Transient saves retry
three times and reconcile lost replies. Once a recognised container is assigned,
Studio can edit it from the spool details' Container card. Studio currently hides
that card and its edit button for unknown containers.

The panel retains its full-canvas flush: partial rectangle transfers produced
right-edge corruption on the JC3248 bench, despite correct framebuffer pixels.
Card recycling avoids unnecessary label allocation/layout during scrolling.
Two fresh weight samples confirm a rapid step of at least 5 g before the median/EMA restart at the latest
sample. A single outlier cannot trigger that reset; existing tare and workflow
settling guards still apply. Above the weight, separate left/right tag outlines
represent the physical readers: red X absent, grey unidentified/blank, blue
recognized TigerTag. Cloud twin lookup never lights an unread antenna. The
indicators retain their last read while scanning is locked; polling confirms
absence when scanning resumes. Zeroing a loaded platform does not hide its tags.

The home button reads "Zero" over "Scale" and retains the former Tare behavior
(set/save the offset and cancel pending automatic tare). Erase tag shares that area and is disabled unless
two distinct tags have been physically detected, and is also disabled when both
are confirmed blank, except when resetting a pending assignment. One confirmation
covers both tag erasure and inventory unlinking. The account must be reachable so a conditional inventory release can
be prepared before either tag changes. Fresh pair preflight precedes erasure;
missing/swapped/unsupported tags prevent writing. Erasure uses the same
three-attempt writer and full read-back checks as
assignment, clearing the 144-byte TigerTag filament record to empty NDEF. It does
not erase the UID, capability/configuration/lock pages, additional user memory
beyond that record. Once both tags verify blank, one atomic inventory update
preserves the spool without tags and removes the old UID assignments. The
prepared versions prevent concurrent overwrites. A verified first tag is not
rewritten when retrying the second. Partial erasure retains the account
assignments and reports the count. Successful erasure and unlinking return home
without an OK dialog. If unlinking fails, the user can retry immediately without
rewriting tags, or lift/replace later to use the existing blank-tag release flow.
An uncertain response is reconciled against the exact preserved inventory data.
Pending assignment recovery can be cancelled through Erase tag, including when
the original tags are already blank. Reset requires the same two physical UIDs
and the original account. The journal is cleared only after both tags verify
blank and the inventory release succeeds; partial erasure or failed release
retains recovery. Unrelated tags and another account cannot cancel it.

Write and erase failures keep their current session open with a translated
left/right positioning prompt and Try again / Cancel. The direction identifies
the failing reader (first slot right, second slot left); tags already verified
are not rewritten. Preflight failures can also be retried after repositioning.
A changed UID or physical removal stops the operation, and cancelling preserves
the existing partial-write recovery behavior. Failed verification reads get
three bounded attempts with same-UID reselection before restarting a tag; a
successful read still has to match every expected byte. Failure logs name the
write/erase phase and distinguish read errors from data mismatches.

Before listing spools, the cloud worker checks the presented UIDs for existing
assignments and offers release if needed. This makes the previous spool available
in the untagged list, including for reuse of the same tags on the same spool.
After selection and confirmation, the cloud worker re-fetches the selected document and checks
that its update time still matches the displayed list. It preserves all original
Firestore fields, including unknown nested values, rack/product links, container,
weight and history. It prepares a conditional commit that creates both UID
records, cross-links their twins and deletes the chipless source atomically.
An existing UID assignment produces a distinct registered-tag condition,
rather than the changed-inventory-record error. The user can confirm releasing
that assignment: the old inventory fields are first copied to `TigerData_`
entries, with chip-version/index/twin/backup fields removed. A physical pair
produces one untagged entry. Backup/listing flags and weight updates do not split reciprocal twins; the most recent `last_update` supplies
the remaining weight. Conflicting retained fields or two unlinked records open
a picker asking which entry to keep. Exit changes nothing. Both document
versions are re-read after selection; an edit invalidates the choice. Container,
product links and unknown fields from the chosen entry are retained. References
to tags outside the presented pair block automatic release.

Both presented tags must freshly verify as blank before release. One conditional
batch creates the preserved entries and deletes the old UID records at their
captured update times. Cancelling this confirmation changes neither account nor
tags. After a successful release, inventory is listed and the user chooses the spool
to assign. Its document is revalidated before the normal write flow continues. A later write failure leaves the previous spool
safely untagged in inventory. A lost release response is reconciled against the
full saved fields, excluding the server-generated update time. Runtime request
`/tag-release.json` is removed after the release attempt. Existing UID records
are never silently overwritten, and a concurrently changed source cannot be deleted. The contract matches
[Studio Manager's inventory promotion](https://github.com/TigerTag-Project/TigerTag-Studio-Manager/blob/main/renderer/inventory.js).

The tag codec follows the
[official SDK field mapping](https://github.com/TigerTag-Project/TigerTag-SDK-JS/blob/main/src/tag.js).
It writes an unsigned TigerTag or TigerTag+ according to the product ID, copies
material/color/print settings, and converts inventory remaining grams to the
chip's unit (mg/g/kg). It rejects values outside the binary field ranges.
The pair shares a real chip-epoch timestamp, and both cloud records use exactly
that timestamp, with indices 1/2 and 2/2. Signature bytes remain zero; no
manufacturer certification is created.

Both original UIDs must still select as blank before either tag is altered.
Only user pages 04-27 are writable. The body is verified before committing the
format marker on page 04, then all 144 bytes are compared. Only a fully verified
pair can trigger the account commit. Partial failures report the verified count,
with up to three attempts per tag for missed reads or writes. Retries reselect
the original UID and reuse the exact payload, timestamp and pair index. A
verified first tag is not rewritten when the second is retried. Only the
session's original blank marker or its own committed marker is accepted during
resume; unexpected markers, different UIDs or lifting stop the operation. If
all attempts fail, the inventory source stays intact; erase both tags before
starting a new assignment.
HSU also retries an individual page up to three times. Recovery cycles the RF
field with 15 ms off/on settling, reselects the original UID and reads the aligned
user-data block. If the requested bytes already match after a lost acknowledgement,
no duplicate write is needed. A different UID aborts recovery. Page diagnostics
include the command ACK, PN532 status and tag ACK, while final whole-record
verification remains mandatory.
Normal HSU selection also allows 15 ms after field-off and field-on; record writes
leave 2 ms between successful body pages for marginally coupled spool tags.
After a successful pair write and account save, the normal RFID/metadata/weigh
workflow starts immediately on the still-loaded spool, without an OK dialog, so
its new filament and container information appears without lifting. This
clears stale UID and metadata state without taring. The blank-picker prompt
remains latched until physical removal. Failed or cancelled assignments still
inhibit normal weighing until the assignment load is lifted.

Before writing, the tag identities, source ID, selected container and physical
payload are saved in `/tag-assignment.json`; `/tag-assignment-commit.json` holds
the prepared batch. These are runtime files, not filesystem-image assets.
Partial physical writes and failed account saves retain recovery. Retries verify
the original pair, reconcile an already completed commit, then re-read the source
and target records before constructing a fresh conditional batch. App-only edits
and current remaining weight are preserved. The tag's weight snapshot need not
match a later account weight, but changes to its filament payload are conflicts.
The saved batch is never blindly replayed. Local parsing uses the same nesting
limit as live responses so nested catalog/history metadata remains valid.

A missing/reassigned source, existing UID assignment or permanent commit
rejection marks a persistent conflict. An incomplete physical write also
requires reset because its tags cannot be verified for a commit. The home screen
shows Assignment needs reset / Use Erase tag, and subsequent placement does not
reopen Resume. Another spool cannot trigger recovery for the saved tag pair.
Temporary network failures still offer retry. Erase/reset is an explicit way to cancel
with the original pair, including partially written tags; it preserves current
inventory data and honors the same conflict selection and version checks.

Fresh empty-platform samples clear displayed material, UIDs and session state
independently of pending recovery. Late metadata cannot restore an old spool on
an empty platform, and stale HX711 readings cannot qualify removal. Changing
accounts cannot redirect a journal or discard another account's assignment.
Do not replace the filesystem image while a recovery record is pending.

Run `python scripts/test-inventory.py` after a PlatformIO build to exercise the
actual codec, migration construction, writer failure paths, color sorting and
physical-removal latch with native fixtures. Hardware acceptance still requires
placing one spool with two blank tags, selecting a real inventory record, confirming
both writes, and checking the resulting twin records in Studio Manager.

## NFC

`PN532Reader` (§5) wraps the Adafruit library behind a small
`isNewCardPresent()` / `readCardSerial()` / `uid` surface, so the polling loop and
metadata code are identical across all three transports. Only the class's
internals differ per `RFID_TRANSPORT_*`.

HSU consumes complete UART response frames for UID and page reads, validating
lengths, checksums, and response types. Adafruit's fixed-size UID read leaves two
bytes after a seven-byte UID; late poll replies and unconsumed RF configuration
replies can then be mistaken for memory-read responses. The HSU wrapper also
waits for the RF retry to finish and consumes both RF configuration replies.
Before selecting a tag, HSU switches the opposing field off and resets the
selected field, then switches it off again during session cleanup. Pair checks
allow three attempts for missing UID or memory replies; a different UID or
successfully read contents that do not match fail immediately.
`[RFID HSU] READ` and `[NTAG] pages03-06` logs expose the raw reply and decoded
header without writing to the tag.

Three things worth knowing:

- **Transport is compile-time.** See [HARDWARE.md](HARDWARE.md). The single most
  common failure mode in this project's history is firmware built for the wrong
  transport, which detects nothing and reports nothing.
- **RF power is a runtime setting**, 6 levels (0–5), default 3, adjustable from
  Settings → Hardware and persisted in NVS. It exists because the two antennas
  sit ~75 mm apart facing each other and cross-talk. Levels 0–4 retain the
  reduced-drive range; level 5 is the factory 106 kbps Type A analog profile from
  [NXP's PN532 manual, table 19](https://www.nxp.com/docs/en/user-guide/141520.pdf),
  available for more distant or weakly coupled spool tags.
- **Read feedback** is one short beep for each distinct physical tag in a
  placement, including blank tags. Mute and volume still apply; read feedback
  uses a single pulse regardless of the theme preview setting. It occurs before
  metadata/cloud-twin deduplication. RF dropouts and post-write rereading do not
  repeat it. `readWeight()` re-arms the two-UID sound latch after 700 ms of fresh
  empty-platform samples; `tagReadBeep()` requires a fresh loaded reading, so
  removal echoes and stale sensor values stay quiet. The separate 1.5 s UID
  dedup window (`isDuplicateRecentUid`) is unchanged.

## <a id="lvgl-v8-traps"></a>LVGL v8 traps

The whole UI is LVGL v8.4. Each of these has cost a real
compile-flash-photograph round-trip on hardware.

- **Never call `lv_timer_handler()` from inside a click callback.** The callback
  already runs inside `lv_timer_handler()`'s own call stack. The pattern used here
  is: the callback sets a flag, and a genuine top-level context such as `loop()`
  does the blocking screen work.
- **`lv_scr_load(newScreen)` before `lv_obj_del(oldScreen)`.** The reverse order
  leaves LVGL's active-screen pointer dangling between the two calls, which
  crashed and rebooted the device 100% reproducibly when it happened here.
- **`lv_obj_align_to()` centres the declared box, not the visible ink.** Icon-font
  glyphs (`LV_SYMBOL_*`) have asymmetric side bearings, so a "centred" glyph can
  look off no matter what offset you pick. If a small icon will not centre after a
  couple of tries, stop guessing pixels and use a pre-rasterised bitmap — see
  `icon_bolt.h` for the pattern (`lv_img_create()` + `lv_img_set_src()` +
  `lv_obj_center()` centres exactly, with no font metrics involved).
- **`lv_obj_set_style_transform_angle()` rotates around the top-left corner** by
  default. Without an explicit `transform_pivot_x/y` set to the object's own
  centre, a rotated shape can swing entirely outside a small parent's clipped
  bounds and simply never appear.
- **Some constructors call `lv_obj_align()` internally** — `lv_keyboard_create()`
  does — which sets a *persistent* style property. A later plain
  `lv_obj_set_pos()` is then silently reinterpreted as an offset from that
  alignment rather than an absolute position. Use
  `lv_obj_align(widget, LV_ALIGN_TOP_LEFT, x, y)` for such widgets.
- **`LV_KEYBOARD_CTRL_BTN_FLAGS` bakes in `LV_BTNMATRIX_CTRL_CHECKED`** on every
  control key (shift, 1#, backspace). It is LVGL's way of giving those keys a
  muted look, *not* a per-key toggle state. Styling via the shared
  `LV_STATE_CHECKED` therefore lights all of them at once, and lights them from
  creation regardless of actual state. To style one button independently, hook
  `LV_EVENT_DRAW_PART_BEGIN` and override `dsc->rect_dsc` / `dsc->label_dsc` when
  `dsc->part == LV_PART_ITEMS && dsc->id == <index>`.
- **Never let raw-`gfx` drawing reach the panel while an LVGL screen is loaded.**
  The two renderers do not coordinate, and LVGL only repaints what *it* thinks is
  dirty, leaving stale pixels behind. A reachable `displayMessage()` call on a
  live LVGL path is a bug — convert it to the shared
  `lvglCenteredScreen()` / `lvglAddStatusBadge()` / `lvglAddCenteredLabel()` toast
  pattern, or delete it if the screen already shows the same information.

`LVGL_TEST_MODE` (§LVGL) is a debugging escape hatch, normally 0. Setting it to 1
makes `loop()` run only `lv_timer_handler()`, isolating the rendering pipeline
from the scale, NFC and cloud code. It is not a migration flag.

## Memory

- **Never use `ps_malloc`.** It returns null silently. Use
  `heap_caps_malloc(n, MALLOC_CAP_SPIRAM)` with a DRAM fallback.
- Free heap has been observed dropping to ~15–23 KB during Firebase HTTPS bursts,
  with frequent `SSL - Memory allocation failed`. A reported
  reset-after-two-weighings could not be reproduced across 11 follow-up cycles, so
  this is a watch item rather than a diagnosed bug. If you are chasing a reset,
  start here.
- Large JSON responses use `DynamicJsonDocument` with filters. A
  `StaticJsonDocument<256>` fails *silently* with `NoMemory` on some of these
  responses, leaving fields mysteriously empty.

## Web server and WebSocket

An `ESPAsyncWebServer` serves the LittleFS web UI plus a JSON API, and pushes
live state over a WebSocket at 10 Hz. `buildWsFrame()` is the single source of
truth for that payload: only changed fields go out on each tick, with a full
snapshot on connect and every 30 s.

Because it is *async*, handlers must not block. The heavy Firestore work is
dispatched to a worker task pinned to core 0 (§14).

## <a id="screen-over-http"></a>Seeing and driving the screen over HTTP

Four routes, no setup and no access code, so checking a screen costs two
requests instead of a trip to the bench:

| Route | What it gives |
|---|---|
| `GET /screen.bmp` | the screen as a 24-bit BMP, 480x320 |
| `GET /api/tap?x=&y=` | a press; add `x2`/`y2` for a swipe |
| `GET /screen.ver` | four bytes, the frame counter |
| `GET /screen` | the picture in a page, click to tap, drag to swipe |

```bash
curl -s -o s.bmp http://tigerscale-CE3F.local/screen.bmp
curl -s "http://tigerscale-CE3F.local/api/tap?x=415&y=285"
curl -s "http://tigerscale-CE3F.local/api/tap?x=200&y=280&x2=200&y2=90"
```

Three decisions worth keeping:

- **The picture comes from the canvas, not from the panel.** `gfx` is an
  `Arduino_Canvas`, so a full framebuffer already exists and is by definition
  what was last drawn -- no mirror sprite, no copy in the flush callback, and no
  read-back from the AXS15231B, which is slow and unreliable. It is served from
  a one-memcpy snapshot in PSRAM, because serialising 450 KB takes far longer
  than a repaint and reading the live canvas would tear across two screens.
- **A swipe is the press walked in twelve steps.** LVGL decides drag-or-tap from
  the movement between two consecutive input reads, so a single jump from start
  to end scrolls nothing at all. Without this, half of any list longer than the
  screen is unreachable from a terminal -- which is half the point.
- **`/api/tap` answers late, and waits without sleeping.** It returns once the
  press has been taken and the screen has finished changing, so the response is
  the signal that the next capture is worth taking. The waiting is done with
  `RESPONSE_TRY_AGAIN`; sleeping in a handler blocks the async TCP task and
  every other request with it.

An injected press does not bypass screen sleep. It goes through `tsRead()`, so
on a dark panel it wakes the scale and is swallowed exactly as a finger is --
verified on the bench with the screen asleep and a tap aimed at the Settings
button, which woke the device onto the home screen. A remote command must never
act on a screen nobody can see.

**What it is and is not.** It is what LVGL drew. Geometry, text, translation,
truncation, which screen is up: reliable. Colour as the eye sees it, backlight,
panel rendering: not. Nor can it see the panel itself, so a change to the flush
path or below can look perfect here and be wrong on the glass.

A swipe takes about two seconds, and the reason is worth recording: each of its
twelve steps scrolls the list, which repaints the screen, which costs a full
307 KB push to the panel -- about **175 ms per step**. A finger pays the same
price, which is why scrolling feels heavy.

## Live view

A bench tool: the panel, in a browser, with clicks going back the other way.
Open `http://<scale-ip>/live` (port 80 redirects to the real server on 81) and
type the six-character code from Settings → LAN. The switch on that page turns
the whole thing on and off. §LIVE in the .ino holds the implementation.

The design turns on one fact: **`gfx` is an `Arduino_Canvas`, so a complete
480×320 RGB565 framebuffer already exists** and `getFramebuffer()` hands it over.
The screen is therefore readable in full at any instant, and no frame ever has
to be reconstructed from the rectangles LVGL repaints. That is what makes a
viewer arriving late get a correct picture rather than a patched-together one.

- **Capture is timed off `lv_disp_flush_is_last()`**, which marks the end of a
  whole LVGL refresh. Sampling at any other moment can catch a half-drawn
  screen. A 500 ms sweep runs as well, to catch the paths that bypass LVGL —
  the boot splash and the screensaver draw straight onto the canvas.
- **The unit is a band of 16 landscape columns.** Rotation 3 stores a landscape
  column contiguously, so a band is one unbroken 10 240-byte block. Each band is
  copied out, hashed, and sent only if its hash differs from what that viewer is
  known to hold. A whole screen is 30 bands and about 21 KB after RLE.
- **A frame is delimited by its end, not counted at its start.** The browser
  decodes bands into an off-screen `ImageData` and calls `putImageData()` once,
  on `FRAME_END`. Nothing partial ever reaches the visible canvas, so a page
  change arrives as one image by construction rather than by tuning.
- **Raw lwIP sockets, not the async server on port 80.** `ESPAsyncWebServer`
  copies every message into an internal-RAM queue capped in messages rather than
  bytes, so a viewer that stops draining becomes a heap leak that kills the
  device somewhere else; AsyncTCP is also not callable from an arbitrary task.
  A blocking `send()` in the live task, against a fixed buffer, *is* the
  backpressure: a slow viewer costs time, never memory.
- **Keep-alive is load-bearing.** Answering each tap with `Connection: close`
  meant one TCP connection per click, and since the scale closes first, each sat
  in `TIME_WAIT` for two minutes. lwIP is built with ten sockets, so a minute of
  ordinary clicking exhausted them and the port began refusing connections — the
  feature worked beautifully and then simply stopped, recovering a minute later.
  One pooled connection now carries every tap.
- **Taps are injected inside `tsRead()`**, not at the LVGL input driver, because
  that is the one place both consumers meet: LVGL's `read_cb` calls it, and so
  do the screens that still poll the panel directly.
- **Two viewers, deliberately.** Each one multiplies the pbufs in flight, and a
  third took free internal RAM tens of kilobytes below where two sit. A ping
  every 5 s doubles as the liveness check, so a browser that is killed rather
  than closed stops holding a slot within a few seconds.

### What it actually costs

Measured on the bench with two viewers in Chrome, over 236 page changes in five
minutes. The firmware logs this split itself — see the `[LIVE]` line in
`liveCapture()`.

| From a click to the new screen appearing | avg |
|---|---|
| the scale rebuilding its own screen | **483 ms** |
| encoding all 30 bands | 32 ms |
| sending them | 119 ms |
| **total** | **638 ms** |

**Three quarters of that is the scale, not the mirror.** A finger on the glass waits
the same ~600 ms for the settings page to be built; the live view adds about
158 ms on top. If this number needs to come down, the work is in the LVGL screen
builders (`runSettingsMenu()` creates roughly a hundred objects, most of them
hand-drawn vector icons), not here. Keep the split in mind before optimising the
wrong half — that log line exists precisely because a slow screen and a slow
mirror are indistinguishable without it.

The send is round trips rather than computation: 21 KB against lwIP's ~5.7 KB
window is four of them, and on the bench LAN a ping to the *gateway* already
averages 25 ms with a 140 ms tail. On a quieter link it lands proportionally
sooner. Making it meaningfully faster means sending fewer bytes, not faster code.

An untouched screen costs 2 bytes per 30 s. Continuous navigation leaves the
long-running view pixel-identical to a viewer that has only just connected —
which is the real test for residue, since a viewer that just arrived cannot be
carrying any.

That five-minute run is roughly twenty times what a person does, and it is the
load the guards are sized against: free internal RAM bottomed out at 9.4 KB,
capture paused nineteen times and hung up once, and nothing else on the scale
noticed — no reset, no missed weighing, no dropped reader.

It also gives memory back rather than taking it. The 10 KB scratch band is held
only while someone is actually watching, an outgoing byte budget caps sustained
traffic (every byte passes through an lwIP pbuf, and pbufs come from the same
internal heap everything else needs), and below a free-heap floor it stops
capturing, then hangs up entirely below a harder one.

## OTA

`otaFetchLatest()` reads `version.json` from GitHub Pages and compares `version`
against `TIGERSCALE_FW_VERSION`; `otaApply()` streams the binary with a progress
bar and verifies a SHA-256.

- **`firmware_url` must point at the plain `firmware.bin`.** `Update.begin()` and
  `Update.write()` only replace the app partition, so handing them a
  `firmware.factory.bin` corrupts the bootloader and partition table.
- The manifest is generated from `TIGERSCALE_FW_VERSION` by the release workflow,
  so the firmware and the manifest cannot drift apart.
- **Two boards, one manifest.** The flat `version` / `firmware_sha` /
  `firmware_url` keys describe the ESP32-S3-Touch-LCD-3.5**B** build and always
  will: every scale in the field is a -3.5B and reads exactly those keys. A -3.5
  reads `boards["3.5"]` and has no fallback to them, because the fallback would
  install the other board's image and leave a black screen.
  `scripts/make-manifest.py` refuses to generate a manifest that breaks this.
- **Known limitation:** published builds assume HSU. A unit wired for SPI or I²C
  that takes a published update loses its reader.

## Keeping the tooling honest

`bash scripts/verify.sh` is the entry point — it runs every guard (i18n, CJK
font coverage, CODEMAP, TOC, emoji, mojibake, release notes) and then builds.
Each guard is also runnable on its own:

```bash
bash scripts/check-i18n.sh      # every key present in all 8 language blocks, in enum order
bash scripts/check-codemap.sh   # CODEMAP line numbers still accurate
bash scripts/update_toc.sh      # regenerate the in-file table of contents
```

CI runs them all.

**On Windows**, two quirks: there may be no system `python3` — the scripts fall
back to PlatformIO's own venv (`~/.platformio/penv/Scripts/python.exe`), or set
`PYTHON=` explicitly — and the toolchain refuses to *build* under Git Bash/MSYS.
So run the guards under Git Bash (`bash scripts/verify.sh --quick`) and build in
PowerShell:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run -e esp32s3_hsu_b
``` They were each broken on macOS before this repository's first
commit — two used bash-4-only builtins and GNU-only grep flags, and
`check-codemap.sh` printed `PASSED` while verifying nothing at all. If you
rewrite them, keep the property that an empty input set is an error rather than a
pass.
