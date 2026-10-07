# kernel-file-io Specification

## Purpose
Defines the file operations the kernel bridge must get right for the title's own caches and saves: renaming open files and FATX's overwrite semantics.

## Requirements

### Requirement: Open files can be renamed
NtSetInformationFile with FileRenameInformation (class 10) SHALL rename the open file. The target SHALL be resolved relative to RootDirectory when set, within the file's own directory for a bare name, and through the Xbox path table otherwise. An existing target SHALL be replaced only when ReplaceIfExists is set; otherwise the call SHALL fail with STATUS_OBJECT_NAME_COLLISION.

#### Scenario: Utility-drive texture cache
- **WHEN** BLiNX 2 writes `z:\media\plcom_tex.tmp` and renames it to `plcom_tex.ipk`
- **THEN** the rename succeeds, no `unhandled class 10` line is logged, and the next open of the `.ipk` succeeds

### Requirement: An overwrite open keeps the data a regrow exposes
An overwrite open (FILE_SUPERSEDE, FILE_OVERWRITE or FILE_OVERWRITE_IF) of an existing file SHALL behave as FATX does. If the handle's first operation sets the end of file, the bytes below the new end SHALL keep their old contents. If its first operation is a read, a write, a size query, an allocation or a close, the file SHALL be empty first.

#### Scenario: Texture-cache trim
- **WHEN** BLiNX 2 writes `z:\lng_us\title_tex_us.tmp` padded to 512 bytes, reopens it with CREATE_ALWAYS, sets the end of file to the true size and renames it to `.ipk`
- **THEN** the `.ipk` holds the written data (it starts with `IPK1`), not zeros

### Requirement: A missing game file is reported once, by name
The kernel SHALL report a failed guest open as a missing game file when all of these hold:
- the status is STATUS_OBJECT_NAME_NOT_FOUND or STATUS_OBJECT_PATH_NOT_FOUND;
- it came through NtCreateFile, NtOpenFile or IoCreateFile;
- the disposition is FILE_OPEN;
- the access mask has no write, append, write-attributes, write-EA or delete access;
- it is not a directory open;
- the name is absolute (it starts with `\` or a drive letter), not relative to a RootDirectory handle;
- the path, after the title's own drive links are resolved, translates through a rule that maps into the game files directory.

The report SHALL be high confidence when the parent directory of the translated host path exists, and low confidence otherwise. The host path SHALL be the one the failed call translated, read from the per-thread last host path; the report SHALL NOT translate the path again, so no second `[PATH]` line is printed and no directory is created.

With the default mode (`RECOMP_TRACE=missing` unset or `1`), the kernel SHALL print one `[FILE] missing <guest path> -> <host path>` line the first time each high-confidence path misses, and nothing more for later attempts at that path. Paths SHALL compare case-insensitively. Once a path has been reported this way, the kernel SHALL NOT print further per-attempt `[FILE] … FAILED` lines for it, and SHALL count them; the first attempt's FAILED line SHALL still print. FAILED lines for paths the default mode does not report SHALL print on every attempt, as before.

When the run ends, the kernel SHALL print one `[FILE] summary:` line with the number of high- and low-confidence missing paths, of failed opens and of FAILED lines not printed. In the default mode it SHALL print only when a high-confidence path was reported; under `all`, whenever any path was recorded. The line SHALL print at most once per run, from whichever of these happens first: the process exiting through `exit` or `main` returning; the title calling HalReturnToFirmware; the title calling KeBugCheck or KeBugCheckEx; the Win32 window closing. Under `all` the line SHALL end with which of these printed it (`[at exit]`, `[at firmware]`, `[at bugcheck]`, `[at window]`). The watchdog and the host crash handler SHALL print the two path counts without taking a lock. A run killed from outside prints no summary.

With `RECOMP_TRACE=missing=all`, the kernel SHALL print the FAILED line on every attempt, suppressing none, and SHALL also print, once per path:
- the low-confidence misses, as `[FILE] not found (no such directory) <guest> -> <host>`;
- failed opens outside the game tree and failed NtQueryFullAttributesFile probes, as `[FILE] not found (<tree>[, probe]) <guest> -> <host>`.

With `RECOMP_TRACE=missing=0`, the kernel SHALL print none of these lines, record nothing, and print every FAILED line as before this change.

With `RECOMP_DEBUG=missing_list=<path>`, each summary SHALL also write the unique misses to that file, one `<class> <attempts> <guest> <host>` line each, with `<class>` one of `high`, `low`, `other`, `probe`.

The report SHALL NOT change any status, handle or memory the guest sees. It SHALL behave the same on the Win32 and POSIX backends. The table of paths SHALL be fixed in size and safe for concurrent opens. Past 4096 unique paths it SHALL count misses without naming them and say so once; their FAILED lines keep printing.

#### Scenario: A removed song is named once
- **WHEN** BLiNX 2 runs `@attract` with `adx\envse_r1_island_omote.adx` removed from a copy of the game files, and the looping ambience retries the open on every loop
- **THEN** the log has exactly one `[FILE] missing d:\adx\envse_r1_island_omote.adx -> …/adx/envse_r1_island_omote.adx` line and one `[FILE] … FAILED` line for that path, and the exit summary counts one high-confidence path, as many failed opens as there were attempts, and all but one of them as not printed

#### Scenario: Verbose keeps every attempt
- **WHEN** the same run sets `RECOMP_TRACE=missing=all`
- **THEN** every attempt prints its FAILED line, and the summary reports no repeats left out

#### Scenario: Normal probes stay quiet
- **WHEN** BLiNX 2 runs `@attract` on the complete dump with an empty HDD directory, so its texture cache (`z:\media\*.ipk`), save metadata (`U:\…\SaveMeta.xbx`, `t:\$u\contentmeta.xbx`) and camera scan (`d:\media\event\EVCAMST0101_005.CAM`, under a directory the dump does not have) all fail
- **THEN** no `[FILE] missing` and no `[FILE] summary` line is printed, and every probe's FAILED lines print as before

#### Scenario: Verbose mode lists the probes
- **WHEN** the same run sets `RECOMP_TRACE=missing=all`
- **THEN** the camera scan prints one `[FILE] not found (no such directory)` line, and the cache and save probes print one `[FILE] not found (hdd)` or `(user)` line each per path

#### Scenario: A missing archive names the archive
- **WHEN** BLiNX 2 boots with `media.ipk` removed and shows its dirty-disc screen
- **THEN** the only `[FILE] missing` line names `d:\media.ipk`, and the loose-file fallbacks it then tries (`d:\media\se\*.bin` and others) are counted as low confidence only

#### Scenario: A relative open is not a game file
- **WHEN** a title opens a name relative to a directory handle, as XDeleteSaveGame does for each child of a save directory, and the open fails
- **THEN** nothing is printed or counted by default, and under `all` the line says `(unknown)`

#### Scenario: The title exits through the firmware
- **WHEN** a title calls HalReturnToFirmware after a missing-file open
- **THEN** the summary line prints before the process exits, and does not print a second time from `atexit` on the POSIX host, where ExitProcess runs the atexit handlers

#### Scenario: The window is closed on Windows
- **WHEN** the user closes the D3D11 or framebuffer window on Windows or Proton after a missing-file open
- **THEN** the summary line prints before the window-close `ExitProcess`

#### Scenario: Report switched off
- **WHEN** a run sets `RECOMP_TRACE=missing=0`
- **THEN** no `[FILE] missing`, `[FILE] not found` or `[FILE] summary` line is printed, and the per-attempt `[FILE] … FAILED` lines are unchanged

#### Scenario: Reporter unit test
- **WHEN** the `kernel_missing_report` ctest feeds failed opens with synthetic statuses, dispositions, access masks and paths over a temporary game directory
- **THEN** repeats are deduplicated case-insensitively, high and low follow the parent directory, write and create opens, directory opens, relative names and other statuses are neither reported nor counted, the save and cache trees are not reported by default, probes count only under `all`, the 4096-path cap counts without naming, repeats of a reported path are counted and flagged for suppression only in the default mode, concurrent notes keep the counts exact, the summary prints once, and a lock-free counts read matches it

### Requirement: Every bridged open logs its failures
NtCreateFile, NtOpenFile and IoCreateFile SHALL each print the per-attempt `[FILE] <guest path> (disp N) -> 0x<status> FAILED (win32 err=E…)` line on failure, and the `[FILE] <guest path> (disp … opts … from …) -> 0x00000000` line on success, in today's format. All three SHALL pass the guest path and status to `xbox_FileOpenHook`.

#### Scenario: NtOpenFile failure is visible
- **WHEN** a title opens a file that does not exist through NtOpenFile
- **THEN** a `[FILE] … FAILED` line names the guest path, as it already does for NtCreateFile

#### Scenario: NtCreateFile logs are unchanged
- **WHEN** BLiNX 2 runs `@attract` on the same dump before and after this change, with the report off
- **THEN** every `[FILE]` and `[PATH]` line of the old log is there, in the same order, and the only added lines are the NtOpenFile and IoCreateFile opens that printed nothing before

### Requirement: A missing directory reports as a missing path on every host
When an open through NtCreateFile, NtOpenFile or IoCreateFile fails because the host file does not exist, the kernel SHALL return:
- STATUS_OBJECT_PATH_NOT_FOUND when the parent directory of the translated path does not exist;
- STATUS_OBJECT_NAME_NOT_FOUND otherwise.

This SHALL hold on both the Win32 and the POSIX backends, as on the console. The POSIX backend SHALL record the matching Win32 error code (2 or 3, and 5 for access denied) for `xbox_LastFileError`. NtQueryFullAttributesFile and NtDeleteFile SHALL keep returning STATUS_OBJECT_NAME_NOT_FOUND in both cases on both backends, as they do today. The Win32 backend SHALL NOT change.

#### Scenario: Status unit test
- **WHEN** the `kernel_file_status` ctest opens a missing file in an existing directory and a file under a missing directory, on the Mac and under Proton
- **THEN** both hosts return 0xC0000034 and 0xC000003A respectively, `xbox_LastFileError` reads 2 and 3, and NtQueryFullAttributesFile returns 0xC0000034 for both paths on both hosts

#### Scenario: Burnout 3 under Proton
- **WHEN** Burnout 3 boots under Proton through the menu's profile flow into a race on the exact head of this change, after the same route was recorded on the base commit
- **THEN** it reaches the race as on the base commit, the set of `[FILE] … FAILED` guest paths and statuses is the same as in the base run, and no `[FILE] missing` line is printed on its complete dump

#### Scenario: BLiNX 2 on the Mac
- **WHEN** BLiNX 2 runs the Metal goldens on the Mac with this change
- **THEN** every golden matches, and the camera-scan probe now fails with 0xC000003A instead of 0xC0000034 without changing what the title does
