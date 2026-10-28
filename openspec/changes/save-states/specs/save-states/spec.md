## ADDED Requirements

### Requirement: States hold guest-level state only
A save state SHALL describe guest threads as guest call chains (function VA, return VA, `ebp` per frame), their thread-local register files and a park record, and SHALL NOT contain host stack contents or host pointers. Host caches (textures, render targets, shaders, pipelines, DSP translations, resamplers) SHALL be rebuilt on load, not stored; surfaces whose contents exist only on the host (D3D11 colour targets, depth and stencil) SHALL be stored by guest offset and format.

#### Scenario: A state loads after an unrelated toolkit rebuild
- **WHEN** a state saved by one build loads into a later build of the same XBE whose chunk versions are unchanged and whose resume sites cover every saved frame
- **THEN** the load succeeds and the game continues

#### Scenario: A frame without a resume entry
- **WHEN** a save finds a thread parked at a call site missing from `config/resume_sites.json`
- **THEN** the save is refused with `[STATE] refused:` naming the function and site, the game continues unchanged, and the save is retried at the next flip

### Requirement: Saves happen at a flip safe point or not at all
The runtime SHALL take a save only with `RECOMP_GUEST_LOCK` on, and SHALL refuse every state key with the lock off, saying why. A save SHALL run on the guest thread that holds the guest CPU, at its first kernel call after a flip, in this order: freeze guest CPU hand-outs; drain the pushbuffer with the device threads live until the flip hold is released, GET equals PUT and no report is owed; stop the device threads at their tick edges; classify every other guest thread as pending, returned or preempted, each thread recording its own registers and chain; read the surfaces back; copy. When that is not reached within two frames, or a guest callback runs inside a host frame, or a thread is at raised IRQL, or a non-restartable call is in progress, the save SHALL be refused with a reason and retried for up to `RECOMP_STATE_RETRY` flips.

#### Scenario: Lock off
- **WHEN** `RECOMP_STATE_SAVE` is set in a build run with `RECOMP_GUEST_LOCK=0`
- **THEN** no save is attempted and `[STATE] disabled: needs RECOMP_GUEST_LOCK=1` is logged

#### Scenario: Save during file I/O
- **WHEN** a save is requested while a worker is inside `NtReadFile`
- **THEN** the save waits for the worker to return, and is refused only if two frames pass

### Requirement: The state file is versioned per chunk
A state file SHALL start with `XBRSTATE`, a format major and minor, the title ID, the XBE sha256, the generated-code key, the exe build ID and the toolkit and game shas, followed by tagged chunks each carrying its own version, size, compression and CRC, and an end sentinel. Every chunk SHALL be encoded field by field in fixed-width little-endian fields, never as a raw host struct. A reader SHALL refuse a different XBE, and SHALL refuse a chunk version it neither knows nor migrates, naming the chunk.

#### Scenario: Mismatched XBE
- **WHEN** a state from another region's XBE is loaded
- **THEN** the load is refused before any guest memory is written

#### Scenario: State made on another host and backend
- **WHEN** a fixture state made on the Mac with Metal is loaded on the Deck with D3D11 under Proton
- **THEN** it loads, every stored surface is uploaded to the D3D11 backend, and the fixture's golden frames pass

### Requirement: Waits are classified by their own threads, and ownership is restored
Every wait bridge SHALL also wait on a per-thread save handle. When the saver signals it, the thread SHALL record its wait as pending (with its guest-clock deadline) if the guest object was not satisfied, or finish every post-wait side effect and record it as returned if it was. On load, each thread SHALL write its own registers and re-acquire the mutants and critical sections it owned, to their recursion depth, before any guest thread resumes.

#### Scenario: Auto-reset event consumed at the save
- **WHEN** a worker's wait on a synchronization event is satisfied while the save is quiescing
- **THEN** the worker clears the event's `SignalState`, records a returned call, and after a load it continues without waiting again

#### Scenario: Lock held across a wait
- **WHEN** a guest thread owns a critical section while it waits on an event at the save
- **THEN** after a load the same guest thread owns the critical section at the same depth before any thread runs

### Requirement: Guest clocks continue from the save
Every guest-visible clock (performance counter, tick count, interrupt and system time, `rdtsc`, the vblank grid, timer due times) SHALL derive from one guest-clock base, and a load SHALL set it so the guest sees time continue from the moment of the save.

#### Scenario: Load a day later
- **WHEN** a state saved at guest tick T is loaded 24 hours later
- **THEN** the first tick count the title reads after the load is within one frame of T

### Requirement: Test fixtures are recipes with local cached states
A fixture SHALL be a committed recipe (a pad-script prefix and a `savestate` step or flip, plus its environment) and a cached state in a shared store outside every worktree, keyed by the XBE sha, the chunk versions and the resume-site coverage, not by the build ID or the toolkit sha. The title's saves SHALL travel in the state's `SAVE` chunk, as in a player slot, and a fixture run SHALL load them into a scratch save directory, never the user's. A stale cached state SHALL be regenerated from its recipe. States SHALL never be committed, published or attached to the tracker. From-state goldens SHALL be fast checks only; the full-prefix goldens SHALL stay the merge gate.

#### Scenario: Golden from a state
- **WHEN** `golden run --from-state stage1-walk` runs after the build changed
- **THEN** the state is made again from the recipe, the run starts from it, and the golden frames pass with the usual tolerance

### Requirement: A state carries the title's own saves
Every state, player slot and fixture SHALL include a `SAVE` chunk with the files under the title's `UDATA/<title_id>/` and `TDATA/<title_id>/`, taken at the save point. Loading SHALL restore the state and those files together, swapping the files in so a failed load leaves the old ones in place, and the undo state before an in-session load SHALL hold the files that were on disk. A `SAVE` chunk above `RECOMP_STATE_SAVE_MAX` (16 MB by default) SHALL be refused for a player slot.

#### Scenario: Load an older slot
- **WHEN** a player saves a slot, then saves progress in the game, then loads the slot
- **THEN** the game and its save files are both as they were at the slot, and the undo slot holds the newer save files

### Requirement: Player slots are single files in an N-slot store
A player slot SHALL be one self-contained file (`<slot id>.xbrslot`) under `<save root>/states/<title_id>/`, outside `UDATA`, with the slot order in `slots.json`. The store SHALL support N slots, rearranging without renaming slot files, deleting, and exporting or importing one slot as one file. An import SHALL refuse a slot from another XBE. The quick save SHALL be off by default and behind `XBOXRECOMP_ENHANCE`; its first release SHALL offer one slot with a save hotkey and a load hotkey. Slots and exported slots hold user save data and SHALL never be committed, published or uploaded by any tool.

#### Scenario: Quick save and load with one slot
- **WHEN** `XBOXRECOMP_ENHANCE` is built in, the quick save is enabled and the player presses the save hotkey, then the load hotkey
- **THEN** the store holds one slot, `quick`, and the game returns to it

#### Scenario: Export and import
- **WHEN** a slot is exported to a file and that file is imported on another machine with the same XBE
- **THEN** the imported slot gets a new id, is appended to the order, and loads with its saves

#### Scenario: Public audit
- **WHEN** a `*.xbrstate` or `*.xbrslot` file is in a public push delta
- **THEN** the audit refuses the push

### Requirement: Stock behaviour is unchanged
With no state key set, no save or load SHALL happen, and the stock goldens SHALL pass. `XBOXRECOMP_STATES` SHALL be part of the gen key, and the build SHALL work with it OFF. It SHALL default ON only while frame CPU time with it ON rises by 3 % or less (median and p99) against OFF on Metal and D3D11 at stock settings over the golden scenarios, and the goldens are frame-identical; otherwise it SHALL default OFF. The cost and the `.text` growth SHALL be published per backend.

#### Scenario: Golden with the feature built in
- **WHEN** the Metal and D3D11 goldens run on a build with `XBOXRECOMP_STATES=ON` and no state keys
- **THEN** they are frame-identical to the OFF build's

#### Scenario: Cost over the threshold
- **WHEN** the phase 1 measurement shows frame CPU time 5 % higher with the option ON on D3D11
- **THEN** the option ships default OFF and the numbers go to the user
