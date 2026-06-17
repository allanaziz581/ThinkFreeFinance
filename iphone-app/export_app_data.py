"""Export the web app's data into plain JSON the iPhone app can bundle.

The webapp stores data as `window.X = {...};` JS files. This strips the wrapper
and writes pure .json into ThinkFree/Resources/ for the SwiftUI app to load.

Run:  ./tf_env/bin/python iphone-app/export_app_data.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "webapp" / "js"
OUT = Path(__file__).resolve().parent / "ThinkFree" / "Resources"

# js file -> (window var, output json name)
FILES = {
    "data.js": ("window.TF_DATA =", "data.json"),
    "fec_data.js": ("window.FEC_DATA =", "fec.json"),
    "usaspending_data.js": ("window.USA_DATA =", "usaspending.json"),
    "secbulk_data.js": ("window.SECBULK_DATA =", "secbulk.json"),
    "states_data.js": ("window.STATES_DATA =", "states.json"),
    "nonprofit_data.js": ("window.NP_DATA =", "nonprofits.json"),
    "influence_data.js": ("window.IW_DATA =", "influence.json"),
    "legiscan_data.js": ("window.LEGISCAN_DATA =", "legiscan.json"),
    "openstates_data.js": ("window.OPENSTATES_DATA =", "openstates.json"),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for js, (marker, out_name) in FILES.items():
        path = WEB / js
        if not path.exists():
            print(f"  skip {js} (missing)")
            continue
        txt = path.read_text(encoding="utf-8")
        i = txt.index(marker) + len(marker)
        body = txt[i:].rstrip().rstrip(";").strip()
        data = json.loads(body)
        (OUT / out_name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"  wrote {out_name} ({(OUT / out_name).stat().st_size // 1024} KB)")
    print(f"\nResources ready at {OUT}")


if __name__ == "__main__":
    main()
