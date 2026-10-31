## Why

The user decided on 2026-10-30 that the MCPX APU DSP, meaning the GP
and EP on the dsp56300 JIT, is compiled in and runs by default in every game,
including every game made from now on. This answers task 7.1 of
`apu-dsp-emulation`, which left the per-game choice to the user.

The decision is an exception to the workspace rule that opt-in features
default OFF and never change stock behaviour (CLAUDE.md, "Opt-in features").
The JIT becomes the stock audio path. The menu-on-by-default decision
(2026-10-27) is the precedent for this kind of exception. Enhancements stay
default OFF.

The situation today:

- The toolkit option `XBOXRECOMP_APU_DSP` defaults OFF.
- The run-time key `RECOMP_APU_DSP` defaults to the stub.
- BLiNX 2 and JSRF compile the JIT in through `game.toml` `stock_cmake`, but
  they still run the stub unless `RECOMP_APU_DSP=1`.
- KUF gets a game-level `D(APU_DSP, "1")` from the tracker item.
- Every other game has no JIT at all.

With the JIT, players hear the title's GP program (reverb, effects sends, the
mix it was written for). The stub only passes the mixbins through. The tracker item
measured the cost on KUF:

- GP+EP stays well under 1 ms per 5.33 ms APU frame on the Mac, the PC and the
  Deck.
- No frames were capped.
- No dropouts were added.

## What changes

- **Toolkit build default ON** on every target that has a dsp56300 archive.
  On a target without one (MSVC, iPadOS, universal macOS) the default stays
  OFF, without a warning; an explicit ON there still warns.
- **Cached OFF trees.** A build tree configured before the change holds the
  old cached OFF, and its next configure turns it ON once. This migration is
  in the toolkit, so it covers every game; BLiNX 2 hands its own
  `CAT_APU_DSP_MIGRATED` over to it. `-DXBOXRECOMP_APU_DSP=OFF` still builds a
  stub-only binary.
- **`stock_cmake` keeps the flag, and every game gets it.**
  `-DXBOXRECOMP_APU_DSP=ON` goes in every game's `game.toml` `stock_cmake`,
  and in the CLI's default and its new-game template. `xbr package` passes
  `stock_cmake` on every packaging configure and refuses a cache that
  differs from it, so the flag keeps package trees explicit. Plain
  `<game> build`, bench and build-host builds never see `stock_cmake`; for
  them the toolkit default and the cache migration turn the DSP on.
- **Run-time default on.** When `RECOMP_APU_DSP` is unset, a build with the
  DSP and its device runs the JIT. The stub can still be selected:
  - `RECOMP_APU_DSP=0` (or empty) selects it in the same exe;
  - a game can default to it with `D(APU_DSP, "0")`;
  - every game's `launch.env.default` names the opt-out in a comment.
- **No config.toml key or menu item** in this change (design D3). A
  follow-up item covers one, in case players need it.
- **Downloads.** The CLI's packaging and bench builds share a per-user
  dsp56300 download cache. The archive is 10–12 MB per target and checked
  against its sha256. A failed download stays a configure error, and the
  error names the offline copy and the opt-out.
- **Universal macOS** stays stub-only. No shipping path builds a universal
  game binary: `xbr package` and the wizard build the game on the player's
  Mac for its own architecture (design D4).
- **Per game**, in this order: BLiNX 2, BLiNX 1, JSRF, SSX 3, Burnout 3,
  KUF. Each game gets:
  - the dsp56300 section in its NOTICE;
  - its env doc and player docs;
  - a CHANGELOG entry;
  - a pin move to the public toolkit tag that carries this change.

  Spartan is parked: it only has to keep building in `build-all`.
- **Failure policy.** A game that breaks with the JIT:
  - gets a game-level `D(APU_DSP, "0")`;
  - gets a follow-up item;
  - is reported to the user.

## Out of scope

- Surround output from the GP. The output stays stereo, from mixbuf bins 0
  and 1.
- A volume adjustment for the JIT path. KUF plays about 8 dB quieter with
  it, and the user chose no boost.
- A universal (lipo) dsp56300 library for macOS.
- Goldens, for the DSP change and for every game's pin move (the user,
  2026-10-30). The user listens to each game by hand (design D6).
