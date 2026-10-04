## ADDED Requirements

### Requirement: Movies are decoded by the title
Sofdec (`.sfd`) video and ADX/AIX audio SHALL be decoded by the translated CRI code. The host SHALL NOT replace the decoder unless the ffmpeg fallback (see proposal) is adopted through its own change. The presentation path SHALL draw the YUY2/UYVY frame texture (formats 0x24/0x25) with BT.601 conversion.

#### Scenario: Intro on Proton
- **WHEN** `logo_mgs.sfd`, `logo_artoon.sfd` and `blinx2_opening.sfd` play
- **THEN** frames appear in the window at the movie's pacing, flips alternate between both back buffers, and no frame is dropped for lack of a decoder

### Requirement: Movie windows are tagged in performance logs
The runtime SHALL mark the interval between opening and closing a `movie\*.sfd` file, so that performance reports can exclude it from 3D statistics.

#### Scenario: Movie window in the log
- **WHEN** the title opens `d:\movie\title_movie_1a.sfd` and later closes it
- **THEN** the log has one line at the open and one at the close, each with a timestamp and the file name

### Requirement: The overlay is not assumed
The runtime SHALL be able to log MMIO writes to the PVIDEO range (`0xFD008000`-`0xFD008FFF`). Movie presentation SHALL rely on the texture path unless such writes are seen.

#### Scenario: No overlay writes during a movie
- **WHEN** the intro plays with the PVIDEO check on
- **THEN** no write to the PVIDEO range is logged
