## ADDED Requirements

### Requirement: The NV2A register trace runs only when asked
The per-kick `[NV2A] <ms> DMA_PUT/DMA_GET/fence` line, the `PCRTC_START` change line, the once-a-second display framebuffer checksum and the periodic `[GPU]`/`[PB]` report SHALL be gated on `RECOMP_TRACE=nv2a`, with `RECOMP_TRACE=pb_scan` also arming the periodic report and `RECOMP_DEBUG=fb_dump` alone keeping the report's periodic picture without its text. `RECOMP_PB_EXEC` SHALL NOT arm any of them, and the executor, the segment scan, the fence mirrors, the flip hold and the `[GPU] flip` line SHALL NOT depend on the trace flag. The per-kick line SHALL be written by one call.

#### Scenario: Default run
- **WHEN** the game runs with no trace key set
- **THEN** the log has no `[NV2A] ... DMA_PUT` line, no `PCRTC_START` line and no periodic `[GPU]` report, and the goldens pass unchanged on Metal and on D3D11 under Proton

#### Scenario: Stall timeline on request
- **WHEN** the game runs with `RECOMP_TRACE=nv2a`
- **THEN** every pushbuffer kick prints one `[NV2A] <ms> DMA_PUT = ... DMA_GET = ... fence ...` line, stamped on the same clock as `[GPU] flip`, so a gap between lines reads as the GPU side standing still

#### Scenario: Picture without the text
- **WHEN** the game runs with `RECOMP_DEBUG=fb_dump=<prefix>` and no trace key
- **THEN** a numbered `<prefix>NNN.bmp` is written every `pb_report_ms` and no `[GPU]` report text is printed
