# Tasks: overlay-saves

## 1. Spec
- [x] 1.1 Proposal, design, tasks.

## 2. Toolkit (branch `feat/ovl-saves` off `posix-host/portability`)
- [x] 2.1 `saves_zip.{c,h}`: CRC32, stored zip writer, reader and
      validator (D2, D3), manifest write and parse.
- [x] 2.2 `tests/saves_zip` ctest for every D3 refusal and the round trip.
- [x] 2.3 Kernel: `xbox_saves_busy()` (D4), `xbox_path_save_root()`,
      `xbox_path_is_save()`, `xbox_path_title_id()`, title name, key
      fingerprint; the guard test in `tests/kernel_directory_posix`.
- [x] 2.4 `saves_store.{c,h}`: collect, backup, stage, swap with rollback
      (D5, D6); tested in `tests/saves_zip`, the rollback with renames
      failed on purpose (`saves_store_rename_hook`).
- [x] 2.5 Menu: `PAGE_SAVES`, save list, export and import flows, the
      browser host page (D7); update `tests/enhance_menu`.
- [x] 2.6 `docs/runtime/config.md`: the Saves section.

## 3. Gates
- [x] 3.1 Mac build and `tests/posix_ctest.sh` (0 FAIL).
- [x] 3.2 BLiNX 2 build and golden on the PC (D3D11 native).
- [ ] 3.3 Hand check (the user): export on one host, import on another,
      progress restored; a foreign or damaged zip refused, saves untouched.

## 4. Follow-ups
- [ ] Deflate import (zips re-packed by desktop tools).
- [ ] A quit poster for the GDI backend.
- [ ] The Lucide `save` glyph if the page ships with `DOWNLOAD`.
- [ ] The T:/U: fallbacks (`TitleData`, `UserData` without a title
      folder) count for the busy guard but are not exported.
