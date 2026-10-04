#!/usr/bin/env python3
"""Drive xemu (flatpak app.xemu.xemu) unattended and capture reference frames.

Runs on the Linux host that has xemu. Use scripts/xemu_capture.sh,
which holds the run lock; this file does the work.

- Config: a private copy under REF_DIR (default ~/xemu-ref). The user's
  xemu.toml, HDD image and EEPROM are only read, never written: the HDD and
  EEPROM are copied once into REF_DIR and xemu runs on the copies.
- Frames: QMP `screendump` (PNG) every --interval seconds into --out; xemu
  0.8.136 lacks it, so the fallback is `spectacle -a`, which shoots the
  *active* window. Don't use the Linux/Proton desktop during a capture, or the
  frames show whatever window has focus.
- xemu instance: the run refuses to start if any app.xemu.xemu instance is
  already running (it could be the user's, and it would also see the virtual
  pad). Cleanup stops only the instance this run started (SIGTERM, then
  `flatpak kill <instance id>`), never the app as a whole.
- Input: a virtual Xbox 360 pad through /dev/uinput (python-evdev), bound to
  port 1 by its SDL GUID in the private config.
- Memory: the QEMU gdb stub (-s, tcp:1234) for the `wait mem` / `poke` steps
  that the @stage1 path needs (the debug stage select, as in src/pad_input.c).

Scenarios mirror the recomp presets: attract (no input, title then the
stg0101 demo), stage1 (debug stage select into stg0101 gameplay) and story
(@story-hub: title START, R0_opening, team editor, SAVE GAME, hub). story runs
on a per-run copy of the private HDD (in --out, removed afterwards), so its
save never reaches the private copy and the next run starts the same way.
"""
import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time

HOME = os.path.expanduser("~")
USER_CFG = os.path.join(HOME, ".var/app/app.xemu.xemu/data/xemu/xemu/xemu.toml")

PAD_NAME = "Microsoft X-Box 360 pad"
PAD_BUS, PAD_VID, PAD_PID, PAD_VER = 0x03, 0x045E, 0x028E, 0x0110


def log(*a):
    print("[xemu-ref %7.2f]" % (time.monotonic() - T0), *a, flush=True)


T0 = time.monotonic()


# ── SDL GUID of the virtual pad (SDL2 >= 2.26 / SDL3 Linux evdev layout) ──
def sdl_crc16(data):
    crc = 0
    for b in data:
        r = (crc ^ b) & 0xFF
        c = 0
        for _ in range(8):
            c = (0xA001 if (c ^ r) & 1 else 0) ^ (c >> 1)
            r >>= 1
        crc = c ^ (crc >> 8)
    return crc


def pad_guid():
    crc = sdl_crc16(PAD_NAME.encode())
    words = [PAD_BUS, crc, PAD_VID, 0, PAD_PID, 0, PAD_VER, 0]
    return "".join("%02x%02x" % (w & 0xFF, w >> 8) for w in words)


# ── private config ──
def toml_get(text, key):
    """A string value from the user's TOML; literal '...' or basic "..." form."""
    m = re.search(r"""^\s*%s\s*=\s*(?:'([^']*)'|"((?:[^"\\]|\\.)*)")""" % re.escape(key), text, re.M)
    if not m:
        return None
    if m.group(1) is not None:
        return m.group(1)
    return json.loads('"%s"' % m.group(2))


def tq(v):
    """A TOML basic string (JSON escaping is valid TOML for these values)."""
    return json.dumps(str(v))


def make_config(ref_dir, iso, scale, run_hdd=None):
    with open(USER_CFG) as f:
        user = f.read()
    files = {}
    for key, name in (("hdd_path", "xbox_hdd.qcow2"), ("eeprom_path", "eeprom.bin")):
        src = toml_get(user, key)
        dst = os.path.join(ref_dir, name)
        if src and not os.path.exists(dst):
            log("copying", key, src, "->", dst)
            shutil.copyfile(src, dst)
        files[key] = dst
    if run_hdd:
        # A throwaway copy of the private HDD for this run only (reflink
        # where the filesystem has it); the private copy stays as it was.
        subprocess.run(["cp", "--reflink=auto", files["hdd_path"], run_hdd], check=True)
        log("run HDD copy", run_hdd)
        files["hdd_path"] = run_hdd
    boot = toml_get(user, "bootrom_path")
    flash = toml_get(user, "flashrom_path")
    if not (boot and flash and os.path.exists(boot) and os.path.exists(flash)):
        sys.exit("xemu-ref: the user's config lacks a readable bootrom/flashrom path")
    vk = toml_get(user, "preferred_physical_device")
    cfg = f"""[general]
show_welcome = false
skip_boot_anim = true

[input.bindings]
port1_driver = 'usb-xbox-gamepad'
port1 = {tq(pad_guid())}

[display]
filtering = 'nearest'

[display.window]
fullscreen_on_startup = false
startup_size = '640x480'

[display.quality]
surface_scale = {scale}

[display.ui]
show_menubar = false
show_notifications = false
aspect_ratio = 'native'
fit = 'center'

[sys]
mem_limit = '64'

[sys.files]
bootrom_path = {tq(boot)}
flashrom_path = {tq(flash)}
eeprom_path = {tq(files["eeprom_path"])}
hdd_path = {tq(files["hdd_path"])}
dvd_path = {tq(iso)}
"""
    if vk:
        cfg = cfg.replace("[display.window]", f"[display.vulkan]\npreferred_physical_device = {tq(vk)}\n\n[display.window]")
    path = os.path.join(ref_dir, "xemu.toml")
    with open(path, "w") as f:
        f.write(cfg)
    return path


# ── flatpak instances ──
APP = "app.xemu.xemu"


def xemu_instances():
    """{instance_id: (wrapper_pid, sandbox_child_pid)} for running app.xemu.xemu,
    or None when `flatpak ps` fails or times out (state unknown)."""
    try:
        p = subprocess.run(["flatpak", "ps", "--columns=instance,application,pid,child-pid"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    out = {}
    for line in p.stdout.splitlines():
        f = line.split()
        if len(f) >= 4 and f[1] == APP:
            out[f[0]] = (int(f[2]), int(f[3]))
    return out


def our_instances(proc):
    """The instances whose flatpak wrapper is in our launch session
    (Popen start_new_session: sid == proc.pid). Ownership by descent, not
    by time, so a user xemu started mid-run is never counted as ours."""
    out = {}
    for inst, (wpid, cpid) in (xemu_instances() or {}).items():
        try:
            if os.getsid(wpid) == proc.pid:
                out[inst] = (wpid, cpid)
        except (ProcessLookupError, PermissionError):
            pass
    return out


def stop_ours(proc, ours):
    """Stop only what this run started: SIGTERM our process group and our
    sandbox's pids, wait, then SIGKILL / `flatpak kill <our instance id>`."""
    pids = [pid for v in ours.values() for pid in v]
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        for pid in pids:
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
        if sig == signal.SIGKILL:
            for inst in ours:
                subprocess.run(["flatpak", "kill", inst], capture_output=True)
        end = time.monotonic() + 10
        while time.monotonic() < end:
            if proc.poll() is not None and not any(i in (xemu_instances() or {}) for i in ours):
                return "sigterm" if sig == signal.SIGTERM else "sigkill"
            time.sleep(0.5)
    return "still running?"


# ── QMP ──
class QMP:
    def __init__(self, path, timeout=60):
        end = time.monotonic() + timeout
        while True:
            try:
                self.s = socket.socket(socket.AF_UNIX)
                self.s.connect(path)
                self.s.settimeout(30)  # a wedged xemu must not block _read forever
                break
            except OSError:
                if time.monotonic() > end:
                    raise
                time.sleep(0.25)
        self.f = self.s.makefile("rwb")
        self._read()
        self.cmd("qmp_capabilities")

    def _read(self):
        while True:
            line = self.f.readline()
            if not line:
                raise EOFError("qmp closed")
            msg = json.loads(line)
            if "event" in msg:
                continue
            return msg

    def cmd(self, name, **args):
        self.f.write(json.dumps({"execute": name, "arguments": args}).encode() + b"\n")
        self.f.flush()
        return self._read()


# ── gdb stub (memory only) ──
class GDB:
    def __init__(self, port=1234, timeout=60):
        end = time.monotonic() + timeout
        while True:
            try:
                self.s = socket.create_connection(("127.0.0.1", port), timeout=10)
                break
            except OSError:
                if time.monotonic() > end:
                    raise
                time.sleep(0.25)
        self.buf = b""
        self.lock = threading.Lock()
        # QEMU stops the VM when the debugger attaches; '?' returns the stop.
        self.packet("?")
        self.send("c", expect=False)

    def _recv_packet(self):
        while True:
            i = self.buf.find(b"$")
            j = self.buf.find(b"#", i + 1) if i >= 0 else -1
            if i >= 0 and j >= 0 and len(self.buf) >= j + 3:
                data = self.buf[i + 1:j]
                self.buf = self.buf[j + 3:]
                self.s.sendall(b"+")
                return data.decode()
            chunk = self.s.recv(65536)
            if not chunk:
                raise EOFError("gdb closed")
            self.buf += chunk

    def send(self, data, expect=True):
        pkt = b"$" + data.encode() + b"#%02x" % (sum(data.encode()) & 0xFF)
        self.s.sendall(pkt)
        return self._recv_packet() if expect else None

    def packet(self, data):
        return self.send(data)

    def _halt(self):
        self.s.sendall(b"\x03")
        self._recv_packet()  # stop reply

    def read32(self, addr):
        """Each read halts the VM (\\x03), reads, then continues it, so a tight
        poll loop slows the guest; poll at >= 0.25 s."""
        with self.lock:
            self._halt()
            r = self.send("m%x,4" % addr)
            self.send("c", expect=False)
        if len(r) != 8:
            return None
        return int.from_bytes(bytes.fromhex(r), "little")

    def write32(self, addr, val):
        with self.lock:
            self._halt()
            r = self.send("M%x,4:%s" % (addr, (val & 0xFFFFFFFF).to_bytes(4, "little").hex()))
            self.send("c", expect=False)
        return r == "OK"


# ── virtual pad ──
class Pad:
    def __init__(self):
        from evdev import UInput, ecodes as e, AbsInfo
        self.e = e
        stick = AbsInfo(0, -32768, 32767, 16, 128, 0)
        trig = AbsInfo(0, 0, 255, 0, 0, 0)
        hat = AbsInfo(0, -1, 1, 0, 0, 0)
        caps = {
            e.EV_KEY: [e.BTN_A, e.BTN_B, e.BTN_X, e.BTN_Y, e.BTN_TL, e.BTN_TR,
                       e.BTN_SELECT, e.BTN_START, e.BTN_MODE, e.BTN_THUMBL, e.BTN_THUMBR],
            e.EV_ABS: [(e.ABS_X, stick), (e.ABS_Y, stick), (e.ABS_RX, stick), (e.ABS_RY, stick),
                       (e.ABS_Z, trig), (e.ABS_RZ, trig), (e.ABS_HAT0X, hat), (e.ABS_HAT0Y, hat)],
        }
        self.ui = UInput(caps, name=PAD_NAME, vendor=PAD_VID, product=PAD_PID,
                         version=PAD_VER, bustype=PAD_BUS)
        self.keys = {"A": e.BTN_A, "B": e.BTN_B, "X": e.BTN_X, "Y": e.BTN_Y,
                     "START": e.BTN_START, "BACK": e.BTN_SELECT,
                     "LB": e.BTN_TL, "RB": e.BTN_TR}
        log("uinput pad", self.ui.device.path if self.ui.device else "?", "guid", pad_guid())

    def tap(self, name, hold=0.12):
        k = self.keys[name]
        self.ui.write(self.e.EV_KEY, k, 1)
        self.ui.syn()
        time.sleep(hold)
        self.ui.write(self.e.EV_KEY, k, 0)
        self.ui.syn()

    def close(self):
        self.ui.close()


# ── capture thread ──
class Capturer(threading.Thread):
    def __init__(self, qmp, out, interval):
        super().__init__(daemon=True)
        self.qmp, self.out, self.interval = qmp, out, interval
        self.stop = threading.Event()
        self.n = 0
        self.tags = []
        self.qmp_shot = True
        self.lock = threading.Lock()

    def shot(self, tag=""):
        """xemu 0.8.136 builds QMP without `screendump`, so the frame comes
        from KDE's spectacle (active window, no GUI, ~0.5 s per shot). The
        640x480 guest image sits centred in the window (fit = center,
        surface_scale 1); scripts/xemu_crop.py crops it. -a is the *active*
        window: if someone focuses another window, that is what is shot."""
        name = "f%05d%s.png" % (self.n, ("-" + tag) if tag else "")
        path = os.path.join(self.out, name)
        t = time.monotonic() - T0
        err = None
        if self.qmp_shot:
            r = self.qmp.cmd("screendump", filename=path, format="png")
            err = r.get("error")
            if err and err.get("class") == "CommandNotFound":
                self.qmp_shot = False
        if not self.qmp_shot:
            p = subprocess.run(["spectacle", "-b", "-n", "-a", "-o", path],
                               capture_output=True, timeout=20)
            err = None if p.returncode == 0 and os.path.exists(path) else (p.stderr.decode()[-200:] or "rc %d" % p.returncode)
        self.tags.append({"n": self.n, "t": round(t, 3), "file": name, "tag": tag, "err": err})
        self.n += 1
        return {"error": err} if err else {}

    def run(self):
        while not self.stop.is_set():
            with self.lock:
                r = self.shot()
            if "error" in r and self.n < 3:
                log("screendump error:", r["error"])
            self.stop.wait(self.interval)


def wait_mem(gdb, addr, val, timeout, pad=None, tap=None, every=0.0):
    end = time.monotonic() + timeout
    last = 0.0
    while time.monotonic() < end:
        v = gdb.read32(addr)
        if v == val:
            log("mem %#x == %#x" % (addr, val))
            return True
        if pad and tap and time.monotonic() - last >= every:
            pad.tap(tap)
            last = time.monotonic()
        time.sleep(0.2)
    log("TIMEOUT mem %#x == %#x (last %s)" % (addr, val, v))
    return False


def wait_until(gdb, what, pred, timeout, pad=None, tap=None, every=0.0):
    """Like wait_mem, for a predicate over gdb reads (the story route)."""
    end = time.monotonic() + timeout
    last = 0.0
    while time.monotonic() < end:
        v = pred()
        if v:
            log("ok:", what, v)
            return v
        if pad and tap and time.monotonic() - last >= every:
            pad.tap(tap)
            last = time.monotonic()
        time.sleep(0.2)
    log("TIMEOUT", what)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=["attract", "stage1", "story", "idle"], default="attract")
    ap.add_argument("--seconds", type=float, default=90)
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref-dir", default=os.path.join(HOME, "xemu-ref"))
    ap.add_argument("--iso", default=os.environ.get("XEMU_ISO"),
                    help="your own dump of the game disc (default: $XEMU_ISO; required)")
    ap.add_argument("--scale", type=int, default=1, help="xemu surface_scale (1 = native 640x480)")
    ap.add_argument("--no-pad", action="store_true")
    ap.add_argument("--no-gdb", action="store_true")
    a = ap.parse_args()
    if not a.iso:
        sys.exit("xemu-ref: no disc image: pass --iso PATH or set XEMU_ISO")
    if not os.path.isfile(a.iso):
        sys.exit("xemu-ref: disc image not found: %s" % a.iso)
    # systemctl stop / kill: run the finally block (flatpak kill, frames.json)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    running = xemu_instances()
    if running is None:
        sys.exit("xemu-ref: refusing to start: `flatpak ps` failed, so it is unknown "
                 "whether an app.xemu.xemu instance (maybe the user's) is running.")
    if running:
        sys.exit("xemu-ref: refusing to start: app.xemu.xemu is already running "
                 "(instances %s); it may be the user's. Close it first." % ", ".join(running))
    os.makedirs(a.ref_dir, exist_ok=True)
    os.makedirs(a.out, exist_ok=True)
    run_hdd = os.path.join(a.out, "story-hdd.qcow2") if a.scenario == "story" else None
    cfg = make_config(a.ref_dir, a.iso, a.scale, run_hdd)
    qsock = os.path.join(a.ref_dir, "qmp.sock")
    if os.path.exists(qsock):
        os.unlink(qsock)

    pad = None
    if not a.no_pad:
        pad = Pad()
        time.sleep(1.0)

    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())
    env.setdefault("WAYLAND_DISPLAY", "wayland-0")
    env.setdefault("DISPLAY", ":0")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", "unix:path=%s/bus" % env["XDG_RUNTIME_DIR"])
    cmd = ["flatpak", "run", "app.xemu.xemu", "-config_path", cfg, "-dvd_path", a.iso,
           "-qmp", "unix:%s,server=on,wait=off" % qsock]
    if not a.no_gdb:
        cmd += ["-s"]
    logf = open(os.path.join(a.out, "xemu.log"), "w")
    log("launch:", " ".join(cmd))
    proc = subprocess.Popen(cmd, env=env, stdout=logf, stderr=subprocess.STDOUT,
                            start_new_session=True)
    cap = None
    rc = 0
    ours = {}
    try:
        # our instance = one whose wrapper is in our launch session
        t_end = time.monotonic() + 30
        while not ours and time.monotonic() < t_end and proc.poll() is None:
            ours = our_instances(proc)
            time.sleep(0.25)
        log("our flatpak instance:", ours or "none found")
        qmp = QMP(qsock)
        log("qmp up:", qmp.cmd("query-version").get("return", {}).get("qemu"))
        gdb = None if a.no_gdb else GDB()
        cap = Capturer(qmp, a.out, a.interval)
        cap.start()
        end = T0 + a.seconds
        if a.scenario == "stage1":
            # SKIP_INTRO: START skips the logos/opening; stop once the title
            # state block is up (the title ignores START for ~10 s anyway).
            # In xemu the state block at 0x5EB620 is up from the first logo
            # (~12 s) and runs through other values (-1, 3, 0) during the
            # intro movies; the title proper fades in with state 5, then
            # "press start" is state 0 (attract run 2026-10-02: 5 at +57 s,
            # 0 at +58 s, 9/10 = demo at +72 s with no input).
            wait_mem(gdb, 0x5EB5F4, 0x5EB620, 120)
            wait_mem(gdb, 0x5EB620, 5, 150, pad, "START", 2.0)
            wait_mem(gdb, 0x5EB620, 0, 30)
            time.sleep(1)
            for addr, val in ((0xB22E3C, 1), (0xAE7A10, 0), (0x5EB630, 0), (0x5EB638, 0), (0x5EB620, 1)):
                log("poke %#x = %#x ->" % (addr, val), gdb.write32(addr, val))
            time.sleep(4)
            wait_mem(gdb, 0x5EB620, 0xB, 30, pad, "A", 0.5)
            time.sleep(4)
            wait_mem(gdb, 0x5EB620, 0x13, 30, pad, "A", 0.5)
            with cap.lock:
                cap.shot("leaving-title")
            # tap A every 3 s until the first checkpoint flag (play starts)
            wait_mem(gdb, 0xAE73FC, 1, 120, pad, "A", 3.0)
            with cap.lock:
                cap.shot("play")
        elif a.scenario == "story":
            # As @story-hub (src/pad_input.c; design.md "Menu catalogue"),
            # on the title state 0x5EB620 and the next scene 0xAE7424 read
            # over gdb instead of file opens. With no save: START -> 0x14 with
            # next scene 0x1B (R0_opening), A skips it -> 0x16 (tsedit), A
            # through the editor until the title is back in 0xD (Story Mode /
            # SAVE GAME), A (slot 1, 1P) until 0x13 (next scene 0xA, hub).
            # With a save on the HDD, START leads straight to 0xD (LOAD GAME).
            st = lambda: gdb.read32(0x5EB620)
            wait_mem(gdb, 0x5EB5F4, 0x5EB620, 120)
            wait_mem(gdb, 0x5EB620, 5, 150, pad, "START", 2.0)
            wait_mem(gdb, 0x5EB620, 0, 30)
            time.sleep(1)
            v = wait_until(gdb, "title left press-start", lambda: (st() in (0x14, 0xD)) and st(),
                           60, pad, "START", 1.0)
            if v == 0x14:
                log("story: new game (no save on the HDD)")
                wait_until(gdb, "R0_opening (next scene 0x1B)",
                           lambda: gdb.read32(0xAE7424) == 0x1B, 30)
                time.sleep(2)
                wait_until(gdb, "tsedit (next scene 0x16)",
                           lambda: gdb.read32(0xAE7424) == 0x16, 60, pad, "A", 1.0)
                with cap.lock:
                    cap.shot("story-tsedit-in")
                n = 0
                t_tag = time.monotonic()
                def editor_done():
                    nonlocal n, t_tag
                    if time.monotonic() - t_tag >= 5:
                        with cap.lock:
                            cap.shot("story-tsedit-%02d" % n)
                        n += 1
                        t_tag = time.monotonic()
                    return st() == 0xD
                wait_until(gdb, "Story Mode (state 0xD)", editor_done, 400, pad, "A", 1.5)
            else:
                log("story: LOAD GAME (a save is on the HDD)")
            time.sleep(2)
            with cap.lock:
                cap.shot("story-menu")
            wait_until(gdb, "leaving for the hub (state 0x13)",
                       lambda: st() in (0x13, 0x14), 120, pad, "A", 1.5)
            log("story: next scene %#x stage %#x" % (gdb.read32(0xAE7424), gdb.read32(0xB871AC)))
            time.sleep(10)
            with cap.lock:
                cap.shot("story-hub")
        elif a.scenario == "attract" and gdb:
            # As @attract: START skips the logos and the opening movie; stop
            # tapping once the title state block is up, then leave the title
            # alone until its timer starts the stg0101 demo.
            wait_mem(gdb, 0x5EB5F4, 0x5EB620, 150, pad, "START", 2.0)
            with cap.lock:
                cap.shot("title-up")
            title_t = time.monotonic()
            prev = None
            while time.monotonic() < end:
                v = gdb.read32(0x5EB620)
                if v != prev:
                    log("title state", v, "at title+%.1fs" % (time.monotonic() - title_t))
                    prev = v
                time.sleep(0.5)
        while time.monotonic() < end and proc.poll() is None:
            time.sleep(0.5)
    except Exception as ex:
        log("ERROR", repr(ex))
        rc = 1
    finally:
        if cap:
            cap.stop.set()
            cap.join(5)
            with open(os.path.join(a.out, "frames.json"), "w") as f:
                json.dump(cap.tags, f, indent=1)
            log("frames:", cap.n)
        # Stop only our instance (by session). If none can be shown to be
        # ours, stop_ours signals only our own process group.
        if not ours:
            ours = our_instances(proc)
        log("stop:", stop_ours(proc, ours))
        if pad:
            pad.close()
        if run_hdd and os.path.exists(run_hdd):
            os.unlink(run_hdd)  # this run's own copy, inside --out
            log("removed", run_hdd)
    return rc


if __name__ == "__main__":
    sys.exit(main())
