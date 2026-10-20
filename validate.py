#!/usr/bin/env python3
"""POST each matching e-invoice to xrechnung.dev /v1/validate and report findings as
GitHub annotations. Stdlib only. Inputs come from the environment (see action.yml)."""
import glob, json, os, sys, urllib.error, urllib.request, uuid

API = os.environ.get("INPUT_API_URL", "https://xrechnung.dev").rstrip("/") + "/v1/validate"
KEY = os.environ.get("INPUT_API_KEY", "").strip()
PATTERNS = os.environ.get("INPUT_FILES", "").split()


def esc(s, prop=False):  # GitHub workflow-command escaping
    s = str(s).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return s.replace(":", "%3A").replace(",", "%2C") if prop else s


def link(code):
    """https://xrechnung.dev/fehler/br-de-23/ for BR-DE-23-a; None for non-rule codes (schema errors)."""
    if not code[:1].isupper():
        return None
    slug = code.lower()
    if slug.endswith(("-a", "-b")):
        slug = slug[:-2]
    return f"https://xrechnung.dev/fehler/{slug}/"


def post(path):
    with open(path, "rb") as f:
        data = f.read()
    b = uuid.uuid4().hex
    body = (f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\n').encode() + data + f"\r\n--{b}--\r\n".encode()
    headers = {"Content-Type": f"multipart/form-data; boundary={b}", "User-Agent": "xrechnung-validate-action/1"}
    if KEY:
        headers["x-api-key"] = KEY
    req = urllib.request.Request(API, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def annotate(level, path, f):
    code = f.get("code") or "error"
    url = link(code)
    msg = f.get("message", "") + (f" - {url}" if url else "")
    print(f"::{level} file={esc(path, True)},title={esc(code, True)}::{esc(msg)}")


def main():
    files = sorted({p for pat in PATTERNS for p in glob.glob(pat, recursive=True) if os.path.isfile(p)})
    if not files:
        print(f"::error::no files matched {' '.join(PATTERNS)}")
        return 1
    failed, usage = 0, None
    for path in files:
        try:
            res = post(path)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except ValueError:
                pass
            hint = " Add an api-key (free tier: 30 documents/month without one)." if e.code == 429 and not KEY else ""
            print(f"::error file={esc(path, True)}::{esc(f'xrechnung.dev returned HTTP {e.code}: {detail}{hint}')}")
            failed += 1
            if e.code in (401, 429):  # every further request would fail the same way
                break
            continue
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"::error file={esc(path, True)}::{esc(f'could not validate: {e}')}")
            failed += 1
            continue
        for f in res.get("errors", []):
            annotate("error", path, f)
        for f in res.get("warnings", []):
            annotate("warning", path, f)
        failed += not res.get("valid")
        usage = res.get("usage") or usage
        c = res.get("counts", {})
        print(f"{'INVALID' if not res.get('valid') else 'valid  '} {path} ({c.get('errors', 0)} errors, {c.get('warnings', 0)} warnings)"
              + (f" [{res.get('scenario')}]" if res.get("scenario") else ""))
    if usage:
        print(f"xrechnung.dev usage this month: {usage.get('used')}/{usage.get('limit')} ({usage.get('plan')})")
    print(f"{len(files)} file(s) checked, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
