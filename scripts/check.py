"""One command for regression tests + an isolated real-UI E2E session."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    subprocess.run([sys.executable,"-m","pytest","tests/test_engine.py","-q"],cwd=ROOT,check=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1",0))
        port=s.getsockname()[1]
    env={**os.environ,"QRSTUDIO_WEB":"1","QRSTUDIO_PORT":str(port),"PYTHONUTF8":"1"}
    env["QRSTUDIO_BASE_URL"]=f"http://127.0.0.1:{port}"
    out=ROOT/"test-results"
    out.mkdir(exist_ok=True)
    with (out/"e2e-server.log").open("w",encoding="utf-8") as log:
        proc=subprocess.Popen([sys.executable,"src/main.py"],cwd=ROOT,env=env,stdout=log,stderr=log,
                              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        try:
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError("E2E server exited. See test-results/e2e-server.log.")
                try:
                    with urllib.request.urlopen(env["QRSTUDIO_BASE_URL"],timeout=1) as response:
                        if response.status==200:
                            break
                except OSError:
                    time.sleep(.3)
            else:
                raise RuntimeError("E2E server did not start.")
            subprocess.run([sys.executable,"scripts/e2e_web.py"],cwd=ROOT,env=env,check=True)
        finally:
            # The only target is the server this script created, including its workers.
            if sys.platform=="win32":
                subprocess.run(["taskkill","/PID",str(proc.pid),"/T","/F"],capture_output=True)
            else:
                proc.terminate()
            proc.wait(timeout=15)


if __name__=="__main__":
    main()
