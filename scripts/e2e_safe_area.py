"""Extra native Android E2E: tall notch and corner cutout on a dedicated QA AVD."""
import json
import time
from e2e_android import OUT, PACKAGE, adb, bounds, dump, find, wait_scan


def main():
    overlays=adb("shell","cmd","overlay","list")
    used=[]
    scenarios=[]
    try:
        for style in ("tall","corner"):
            overlay="com.android.internal.display.cutout.emulation."+style
            assert "[ ] "+overlay in overlays,"Run this only on an unmodified QA emulator."
            used.append(overlay)
            adb("shell","cmd","overlay","enable",overlay)
            time.sleep(1.5)
            # A device's notch configuration is in place before normal app launch.
            # Overlay changes can recreate Android activities, so test a cold start.
            adb("shell","am","force-stop",PACKAGE)
            adb("shell","am","start","-n",PACKAGE+"/.MainActivity")
            wait_scan("https://example.com",f"04-cutout-{style}.png")
            tree=dump()
            header=find("QR Generator",tree,exact=True)
            nav=find("Preview & export",tree,exact=True)
            assert header is not None and nav is not None
            assert bounds(header)[1]>0
            assert bounds(nav)[3]<2400
            scenarios.append(f"{style} display cutout: preview decodes, header and bottom navigation remain visible")
            adb("shell","cmd","overlay","disable",overlay)
            used.remove(overlay)
        (OUT/"safe-area-report.json").write_text(json.dumps({"result":"PASS","scenarios":scenarios},indent=2),encoding="utf-8")
        print(json.dumps({"result":"PASS","scenarios":scenarios},indent=2))
    finally:
        for overlay in used:
            adb("shell","cmd","overlay","disable",overlay)


if __name__=="__main__":
    main()
