"""Exercise the installed demo on one disposable Android emulator and capture evidence."""

import argparse
import contextlib
import json
import re
import struct
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "vn.tdtu.securechat"
PORT = "tcp:8443"
MARKER = "TDTU-LAB-NOTE-130"


class Demo:
    def __init__(self, serial, output):
        self.serial = serial
        self.output = output
        self.results = []
        self.policy = ""

    def adb(self, *args, check=True, binary=False):
        proc = subprocess.run(
            ["adb", "-s", self.serial, *args],
            cwd=ROOT,
            timeout=100,
            capture_output=True,
            text=not binary,
            check=False,
        )
        if check and proc.returncode:
            raise RuntimeError(f"adb {args}: {proc.stderr or proc.stdout}")
        return proc.stdout if binary else proc.stdout + proc.stderr

    def shell(self, *args, check=True):
        return self.adb("shell", *args, check=check)

    def nodes(self):
        self.shell("uiautomator", "dump", "/sdcard/secure-chat-test.xml")
        return ET.fromstring(self.shell("cat", "/sdcard/secure-chat-test.xml")).iter(
            "node"
        )

    def find(self, value, field="text", exact=False):
        for _ in range(4):
            for node in self.nodes():
                label = node.get(field, "")
                if label == value if exact else value in label:
                    return node
        raise AssertionError(f"Missing UI {field}: {value!r}")

    def click(self, name, field="text", exact=True):
        node = self.find(name, field=field, exact=exact)
        assert node.get("enabled") == "true", f"{name} is disabled"
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.attrib["bounds"]))
        self.shell("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))

    def capture(self, filename, landscape=None):
        content = self.adb("exec-out", "screencap", "-p", binary=True)
        assert content.startswith(b"\x89PNG\r\n\x1a\n")
        if landscape is not None:
            width, height = struct.unpack(">II", content[16:24])
            assert (width > height) == landscape, (width, height)
        (self.output / f"{filename}.png").write_bytes(content)

    def launch(self, policy):
        self.policy = policy
        app = f"{PACKAGE}.{policy}"
        self.shell("am", "force-stop", app)
        output = self.shell("am", "start", "-W", "-n", f"{app}/{PACKAGE}.ChatActivity")
        assert "Status: ok" in output, output

    def record(self, case, observed):
        self.results.append({"case": case, "observed": observed, "status": "PASS"})
        print(f"PASS {case}: {observed}", flush=True)

    @contextlib.contextmanager
    def server(self, fixture, label=None):
        with tempfile.NamedTemporaryFile(mode="w+b") as log:
            proc = subprocess.Popen(
                [sys.executable, "-m", "backend.server", fixture],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
            )

            def log_text():
                with open(log.name, "rb") as reader:
                    return reader.read().decode()

            try:
                for _ in range(150):
                    if "READY" in log_text() or proc.poll() is not None:
                        break
                    time.sleep(0.1)
                assert "READY" in log_text(), log_text()
                yield log_text
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
                (self.output / f"{self.policy}-{label or fixture}.log").write_text(
                    log_text()
                )

    def refresh(self, expected):
        self.click("Refresh")
        self.find(expected)

    def send(self, marker):
        self.click("Message text", field="content-desc")
        self.shell("input", "text", marker)
        self.shell("input", "keyevent", "4")
        self.click("Send message")

    def flow(self):
        self.launch("baseline")
        for fixture in ("a", "b"):
            with self.server(fixture) as log:
                self.refresh("TLS accepted")
                assert "HTTP GET 200" in log()
                self.capture(f"baseline-{fixture}")
                self.record(
                    f"Baseline + {fixture.upper()}", "TLS accepted and GET returned 200"
                )

        self.launch("pinned")
        self.click("Send message")
        self.find("Enter a message before sending.")
        self.record("Empty message", "Rejected in the Android UI")
        with self.server("a") as log:
            self.refresh("TLS accepted")
            assert "HTTP GET 200" in log()
            self.capture("pinned-a")
            self.record("Pinned + A", "TLS accepted and GET returned 200")

        with self.server("b") as log:
            self.adb("logcat", "-c")
            self.send("TDTU-TLS-DENIAL")
            self.find("TLS refused · Server identity")
            self.find("TDTU-TLS-DENIAL", exact=True)
            assert "HTTP " not in log(), log()
            trace = self.adb("logcat", "-d", "-s", "SecureChat:I", "*:S")
            assert "Pin verification failed" in trace, trace
            (self.output / "pinned-b-logcat.txt").write_text(trace)
            self.capture("pinned-b")
            self.record(
                "Pinned + B",
                "Pin verification failed. No HTTP request reached Handler.",
            )

        with self.server("backup") as log:
            self.refresh("TLS accepted")
            assert "HTTP GET 200" in log()
            self.record("Pinned + backup key", "TLS accepted and GET returned 200")

        with self.server("untrusted") as log:
            self.adb("logcat", "-c")
            self.refresh("TLS refused · Server identity")
            assert "HTTP " not in log(), log()
            trace = self.adb("logcat", "-d", "-s", "SecureChat:I", "*:S")
            assert "Trust anchor" in trace, trace
            (self.output / "pinned-untrusted-logcat.txt").write_text(trace)
            self.record(
                "Pinned + untrusted CA",
                "Trust anchor rejected. No HTTP request reached Handler.",
            )

        # Recreate the input after the prior send was rejected so the outcome uses a known marker.
        self.launch("pinned")
        with self.server("a", "a-recovered") as log:
            self.send(MARKER)
            self.find("TLS accepted · Message sent")
            self.find(MARKER)
            assert log().count("HTTP POST 201") == 1 and "HTTP GET" not in log(), log()
            self.capture("pinned-a-recovered")
            self.record(
                "Pinned + A restored",
                "One POST returned 201 with the updated chat. No follow-up GET.",
            )
            self.click("Message #1", exact=False)
            self.find(MARKER)
            self.capture("intent-internal")
            self.record(
                "Private Activity within app",
                "Explicit navigation displayed message #1",
            )
            # Both clients use the same live server instance for the exchange.
            self.launch("baseline")
            self.refresh("TLS accepted")
            self.find(MARKER)
            reply = "G02-REPLY"
            self.send(reply)
            self.find("TLS accepted · Message sent")
            self.launch("pinned")
            self.refresh("TLS accepted")
            self.find(MARKER)
            self.find(reply)
            assert log().count("HTTP POST 201") == 2, log()
            self.capture("cross-client-chat")
            self.record(
                "Two-client conversation",
                "Both Android variants read messages sent by the other.",
            )
        self.launch("pinned")
        self.find("Encrypted cache restored")
        self.find(MARKER)
        content = self.adb(
            "exec-out",
            "run-as",
            f"{PACKAGE}.pinned",
            "cat",
            "no_backup/messages.gcm",
            binary=True,
        )
        assert len(content) >= 28 and MARKER.encode() not in content
        self.capture("cache-restored")
        self.record(
            "Encrypted cache after process restart",
            f"Message restored. Marker absent from {len(content)} stored bytes.",
        )
        self.refresh("Connection unavailable")
        self.find(MARKER)
        self.record(
            "Backend offline",
            "UI reports unreachable backend and keeps cached conversation",
        )

        self.layout_checks()
        self.shell("input", "keyevent", "3")
        denied = self.shell(
            "am",
            "start",
            "-W",
            "-n",
            f"{PACKAGE}.pinned/{PACKAGE}.DetailActivity",
            "--ei",
            "id",
            "1",
            check=False,
        )
        assert "Permission Denial" in denied and "not exported" in denied, denied
        (self.output / "intent-os-denial.txt").write_text(denied)
        self.record(
            "Private Activity from shell UID",
            "Android returned Permission Denial (not exported)",
        )

        self.shell("am", "force-stop", f"{PACKAGE}.pinned")
        result = self.shell(
            "am",
            "instrument",
            "-w",
            "-r",
            f"{PACKAGE}.pinned.test/androidx.test.runner.AndroidJUnitRunner",
        )
        (self.output / "android-instrumentation.txt").write_text(result)
        assert re.search(r"OK \(2 tests?\)", result), result
        self.record(
            "Android instrumentation",
            "2 tests passed: cache authentication, manifest and ID validation",
        )

    def layout_checks(self):
        self.shell("cmd", "window", "user-rotation", "lock", "0")
        initial_scale = self.shell("settings", "get", "system", "font_scale").strip()
        try:
            self.shell("wm", "size", "1080x1920")
            self.shell("wm", "density", "480")
            self.shell("settings", "put", "system", "font_scale", "1.25")
            self.launch("pinned")
            self.find("Encrypted cache restored")
            self.find(MARKER)
            self.find("Send message", exact=True)
            self.find("Refresh", exact=True)
            self.capture("compact-portrait", landscape=False)
            self.record(
                "Compact portrait and large text",
                "360 dp width at 125% font scale. Cache and controls visible.",
            )

            self.click("Message text", field="content-desc")
            draft = "G02-DRAFT"
            self.shell("input", "text", draft)
            self.find(draft, exact=True)
            self.shell("input", "keyevent", "4")
            self.shell("cmd", "window", "user-rotation", "lock", "1")
            self.find("Refresh", exact=True)
            self.find(draft, exact=True)
            self.capture("landscape-draft", landscape=True)
            self.record(
                "Landscape rotation preserves draft",
                "Draft and actions remain visible in landscape.",
            )
        finally:
            if initial_scale in ("", "null"):
                self.shell("settings", "delete", "system", "font_scale")
            else:
                self.shell("settings", "put", "system", "font_scale", initial_scale)
            self.shell("wm", "density", "reset")
            self.shell("wm", "size", "reset")
            self.shell("cmd", "window", "user-rotation", "lock", "0")
            self.shell("cmd", "window", "user-rotation", "free")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "serial", help="Serial of a disposable emulator, e.g. emulator-5562"
    )
    parser.add_argument(
        "output", type=Path, help="New output directory for screenshots and logs"
    )
    args = parser.parse_args()
    if not re.fullmatch(r"emulator-\d+", args.serial):
        parser.error("Use a disposable Android Emulator instance")
    demo = Demo(args.serial, args.output.resolve())
    assert demo.shell("getprop", "ro.build.version.sdk").strip() == "36", (
        "Requires emulator API 36"
    )
    assert PORT not in demo.adb("reverse", "--list"), "Port 8443 already forwarded"
    demo.output.mkdir(parents=True)
    for flavor in ("baseline", "pinned"):
        apk = (
            ROOT
            / f"android/app/build/outputs/apk/{flavor}/debug/app-{flavor}-debug.apk"
        )
        assert "Success" in demo.adb("install", "-r", str(apk))
        assert "Success" in demo.shell("pm", "clear", f"{PACKAGE}.{flavor}")
    test = (
        ROOT
        / "android/app/build/outputs/apk/androidTest/pinned/debug/app-pinned-debug-androidTest.apk"
    )
    assert "Success" in demo.adb("install", "-r", str(test))
    demo.adb("reverse", PORT, PORT)
    try:
        demo.flow()
    finally:
        demo.adb("reverse", "--remove", PORT, check=False)
    (demo.output / "results.json").write_text(
        json.dumps(
            {
                "android_release": demo.shell(
                    "getprop", "ro.build.version.release"
                ).strip(),
                "api": 36,
                "architecture": demo.shell("getprop", "ro.product.cpu.abi").strip(),
                "tests": demo.results,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
