# Shared shaders: present shaders in every game, and a check for gaps

## Why

The toolkit's present chain and the menu's Shaders page are game-agnostic, yet
four of the eight games never showed them: the page hides itself unless the
presets and librashader sit beside the executable, and staging them took a
`xboxrecomp_present_shaders(<exe>)` line each game had to remember. JSRF, SSX 3,
Burnout 3 and Quantum Redshift do not have it. Nothing told anyone. Any new
shared feature can drift the same way.

## What changes

- **Toolkit:** every executable linking `xbox_enhance` stages the presets and
  librashader by itself. The per-game call keeps working and is idempotent.
- **Games:** the four games get the explicit call now (see the sequencing in
  the design), plus the config rows and the README rows.
- **CLI:** `<game> features` lists the shared features a game should have and
  fails on a gap; `doctor` shows the gaps, and `public audit` and `public
  export` refuse them, through the layout report.
- **Templates and docs:** the README template's Profile row is the default, not
  a conditional one.

## What does not change

- `present.shader = "none"` stays the default, so stock behaviour and the
  goldens do not change.
- No pin moves here: the tracker item moves JSRF, SSX 3 and Quantum Redshift.
- Spartan stays parked: no edits, its build-all check is report-only for this.
