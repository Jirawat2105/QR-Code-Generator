"""Exercise the distributed Windows BAT with no discoverable Python or cached setup.

Requires a built release ZIP and the development environment (Edge/Playwright).
Downloads real setup tools/Python/packages into an isolated QA directory. Does not
remove or modify system Python. macOS receives archive/syntax/download checks only.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def stop(proc):
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    proc.wait(timeout=20)


def wait_for_app(proc, url, timeout=600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("Launcher exited. See launcher-first-start.log.")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(.5)
    raise TimeoutError("Python bootstrap/app start timed out.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.platform != "win32":
        raise SystemExit("This E2E workflow tests the real Windows launcher on Windows.")
    qa = ROOT/".qa"/f"launchers-{time.strftime('%Y%m%d-%H%M%S')}"
    qa.mkdir(parents=True)
    extracted = qa/"space and Thai ทดสอบ"
    with zipfile.ZipFile(ROOT/"dist/QRGenerator-1.2.0-Windows.zip") as archive:
        assert archive.testzip() is None
        archive.extractall(extracted)
    app = extracted/"QRGenerator"
    assert (app/"run.bat").exists() and (app/"src/main.py").exists()
    # Simulate an unavailable bundled executable; fallback must be independent.
    (app/"QRGenerator.exe").rename(app/"QRGenerator.exe.not-used")
    with zipfile.ZipFile(ROOT/"dist/QRGenerator-1.2.0-macOS-Python.zip") as archive:
        assert archive.testzip() is None
        info = archive.getinfo("QRGenerator/Run.command")
        assert info.external_attr >> 16 & 0o111
        assert b"\r" not in archive.read(info)
        assert not any("_internal/" in p or p.endswith((".exe", ".pyc"))
                       or ".python-env/" in p for p in archive.namelist())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ)
    for key in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH"):
        env.pop(key, None)
    env.update({
        "PATH": os.pathsep.join([str(Path(os.environ["SystemRoot"])/"System32"), os.environ["SystemRoot"]]),
        "LOCALAPPDATA": str(qa/"user-local"),
        "UV_CACHE_DIR": str(qa/"uv-cache"),
        "UV_PYTHON_INSTALL_DIR": str(qa/"managed-python"),
        "UV_PYTHON_PREFERENCE": "only-managed",
        "QRGENERATOR_NO_PAUSE": "1",
        "QRSTUDIO_WEB": "1", "QRSTUDIO_PORT": str(port), "PYTHONUTF8": "1",
        "QRSTUDIO_TEST_TARGET": "release-zip-run.bat-auto-python-no-exe",
        "QRSTUDIO_BASE_URL": f"http://127.0.0.1:{port}",
    })
    assert shutil.which("python", path=env["PATH"]) is None
    assert not (app/".python-env").exists()
    result = {"qa_directory": str(qa), "checks": [], "native_macos": "not tested"}
    result["checks"].append("Windows source complete; macOS source-only ZIP, executable mode, LF and CRC verified")
    log_path = qa/"launcher-first-start.log"
    print(f"Testing actual BAT, without Python on PATH: {app}", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen([os.environ["COMSPEC"], "/d", "/c", str(app/"run.bat")],
                                cwd=qa, env=env, stdout=log, stderr=log)
        try:
            wait_for_app(proc, env["QRSTUDIO_BASE_URL"])
            result["checks"].append("Actual BAT downloaded verified uv, installed managed Python and dependencies, then started actual Flet app with bundled EXE unavailable; spaces/Thai path")
            # The driver has dev dependencies; the server uses only the shipped runtime requirements.
            driver_env = {**os.environ, **{key: env[key] for key in
                          ("QRSTUDIO_BASE_URL", "QRSTUDIO_TEST_TARGET")}}
            subprocess.run([sys.executable, "scripts/e2e_web.py"], cwd=ROOT,
                           env=driver_env, check=True)
            report = json.loads((ROOT/"test-results/e2e/report.json").read_text(encoding="utf-8"))
            result["ui_scenarios"] = len(report["scenarios"])
            shutil.copy2(ROOT/"test-results/e2e/report.json", qa/"ui-report.json")
        finally:
            stop(proc)
    python = app/".python-env/Scripts/python.exe"
    diagnostic = subprocess.check_output([str(python), "-I", "-c",
        "import json,sys,importlib.metadata as m; print(json.dumps({'python':sys.version, 'base':sys.base_prefix,'packages':{n:m.version(n) for n in ('flet','flet-desktop','flet-web','qrcode','pillow')}}))"], text=True)
    result["runtime"] = json.loads(diagnostic)
    assert str(qa/"managed-python").casefold() in result["runtime"]["base"].casefold()
    # No download is allowed on repeat setup. Same installation must be reused.
    offline = {**env, "UV_OFFLINE": "true", "UV_PYTHON_DOWNLOADS": "never"}
    before = python.stat().st_mtime_ns
    completed = subprocess.run([os.environ["COMSPEC"], "/d", "/c", str(app/"setup.bat")],
                               cwd=qa, env=offline, capture_output=True, timeout=90)
    (qa/"launcher-offline.log").write_bytes(completed.stdout+completed.stderr)
    assert completed.returncode == 0, completed.stdout+completed.stderr
    assert python.stat().st_mtime_ns == before
    result["checks"].append("Repeat setup succeeds offline, reusing Python and dependencies without reinstalling")
    # Remove a real dependency using the distributed installer, then repair offline from cache.
    uv = qa/"user-local/QRGenerator/tools/uv-0.13.10/uv.exe"
    subprocess.run([str(uv), "--no-config", "pip", "uninstall", "--python", str(python), "qrcode"], env=env, check=True)
    completed = subprocess.run([os.environ["COMSPEC"], "/d", "/c", str(app/"setup.bat")],
                               cwd=qa, env=offline, capture_output=True, timeout=90)
    (qa/"launcher-repair.log").write_bytes(completed.stdout+completed.stderr)
    assert completed.returncode == 0, completed.stdout+completed.stderr
    subprocess.run([str(python), "-I", "-c", "import qrcode, flet_desktop, PIL"], check=True)
    result["checks"].append("Missing real runtime dependency is reinstalled automatically from cache")
    # An unresolvable requirement must stop setup before attempting to launch the app.
    requirements = app/"requirements.txt"
    original = requirements.read_bytes()
    try:
        requirements.write_bytes(original+b"\nqr-generator-deliberately-missing-qa-package==0.0.0\n")
        completed = subprocess.run([os.environ["COMSPEC"], "/d", "/c", str(app/"run.bat")],
                                   cwd=qa, env=offline, capture_output=True, timeout=90)
        (qa/"launcher-install-failure.log").write_bytes(completed.stdout+completed.stderr)
        assert completed.returncode != 0
        assert b"Starting QR Generator" not in completed.stdout
        result["checks"].append("Dependency installation failure returns nonzero and does not launch the app")
    finally:
        requirements.write_bytes(original)
    result["result"] = "PASS"
    (ROOT/"test-results/launcher-report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
