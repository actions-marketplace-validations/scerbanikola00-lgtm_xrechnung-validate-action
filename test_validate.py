"""Runs validate.py against a local mock of /v1/validate. No network.  python3 -m unittest -v"""
import json, os, subprocess, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
INVALID = {"valid": False, "scenario": "EN16931 XRechnung (CII)", "profile": "",
           "errors": [{"code": "BR-DE-15", "message": "[BR-DE-15] Das Element \"Buyer reference\" (BT-10) muss übermittelt werden.", "location": "/x"},
                      {"code": "BR-DE-23-a", "message": "[BR-DE-23-a] BG-17 fehlt, 100% sicher", "location": "/y"}],
           "warnings": [{"code": "BR-DE-27", "message": "[BR-DE-27] In BT-42 sollen mindestens drei Ziffern enthalten sein.", "location": "/z"}],
           "informations": [], "counts": {"errors": 2, "warnings": 1, "informations": 0},
           "filename": "bad.xml", "usage": {"plan": "free", "used": 2, "limit": 10}}
VALID = {"valid": True, "scenario": "EN16931 XRechnung (UBL Invoice)", "errors": [], "warnings": [], "informations": [],
         "counts": {"errors": 0, "warnings": 0, "informations": 0}, "usage": {"plan": "free", "used": 1, "limit": 10}}
seen = []


class Mock(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        seen.append((self.path, self.headers.get("x-api-key"), self.headers["Content-Type"], body))
        if b"QUOTA" in body:
            code, out = 429, {"detail": "monthly limit reached (10 documents on the Free plan)."}
        else:
            code, out = 200, (INVALID if b"BROKEN" in body else VALID)
        data = json.dumps(out).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, *a):
        pass


class ActionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Mock)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def run_action(self, files, key=""):
        with tempfile.TemporaryDirectory() as d:
            for name, content in files.items():
                p = Path(d, name); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
            env = dict(os.environ, INPUT_FILES="invoices/**/*.xml", INPUT_API_KEY=key, INPUT_API_URL=self.url)
            return subprocess.run([sys.executable, str(HERE / "validate.py")], cwd=d, env=env, capture_output=True, text=True)

    def test_invalid_file_annotates_and_fails(self):
        seen.clear()
        r = self.run_action({"invoices/a/bad.xml": "<x>BROKEN</x>", "invoices/good.xml": "<x/>", "other.xml": "<x/>"}, key="xr_test")
        print(r.stdout)
        self.assertEqual(r.returncode, 1)
        self.assertIn("::error file=invoices/a/bad.xml,title=BR-DE-15::[BR-DE-15] Das Element \"Buyer reference\" (BT-10) muss übermittelt werden. - https://xrechnung.dev/fehler/br-de-15/", r.stdout)
        self.assertIn("title=BR-DE-23-a::[BR-DE-23-a] BG-17 fehlt, 100%25 sicher - https://xrechnung.dev/fehler/br-de-23/", r.stdout)
        self.assertIn("::warning file=invoices/a/bad.xml,title=BR-DE-27::", r.stdout)
        self.assertIn("2 file(s) checked, 1 failed", r.stdout)  # other.xml is outside the glob
        self.assertEqual({s[0] for s in seen}, {"/v1/validate"})
        self.assertEqual({s[1] for s in seen}, {"xr_test"})
        self.assertTrue(all(s[2].startswith("multipart/form-data; boundary=") and b'name="file"' in s[3] for s in seen))

    def test_all_valid_passes_without_key(self):
        seen.clear()
        r = self.run_action({"invoices/good.xml": "<x/>"})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(seen[0][1], None)
        self.assertIn("usage this month: 1/10 (free)", r.stdout)

    def test_quota_exceeded_fails_with_hint(self):
        r = self.run_action({"invoices/q.xml": "<x>QUOTA</x>"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("HTTP 429", r.stdout)
        self.assertIn("Add an api-key", r.stdout)

    def test_no_match_fails(self):
        r = self.run_action({"nothing.txt": ""})
        self.assertEqual(r.returncode, 1)
        self.assertIn("::error::no files matched", r.stdout)


if __name__ == "__main__":
    unittest.main()
