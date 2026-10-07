## ADDED Requirements

### Requirement: A TEST lifts as a compare of its AND against zero
The lifter SHALL lift every `test a, b` as `cmp (a & b), 0` at the operand width: the flag snapshot holds the masked AND in `_fa` and 0 in `_fb`, the recorded flag state is a `cmp` of that width, and `_cf` is 0. A join whose predecessors end in a `cmp` and a `test` of the same width SHALL inherit a flag state, so its jcc, setcc or cmovcc compiles to a real condition. The `cmp` arm of the condition builder SHALL answer `jo` and `jno` with the exact overflow of the wrapped difference at the operand width. The emitted C for `test X, X` SHALL NOT change.

#### Scenario: The stage 1 talk-zone join
- **WHEN** a block is reached by `cmp eax, 0` on one edge and `test esi, 0x100` on the other and starts with `je`
- **THEN** the `je` compiles to `CMP_EQ(_fa, _fb)` and not to `_flags`, and on the `test` edge `_fa` holds `esi & 0x100`

#### Scenario: Every condition after a test reads x86 semantics
- **WHEN** `test` is followed, directly or across a join, by any of je, jne, jb, jae, jbe, ja, jl, jge, jle, jg, js, jns, jp, jnp, jo, jno
- **THEN** the condition evaluates as the hardware would on 0, the sign bit of the width, the full mask and a negative immediate, at 8, 16 and 32 bits

### Requirement: Compare states of different widths merge for width-independent conditions
When the predecessors of a join carry `cmp` states of different operand widths, the join SHALL inherit a mixed-width compare state. A je, jne, jb, jae, jbe, ja, jl, jge, jle, jg, jp or jnp (and the matching setcc and cmovcc) after it SHALL read that edge's own snapshot, which is exact because `_fa/_fb` are masked and `_fas/_fbs` sign-extended at each edge's width. A js, jns, jo or jno after it SHALL keep the fallback, because the sign and overflow of the difference depend on the width.

#### Scenario: Mixed widths merge for the zero flag
- **WHEN** a block is reached by `cmp al, 0` on one edge and `test eax, eax` on the other and starts with `je`
- **THEN** the `je` compiles to `CMP_EQ(_fa, _fb)` and not to `_flags`

#### Scenario: Mixed widths refuse the sign flag
- **WHEN** a block is reached by `cmp al, 0x80` on one edge and `cmp eax, 0x80` on the other and starts with `js`
- **THEN** the `js` compiles to the fallback and is counted, since with al = 0x80 the hardware's SF is 0 at 8 bits and 1 at 32

### Requirement: Flag fallbacks are measured, not assumed
`recomp` SHALL record every `_flags` fallback it emits (function, guest address, condition, and why the state was lost) to `flag_fallbacks.json` in its output directory, counted once per guest address across alias bodies, SHALL put the totals in `summary.json`, SHALL print one summary line, and SHALL list the functions in the observed seed set that contain one. The report SHALL NOT fail the build.

#### Scenario: Before and after a lifter change
- **WHEN** `recomp` runs before and after a change to flag tracking
- **THEN** the difference between the two `flag_fallbacks.json` files is the list of branches whose behaviour can change, by guest address

#### Scenario: An alias body does not inflate the count
- **WHEN** a function body is emitted for its owner and for a tail-jump alias
- **THEN** each fallback site in it is counted once
