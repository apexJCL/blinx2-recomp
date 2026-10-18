# pushbuffer-executor Specification

## Purpose
Defines how the toolkit's pushbuffer executor consumes the NV2A command stream a translated title submits: decoding transform-unit state, running vertex programs on the CPU, keeping the GPU fence honest, and producing frames on the CPU reference path.

## Requirements

### Requirement: The pushbuffer executor produces the title's frames
The toolkit executor SHALL be on by default (`RECOMP_PB_EXEC=0` turns it off) and SHALL consume each pushbuffer segment the title submits before `DMA_GET` reports it as consumed. It SHALL write clears and screen-space batches into the guest colour surface. With `RECOMP_FB_DUMP=<prefix>`, it SHALL write the drawn surface as BMP files.

#### Scenario: Intro movie frames on macOS
- **WHEN** BLiNX 2 boots on macOS with `RECOMP_FB_DUMP=<dir>/f`
- **THEN** within 60 s the dumps include 640x480 frames of the intro movie (studio logos, intro cuts), and the report shows 0 batches skipped as not screen-space

### Requirement: The GPU fence advances when the executor consumes the release
The executor SHALL implement `NV097_SET_CONTEXT_DMA_SEMAPHORE`, `NV097_SET_SEMAPHORE_OFFSET` and `NV097_BACK_END_WRITE_SEMAPHORE_RELEASE`. On a release it SHALL write the parameter, at the moment the method runs, to the semaphore context DMA object's base plus the semaphore offset.

When a bind method runs (`NV097_SET_CONTEXT_DMA_SEMAPHORE`, `NV097_SET_CONTEXT_DMA_REPORT`) the executor SHALL read the object's base and limit from instance memory: the handle's RAMHT entry (RAMHT located through `PFIFO_RAMHT`; a valid entry whose handle matches) gives the PRAMIN instance; the base is the frame in word 2, bits 31:12, plus the adjust in word 0, bits 31:20; the limit is word 1. It SHALL keep that result until the next bind of the same purpose and SHALL NOT re-read instance memory per release or per report. When RAMHT does not hold the handle, or the aperture is not mapped, it SHALL use base 0 with no limit and log this once. `NV097_GET_REPORT` SHALL write at the report object's base plus the method's offset. A release or report that would end past the found object's limit SHALL be refused and logged once.

#### Scenario: D3D fence word written by the executor
- **WHEN** the executor runs and the title releases its fence
- **THEN** the first release is logged with its value, its resolved address and its DMA handle and offset, and the word at `*(device + 0x30)` equals the last value released

#### Scenario: A semaphore object that does not start at physical 0
- **WHEN** Spartan's D3D binds object 8 (`0x0002B03D, 0x20, 0x00002003`, base physical 0x2000, limit 0x20) and releases at offset 0
- **THEN** the bind is logged with base 0x00002000 and limit 0x20, the value lands at 0x80002000, D3D's fence word, and physical 0 is untouched

#### Scenario: The gate titles' fences move from the mirror to the executor
- **WHEN** BLiNX 2 or Burnout 3 runs with a fence mirror registered and the executor on
- **THEN** the bind line shows the object's base (BLiNX 2: 0x1000 or 0, by build; Burnout 3: its fence page), the first release lands on the mirrored fence word, and the mirror logs `now written by the executor; mirror off`

#### Scenario: A re-bind refreshes the cached object
- **WHEN** a title binds a handle, rewrites that object's words in PRAMIN, and binds the handle again
- **THEN** releases after the second bind use the new base, and releases between the rewrite and the second bind used the old one

#### Scenario: A write past the object's limit
- **WHEN** a release's offset puts its 4 bytes past `limit + 1` of a found object
- **THEN** nothing is written, and one log line names the handle, offset and limit

#### Scenario: A report object with a non-zero base
- **WHEN** a title binds a report object whose base is not 0 and issues `GET_REPORT` at offset o
- **THEN** the 16-byte report lands at base plus o on every backend

#### Scenario: A handle RAMHT does not hold
- **WHEN** a title binds a handle that no valid RAMHT entry names
- **THEN** one log line says so, and releases through it use the bare offset as before this change

### Requirement: The submitted-to-completed fence mirror is only a fallback
A fence mirror registered with `xbox_Nv2aMirrorFence` SHALL stop writing once the executor has released a semaphore onto the same fence word. It SHALL keep mirroring when the executor is off, before the first release, or when the semaphore targets a different word, and it SHALL log once which case applies.

#### Scenario: Executor on
- **WHEN** the executor is on and the first release lands on the mirrored word
- **THEN** the log says `now written by the executor; mirror off`, and the mirror makes no further writes

#### Scenario: Executor off
- **WHEN** `RECOMP_PB_EXEC=0` turns the executor off
- **THEN** the mirror writes submitted -> completed on every ack tick, and the title passes its fence waits

### Requirement: Transform-unit state is decoded from the stream
The executor SHALL capture SET_TRANSFORM_PROGRAM into 136 instruction slots at the LOAD cursor, SET_TRANSFORM_CONSTANT into 192 vec4 constants at the CONSTANT_LOAD cursor, SET_TRANSFORM_EXECUTION_MODE, SET_TRANSFORM_PROGRAM_START, SET_VIEWPORT_OFFSET/SCALE and the SET_VERTEX_DATA* inline attribute values.

#### Scenario: Program upload at a cursor
- **WHEN** the stream sets the LOAD cursor and then sends N program words
- **THEN** the words land in consecutive slots starting at that cursor, and the cursor advances by one slot per four words

### Requirement: Program-mode batches are transformed on the CPU
When the execution mode is PROGRAM, the executor SHALL run the current program per vertex, take oPos as surface pixels with clip w (the XDK viewport epilogue), drop triangles with any w < 0, draw a vertex with w == 0 as w = 1 (as the D3D11 and Metal backends do; toolkit 9879d32, a Burnout 3 2D program), and rasterise with the existing surface model. Fixed-function mode SHALL keep the screen-space path. `RECOMP_PB_VSH=0` SHALL disable the program path, for A/B comparison.

#### Scenario: Title stage geometry
- **WHEN** BLiNX 2 reaches the title stage (after `title_movie_1a.sfd` opens)
- **THEN** the report shows 0 program-mode batches skipped as "not screen-space", and a `RECOMP_FB_DUMP` frame shows the stage, not black

#### Scenario: Path disabled
- **WHEN** the same run uses `RECOMP_PB_VSH=0`
- **THEN** program-mode batches are skipped, as on the screen-space-only executor

### Requirement: The CPU path is an oracle, not the product
The design SHALL state the stopping rule. Once one title-stage frame matches a reference (an xemu capture, or a golden frame checked against one), new per-pixel features SHALL go to the GPU render backends (`gpu-backend`) or to `render-fidelity`, and the CPU path SHALL be kept as the reference renderer (`RECOMP_PB_BACKEND` unset or `cpu`, the toolkit default).

#### Scenario: Reference frame matched
- **WHEN** a title-stage dump matches the xemu capture of the same scene
- **THEN** later rendering features are tracked against the GPU backends or `render-fidelity`, not added to the CPU path first

### Requirement: A batch keeps every index the title sends
The executor SHALL collect at least `0x80000` (524,288) indices per BEGIN/END batch from `ARRAY_ELEMENT16`, `ARRAY_ELEMENT32` and `DRAW_ARRAYS`, and every backend SHALL draw the whole list. The NV2A accepts batches of at least `0x0FFFFF` elements and retail titles are known to send at least `0x410FA` in one draw, so a smaller cap cuts real geometry. Indices SHALL stay 16-bit: the hardware faults on a `DRAW_ARRAYS` start above `0xFFFF`, so no title references more than 65536 vertices in one batch. When a batch would pass the executor's limit, the executor SHALL print one `[GPU] index batch over N indices` warning per run and SHALL count the batches that overflowed. Indices past `0xFFFF` from `ARRAY_ELEMENT32` SHALL be counted too. It SHALL NOT drop indices silently.

#### Scenario: The stage 1 water grid reaches the horizon
- **WHEN** BLiNX 2 draws its stage 1 water grid as one 4592-index quad list (the lighthouse warp, `runs/stage1-water/scripts/warp_lhp.txt`, flip 2490)
- **THEN** all 1148 quads are drawn on the CPU path, Metal and D3D11, and the cyan water reaches the horizon with no hard edge, as in xemu

#### Scenario: A quad past index 4096
- **WHEN** a backend smoke test sends an indexed quad list of more than 4096 indices as `ARRAY_ELEMENT16`, with a distinct colour on the quads from index 4096 on
- **THEN** a pixel inside a quad past index 4096 has that colour on the CPU path and on the GPU backend under test, and the two frames match

#### Scenario: Overflow is visible
- **WHEN** a batch sends more indices than the executor holds
- **THEN** the run log has one `[GPU] index batch over` line, and the overflow count on the periodic `[GPU]` summary line is non-zero

### Requirement: The odd index of an indexed draw is kept
The executor SHALL decode `NV097_ARRAY_ELEMENT32` (0x1808) as one index per word, appended to the open batch under the same limit and warning as `ARRAY_ELEMENT16`. The XDK sends the last index of an odd-count `DrawIndexedVertices` this way; dropping it loses the batch's last primitive.

#### Scenario: A triangle list whose last index is a 32-bit element
- **WHEN** a backend smoke test sends a triangle list as `ARRAY_ELEMENT16` words followed by one `ARRAY_ELEMENT32` word
- **THEN** a pixel inside the last triangle is drawn on the CPU path and on the GPU backend under test, and `0x1808` does not appear in the unhandled-method ranking

### Requirement: The summary says how big batches get
The executor's periodic `[GPU]` summary SHALL print the largest index count of any batch so far and the number of overflowed batches (`index batches: max M, N overflowed`), and SHALL print the count of `DRAW_ARRAYS` runs that reached past index `0xFFFF` when it is non-zero. A run log then shows whether a title ever needed more than an earlier cap, and whether the walker decoded a start the hardware would have rejected.

#### Scenario: Reading a title's largest batch from its log
- **WHEN** a golden or Burnout 3 run finishes with the NV2A trace on
- **THEN** its log's last `[GPU]` summary carries `index batches: max M, N overflowed`, with N = 0 for every scenario of BLiNX 2 and Burnout 3 at the new cap

### Requirement: A backend draws any batch the executor accepts
A GPU backend's index ring SHALL hold the expanded list of a batch of `NV_MAX_INDICES` indices (three list indices per input index, 32-bit each), and its per-index scratch SHALL grow with the batch rather than be sized statically to the cap. The CPU program path's transformed-vertex scratch SHALL do the same. A batch the executor collects whole is then never dropped for its size downstream.

#### Scenario: Scratch costs what the run uses
- **WHEN** BLiNX 2 runs its stage 1 golden
- **THEN** the per-index scratch on each backend is sized to the run's largest batch (4592 indices), not to the cap

### Requirement: The NV2A register trace runs only when asked
The per-kick `[NV2A] <ms> DMA_PUT/DMA_GET/fence` line, the `PCRTC_START` change line, the once-a-second display framebuffer checksum and the periodic `[GPU]`/`[PB]` report SHALL be gated on `RECOMP_TRACE=nv2a`, with `RECOMP_TRACE=pb_scan` also arming the periodic report and `RECOMP_DEBUG=fb_dump` alone keeping the report's periodic picture without its text. `RECOMP_PB_EXEC` SHALL NOT arm any of them, and the executor, the segment scan, the fence mirrors, the flip hold and the `[GPU] flip` line SHALL NOT depend on the trace flag. The per-kick line SHALL be written by one call.

#### Scenario: Default run
- **WHEN** the game runs with no trace key set
- **THEN** the log has no `[NV2A] ... DMA_PUT` line, no `PCRTC_START` line and no periodic `[GPU]` report, and the goldens pass unchanged on Metal and on D3D11 under Proton

#### Scenario: Stall timeline on request
- **WHEN** the game runs with `RECOMP_TRACE=nv2a`
- **THEN** every pushbuffer kick prints one `[NV2A] <ms> DMA_PUT = ... DMA_GET = ... fence ...` line, stamped on the same clock as `[GPU] flip`, so a gap between lines reads as the GPU side standing still

#### Scenario: Picture without the text
- **WHEN** the game runs with `RECOMP_DEBUG=fb_dump=<prefix>` and no trace key
- **THEN** a numbered `<prefix>NNN.bmp` is written every `pb_report_ms` and no `[GPU]` report text is printed

### Requirement: A GET_REPORT handed to a backend is written before the title can read it
The executor's `on_report` hook contract SHALL be: a backend that returns 1 writes the 16-byte report (`{timestamp, count, status 0}`) now or later, and no later than the next `on_poll` returns. Until then the status keeps the 0xFFFFFFFF that D3D wrote (TESTINCOMPLETE).

The executor SHALL call the backend's `on_poll` at two points after such a report:
- before the next `BACK_END_WRITE_SEMAPHORE_RELEASE` writes its semaphore;
- at the end of the walk, before GET is stored or a stop's salvage releases a semaphore.

The ack thread SHALL still call `on_poll` once per pass.

The walker's own paths SHALL be unchanged: the CPU rasteriser writes its fragment count at `GET_REPORT`, and `zpass_fixed` or a backend without the hooks writes the fixed value there.

#### Scenario: Deferred report complete when the walk hands back
- **WHEN** a GPU backend takes a `GET_REPORT` and the walk then releases a semaphore or ends
- **THEN** before the semaphore word or GET changes, the report's status is 0 and its count is one of: the query's result, the address's last completed count, or the visible fallback

#### Scenario: CPU path unchanged
- **WHEN** the CPU rasteriser (or `RECOMP_DEBUG=zpass_fixed=n`) handles a `GET_REPORT`
- **THEN** the report is written at the method, as before, and no `on_poll` is owed

### Requirement: The present size scan covers every buffer the title scans out
The executor SHALL keep a scanout set: the offsets of the surfaces the last `present_stale` flips presented (compared as physical addresses, as the display address is), cleared when the display-mode generation changes. When a display mode is set, the size scan of the present pick SHALL take the largest fresh surface at the display address or at any scanout offset, at the display pitch (or the field pitch when that rule is in force); with none fresh, the largest stale one there still sets the size and leaves no candidate, as before. Of that size, the newest draw since the last flip SHALL still win, else the newest clear, else the screen stays. When the surface table is full, eviction SHALL take the least recently used entry that is not at a scanout offset or the display address at that pitch, and only when every entry is such an entry the least recently used of all. The table SHALL hold at least 32 entries. Without a display mode, the pick SHALL be as before (the largest fresh surface anywhere). A pick's size SHALL therefore not change between two flips of a double-buffered title whose frames draw the same clip extents into each buffer, however many offscreen surfaces a frame touches.

#### Scenario: Double-buffered title with three clip extents a frame
- **WHEN** the display is at A and each frame draws into A or B in turn at clip extents 640x480, 640x464 and 640x463, and also into 19 offscreen surfaces, then flips (`nv2a_backend_smoke`, CPU path)
- **THEN** from the third flip, eight consecutive flips present the buffer drawn that frame at 640x480; on the executor before this change the size alternates 640x480 and 640x464

#### Scenario: Single-buffered title with many offscreen surfaces
- **WHEN** the display is at A and each frame draws into A at 640x480, into 19 offscreen surfaces, then into A at 640x464, and flips
- **THEN** eight consecutive flips present A at 640x480, because A's entries are spared eviction

#### Scenario: Display-mode change clears the set
- **WHEN** after presenting from A and B the title sets a display mode at C, a frame draws into A at 1280x720 and into C at 640x480, and flips
- **THEN** the pick is C at 640x480: A's larger entry no longer sets the size

#### Scenario: A table of protected entries still evicts
- **WHEN** the display is at A and a frame draws into A at 40 distinct clip extents, then at 640x480, and flips
- **THEN** the pick is A at 640x480 and the executor neither stalls nor asserts; plain LRU applied once every entry was protected

#### Scenario: Burnout 3 race-start card
- **WHEN** a Burnout 3 race starts on Metal (Mac) or D3D11 under Proton with a scaling present (`present.fullscreen`, `present.surface = internal`, a filter or `render.scale > 1`)
- **THEN** every flip across the race-start card presents 640x480 and the picture does not move on screen; after the race loads the flip log shows no change of present size to the end of the drive

#### Scenario: BLiNX 2 unchanged
- **WHEN** attract, stage1 and story run with `RECOMP_FLIP_LOG=1` and `RECOMP_PRESENT_TRACE=1` on main and on the change
- **THEN** the per-flip `(offset, w, h)` sequences are identical, the protected-eviction count is 0, and the goldens pass with the same verdicts on Metal and D3D11 without a re-record

### Requirement: A flip waits for the guest vblank its presentation interval asks for
The pushbuffer executor SHALL NOT let the title see a flip complete sooner than the swap's presentation interval allows, counted on the guest's 60 Hz vblank clock (`xbox_VblankCount`).

The interval is decoded from D3D's swap software method (`NO_OPERATION` with `(param & 0x1F) == 1`: `interval = (param >> 5) & 7`, IMMEDIATE = `(param >> 5) & 8`). A FLIP_STALL with no swap NOP since the previous one SHALL count as interval 1, and interval 0 with IMMEDIATE SHALL never hold. After a FLIP_STALL whose target vblank (`last_flip_vblank + interval`) hasn't arrived, the walker SHALL:
- finish its current segment;
- leave `DMA_GET` equal to the `PUT` it walked to;
- not walk the next segment;
- not acknowledge the KickOff flush, on either kick path,

until the vblank count reaches the target. The frame SHALL still be presented at the FLIP_STALL, on every backend (CPU, D3D11, Metal). `last_flip_vblank` SHALL be `max(target, count at FLIP_STALL)`, the count sampled when the walk that reaches the FLIP_STALL began (the title's kick of its Swap segment), not after the segment's draws; the hold's 100 ms clock starts at the FLIP_STALL, before the backend's present.

The hold SHALL run on the walker's own thread (`nv2a-ack`) and SHALL hold no lock while it waits: not the guest CPU, not the DISPATCH gate, not the DPC lock, not a backend lock. Its release SHALL depend only on `xbox_VblankCount()` and host time, never on a guest thread. The ack loop SHALL call `xbox_SpinWake()` whenever it clears the kick bit.

The hold SHALL NOT apply:
- while the vblank clock is off, or hasn't advanced for 100 ms;
- inside a pushbuffer CALL;
- for longer than 100 ms of host time.

`RECOMP_DEBUG=flip_pacing=0` SHALL restore the immediate FLIP_STALL. `RECOMP_DEBUG=flip_pacing=edge` SHALL select D3D's rule, `target = max(last_flip_vblank + interval, count at FLIP_STALL + 1)`, interval 0 with IMMEDIATE still never holding and a late ONE_OR_IMMEDIATE flipping at once; it is an A/B switch and the goldens pin the default.

#### Scenario: Burnout 3 front end on Metal
- **WHEN** Burnout 3 boots on the Mac with the Metal backend and sits in the attract loop and menus
- **THEN** flips.py shows about 60 flips/s per 10 s bucket after the boot clears (not about 350), the vblank stays at 60 Hz, and the intro movies take their real length

#### Scenario: Burnout 3 race on Metal
- **WHEN** the scripted race runs on Metal
- **THEN** the race buckets show at most about 60 flips/s (not 70-90), and the HUD race clock advances at wall-clock rate between two dumped frames

#### Scenario: Host display faster than 60 Hz
- **WHEN** Burnout 3 runs on D3D11 under Proton on the Steam Deck's 90 Hz screen
- **THEN** the menus run at 60 fps, not 90, and the audio stays in phase with the picture

#### Scenario: A title that paces itself is held only at interval changes
- **WHEN** BLiNX 2 runs its story, stage 1 and attract goldens
- **THEN** the goldens pass unchanged, on Metal and on D3D11 under Proton; the pacing trace reports holds only rarely (under 1% of flips, each about one vblank, where the title's swap interval changes), `hold_timeouts` 0 and no stand-down log line; flips/s and raster ms stay within the bench thresholds on the CPU backend too

#### Scenario: Slow backend is not quantised
- **WHEN** a frame reaches FLIP_STALL `interval` or more vblanks after the previous flip
- **THEN** the walker doesn't hold, and the CPU backend's flips/s is unchanged within the bench thresholds

#### Scenario: Standalone rule
- **WHEN** `tests/flip_hold` drives the rule with these cases: interval 1 frames at 5 ms, interval 2, IMMEDIATE, no swap NOP, a 20 ms frame, a stopped vblank clock, a 100 ms timeout and `last_flip` after it, two stalls in one walk, a count wrap, and the 20 ms frame and a late ONE_OR_IMMEDIATE under `edge`
- **THEN** the hold arms and releases at exactly the vblank the rule gives, never holds in the slow, immediate and stopped-clock cases, holds the slow frame to the next edge only under `edge` (a late ONE_OR_IMMEDIATE still flips at once), adds no held time for a stall nothing waited on, and counts the timeout

### Requirement: A held title's KickOff spin yields
The KickOff spin on PFB 0x100410 bit 16 SHALL be a listed spin-wait site (`config/spin_waits.json`) in every title the hold ships for (BLiNX 2 at 0x002E7F20, Burnout 3 at 0x00351BF0 in `sub_00351BD0`), so that a title held in KickOff yields the guest CPU under the guest-CPU lock and sleeps under `present.pacing=sleep`. A site the matcher rejects SHALL be fixed in the matcher, with a test, not dropped from the list.

#### Scenario: Burnout 3 on the Mac with the guest-CPU lock
- **WHEN** Burnout 3 runs on Metal with the guest-CPU lock on and the hold active
- **THEN** the spin-site trace shows the KickOff site yielding, and the APU reports no more underruns than a run with `flip_pacing=0`

### Requirement: A frame counter the title moves itself is left to the title
A counter registered with `xbox_Nv2aFrameCounter` SHALL be advanced by the toolkit (per flip, and by the 60 Hz fallback) only until the toolkit sees it advanced by something else since its own last write. The first bump SHALL always happen and seed the last-written value; the comparison starts with the second. From then on the toolkit SHALL NOT write it, and SHALL say so once in the log. A counter that went backwards SHALL stay the toolkit's. `RECOMP_DEBUG=flip_pacing=0` SHALL restore the unconditional bump.

#### Scenario: A counter that starts non-zero
- **WHEN** a registered counter already holds a non-zero value at the toolkit's first bump and nothing else moves it afterwards
- **THEN** the toolkit bumps it and keeps bumping it; it is not stood down

#### Scenario: Burnout 3's vblank count
- **WHEN** Burnout 3's vblank DPC starts incrementing device + 0x1DE8 (the miniport's vblank count) after D3D initialises
- **THEN** the toolkit stops bumping it, the log says so once, and the count advances at 60 per second

#### Scenario: A counter only the toolkit moves
- **WHEN** a title's registered counter is never written by the title
- **THEN** the toolkit keeps advancing it per flip and by the 60 Hz fallback, as before

### Requirement: PGRAPH 0x400B10 follows the executor when no fence mirror is registered
When no fence mirror is registered (`g_fence_mirror_count == 0`) and the executor has run at least one `BACK_END_WRITE_SEMAPHORE_RELEASE`, the ack loop SHALL set PGRAPH `0x400B10` bits 2..6 from the executor's last released value, exactly as it sets them from a mirror's completed word, and SHALL log once that the register follows the executor's releases. It SHALL NOT do so while any mirror is registered, whether or not that mirror's device is readable yet, and it SHALL NOT write the register before the first release. The tick that writes the register SHALL be callable outside the ack loop (`xbox_Nv2aPgraphFenceTick`) so a ctest can drive it. `RECOMP_VBLANK` SHALL be read as a switch (`recomp_env_on`): `=0` turns vblanks off.

#### Scenario: A title with no mirror passes D3D's wait-for-idle
- **WHEN** a scaffolded title registers no fence mirror, the executor is on, and D3D's wait-for-idle polls `0x400B10` against its fence word
- **THEN** after the executor's first release the register's bits 2..6 equal the released value's low five bits shifted by 2, the wait ends, and the log holds one `NV2A PGRAPH fence: no fence mirror registered` line

#### Scenario: A registered mirror is never overridden
- **WHEN** a mirror is registered whose device pointer is still 0 and the executor releases value 9
- **THEN** the register keeps its previous bits; once the device exists and its completed word reads 3, the register shows 3

#### Scenario: Before the first release
- **WHEN** no mirror is registered and the executor has released nothing
- **THEN** a tick leaves the register unchanged, bits outside 2..6 included

#### Scenario: The gate titles are unaffected
- **WHEN** BLiNX 2 or Burnout 3 runs with its mirror registered
- **THEN** no `PGRAPH fence` line appears, the mirror lines read as before, and the goldens and flips/s match main

#### Scenario: Vblanks switched off
- **WHEN** `RECOMP_VBLANK=0` is in the environment
- **THEN** the kernel timer raises no vblank and `xbox_VblankCount()` stays 0

### Requirement: A stride-0 vertex array is an array
A vertex attribute whose SET_VERTEX_DATA_ARRAY_FORMAT size is non-zero SHALL be read from memory on every backend (CPU, Metal, D3D11), whatever its stride. At stride 0 every vertex of the draw SHALL read the one element at the attribute's offset. Only an attribute with size 0 SHALL read its SET_VERTEX_DATA (inline) value.

#### Scenario: Per-batch constant in an array
- **WHEN** attribute 4 is float, size 3, stride 0, at an offset holding (0, 1, 0), the inline v4 is (1, 0, 0, 1), and a program writes v4 to oD0
- **THEN** every vertex reads (0, 1, 0, 1) and the quad draws opaque green

#### Scenario: Disabled attribute
- **WHEN** the same attribute has size 0
- **THEN** every vertex reads the inline value (1, 0, 0, 1)

### Requirement: The ack loop's poll interval is honoured on every host
While the title is kicking, the walker's ack loop polls the KickOff flush bit and `DMA_PUT` at about 50 us (`RECOMP_FAST_KICK`, default on). The nap between polls SHALL be about 50 us on native Windows as well as under Wine and on POSIX while the loop is within 2 ms of its last activity (a kick acknowledged, a new `PUT`, a flip hold): native Windows SHALL spin on the clock with a pause instruction for those naps and SHALL wait on a high-resolution waitable timer beyond the 2 ms budget, since every timed wait there expires on the system clock interrupt (0.5 ms at best); Wine SHALL keep `NtDelayExecution`; POSIX SHALL keep `nanosleep`. The 200 ms idle `Sleep(1)` SHALL be unchanged. The observer thread that times kicks for `[PB-PERF]` SHALL nap through the same helper on the cold primitive (the timer on Windows). The nap mode SHALL be set before the ack thread is created. The startup line SHALL name the nap mode in effect, the budget, and the measured p50 of a 50 us nap on each primitive the mode uses. `RECOMP_DEBUG=kick_nap=hybrid|timer|delay|spin` SHALL select the mode for comparison; unset SHALL be the rule above. Beside `timeBeginPeriod(1)` the process SHALL opt out of Windows 11's occluded-window timer-resolution policy (`PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION` turned off), so the millisecond paths stay at 1 ms when the window loses focus.

#### Scenario: Native Windows
- **WHEN** the game runs on Windows 10 1803 or later, outside Wine, with no `kick_nap` key
- **THEN** the startup line reads `nap hybrid (spin within 2 ms of activity, then timer): spin p50 N us, timer p50 N us` with the spin p50 under 100 us, and on the mission 1-2 city view the `[PACING]` window p50 returns to the 33.3 ms lock with p95 within 1-1's band, where the 1 ms-rounded nap gave p50 38-42 ms; `cpu process` rises by the walker's former sleeping share and no more

#### Scenario: The walker sleeps when the title is not kicking
- **WHEN** the title has not kicked, written `PUT` or held a flip for more than 2 ms (a menu, a light scene, a backgrounded window)
- **THEN** the ack loop's naps are timer waits, not spins, and after 200 ms idle the loop is a plain `Sleep(1)` as before this change

#### Scenario: Wine and POSIX unchanged
- **WHEN** the game runs under Proton or on macOS with no `kick_nap` key
- **THEN** the nap is the same `NtDelayExecution` or `nanosleep` call as before (the startup line reads `nap delay (wine)` or `nap nanosleep`), and the D3D11 and Metal goldens pass unchanged

#### Scenario: No high-resolution timer
- **WHEN** the host cannot create a high-resolution waitable timer
- **THEN** the hybrid's cold naps fall back to `NtDelayExecution`, its hot naps still spin, the startup line says so, and the game runs correctly

#### Scenario: The A/B values
- **WHEN** `RECOMP_DEBUG=kick_nap=timer` or `=delay` is set on native Windows
- **THEN** every nap is the high-resolution timer or `NtDelayExecution` respectively, and the startup line records its p50 (about 0.5 ms and 1 ms on the 2026-10-14 hardware) beside the mode name, for the recorded comparison

#### Scenario: The helper is bounded standalone
- **WHEN** `tests/host_nap` runs under the POSIX ctest script, under the Proton runner, or by hand on native Windows
- **THEN** 200 naps of 50 us have a p50 under 100 us in the spin mode on every host, a p50 under 400 us in the delay mode on Wine and POSIX, the timer and the Windows delay figures are printed for the record without a bound, `AUTO` resolves to `hybrid` on native Windows and `delay` elsewhere, and a zero-length nap has a p50 under 50 us

### Requirement: Bump-environment state is decoded from the stream
The executor SHALL keep `SET_SHADER_OTHER_STAGE_INPUT` (0x1E78) in the transform-unit state it hands the backends, and `nv2a_stage_decode` SHALL carry each stage's `SET_TEXTURE_SET_BUMP_ENV_MAT` (four registers, in stream order), `BUMP_ENV_SCALE` and `BUMP_ENV_OFFSET`. With `RECOMP_TRACE=bump` (trace tier; printing only) the executor SHALL log, once per distinct combination of stage, input stage, matrix, scale, offset and texture format and size, one line naming the flip it first appeared in, so the scenes a title bump-maps and the matrices it writes can be found from a run.

#### Scenario: BLiNX 2 and Burnout 3 scenes found
- **WHEN** attract, stage 1 and a Burnout 3 race run with `RECOMP_TRACE=bump`
- **THEN** the log names each mode-6 stage, its input stage and matrix with the first flip, matching the end-of-run `[VSH]` mode counts (mode 6 on stages 1 and 2 for BLiNX 2, stage 1 for Burnout 3), and no line appears for a title that uses no bump stage

#### Scenario: No behaviour change
- **WHEN** the trace key is unset
- **THEN** no bump line is printed and the frames are those of a run without the key

### Requirement: The present extent is the display mode's size
The kernel SHALL resolve the mode word AvSetDisplayMode receives to the frame size of its timing (640x480, 720x480, 1280x720, 1920x1080, 640x576 or 720x576, by the word's timing byte) and record it beside the framebuffer address, pitch and format before the display-mode generation is bumped; a word with an unknown timing byte SHALL record no size and log once, and a pitch that is neither the size's width nor half of it (a field title) in the format's pixels SHALL log once and record no size. The executor's present pick SHALL choose the surface as before and then publish, as the extent a flip shows: the display's width and height when the surface is at the display pitch; the display's width and half its height when the surface is at twice the display pitch (field rendering, one field); and the surface's clip extent when there is no display mode, no recorded size, another pitch, or a surface chosen without one at the display address or in the scanout set. Phase 1's scanout set SHALL accordingly take only picks sized from the display address or the set; a pick made with neither (the largest fresh surface anywhere) SHALL not join it. The extent SHALL therefore not change between a title's screens drawn at different clip heights into buffers of one display mode, and SHALL never exceed the frame the mode defines.

#### Scenario: Menus and races at one size
- **WHEN** a title in a 640x480 mode draws twenty frames at clip 640x464, then twenty at clips 640x480, 640x464 and 640x463 a frame (`nv2a_backend_smoke`, CPU path), flipping between two buffers
- **THEN** every flip presents 640x480, with zero size changes across the transition; on the executor before this change the first twenty present 640x464

#### Scenario: Field buffers keep their height
- **WHEN** a 640x480 mode is set at pitch 2560 and every frame draws a 640x240 surface at pitch 5120 and flips
- **THEN** the pick's extent is 640x240 at pitch 5120 and the field warning prints once; after a surface at pitch 2560 is drawn and flipped the extent is 640x480

#### Scenario: Mode change and an HD mode
- **WHEN** the title sets mode 0x880B0A02 at pitch 5120 at a new address, draws 1280x720 and flips, then sets 0x0801010D at pitch 2560 again
- **THEN** the extents are 1280x720 and then 640x480, and no buffer of the previous mode is picked in between

#### Scenario: Unknown word falls back
- **WHEN** a mode word with a timing byte the table does not know is set
- **THEN** one `[AV]` line says so, no size is recorded, and the pick's extent is the surface's clip extent, as under present-scanout

#### Scenario: Burnout 3 from title to drive
- **WHEN** Burnout 3 runs on D3D11 under Proton with `present.fullscreen` and `RECOMP_FLIP_LOG=1`, from the title screen through the menus and a race
- **THEN** the flip log shows no change of present size from the `[AV] SetDisplayMode` line to the end of the drive, and the picture does not move at the menu-to-race transition on Metal or D3D11

#### Scenario: BLiNX 2 unchanged
- **WHEN** attract, stage1 and story run with `RECOMP_FLIP_LOG=1` on main and on the change
- **THEN** the per-flip `(offset, w, h)` sequences are identical (640x480 throughout, the mode's size), and the goldens pass with the same verdicts on Metal and D3D11 without a re-record

### Requirement: vsh_dump writes vertex programs on every backend
With `RECOMP_DEBUG=vsh_dump=<prefix>`, the executor SHALL write each new `(hash, start)` vertex program to `<prefix>NN_HASH.bin` on the CPU, Metal and D3D11 backends alike. Without `vsh_dump` or the `vsh` trace, a GPU backend SHALL NOT hash the program per draw.

#### Scenario: Metal
- **WHEN** SSX 3 runs on Metal with `vsh_dump` set
- **THEN** one `.bin` per program is written, and the end-of-run `[VSH]   program` lines list them

### Requirement: Frames around a program's first draw
With `fb_dump` and `fb_dump_prog=HASH[,HASH]`, the first draw of any listed program at flip count k SHALL dump flips k+1 to k+`fb_dump_prog_after`. On the CPU and write-back backends, it SHALL also dump the `fb_dump_prog_before` flips up to k from a memory ring. All of these SHALL be named `flip_NNNNN.bmp`. The trigger SHALL fire once and log the program, flip, draw and range. Unset, it SHALL cost nothing.

#### Scenario: Onset not known in advance
- **WHEN** a run sets `fb_dump_prog=8F706D7F` and the program first draws at flip 5327
- **THEN** flips 5298–5327 (from the ring) and 5328–5387 are written, and the log names flip 5327

### Requirement: fb_dump_at reports its limit
`fb_dump_at` SHALL accept 256 ranges and SHALL print how many past that were ignored.

#### Scenario: Ranges past the limit
- **WHEN** `fb_dump_at` lists 300 ranges
- **THEN** the first 256 are dumped and one line reports that 44 were ignored
