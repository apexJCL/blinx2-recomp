#!/usr/bin/env python3
"""Checks on an audio dump (RECOMP_DEBUG=audio_wav) or an xemu reference capture.

  audio_check.py WAV [--log LOG] [--rate] [--golden JSON --scenario NAME]
                     [--voice-dump RAW ...] [--dump-rate HZ]
                     [--ref REF.wav] [--json]

Needs numpy (nothing else outside the standard library). The system python3 on
the macOS host and on the Linux/Proton host has none; the toolkit venv
(xboxrecomp/.venv/bin/python3) does.

Report, always:
  duration, rate and channels; first sound (first sample at or above the
  silence floor, -40 dBFS by default); RMS per 100 ms window (min / median /
  max after the first sound, all of them with --json); dropouts (runs of
  digital zero, every channel, longer than the limit -- 2 ms -- between the
  first and the last sound, with sound at or above the silence floor in the
  50 ms on each side: trailing silence is not a dropout, and neither are the
  zeros a blank movie track dithers through); clipping (the share of samples
  at full scale).

With --log: the sample-rate ratio, from the toolkit's two submit lines
    [APU] first submit t=<seconds>
    [APU] last submit t=<seconds> [samples=<frames submitted in between>]
  ratio = frames / (rate x (t_last - t_first)), frames being samples= when
  present, else the WAV's frame count (a WAV capped by audio_wav_secs
  needs samples=). --rate makes a missing pair of lines a failure.

With --log, also host starvation: the toolkit's lines (RECOMP_TRACE=apu or
    RECOMP_TRACE=audio_host)
    [AUDIO-HOST] starve wav=<sample index> ms=<length> ...
  each a stretch the host device had nothing queued and played silence. The
  WAV tap records submissions back to back, so it has no hole there; the
  check splices that much digital zero in at that index first, so the
  dropout check below runs on what the speaker played, not on what the
  guest mixed. Reported as host starvation (count, total ms).

With --log, also stale-lap replays (RECOMP_TRACE=apu_ring): a title that
  streams compressed audio decodes it into a looping buffer voice and keeps
  writing ahead of the play cursor; when the writer falls behind, the voice
  plays the previous lap again. That is no digital zero, and under the rest
  of the mix the checks above cannot see it, but it is audible as a stutter
  or a voice cutting out. The toolkit's once-a-second lines
    [APU-RING] t=<s> v=<voice> ... stale_total=<n> ...
  count, per voice, 1 KB blocks played again unchanged since their last
  play; the check fails when the total over all voices exceeds
  max_ring_stale (0). Not with --golden, unless the JSON sets it: the
  golden gate leaves it out until a clean run shows that a stream's last
  lap, played again as the stream ends, does not trip it.

With --voice-dump RAW (repeatable; RECOMP_DEBUG=apu_voice_dump=all writes
  one s16 stereo file per voice): the same thing offline. Every 256-frame
  chunk (at a 64-frame step, digital silence skipped) is looked up among the
  chunks before it, up to 2^20 frames back; an exact match is a replay.
  Consecutive matches at one lag make a run. A slot that plays the same
  one-shot sound again repeats all of it (a run about as long as the lag);
  a starved ring repeats in bursts, so only runs shorter than half their lag
  count, and replayed audio over max_replay_ms (0) fails. A writer that
  misses a whole lap escapes this; the [APU-RING] check sees it.

With --ref: the envelope cross-correlation lag (1 ms envelope, searched within
  +/- max_lag_ms, 500 ms) and its peak correlation, then per-band spectral
  correlation of the aligned signals: 8 log-spaced bands from 50 Hz to 16 kHz,
  each band's energy over 1 s windows (in 1/48 s frames) correlated between the
  two and averaged over the windows. Bands silent in both are skipped.

Noise (when max_noise_fraction is below 1, which the golden JSON sets): the
  spectral flatness of each 1 s window of the mono mix at or above the silence
  floor -- geometric over arithmetic mean of the Hann-windowed power spectrum
  between 200 Hz and 16 kHz, and the share of the window's energy above 8 kHz.
  Music sits well under 0.3 flatness with a few percent up there; white noise
  gives about 0.56 (a single periodogram's chi-square bins, not 1.0) and two
  thirds. A window at or above both noise_flatness and noise_hf_share is
  noise-like, and the check fails when more than max_noise_fraction of the
  windows are. This is what caught the APU reading .text as PCM (every effect
  full-scale static, the music's upper half gone): that dump passed every
  other check.

  The limits sit between what was measured: clean runs (five, 60-105 s, title
  and in-game) peak at flatness 0.315 and 16 % above 8 kHz; the .text-as-PCM
  windows were 0.40-0.51 and 57-67 %. noise_flatness 0.36 leaves 0.045 of
  margin on each side and noise_hf_share 0.25 leaves 0.09 below and 0.3
  above. A scenario with sustained broadband effects (wind, water, crowd)
  can sit higher on both and still be clean: give that scenario its own
  noise_flatness / noise_hf_share / max_noise_fraction in the golden JSON
  (its keys override `compare`), measured from a run known good by ear,
  rather than raising the shared limits.

With --golden JSON --scenario NAME: thresholds from the JSON's `compare`,
  overridden by the scenario's own keys (any of the limits below), and the
  scenario's `first_sound_window` [lo, hi] seconds. Without --golden the
  built-in defaults below apply and first sound is only required to exist.

Exit 0 when every check passes, 1 on a failed check (each failure printed as
FAIL with the scenario and the window or value), 2 on a usage error or an
unreadable file.
"""

import argparse
import hashlib
import json
import math
import re
import struct
import sys

try:
    import numpy as np
except ImportError:  # pragma: no cover
    sys.stderr.write("audio_check.py needs numpy: run it with the toolkit venv "
                     "(xboxrecomp/.venv/bin/python3)\n")
    sys.exit(2)

DEFAULTS = {
    "silence_floor_dbfs": -40.0,
    "max_dropout_ms": 2.0,
    "max_clipping_fraction": 0.001,
    "rate_tolerance": 0.005,
    "min_band_correlation": 0.8,
    "min_envelope_correlation": 0.8,
    "max_lag_ms": 500.0,
    "noise_flatness": 0.36,       # clean max 0.315, noise from 0.40 (see above)
    "noise_hf_share": 0.25,       # clean max 0.16, noise from 0.57
    "max_noise_fraction": 1.0,    # off unless the golden JSON lowers it
    "max_ring_stale": 0,          # [APU-RING] stale-lap blocks, all voices
    "max_replay_ms": 0.0,         # --voice-dump: replayed audio per voice
}

NOISE_LO_HZ = 200.0
NOISE_HI_HZ = 16000.0
NOISE_HF_HZ = 8000.0

BANDS = 8
BAND_LO_HZ = 50.0
BAND_HI_HZ = 16000.0


class Bad(Exception):
    """A usage or input error (exit 2)."""


# ── WAV ────────────────────────────────────────────────────────────────────

def _chunks_follow(data, pos):
    """True if data[pos:] is empty or a run of well-formed RIFF chunks."""
    while pos < len(data):
        if pos + 8 > len(data):
            return False
        cid = data[pos:pos + 4]
        if not all(32 <= c < 127 for c in cid):
            return False
        size = struct.unpack_from("<I", data, pos + 4)[0]
        pos += 8 + size + (size & 1)
        if pos > len(data):
            return False
    return True


def read_wav(path):
    """(rate, samples as float array [frames, channels] in -1..1).

    RIFF parsed by hand rather than with `wave`: a dump whose header was never
    finalised (data size 0 or past the end) still reads, up to the file end.
    So does one whose header is stale (a hard exit after the last
    once-a-second refresh): bytes after the declared data that do not parse
    as further chunks are audio, and are read up to the file end too.
    """
    try:
        data = open(path, "rb").read()
    except OSError as e:
        raise Bad(f"{path}: {e}")
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise Bad(f"{path}: not a RIFF/WAVE file")
    pos, fmt, pcm = 12, None, None
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        body = pos + 8
        if cid == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", data, body)
        elif cid == b"data":
            end = body + size
            if size == 0 or end > len(data) or not _chunks_follow(data, end + (size & 1)):
                end = len(data)
            pcm = data[body:end]
            break
        pos = body + size + (size & 1)
    if fmt is None or pcm is None:
        raise Bad(f"{path}: no fmt or data chunk")
    tag, channels, rate, _, align, bits = fmt
    if tag not in (1, 0xFFFE) or bits != 16:
        raise Bad(f"{path}: only 16-bit PCM is read (format {tag}, {bits} bits)")
    frames = len(pcm) // align
    x = np.frombuffer(pcm[:frames * align], dtype="<i2").reshape(frames, channels)
    return rate, x.astype(np.float64) / 32768.0


def write_wav(path, rate, samples):
    """16-bit PCM WAV from float samples [frames, channels] in -1..1 (tests)."""
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    pcm = np.clip(np.round(x * 32768.0), -32768, 32767).astype("<i2").tobytes()
    ch = x.shape[1]
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<IHHIIHH", 16, 1, ch, rate,
                                      rate * ch * 2, ch * 2, 16))
        f.write(b"data" + struct.pack("<I", len(pcm)) + pcm)


# ── Measurements ───────────────────────────────────────────────────────────

def dbfs(v):
    return 20.0 * math.log10(v) if v > 0 else float("-inf")


def first_last_sound(x, floor_dbfs):
    """Frame indexes of the first and last frame at or above the floor."""
    thr = 10.0 ** (floor_dbfs / 20.0)
    loud = np.flatnonzero(np.max(np.abs(x), axis=1) >= thr)
    if loud.size == 0:
        return None, None
    return int(loud[0]), int(loud[-1])


def rms_windows(x, rate, ms=100):
    n = max(1, int(rate * ms / 1000))
    w = x.shape[0] // n
    if w == 0:
        return []
    blk = x[:w * n].reshape(w, n * x.shape[1])
    return [dbfs(v) for v in np.sqrt(np.mean(blk * blk, axis=1))]


def zero_runs(x, start, end):
    """(start, length) of each run of all-channel digital zero inside
    [start, end] -- the span between the first and last sound."""
    if start is None or end <= start:
        return []
    z = np.all(x[start:end + 1] == 0.0, axis=1).astype(np.int8)
    d = np.diff(np.concatenate(([0], z, [0])))
    s = np.flatnonzero(d == 1)
    e = np.flatnonzero(d == -1)
    return [(int(a) + start, int(b - a)) for a, b in zip(s, e)]


def in_sound(x, rate, start, length, floor_dbfs, ms=50):
    """Whether the `ms` of audio on each side of a zero run are at or above
    the floor: a hole in sound, as opposed to zeros inside near-silence (a
    movie's blank track dithers around zero and touches it for milliseconds
    at a time -- not a dropout)."""
    n = max(1, int(rate * ms / 1000))
    thr = 10.0 ** (floor_dbfs / 20.0)
    before = x[max(0, start - n):start]
    after = x[start + length:start + length + n]
    return (before.size > 0 and np.sqrt(np.mean(before * before)) >= thr
            and after.size > 0 and np.sqrt(np.mean(after * after)) >= thr)


def clipping_fraction(x):
    return float(np.mean(np.abs(x) >= 32767.0 / 32768.0)) if x.size else 0.0


def spectral_flatness(x, rate, floor_dbfs, secs=1.0):
    """(flatness, share of energy above NOISE_HF_HZ) of each `secs` window of
    the mono mix whose RMS is at or above the floor. Flatness is the geometric
    over the arithmetic mean of the Hann-windowed power spectrum between
    NOISE_LO_HZ and NOISE_HI_HZ: white noise comes out near 0.56, music under
    0.3. The high-frequency share tells noise from a busy mix: white noise
    puts two thirds of its energy above 8 kHz, music a few percent. Silent
    windows are left out."""
    n = int(rate * secs)
    m = np.mean(x, axis=1)
    w = len(m) // n
    if w == 0 or n < 16:
        return []
    thr = 10.0 ** (floor_dbfs / 20.0)
    seg = m[:w * n].reshape(w, n)
    loud = np.sqrt(np.mean(seg * seg, axis=1)) >= thr
    if not loud.any():
        return []
    spec = np.abs(np.fft.rfft(seg[loud] * np.hanning(n), axis=1)) ** 2
    freqs = np.fft.rfftfreq(n, 1.0 / rate)
    sel = (freqs >= NOISE_LO_HZ) & (freqs < min(NOISE_HI_HZ, rate / 2))
    p = spec[:, sel] + 1e-20
    flat = np.exp(np.mean(np.log(p), axis=1)) / np.mean(p, axis=1)
    hf = spec[:, freqs >= NOISE_HF_HZ].sum(axis=1) / (spec.sum(axis=1) + 1e-20)
    return [(float(a), float(b)) for a, b in zip(flat, hf)]


SUBMIT_RE = re.compile(r"\[APU\] (first|last) submit\b.*?\bt=([0-9.]+)"
                       r"(?:.*?\bsamples=([0-9]+))?")


def submit_times(log_path):
    """(t_first, t_last, samples or None) from the toolkit's submit lines."""
    first = last = samples = None
    try:
        f = open(log_path, encoding="utf-8", errors="replace")
    except OSError as e:
        raise Bad(f"{log_path}: {e}")
    with f:
        for line in f:
            m = SUBMIT_RE.search(line)
            if not m:
                continue
            if m.group(1) == "first" and first is None:
                first = float(m.group(2))
            elif m.group(1) == "last":
                last = float(m.group(2))
                samples = int(m.group(3)) if m.group(3) else None
    return first, last, samples


HOST_STARVE_RE = re.compile(r"\[AUDIO-HOST\] starve wav=([0-9]+) ms=([0-9.]+)")


def host_starves(log_path):
    """[(wav sample index, ms)] from the toolkit's [AUDIO-HOST] starve lines."""
    out = []
    try:
        f = open(log_path, encoding="utf-8", errors="replace")
    except OSError as e:
        raise Bad(f"{log_path}: {e}")
    with f:
        for line in f:
            m = HOST_STARVE_RE.search(line)
            if m:
                out.append((int(m.group(1)), float(m.group(2))))
    return out


RING_RE = re.compile(r"\[APU-RING\] t=[0-9]+s v=([0-9]+)\b.*?\bstale_total=([0-9]+)")


def ring_stale(log_path):
    """{voice: stale_total} from the [APU-RING] lines, or None when the log
    has none (the trace was off)."""
    out = None
    try:
        f = open(log_path, encoding="utf-8", errors="replace")
    except OSError as e:
        raise Bad(f"{log_path}: {e}")
    with f:
        for line in f:
            m = RING_RE.search(line)
            if m:
                out = out if out is not None else {}
                v = int(m.group(1))
                out[v] = max(out.get(v, 0), int(m.group(2)))
    return out


REPLAY_CHUNK = 256
REPLAY_STEP = 64
REPLAY_MAX_LAG = 1 << 20


def voice_replays(path):
    """Stale-lap replays in one voice dump (raw s16 stereo):
    {frames, sound_frames, replay_frames, lag (the commonest), runs}.

    A replay is a stretch identical to the audio `lag` frames before it. A
    voice slot that plays the same one-shot sound twice repeats too, but the
    whole sound: the run is about as long as the lag. A ring the writer fell
    behind on repeats in bursts much shorter than one lap. Only runs shorter
    than half their lag count."""
    try:
        raw = np.fromfile(path, dtype="<i2")
    except OSError as e:
        raise Bad(f"{path}: {e}")
    x = raw[: raw.size // 2 * 2].reshape(-1, 2)
    n = x.shape[0]
    flat = x.reshape(-1)
    seen = {}
    hits = []
    sound = 0
    for pos in range(0, n - REPLAY_CHUNK + 1, REPLAY_STEP):
        c = flat[2 * pos: 2 * (pos + REPLAY_CHUNK)]
        if not c.any():
            continue
        sound += 1
        # A 16-byte digest, not the 1 KB chunk: a 5-minute dump would
        # otherwise hold ~200 MB of keys.
        key = hashlib.blake2b(c.tobytes(), digest_size=16).digest()
        p = seen.get(key)
        if p is not None and pos - p <= REPLAY_MAX_LAG:
            hits.append((pos, pos - p))
        seen[key] = pos
    runs = []                       # (start, length, lag)
    for pos, lag in hits:
        if runs and runs[-1][2] == lag and pos <= runs[-1][0] + runs[-1][1]:
            st, ln, lg = runs[-1]
            runs[-1] = (st, pos + REPLAY_CHUNK - st, lg)
        else:
            runs.append((pos, REPLAY_CHUNK, lag))
    stale = [r for r in runs if r[1] < r[2] / 2]
    lags = {}
    for _, ln, lg in stale:
        lags[lg] = lags.get(lg, 0) + ln
    return {"frames": n, "sound_frames": sound * REPLAY_STEP,
            "replay_frames": int(sum(ln for _, ln, _ in stale)),
            "lag": max(lags, key=lags.get) if lags else None,
            "runs": len(stale)}


def splice_starves(x, rate, starves):
    """x with each starvation's silence inserted at its sample index: the
    timeline the device played."""
    if not starves:
        return x
    parts, pos = [], 0
    for idx, ms in sorted(starves):
        idx = min(max(idx, pos), x.shape[0])
        parts.append(x[pos:idx])
        parts.append(np.zeros((int(round(ms * rate / 1000.0)), x.shape[1])))
        pos = idx
    parts.append(x[pos:])
    return np.concatenate(parts)


def envelope(x, rate, ms=1):
    """Mean absolute value of the mono mix per `ms` block."""
    n = max(1, int(rate * ms / 1000))
    m = np.mean(np.abs(x), axis=1)
    w = m.shape[0] // n
    return m[:w * n].reshape(w, n).mean(axis=1)


def envelope_lag(test, ref, rate, max_lag_ms):
    """(lag_ms, correlation): how much later `test` is than `ref`, from the
    normalised cross-correlation of their 1 ms envelopes."""
    a = envelope(test, rate)
    b = envelope(ref, rate)
    a = a - a.mean()
    b = b - b.mean()
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0, 0.0
    n = len(a) + len(b) - 1
    size = 1 << (n - 1).bit_length()
    xc = np.fft.irfft(np.fft.rfft(a, size) * np.conj(np.fft.rfft(b, size)), size)
    max_lag = int(max_lag_ms)
    lags = np.arange(-max_lag, max_lag + 1)
    vals = xc[lags % size]  # xc[k] = sum a[n+k] b[n]: test lags ref by k
    i = int(np.argmax(vals))
    return float(lags[i]), float(vals[i] / (na * nb))


def align(test, ref, rate, lag_ms):
    """Both signals cut to their overlap once `test` is shifted back by lag."""
    k = int(round(lag_ms * rate / 1000.0))
    if k > 0:
        test = test[k:]
    elif k < 0:
        ref = ref[-k:]
    n = min(len(test), len(ref))
    return test[:n], ref[:n]


def band_energies(x, rate, frame):
    """[frames, BANDS] energy of the mono mix per STFT frame and band."""
    m = np.mean(x, axis=1)
    w = len(m) // frame
    if w == 0:
        return np.zeros((0, BANDS))
    seg = m[:w * frame].reshape(w, frame) * np.hanning(frame)
    # Scaled so a frame's bins sum to about its windowed time-domain energy.
    spec = np.abs(np.fft.rfft(seg, axis=1)) ** 2 / (frame / 2.0)
    freqs = np.fft.rfftfreq(frame, 1.0 / rate)
    edges = np.geomspace(BAND_LO_HZ, min(BAND_HI_HZ, rate / 2), BANDS + 1)
    out = np.zeros((w, BANDS))
    for b in range(BANDS):
        sel = (freqs >= edges[b]) & (freqs < edges[b + 1])
        if sel.any():
            out[:, b] = spec[:, sel].sum(axis=1)
    return out


def band_correlation(test, ref, rate, floor_dbfs):
    """Per band: the mean over 1 s windows of the correlation between the two
    signals' band energy (in dB) across the window's frames. None for a band
    silent in both."""
    frame = max(64, rate // 48)  # ~21 ms frames, 48 to a 1 s window
    et = band_energies(test, rate, frame)
    er = band_energies(ref, rate, frame)
    per_win = 48
    # Windowed energy of a full-band frame at the floor (Hann: mean w^2 = 3/8).
    floor = 10.0 ** (floor_dbfs / 10.0) * frame * 0.375
    result = []
    for b in range(BANDS):
        cs = []
        for w0 in range(0, min(len(et), len(er)) - per_win + 1, per_win):
            t = et[w0:w0 + per_win, b]
            r = er[w0:w0 + per_win, b]
            if t.max() < floor and r.max() < floor:
                continue
            tl = 10 * np.log10(t + floor * 1e-3)
            rl = 10 * np.log10(r + floor * 1e-3)
            st, sr = tl.std(), rl.std()
            if st < 0.5 and sr < 0.5:  # both steady: compare levels instead
                cs.append(1.0 if abs(tl.mean() - rl.mean()) <= 3.0 else 0.0)
            elif st == 0 or sr == 0:
                cs.append(0.0)
            else:
                cs.append(float(np.corrcoef(tl, rl)[0, 1]))
        result.append(float(np.mean(cs)) if cs else None)
    return result


# ── Driver ─────────────────────────────────────────────────────────────────

def load_golden(path, scenario):
    try:
        g = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Bad(f"{path}: {e}")
    scen = g.get("scenarios", {})
    if scenario not in scen:
        raise Bad(f"{path}: no scenario {scenario!r} (have: "
                  f"{', '.join(sorted(scen)) or 'none'})")
    limits = dict(DEFAULTS)
    # Not gated in golden until a clean run shows a stream's last lap at its
    # end does not count as stale; the JSON can still set it.
    limits["max_ring_stale"] = None
    limits.update({k: v for k, v in g.get("compare", {}).items()
                   if k in DEFAULTS})
    limits.update({k: v for k, v in scen[scenario].items() if k in DEFAULTS})
    return limits, scen[scenario].get("first_sound_window")


def check(wav, log=None, need_rate=False, limits=None, window=None,
          ref=None, scenario=None, voice_dumps=(), dump_rate=44100):
    """(report dict, list of failure strings)."""
    lim = dict(DEFAULTS)
    lim.update(limits or {})
    rate, x = read_wav(wav)
    where = f"scenario {scenario}: " if scenario else ""
    fails = []
    rep = {"file": wav, "rate": rate, "channels": int(x.shape[1]),
           "frames": int(x.shape[0]),
           "duration_s": x.shape[0] / rate if rate else 0.0}
    if log:
        st = host_starves(log)
        rep["host_starves"] = {"count": len(st),
                               "total_ms": float(sum(ms for _, ms in st))}
        x = splice_starves(x, rate, st)

    first, last = first_last_sound(x, lim["silence_floor_dbfs"])
    rep["first_sound_s"] = None if first is None else first / rate
    rep["last_sound_s"] = None if last is None else last / rate
    if first is None:
        fails.append(f"{where}no sound at or above {lim['silence_floor_dbfs']}"
                     f" dBFS in 0-{rep['duration_s']:.2f} s"
                     + (f" (first-sound window {window[0]}-{window[1]} s)"
                        if window else ""))
    elif window and not (window[0] <= first / rate <= window[1]):
        fails.append(f"{where}first sound at {first / rate:.3f} s, outside the"
                     f" window {window[0]}-{window[1]} s")

    rms = rms_windows(x, rate)
    rep["rms_100ms_dbfs"] = rms
    if first is not None:
        after = [v for v in rms[first * 10 // rate:] if v != float("-inf")]
        if after:
            rep["rms_after_first_dbfs"] = {
                "min": min(after), "median": float(np.median(after)),
                "max": max(after)}

    runs = zero_runs(x, first, last)
    limit = int(round(lim["max_dropout_ms"] * rate / 1000.0))
    drops = [(s, n) for s, n in runs
             if n > limit and in_sound(x, rate, s, n, lim["silence_floor_dbfs"])]
    rep["dropouts"] = [{"at_s": s / rate, "ms": n * 1000.0 / rate}
                       for s, n in drops]
    for s, n in drops[:10]:
        fails.append(f"{where}dropout of {n * 1000.0 / rate:.2f} ms at "
                     f"{s / rate:.3f} s (limit {lim['max_dropout_ms']} ms)")
    if len(drops) > 10:
        fails.append(f"{where}... {len(drops) - 10} more dropouts")

    clip = clipping_fraction(x)
    rep["clipping_fraction"] = clip
    if clip > lim["max_clipping_fraction"]:
        fails.append(f"{where}clipping {clip:.5f} of samples (limit "
                     f"{lim['max_clipping_fraction']})")

    if lim["max_noise_fraction"] < 1.0:
        win = spectral_flatness(x, rate, lim["silence_floor_dbfs"])
        flat = [f for f, _ in win]
        noisy = [1 for f, h in win
                 if f >= lim["noise_flatness"] and h >= lim["noise_hf_share"]]
        rep["noise"] = {
            "windows": len(win), "noise_like": len(noisy),
            "median_flatness": float(np.median(flat)) if flat else None,
            "max_flatness": max(flat) if flat else None,
            "max_hf_share": max(h for _, h in win) if win else None}
        if win and len(noisy) / len(win) > lim["max_noise_fraction"]:
            fails.append(f"{where}noise-like audio: {len(noisy)} of {len(win)}"
                         f" 1 s windows have spectral flatness >= "
                         f"{lim['noise_flatness']} and >= "
                         f"{lim['noise_hf_share']:.0%} of their energy above "
                         f"{NOISE_HF_HZ / 1000:.0f} kHz (max share "
                         f"{lim['max_noise_fraction']}, median flatness "
                         f"{rep['noise']['median_flatness']:.2f})")

    if log:
        t0, t1, n = submit_times(log)
        if t0 is None or t1 is None or t1 <= t0:
            rep["rate_ratio"] = None
            if need_rate:
                fails.append(f"{where}no '[APU] first submit' / '[APU] last "
                             f"submit' pair in {log}")
        else:
            frames = n if n is not None else x.shape[0]
            ratio = frames / (rate * (t1 - t0))
            rep["rate_ratio"] = ratio
            rep["submit_window_s"] = [t0, t1]
            if abs(ratio - 1.0) > lim["rate_tolerance"]:
                fails.append(f"{where}sample-rate ratio {ratio:.5f} over "
                             f"{t0:.3f}-{t1:.3f} s (tolerance "
                             f"{lim['rate_tolerance']})")
    elif need_rate:
        raise Bad("--rate needs --log")

    if log:
        rs = ring_stale(log)
        rep["ring_stale"] = rs
        if rs is not None:
            total = sum(rs.values())
            if (lim["max_ring_stale"] is not None
                    and total > lim["max_ring_stale"]):
                worst = ", ".join(f"voice {v}: {n}" for v, n in
                                  sorted(rs.items(), key=lambda t: -t[1]) if n)
                fails.append(f"{where}stale-lap replays: {total} 1 KB blocks "
                             f"played again unchanged ({worst}; limit "
                             f"{lim['max_ring_stale']})")

    if voice_dumps:
        rep["voice_dumps"] = {}
        for path in voice_dumps:
            r = voice_replays(path)
            r["replay_ms"] = r["replay_frames"] * 1000.0 / dump_rate
            r["sound_ms"] = r["sound_frames"] * 1000.0 / dump_rate
            rep["voice_dumps"][path] = r
            if r["replay_ms"] > lim["max_replay_ms"]:
                fails.append(f"{where}{path}: {r['replay_ms']:.0f} ms replayed "
                             f"exactly (commonest lag {r['lag']} frames; limit "
                             f"{lim['max_replay_ms']} ms)")

    if ref:
        rrate, r = read_wav(ref)
        if rrate != rate:
            raise Bad(f"{ref}: {rrate} Hz, the dump is {rate} Hz")
        lag, corr = envelope_lag(x, r, rate, lim["max_lag_ms"])
        rep["ref"] = {"file": ref, "lag_ms": lag, "envelope_correlation": corr}
        if abs(lag) >= lim["max_lag_ms"]:
            fails.append(f"{where}lag against the reference at the search "
                         f"bound ({lag:.0f} ms, max {lim['max_lag_ms']} ms)")
        if corr < lim["min_envelope_correlation"]:
            fails.append(f"{where}envelope correlation {corr:.3f} with the "
                         f"reference (min {lim['min_envelope_correlation']})")
        a, b = align(x, r, rate, lag)
        bands = band_correlation(a, b, rate, lim["silence_floor_dbfs"])
        rep["ref"]["band_correlation"] = bands
        for i, c in enumerate(bands):
            if c is not None and c < lim["min_band_correlation"]:
                fails.append(f"{where}band {i} correlation {c:.3f} with the "
                             f"reference (min {lim['min_band_correlation']})")
    return rep, fails


def fmt_report(rep):
    out = [f"{rep['file']}: {rep['duration_s']:.3f} s, {rep['rate']} Hz, "
           f"{rep['channels']} ch"]
    fs = rep["first_sound_s"]
    out.append("first sound: " + ("none" if fs is None else f"{fs:.3f} s"))
    if "rms_after_first_dbfs" in rep:
        r = rep["rms_after_first_dbfs"]
        out.append(f"rms/100ms after first sound: min {r['min']:.1f} median "
                   f"{r['median']:.1f} max {r['max']:.1f} dBFS")
    if "host_starves" in rep:
        h = rep["host_starves"]
        out.append(f"host starvation: {h['count']} ({h['total_ms']:.1f} ms), "
                   f"spliced in before the dropout check")
    out.append(f"dropouts: {len(rep['dropouts'])}")
    out.append(f"clipping: {rep['clipping_fraction']:.5f}")
    if "noise" in rep:
        nz = rep["noise"]
        if nz["windows"]:
            out.append(f"noise: {nz['noise_like']} of {nz['windows']} windows "
                       f"noise-like, flatness median {nz['median_flatness']:.2f}"
                       f" max {nz['max_flatness']:.2f}, energy above 8 kHz "
                       f"max {nz['max_hf_share']:.0%}")
        else:
            out.append("noise: no windows above the silence floor")
    if "rate_ratio" in rep:
        out.append("rate ratio: " + ("n/a" if rep["rate_ratio"] is None
                                     else f"{rep['rate_ratio']:.5f}"))
    if "ring_stale" in rep:
        rs = rep["ring_stale"]
        out.append("stale-lap replays: " + (
            "n/a (no [APU-RING] lines)" if rs is None else
            f"{sum(rs.values())} block(s) over {len(rs)} ring voice(s)"))
    for path, r in rep.get("voice_dumps", {}).items():
        out.append(f"voice dump {path}: {r['replay_ms']:.0f} ms replayed of "
                   f"{r['sound_ms']:.0f} ms with sound"
                   + (f" in {r['runs']} burst(s), lag {r['lag']}"
                      if r["lag"] else ""))
    if "ref" in rep:
        f = rep["ref"]
        bands = " ".join("-" if c is None else f"{c:.2f}"
                         for c in f["band_correlation"])
        out.append(f"reference: lag {f['lag_ms']:.0f} ms, envelope correlation "
                   f"{f['envelope_correlation']:.3f}, bands {bands}")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("wav")
    ap.add_argument("--log", help="stdio log with the [APU] submit lines")
    ap.add_argument("--rate", action="store_true",
                    help="fail when the rate cannot be measured")
    ap.add_argument("--golden", help="analysis/golden/audio.json")
    ap.add_argument("--scenario")
    ap.add_argument("--ref", help="reference WAV (xemu capture)")
    ap.add_argument("--json", action="store_true", help="report as JSON")
    ap.add_argument("--voice-dump", action="append", default=[],
                    help="per-voice raw s16 stereo dump to check for replays")
    ap.add_argument("--dump-rate", type=int, default=44100,
                    help="voice dump frames per second, for ms (44100)")
    a = ap.parse_args(argv)
    try:
        limits, window = None, None
        if a.golden or a.scenario:
            if not (a.golden and a.scenario):
                raise Bad("--golden and --scenario go together")
            limits, window = load_golden(a.golden, a.scenario)
        rep, fails = check(a.wav, a.log, a.rate, limits, window, a.ref,
                           a.scenario, a.voice_dump, a.dump_rate)
    except Bad as e:
        print(f"audio_check: {e}", file=sys.stderr)
        return 2
    if a.json:
        rep["fail"] = fails
        print(json.dumps(rep, indent=1))
    else:
        print(fmt_report(rep))
        for f in fails:
            print(f"FAIL {f}")
        print("PASS" if not fails else f"{len(fails)} check(s) failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
