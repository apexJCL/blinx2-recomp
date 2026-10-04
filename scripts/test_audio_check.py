#!/usr/bin/env python3
"""Tests for audio_check.py on synthetic WAVs. Plain asserts; runs alone or
under pytest (the `d` fixture is pytest's tmp_path).

  xboxrecomp/.venv/bin/python3 scripts/test_audio_check.py
  xboxrecomp/.venv/bin/python3 -m pytest scripts/test_audio_check.py

Exit 0 when every test passes.
"""

import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audio_check as ac  # noqa: E402

RATE = 48000
GOLDEN = os.path.join(HERE, "..", "analysis", "golden", "audio.json")

try:
    import pytest
except ImportError:
    pytest = None
if pytest is not None:
    @pytest.fixture
    def d(tmp_path):
        return str(tmp_path)


def tone(secs, hz=440.0, amp=0.5, ch=2):
    t = np.arange(int(secs * RATE)) / RATE
    return np.repeat((amp * np.sin(2 * np.pi * hz * t))[:, None], ch, axis=1)


def noise(secs, seed, amp=0.3, ch=2):
    rng = np.random.default_rng(seed)
    return amp * rng.uniform(-1, 1, (int(secs * RATE), ch))


def burst_signal(secs, start, length, seed, amp=0.5):
    """Low-level noise floor with a loud noise burst; the same seed gives the
    same samples."""
    x = noise(secs, seed + 1000, amp=0.003)
    b = noise(length, seed, amp=amp)
    s = int(start * RATE)
    x[s:s + len(b)] += b
    return x


def run_cli(args):
    p = subprocess.run([sys.executable, os.path.join(HERE, "audio_check.py")]
                       + args, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def test_silence_fails(d):
    p = os.path.join(d, "silence.wav")
    ac.write_wav(p, RATE, np.zeros((RATE * 2, 2)))
    rep, fails = ac.check(p)
    assert rep["first_sound_s"] is None, rep
    assert any("no sound" in f for f in fails), fails
    rc, out = run_cli([p])
    assert rc == 1, (rc, out)


def test_tone_passes(d):
    p = os.path.join(d, "tone.wav")
    x = np.concatenate([np.zeros((RATE // 2, 2)), tone(2.0)])
    ac.write_wav(p, RATE, x)
    rep, fails = ac.check(p)
    assert not fails, fails
    assert abs(rep["first_sound_s"] - 0.5) < 0.002, rep["first_sound_s"]
    assert rep["dropouts"] == [], rep["dropouts"]
    assert rep["clipping_fraction"] == 0.0
    r = rep["rms_after_first_dbfs"]
    assert abs(r["median"] - 20 * np.log10(0.5 / np.sqrt(2))) < 0.2, r
    rc, out = run_cli([p])
    assert rc == 0, (rc, out)


def test_tone_gap_fails(d):
    p = os.path.join(d, "gap.wav")
    x = tone(2.0)
    s = RATE                       # a 5 ms hole at 1 s
    x[s:s + RATE * 5 // 1000] = 0.0
    ac.write_wav(p, RATE, x)
    rep, fails = ac.check(p)
    assert len(rep["dropouts"]) == 1, rep["dropouts"]
    dd = rep["dropouts"][0]
    assert abs(dd["ms"] - 5.0) < 0.1 and abs(dd["at_s"] - 1.0) < 0.001, dd
    assert any("dropout" in f for f in fails), fails
    # Trailing silence is not a dropout; a 1 ms hole is under the limit.
    y = np.concatenate([tone(1.0), np.zeros((RATE, 2))])
    y[RATE // 2:RATE // 2 + RATE // 1000] = 0.0
    ac.write_wav(p, RATE, y)
    rep, fails = ac.check(p)
    assert not fails, fails
    # Zeros inside near-silence are not dropouts either: a blank movie track
    # at -70 dBFS that touches zero for 10 ms, between two tones.
    quiet = noise(2.0, seed=9, amp=0.0003)
    quiet[RATE:RATE + RATE // 100] = 0.0
    z = np.concatenate([tone(0.5), quiet, tone(0.5)])
    ac.write_wav(p, RATE, z)
    rep, fails = ac.check(p)
    assert rep["dropouts"] == [], rep["dropouts"]
    assert not fails, fails


def test_clipping_fails(d):
    p = os.path.join(d, "clip.wav")
    ac.write_wav(p, RATE, np.clip(tone(1.0, amp=2.0), -1, 1))
    _, fails = ac.check(p)
    assert any("clipping" in f for f in fails), fails


def test_burst_lag(d):
    ref = os.path.join(d, "ref.wav")
    tst = os.path.join(d, "test.wav")
    ac.write_wav(ref, RATE, burst_signal(3.0, 0.8, 0.6, seed=7))
    ac.write_wav(tst, RATE, burst_signal(3.0, 0.92, 0.6, seed=7))
    rep, fails = ac.check(tst, ref=ref)
    f = rep["ref"]
    assert abs(f["lag_ms"] - 120) <= 2, f
    assert f["envelope_correlation"] > 0.95, f
    assert not fails, fails
    # Reversed roles: the lag changes sign.
    rep, _ = ac.check(ref, ref=tst)
    assert abs(rep["ref"]["lag_ms"] + 120) <= 2, rep["ref"]


def test_uncorrelated_fails(d):
    a = os.path.join(d, "na.wav")
    b = os.path.join(d, "nb.wav")
    # Noise with a random envelope (independent per 10 ms block), so neither
    # the envelope nor the band energies line up.
    def shaped(seed):
        rng = np.random.default_rng(seed)
        env = np.repeat(rng.uniform(0.05, 1.0, 300), RATE // 100)
        return noise(3.0, seed + 50) * env[:, None]
    ac.write_wav(a, RATE, shaped(1))
    ac.write_wav(b, RATE, shaped(2))
    rep, fails = ac.check(a, ref=b)
    assert rep["ref"]["envelope_correlation"] < 0.5, rep["ref"]
    assert fails, rep["ref"]
    rc, _ = run_cli([a, "--ref", b])
    assert rc == 1


def test_noise_fails(d):
    # Off by default (the burst tests above are noise by construction); on
    # with the golden limits, white noise fails and a tone over the same
    # length passes. A 44.1 kHz-style resampled tone is still a tone.
    lim = {"max_noise_fraction": 0.1}
    p = os.path.join(d, "white.wav")
    ac.write_wav(p, RATE, noise(5.0, seed=3, amp=0.2))
    rep, fails = ac.check(p, limits=lim)
    assert rep["noise"]["windows"] == 5, rep["noise"]
    assert rep["noise"]["median_flatness"] > 0.45, rep["noise"]
    assert any("noise-like" in f for f in fails), fails
    q = os.path.join(d, "music.wav")
    x = tone(5.0, 220.0, amp=0.3) + tone(5.0, 3300.0, amp=0.1)
    ac.write_wav(q, RATE, x)
    rep, fails = ac.check(q, limits=lim)
    assert rep["noise"]["max_flatness"] < 0.1, rep["noise"]
    assert not fails, fails
    # The mix the APU made while it read .text as PCM: music under a noise
    # floor well above it. Fails; the music alone passes.
    r = os.path.join(d, "mixed.wav")
    ac.write_wav(r, RATE, x * 0.1 + noise(5.0, seed=4, amp=0.3))
    _, fails = ac.check(r, limits=lim)
    assert any("noise-like" in f for f in fails), fails
    rc, out = run_cli([p, "--golden", GOLDEN, "--scenario", "boot-title"])
    assert rc == 1 and "noise-like" in out, out
    rc, out = run_cli([p])
    assert rc == 0, (rc, out)       # no golden: the check is off
    # The limits keep a margin on both sides of what was measured: clean
    # runs peak at flatness 0.315 and 16 % above 8 kHz, the .text-as-PCM
    # windows started at 0.40 and 57 %.
    assert 0.315 < ac.DEFAULTS["noise_flatness"] < 0.40, ac.DEFAULTS
    assert 0.16 < ac.DEFAULTS["noise_hf_share"] < 0.57, ac.DEFAULTS
    g = json.load(open(GOLDEN))["compare"]
    assert g["noise_flatness"] == ac.DEFAULTS["noise_flatness"], g
    assert g["noise_hf_share"] == ac.DEFAULTS["noise_hf_share"], g
    # A scenario's own keys override compare's: one with sustained broadband
    # effects can raise the limits for itself and the others keep them.
    gj = os.path.join(d, "golden.json")
    json.dump({"compare": {"max_noise_fraction": 0.1},
               "scenarios": {"windy": {"noise_flatness": 0.9,
                                       "noise_hf_share": 0.99},
                             "calm": {}}}, open(gj, "w"))
    rc, out = run_cli([p, "--golden", gj, "--scenario", "windy"])
    assert rc == 0, (rc, out)
    rc, out = run_cli([p, "--golden", gj, "--scenario", "calm"])
    assert rc == 1 and "noise-like" in out, out


def test_rate_from_log(d):
    p = os.path.join(d, "rate.wav")
    ac.write_wav(p, RATE, tone(2.0))
    log = os.path.join(d, "run.log")
    with open(log, "w") as f:
        f.write("noise\n[APU] first submit t=10.000000\nmore\n"
                "[APU] last submit t=12.000000\n")
    rep, fails = ac.check(p, log=log, need_rate=True)
    assert abs(rep["rate_ratio"] - 1.0) < 1e-9 and not fails, (rep, fails)
    with open(log, "w") as f:   # 1 % slow: frames from samples=
        f.write("[APU] first submit t=0.5\n"
                "[APU] last submit t=2.5 samples=95040\n")
    rep, fails = ac.check(p, log=log, need_rate=True)
    assert abs(rep["rate_ratio"] - 0.99) < 1e-9, rep
    assert any("sample-rate ratio" in f for f in fails), fails
    with open(log, "w") as f:
        f.write("nothing here\n")
    _, fails = ac.check(p, log=log, need_rate=True)
    assert any("first submit" in f for f in fails), fails
    rc, _ = run_cli([p, "--rate"])
    assert rc == 2


def test_golden(d):
    g = json.load(open(GOLDEN))
    names = sorted(g["scenarios"])
    assert names == ["boot-title", "stage1", "title-menu"], names
    p = os.path.join(d, "late.wav")
    ac.write_wav(p, RATE, np.concatenate([np.zeros((RATE * 12, 2)),
                                          tone(1.0)]))
    for n in names:
        rc, out = run_cli([p, "--golden", GOLDEN, "--scenario", n])
        assert rc in (0, 1), (n, rc, out)
    rc, out = run_cli([p, "--golden", GOLDEN, "--scenario", "boot-title"])
    assert rc == 1 and "scenario boot-title" in out and "window" in out, out
    rc, out = run_cli([p, "--golden", GOLDEN, "--scenario", "nope"])
    assert rc == 2 and "boot-title" in out, out
    silent = os.path.join(d, "silent.wav")
    ac.write_wav(silent, RATE, np.zeros((RATE, 2)))
    rc, out = run_cli([silent, "--golden", GOLDEN, "--scenario", "boot-title"])
    assert rc == 1 and "scenario boot-title: no sound" in out, out


def test_unfinalised_header(d):
    p = os.path.join(d, "open.wav")
    ac.write_wav(p, RATE, tone(0.5))
    raw = bytearray(open(p, "rb").read())
    raw[40:44] = b"\0\0\0\0"        # data size never written
    open(p, "wb").write(raw)
    rate, x = ac.read_wav(p)
    assert rate == RATE and x.shape == (RATE // 2, 2), x.shape


def test_stale_header(d):
    # A hard exit after the last once-a-second refresh: the header declares
    # 1 s, the file holds 1.5 s. Everything up to the end is read.
    p = os.path.join(d, "stale.wav")
    ac.write_wav(p, RATE, tone(1.5))
    raw = bytearray(open(p, "rb").read())
    declared = RATE * 4
    raw[40:44] = declared.to_bytes(4, "little")
    raw[4:8] = (36 + declared).to_bytes(4, "little")
    open(p, "wb").write(raw)
    rate, x = ac.read_wav(p)
    assert rate == RATE and x.shape == (RATE * 3 // 2, 2), x.shape
    # A well-formed chunk after the data is not audio.
    q = os.path.join(d, "list.wav")
    ac.write_wav(q, RATE, tone(1.0))
    open(q, "ab").write(b"LIST" + (4).to_bytes(4, "little") + b"INFO")
    rate, x = ac.read_wav(q)
    assert x.shape == (RATE, 2), x.shape


def test_host_starve_from_log(d):
    """A continuous WAV passes alone; the same WAV with a host starvation
    logged inside the sound fails as a dropout at the spliced position."""
    p = os.path.join(d, "starve.wav")
    ac.write_wav(p, RATE, tone(2.0))
    rep, fails = ac.check(p)
    assert not fails, fails
    log = os.path.join(d, "starve.log")
    with open(log, "w") as f:
        f.write("[AUDIO-HOST] wav=0 starves=0 starved_ms=0.0\n")
        f.write(f"[AUDIO-HOST] starve wav={RATE} ms=30.0 queued=0 gap_ms=40.0"
                " trapped=1\n")
    rep, fails = ac.check(p, log=log)
    assert rep["host_starves"] == {"count": 1, "total_ms": 30.0}, rep
    assert len(rep["dropouts"]) == 1, rep["dropouts"]
    assert abs(rep["dropouts"][0]["at_s"] - 1.0) < 0.001, rep["dropouts"]
    assert abs(rep["dropouts"][0]["ms"] - 30.0) < 0.1, rep["dropouts"]
    assert any("dropout" in f for f in fails), fails


def test_ring_stale_from_log(d):
    """[APU-RING] stale_total is per voice and cumulative: the max per voice,
    summed over voices, fails past max_ring_stale (0); golden leaves it
    ungated; a log without the lines reports n/a."""
    p = os.path.join(d, "ring.wav")
    ac.write_wav(p, RATE, tone(2.0))
    log = os.path.join(d, "ring.log")
    with open(log, "w") as f:
        f.write("[APU-RING] t=4s v=68 bytes=65536 entries=91 stale=6 "
                "stale_total=6 lead_min=0 lead_avg=292\n"
                "[APU-RING] stale v=68 blk=0/64 lap=2 ms=1\n"
                "[APU-RING] t=5s v=68 bytes=65536 entries=51 stale=10 "
                "stale_total=16 lead_min=0 lead_avg=376\n"
                "[APU-RING] t=5s v=70 bytes=65536 entries=172 stale=0 "
                "stale_total=0 lead_min=13568 lead_avg=15182\n")
    assert ac.ring_stale(log) == {68: 16, 70: 0}, ac.ring_stale(log)
    rep, fails = ac.check(p, log=log)
    assert rep["ring_stale"] == {68: 16, 70: 0}, rep
    assert any("stale-lap replays: 16" in f and "voice 68: 16" in f
               for f in fails), fails
    assert "stale-lap replays: 16 block(s) over 2" in ac.fmt_report(rep), rep
    limits, _ = ac.load_golden(GOLDEN, "boot-title")
    assert limits["max_ring_stale"] is None, limits
    _, fails = ac.check(p, log=log, limits=limits)
    assert not any("stale-lap" in f for f in fails), fails
    clean = os.path.join(d, "clean.log")
    with open(clean, "w") as f:
        f.write("[APU-RING] t=5s v=71 bytes=65536 entries=172 stale=0 "
                "stale_total=0 lead_min=15104 lead_avg=15834\n")
    _, fails = ac.check(p, log=clean)
    assert not fails, fails
    with open(clean, "w") as f:
        f.write("no ring lines\n")
    assert ac.ring_stale(clean) is None
    rep, fails = ac.check(p, log=clean)
    assert rep["ring_stale"] is None and not fails, (rep, fails)
    assert "n/a" in ac.fmt_report(rep)


def write_raw(path, x):
    np.asarray(np.round(x * 32767), dtype="<i2").tofile(path)


def test_voice_replays(d):
    """A ring the writer fell behind on repeats short stretches one lap back
    (counted); a slot playing a whole sound twice repeats all of it (not
    counted); digital silence is skipped."""
    rate = 44100
    lap = 16384                                 # 64 KB ring of s16 stereo
    src = noise(5.0, seed=7)[: 5 * rate]
    x = src.copy()
    # Two stale bursts: 2048 frames replaying the audio one lap earlier.
    for at in (3 * lap, 6 * lap):
        x[at:at + 2048] = x[at - lap:at - lap + 2048]
    x[rate * 4: rate * 4 + 8000] = 0            # silence: never a key
    p = os.path.join(d, "v71.raw")
    write_raw(p, x)
    r = ac.voice_replays(p)
    assert r["frames"] == x.shape[0], r
    assert r["lag"] == lap and r["runs"] == 2, r
    assert 2 * 2048 - 2 * ac.REPLAY_CHUNK <= r["replay_frames"] <= 2 * 2048, r
    assert r["sound_frames"] < x.shape[0], r
    w = os.path.join(d, "vr.wav")
    ac.write_wav(w, RATE, tone(1.0))
    rep, fails = ac.check(w, voice_dumps=[p], dump_rate=rate)
    vd = rep["voice_dumps"][p]
    assert abs(vd["replay_ms"] - r["replay_frames"] * 1000.0 / rate) < 1e-9
    assert abs(vd["sound_ms"] - r["sound_frames"] * 1000.0 / rate) < 1e-9
    assert any("replayed exactly" in f for f in fails), fails
    assert f"{vd['sound_ms']:.0f} ms with sound" in ac.fmt_report(rep)
    # Half rate: the report's ms follow --dump-rate, not a fixed 44100.
    rep2, _ = ac.check(w, voice_dumps=[p],
                       dump_rate=rate // 2)
    vd2 = rep2["voice_dumps"][p]
    assert abs(vd2["sound_ms"] - 2 * vd["sound_ms"]) < 1e-6, (vd, vd2)
    assert f"{vd2['sound_ms']:.0f} ms with sound" in ac.fmt_report(rep2)

    # One-shot sound played twice in the same slot: a run as long as the lag.
    shot = noise(0.5, seed=9)
    gap = np.zeros((int(0.1 * rate), 2))
    y = np.concatenate([shot, gap, shot])
    q = os.path.join(d, "shot.raw")
    write_raw(q, y)
    r = ac.voice_replays(q)
    assert r["replay_frames"] == 0 and r["runs"] == 0 and r["lag"] is None, r

    z = os.path.join(d, "zero.raw")
    write_raw(z, np.zeros((rate, 2)))
    r = ac.voice_replays(z)
    assert r["sound_frames"] == 0 and r["replay_frames"] == 0, r



def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    with tempfile.TemporaryDirectory() as d:
        for t in tests:
            t(d)
            print(f"ok {t.__name__}")
    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    main()
