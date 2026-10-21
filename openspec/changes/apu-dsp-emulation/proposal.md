## Why

The toolkit stubs the MCPX APU's two DSP56300 cores. Titles load their
own programs into them: the GP (global processor: mixing, reverb, I3DL2,
the output stage) and the EP (encode processor: AC-3 for S/PDIF). The
stub has no DSP. It does three things instead:

- it acks the GP doorbell from the host (`apu_dsp.c:210`
  `mcpx_apu_dsp_ack_poll`, called at `apu_core.c:1262`);
- it folds the 32 VP mixbins to stereo with fixed rules
  (`apu_dsp.c:324` `mcpx_apu_dsp_frame`, modes at `apu_dsp.c:113`);
- it keeps a GPRST shadow (`apu_dsp.c:173`).

So every title loses whatever its DSP program does:

- no reverb or I3DL2 effects;
- surround is folded to stereo;
- titles that ship a custom GP image are missing parts of their mix.
  Burnout 3's front-end music is silent (`B3XboxFx.bin`).

Performance is the main reason for this spike. The question
is whether a real DSP can run inside the APU frame budget on the
D3D11 and Metal targets without costing flips/s.

The spike measured one candidate on the Mac and the Deck and assessed
the others. **Licence decision:** the toolkit and the game repos are
MIT, with the LGPL-2.1+ xemu APU files listed in `NOTICE` as the one
precedent. Code under any GPL would change the licence of the shipped
binaries, so this change allows MIT (and other permissive licences,
such as Apache-2.0 and Zlib) plus LGPL-2.1+ only. A GPL option needs a
new decision from the user. Within those licences the choice is made on
accuracy, speed and effort.

## What Changes

This change is a plan. Nothing here alters stock audio.

- **Recommendation:** the MIT `mborgerson/dsp56300` JIT (option e),
  linked from its pinned prebuilt release. It is driven by a device model
  ported from xemu's LGPL-2.1+ `gp_ep.c` and `dsp_dma.c`. A build option
  and a `recomp_env` config key gate it, and both default OFF. The stub
  stays the default until goldens and the Deck and Windows numbers say
  otherwise.
- **No licensed fallback.** gearmulator's DSP core (option f, GPL-3)
  and xemu's DSP cores (options a and a′, GPL-2+) are excluded under
  the licence decision. If (e) fails on accuracy or on a target, the
  work stops and the user is asked, either to decide on a GPL option or
  to pick another path (for example keeping the stub on that host).
- **Device model licence:** the port of xemu's `gp_ep.c` and
  `dsp_dma.c` is LGPL-2.1+, the same terms as the xemu APU files already
  in the toolkit and listed in `NOTICE`, so it follows that precedent.
- **Evidence:** a probe on the toolkit branch `spike/apu-dsp`
  (`7fc03472`, plus `573f82db` for its Windows build; **probe only**,
  never merged), JSRF runs on the Mac and on the Deck under Proton, and
  SSX 3 WAV captures on both.
- **Renderer-agnostic:** the change touches the APU and the audio
  output only, not D3D11 or Metal, so the rule that the two GPU
  backends agree does not apply.
- **Slices:** see `tasks.md`, each with an estimate in agent-days.

## Capabilities

### New Capabilities

- `apu-dsp`: the opt-in DSP56300 emulation of the GP and EP. Its spec,
  `specs/apu-dsp/spec.md`, is written in the first slice (task 1.5).

### Modified Capabilities

None.

## Impact

- **Toolkit (`src/apu/`):**
  - a new `apu_dsp_emu.c` (the device model, LGPL-2.1+ like its xemu
    sources);
  - a hook in `mcpx_apu_dsp_frame` and `mcpx_apu_dsp_ack_poll`;
  - the GPRST path;
  - CMake fetch-and-pin of the dsp56300 release per target.
- **Licences:** the toolkit `NOTICE` and `LICENSES/` gain the dsp56300
  MIT text and the licences of the Rust std and crates that the
  prebuilt archive bundles: Apache-2.0 (some WITH LLVM-exception), MIT,
  Unicode-3.0 and Zlib, with no GPL (task 1.4). The game repos' `NOTICE`
  names them the way it names the xemu APU code.
- **Wizard builds:** one more pinned download per target, a static
  library of about 10–12 MB. The release has archives for
  `aarch64-apple-darwin`, `x86_64-apple-darwin`,
  `x86_64-pc-windows-gnu`, `aarch64-pc-windows-gnullvm`,
  `x86_64-unknown-linux-gnu` and `aarch64-unknown-linux-gnu`. A target
  without an archive, such as iPadOS, builds with the option OFF. The
  `windows-gnu` archive links with llvm-mingw 20260922 (checked in the
  spike). The wizard builder image still needs the same check (task 1.3).
- **Hosts:** the Deck cost at an idle GP is measured. A real GP load on
  the Deck and native Windows still need runs (task 6). The orchestrator
  schedules them.
