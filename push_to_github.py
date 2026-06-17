"""One-shot push of the already-committed repo to GitHub.

The repo is already initialized and committed (branch: main) via dulwich.
This reads GITHUB_TOKEN from .env (gitignored) and pushes. .env itself is
NOT part of the commit, so no keys are uploaded.

Run:  ./tf_env/bin/python push_to_github.py
"""
import json
import urllib.request
from pathlib import Path
from dulwich import porcelain

ROOT = Path(__file__).resolve().parent
OWNER, REPO = "allanaziz581", "ThinkFree"

tok = None
for line in open(ROOT / ".env", encoding="utf-8"):
    if line.startswith("GITHUB_TOKEN="):
        tok = line.strip().split("=", 1)[1]
if not tok:
    raise SystemExit("No GITHUB_TOKEN in .env")


def api(path, method="GET", body=None):
    req = urllib.request.Request("https://api.github.com" + path, data=body, method=method,
                                 headers={"Authorization": "token " + tok, "User-Agent": "TF",
                                          "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.getcode(), json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200].decode("utf-8", "ignore")


code, repo = api(f"/repos/{OWNER}/{REPO}")
if code == 404:
    print("Creating private repo...")
    c2, d = api("/user/repos", "POST", json.dumps({"name": REPO, "private": True}).encode())
    print("create:", c2, d.get("full_name") if isinstance(d, dict) else d)
else:
    print("repo exists:", repo.get("full_name") if isinstance(repo, dict) else repo)

print("Pushing main...")
porcelain.push(str(ROOT), f"https://github.com/{OWNER}/{REPO}.git",
               "refs/heads/main:refs/heads/main", username=OWNER, password=tok)
print("PUSH OK -> https://github.com/%s/%s" % (OWNER, REPO))
