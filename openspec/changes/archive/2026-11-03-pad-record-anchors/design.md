## Grammar

    f<flip>:@open:<text>[:<buttons>/<period>]

- `<flip>` is the flip at which the open came in the record. An anchor
  without `f` is an error: it only means something on the flip clock.
- `<text>` matches the start of the guest path's file name, in any case, so
  `op.sfd` does not take `stop.sfd`. A text holding `\` or `/` matches any
  part of the path instead, for a hand-written `movie\op`. It ends at `:`,
  `,`, `#` or a blank. The recorder writes the file name only (no drive or
  directory), and leaves out a name that holds one of those characters.
- `<buttons>/<period>` (optional) is the retry: `a/61`, `p2-start/30`. The
  buttons must be buttons (no stick, none unknown, at least one) and the
  period 2 to 300 flips (`PAD_RETRY_MAX_FLIPS`); anything else ends the
  parse, as a step without a time does. A pad goes on the retry: a `p2-`
  before `@open` is refused, since an anchor is an event for every pad.

## Decisions

**D1. A step belongs to the last anchor before it starts.** The record
writes a step when it ends, so file order is not time order. After a parse,
the anchors are sorted by flip and each step takes the last anchor whose
flip is at or before the step's start (`pad_anchors_assign`). A step held
across an open keeps the anchor it started under.

**D2. Ties go after the anchor.** A step that starts at the anchor's flip
counts from the open. A press that started earlier in the same flip than
the open would then wait for the open it caused. So when an open comes
while a pad's flip under gathering already holds a new press, the recorder
writes the anchor one flip later. The press then stays before it.

**D3. Anchors match in order.** Only the first unmatched anchor is armed.
Each open is matched against it, case-insensitive, and the first match sets
the anchor's replay flip. An open before the armed anchor's own is ignored,
as cat's `wait open` consumes opens. One open matches one anchor.

**D4. The clock of a step is its anchor's.** For a step under anchor k, the
replay flip `f` reads as `f - seen_k + at_k` (seen_k is the replay flip of
the open, at_k the record's). Before the open the step neither presses nor
counts as done, so a live session's compaction keeps it. A step under no
anchor reads the raw flip, as before.

**D5. Retry while late.** The armed anchor waits from the moment the clock
it belongs to (the anchor before it, or the raw flip) reaches `at_k`. When
it has a retry, the replay presses the retry's buttons for `period/2` flips
(at least 1) every `period` flips, starting `period/2` flips after `at_k`.
The half-period gap leaves a release after the last recorded press, so the
first retry is a new edge. Without a retry the replay only waits. The wait
is logged once ("PAD: waiting on @open:<text>").

**D6. The recorder infers the retry, only for a tap.** Each pad's recorder
keeps the start flips and buttons of its last three presses (and the press
it is gathering). The anchor gets `<buttons>/<period>` when the newest three
all came after the previous anchor, press the same buttons, are evenly
spaced (the two gaps within 2 flips, each at most 300), and the open comes
within the last gap (plus 2) of the last press; the period is the last gap.
The first pad that has one gives it. A script's `tap A every 1 until open`,
or a person tapping A until a movie skips, gives three or more such
presses. Two menu choices with A ("New game", then "OK"), presses at uneven
spacing, or a last press long before the open give none: the retry would
press A on whatever screen comes before a slow open, which the record never
did. A `# retry <buttons>/<period>: pressed at f.. f.. f.., the open N flips
after the last` line goes before the anchor, so a person can see why and
delete a wrong retry. Three same-button presses that miss the spacing or the
open's distance, the last no more than three spacings before the open, get
a `# no retry <buttons>: pressed at f.. f.. f.. (gaps g1 g2), the open N
flips after the last` line instead, so a person can add one by hand.
Presses further back are a menu walk, not a wait for the open, and get no
line. In the replay a retry taps `PAD_RETRY_MAX_TAPS` (8) times,
then only waits for the open or the give-up: a wrong guess presses at most
eight times at whatever screen is up. (Review option chosen: three presses plus the open
within one period. An explicit opt-in key was the other option; it would
make every `@story-hub` record need it, and the tap test already tells a
script's tap from a menu press.)

**D7. Which opens are anchors.** `pad_anchor=<text>|<text>`, a `|` list
since `RECOMP_DEBUG` is a comma list. Unset, a record has no anchors and is
what it was. Every open would be too many: a story run opens about 800
files, many from the loading threads in varying order.
An open of the same name as the last anchor written is no new anchor: a
file opened twice in a row (a probe, then the read) gives one.

**D8. The open notice is a direct call.** `xbox_FileOpenHook` is one pointer
and cat owns it for its `wait open`. The kernel calls
`usb_gamepad_file_open(path, status)` next to the hook, on the opening
thread. Opens come on any game thread at once (a loader and the main
thread), and a lost or doubled match would hang the replay, so the match
and the record's anchor line run under one SRW lock (`s_anchor_lock`). The
pad thread takes it for the give-up tick and the retry, and for the
recorder's feed while recording, so the presses the retry is read from are
whole. Every anchor log line (match, give-up, the retry's wait and cap, and
`pad_record_open`'s "cannot be an anchor" and "too long") is formatted
under the lock and printed after it, so a slow stderr does not
hold the pad thread. The open's thread never reads the script, which the
pad thread writes unlocked (`announced`, and live lines' appends and
compaction): a give-up from an open marks its anchors, and the pad thread
counts the steps it skipped at its next tick. A line dropped or cut by a
full buffer leaves "...\n" at its end. Without a pad script or record the call is one cached load and
returns: no lock.

**D9. A late open is given up.** An open the replay never makes (a save in
one run only, a file the RAM cache serves without `NtCreateFile`, two files
that open in the other order) would leave the steps waiting and the retry
tapping at a frozen screen. When the armed anchor's clock reaches
`at + 1800` flips (`PAD_ANCHOR_GIVE_UP_FLIPS`, 30 s at 60 flips/s; a movie
anchor is 3 to 15 s late at most), the replay marks it seen as if it came
on time, and goes on: its retry stops, and its steps run on the clock it
was due by, the raw count when it is the first. Later anchors that clock
has already passed go with it, silently: their opens would have been taken
during the wait, and their retries must not all tap at once. The steps that
clock has already passed are skipped, not pressed. One line logs it ("PAD:
gave up on @open:<text> at flip F, N flips late[, and K later anchor(s) it
passed]; S step(s) skipped, the rest on the record's clock").

An open that matches a later anchor gives up the armed one and those
between and takes the later one, in two cases:
- the later anchor is on the armed one's record flip: two loader opens
  that came in the other order. On time or late; nothing is recorded
  between them, so nothing is skipped, and the first one's open after it
  is a re-open (below).
- the armed anchor is late (its clock past its `at`) and the later anchor
  is no more than 1800 record flips after it: the game has reached a later
  event, so the earlier one was missed (served from the cache, say).
The given-up anchors are read on the clock of the later one's `at` (or
later, if the clock is past it), so their steps are passed and skipped; the
pad thread logs how many at its next tick. Otherwise the order holds: a
later file's early open is not taken over the armed one, as cat's `wait
open` consumes opens in order. (Review option chosen: look ahead only when
late, or on the same record flip. Looking ahead always would let a file
that also opens early, a shared texture say, skip the event the steps wait
for.)

An open whose file matches the last seen anchor (or one on its record flip)
is not taken as that name's later anchor j while its clock is nearer the
seen one: before the midpoint of the two record flips, (at_seen + at_j)/2.
The recorder writes one anchor for a file opened twice in a row (D7), so a
probe then the read, or a movie that loops by opening again, shows once in
the record; without the rule, the second open would jump the clock to that
name's next anchor (a, b, a: a late b skipped for a loop of a). Past the
midpoint it is j's own open with b missed, and is taken. The rule holds
only for a j past the armed anchor's record flip: inside one flip the
recorder writes a name again after another (x, y, x), so x, x, y there is
the third anchor, not a re-open. The swap's log line says "@open:<j> taken
before @open:<armed> (same record flip)", as nothing is skipped; the match
line's offset is from the clock before it is raised to at_j. There is no
env override:
a record that needs a longer wait is a record to re-take, and a fixed
value keeps the key table short.

**D10. Live lines take no anchors.** `RECOMP_PAD_LIVE` parses without the
anchor table: a line is pressed now, not on a recorded event, and adding an
anchor on the pad thread would race the opens and re-tie the steps already
pressing. An anchor line there is skipped with a warning; live steps stay
on the raw clock.

## Limits

- An anchor whose file does not open in the replay waits 1800 flips, then
  is given up (D9) and the replay may miss there. A save that exists in one
  run and not in the other, or a file the cache skips, are such opens.
  Pick anchor texts that every run opens: movies, screens.
- D2's flip: an anchor the recorder moved to F+1 for an open at F maps the
  replay's open to F+1, so every step under it replays one flip early
  against the open. It is harmless at a 9-flip hold and the right trade
  against a press that waits for its own effect; it is not a bug to chase.
- A step under anchor k-1 still due when anchor k's open comes early keeps
  its own clock and can press after steps of anchor k
  (`test_anchor_early_limit`).
- The look-ahead (D9) takes the first later anchor whose text matches. A
  re-open of the last seen anchor's file is refused before the midpoint, but a file opened
  again further back (a, b, c, a with c late, and a opened again) can take
  the second a and skip c's steps. Pick texts that open once per event.
- Any file whose anchor shares a record flip with the armed one can take
  its group early (D9): a shared texture opened early on that flip fires
  the steps after it before the event they wait for.
- A live line's compaction (`RECOMP_PAD_LIVE`) runs before the tick and can
  drop steps a give-up skipped before they are counted: only the logged
  count is then low.
- Two opens that swap order across record flips (x at 100, y at 101, come
  y then x, on time) cost y the full give-up: only anchors on the armed
  one's record flip are taken early.
- The retry guesses intent from three evenly spaced presses (D6). A record
  with no tap before an anchor only waits there; a movie that plays out
  still gets there.
- Memory states (`wait mem`) are not events here. Only file opens are.
