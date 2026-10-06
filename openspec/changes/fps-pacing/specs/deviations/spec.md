## ADDED Requirements

### Requirement: Spin waits may sleep
With `present.pacing = "sleep"`, the guest busy-wait loops lowered at generation time (`config/spin_waits.json`; v1: `0x00060475` only) SHALL block in the host instead of spinning, waking on kernel signals or after at most 1 ms (`frame-pacing`). On hardware the CPU spins.
- Reason: the spin holds one host core at about 97% while it waits for the vblank count, which costs heat and battery and takes a core from the raster threads (`analysis/research/hot-threads-macos.md` §1a).
- Risk: a lowered loop whose condition is changed by something the kernel does not signal advances up to 1 ms late on each pass, so a wait in a tight hand-off could slow the title. On the console's one CPU, a spinning thread also delays other guest threads; on the host it does not, and that difference shrinks when the loop sleeps.
- Detect: in the `pacing` trace, more than 5% of a site's loop exits are on the timeout, or a pacing A/B flags flips/s or raster ms.
- Exit: none planned while sleeping saves a core. The deviation is retired for a site that is removed from the list, and for all sites if `present.pacing` returns to `spin` everywhere. While the default is `spin` the deviation is in effect only for a player who selects `sleep`; the change that flips the default updates this entry.

#### Scenario: Site leaves on timeouts
- **WHEN** the `pacing` trace shows a lowered site with more than 5% of its loop exits on the timeout
- **THEN** the site is either excluded from `config/spin_waits.json` or given a wake at its writer, and this entry records which
