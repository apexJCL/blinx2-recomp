## Why

The user asked on 2026-10-15 (verbatim):

> include an "info" button on the app that renders a list of all the
> open-source projects involved. Start with our repos, then on the
> third-party tools we directly rely on. All of them need to include a
> link to their GitHub pages if available. The info button should be
> located on the UI in a place where it is not obstrusive, but always
> accessible. On the home page, we could show the exact same table (and
> hide the button) right below the welcome message, so everyone's
> credited right off the bat

and corrected the order (verbatim):

> Because the wizard is meant to be generic initially and part of
> `xboxrecomp-cli`, I think it should be listed first - except when
> someone picks the wizard for their repo (like blinx), then the repo
> itself is listed first, then the cli

Today the wizard names none of the projects it and the build stand on.
The licence texts of what the wizard's binaries contain ship in
`NOTICES.txt` (wizard-test-notes, review fix 1), but nothing in the
window points at the projects themselves.

Opus wrote and implements this change with no Fable revision: the user
said "for these changes, there's no need for fable, you can use opus".

## What changes

- **One credits list, owned by the CLI.** `credits.py` holds the
  toolkit's own entries (xboxrecomp-cli, the toolkit fork, its
  upstream) and the third-party projects the wizard and the build
  directly use. A game adds its own entries in game.toml with
  `[[wizard.credit]]` (its repo, and any project only that game uses).
  The CLI merges them in a fixed order: the game's entries, then the
  CLI, the toolkit, its upstream, then the third-party projects. A game
  that lists nothing gets the generic order, the CLI first.
- **In the wizard config.** The merged list is the config's `credits`
  key, so the binary embeds it at build time and `--game DIR` reads it
  from `wizard config --json --dev`. A config without the key (an older
  CLI) falls back to the wizard's own list: xboxrecomp-cli and the
  wizard's direct Go dependencies.
- **An info button.** A small (i) glyph button at the right end of the
  header, on every page but Welcome. It opens a dialog with the list,
  sized to the window by the stop dialog's rules and following a
  resize.
- **On Welcome.** The same list right below the welcome message, under
  "Made with these open-source projects": one line per entry in a box
  about eight rows tall that scrolls, so the folder pickers stay close.
- Each entry: its name as a link (with the external-link glyph) to its
  GitHub page, or its official site when it has none, then its role and
  its licence (SPDX). The dialog gives each entry two lines.

## Out of scope

- The game bundles' own notices (SDL, OpenSSL, libepoxy, the
  xemu-derived toolkit code): `package` ships the game's `LICENSE` and
  `NOTICE`. Whether those cover what each bundle links is a separate
  check (TASKS follow-up).
- Showing the licence texts in the window. The dialog says where
  `NOTICES.txt` is.
