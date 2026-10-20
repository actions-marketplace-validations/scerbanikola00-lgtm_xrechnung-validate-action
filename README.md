# XRechnung Validate Action

Validate XRechnung, ZUGFeRD / Factur-X and EN 16931 e-invoices in your GitHub workflow —
**no JVM required, always the current official KoSIT rules.**

The usual way to check an XRechnung in CI is to download the KoSIT validator, a Java
runtime and the right validator configuration, and keep all three up to date. This action
skips all of that: it sends each file to [xrechnung.dev](https://xrechnung.dev), which runs
the official KoSIT validator with the current XRechnung configuration, and turns the result
into GitHub annotations on the offending file. A composite action with a ~100-line Python
script (standard library only) — no Docker image, no Java, starts in about a second.

- Errors and warnings show up as `::error` / `::warning` annotations with the rule ID as title
- Every rule links to a plain-language explanation, e.g. https://xrechnung.dev/fehler/br-de-15/
- The job fails when any file is invalid
- UBL and CII XRechnung 3.0, ZUGFeRD / Factur-X PDFs (embedded XML), plain EN 16931

## Usage

```yaml
name: Validate e-invoices
on: [push, pull_request]

jobs:
  xrechnung:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: scerbanikola00-lgtm/xrechnung-validate-action@v1
        with:
          files: invoices/**/*.xml
          api-key: ${{ secrets.XRECHNUNG_API_KEY }}   # optional
```

Example output:

```
Error: BR-DE-15  [BR-DE-15] Das Element "Buyer reference" (BT-10) muss übermittelt werden. - https://xrechnung.dev/fehler/br-de-15/
INVALID invoices/2026/RE-0001.xml (1 errors, 0 warnings) [EN16931 XRechnung (CII)]
valid   invoices/2026/RE-0002.xml (0 errors, 0 warnings) [EN16931 XRechnung (UBL Invoice)]
2 file(s) checked, 1 failed
```

See [`examples/validate-invoices.yml`](examples/validate-invoices.yml) for a workflow that
only runs when invoice files change.

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `files` | yes | | Glob(s), space or newline separated. `**` recurses. XML or PDF. |
| `api-key` | no | | xrechnung.dev API key. Store it as a repository secret. |
| `api-url` | no | `https://xrechnung.dev` | Only for testing. |

## Free tier and API keys

Without a key you get **30 documents per month** for free. For more, get a key at
https://xrechnung.dev/#pricing, add it as a repository secret named `XRECHNUNG_API_KEY`
(Settings → Secrets and variables → Actions → New repository secret) and pass it as shown
above. When the monthly limit is reached the action fails with a clear HTTP 429 message.

## Privacy

Each matching file is uploaded to xrechnung.dev for validation only.
See https://xrechnung.dev/datenschutz.html. Use test or anonymised invoices if your
repository contains real customer data you may not share.

## Notes

- Runs on Linux and macOS runners (needs `python3` and `bash`, both preinstalled).
- Want negative test files? See the
  [XRechnung test corpus](https://github.com/scerbanikola00-lgtm/xrechnung-testcorpus): one broken
  invoice per German business rule.

## Development

```sh
python3 -m unittest -v test_validate   # runs against a local mock server, no network
```

## License

MIT — see [LICENSE](LICENSE). Validation rules: KoSIT / XRechnung (Apache-2.0).
