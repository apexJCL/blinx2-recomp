## ADDED Requirements

### Requirement: vsh_dump writes vertex programs on every backend
With `RECOMP_DEBUG=vsh_dump=<prefix>`, the executor SHALL write each new `(hash, start)` vertex program to `<prefix>NN_HASH.bin` on the CPU, Metal and D3D11 backends alike. Without `vsh_dump` or the `vsh` trace, a GPU backend SHALL NOT hash the program per draw.

#### Scenario: Metal
- **WHEN** SSX 3 runs on Metal with `vsh_dump` set
- **THEN** one `.bin` per program is written, and the end-of-run `[VSH]   program` lines list them

### Requirement: Frames around a program's first draw
With `fb_dump` and `fb_dump_prog=HASH[,HASH]`, the first draw of any listed program at flip count k SHALL dump flips k+1 to k+`fb_dump_prog_after`. On the CPU and write-back backends, it SHALL also dump the `fb_dump_prog_before` flips up to k from a memory ring. All of these SHALL be named `flip_NNNNN.bmp`. The trigger SHALL fire once and log the program, flip, draw and range. Unset, it SHALL cost nothing.

#### Scenario: Onset not known in advance
- **WHEN** a run sets `fb_dump_prog=8F706D7F` and the program first draws at flip 5327
- **THEN** flips 5298–5327 (from the ring) and 5328–5387 are written, and the log names flip 5327

### Requirement: fb_dump_at reports its limit
`fb_dump_at` SHALL accept 256 ranges and SHALL print how many past that were ignored.
