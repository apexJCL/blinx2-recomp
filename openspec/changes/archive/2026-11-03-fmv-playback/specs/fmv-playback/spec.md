## ADDED Requirements

### Requirement: Movies are decoded by the title
Sofdec (`.sfd`) video and ADX/AIX audio SHALL be decoded by the translated CRI code. The host SHALL NOT replace the decoder unless the ffmpeg fallback (see proposal) is adopted through its own change. The presentation path SHALL draw the YUY2/UYVY frame texture (formats 0x24/0x25) with BT.601 conversion.

#### Scenario: Intro on Proton
- **WHEN** `logo_mgs.sfd`, `logo_artoon.sfd` and `blinx2_opening.sfd` play
- **THEN** frames appear in the window at the movie's pacing, flips alternate between both back buffers, and no frame is dropped for lack of a decoder
