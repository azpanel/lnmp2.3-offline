"""Download audit tests use a local HTTP server and temporary package roots."""

from datetime import datetime, timezone
import functools
import hashlib
import http.server
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import threading
import unittest


REPO = Path(__file__).resolve().parents[1]
PAYLOAD = b"local download fixture\n"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class DownloadLoggingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.remote = tempfile.TemporaryDirectory(prefix="lnmp-download-server-")
        Path(cls.remote.name, "archive.tar.gz").write_bytes(PAYLOAD)
        cls.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(QuietHandler, directory=cls.remote.name))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.remote.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lnmp audit ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "include").mkdir()
        (self.root / "tools").mkdir()
        self.src = self.root / "src"
        self.src.mkdir()
        self.main = self.root / "include/main.sh"
        shutil.copy(REPO / "include/main.sh", self.main)
        self.log = self.root / "soft-lnmp-downloads.log"
        self.url = f"http://soft.lnmp.com:{self.server.server_port}/archive.tar.gz"

    def bash(self, script, *, cwd=None, check=True):
        # Only rewrite DNS for the test server; run the real wget and hash tools.
        setup = f"""
source {shlex.quote(str(self.main))}
cur_dir={shlex.quote(str(self.root))}
Enable_Download_Checksum=y
wget() {{
    local arg
    local -a args=()
    for arg in "$@"; do
        args+=("${{arg/soft.lnmp.com/127.0.0.1}}")
    done
    command wget --no-proxy --tries=1 --timeout=3 "${{args[@]}}"
}}
"""
        result = subprocess.run(["bash", "-c", setup + script], cwd=cwd or self.src,
                                text=True, capture_output=True)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def records(self):
        return [dict(field.split("=", 1) for field in line.split("\t"))
                for line in self.log.read_text().splitlines()]

    def test_download_and_cache_log_time_hash_absolute_path(self):
        self.bash(f'Download_Files {shlex.quote(self.url)} "archive.tar.gz"; '
                  f'Download_Files {shlex.quote(self.url)} "archive.tar.gz"')
        records = self.records()
        self.assertEqual([record["status"] for record in records], ["downloaded", "cached"])
        for record in records:
            self.assertEqual(record["sha256"], DIGEST)
            self.assertEqual(record["path"], str(self.src / "archive.tar.gz"))
            self.assertEqual(record["url"], self.url)
            self.assertEqual(record["exit_code"], "0")
            timestamp = datetime.strptime(record["time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            self.assertLess(abs((datetime.now(timezone.utc) - timestamp).total_seconds()), 10)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.src / self.log.name).exists())

    def test_checksum_failure_records_hash_before_file_removal(self):
        (self.src / "checksums.sha256").write_text("0" * 64 + "  archive.tar.gz\n")
        result = self.bash(f'Download_Files {shlex.quote(self.url)} archive.tar.gz', check=False)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.src / "archive.tar.gz").exists())
        record = self.records()[0]
        self.assertEqual(record["sha256"], DIGEST)
        self.assertEqual(record["status"], "downloaded_verification_failed")
        self.assertEqual(record["exit_code"], "1")
        (self.src / "archive.tar.gz").write_bytes(PAYLOAD)
        result = self.bash(f'Download_Files {shlex.quote(self.url)} archive.tar.gz', check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.records()[1]["status"], "cached_verification_failed")

    def test_failed_download_records_missing_or_partial_file(self):
        url = self.url.replace("archive.tar.gz", "missing.tar.gz")
        result = self.bash(f'Download_Files {shlex.quote(url)} missing.tar.gz', check=False)
        self.assertEqual(result.returncode, 1)
        record = self.records()[0]
        self.assertEqual(record["status"], "download_failed")
        self.assertEqual(record["exit_code"], "8")
        # wget can leave an empty file on HTTP errors; hash those bytes if present.
        self.assertEqual(record["sha256"], hashlib.sha256(b"").hexdigest())
        result = self.bash('wget() { printf partial > partial.tar.gz; return 4; }; '
                           f'Download_Files {shlex.quote(self.url)} partial.tar.gz', check=False)
        self.assertEqual(result.returncode, 1)
        record = self.records()[1]
        self.assertEqual(record["sha256"], hashlib.sha256(b"partial").hexdigest())
        self.assertEqual(record["exit_code"], "4")

    def test_domain_filter_excludes_other_sources(self):
        (self.src / "archive.tar.gz").write_bytes(PAYLOAD)
        self.bash('for url in https://nginx.org/a https://soft.lnmp.com.evil/a '
                  'https://soft.lnmp.com@evil/a https://evil/soft.lnmp.com/a; do '
                  'Download_Files "$url" archive.tar.gz || exit 1; done')
        self.assertFalse(self.log.exists())
        self.bash('Is_Soft_LNMP_URL HTTPS://SOFT.LNMP.COM/a && '
                  '! shopt -q nocasematch')

    def test_logging_failure_is_silent_and_keeps_download_status(self):
        self.log.mkdir()
        (self.src / "archive.tar.gz").write_bytes(PAYLOAD)
        result = self.bash(f'Download_Files {shlex.quote(self.url)} archive.tar.gz')
        self.assertEqual(result.stdout, "archive.tar.gz [found]\n")
        self.assertEqual(result.stderr, "")

    def test_logs_from_tools_and_escapes_paths(self):
        filename = "file with\ttab\nand\\slash.gz"
        (self.root / "tools" / filename).write_bytes(PAYLOAD)
        self.bash(f'unset cur_dir; Download_Files {shlex.quote(self.url)} {shlex.quote(filename)}',
                  cwd=self.root / "tools")
        records = self.records()
        self.assertEqual(len(records), 1)
        self.assertIn(r"\ttab\nand\\slash.gz", records[0]["path"])
        self.assertEqual(records[0]["sha256"], DIGEST)

    def test_rpm_is_downloaded_and_logged_before_install(self):
        result = self.bash('rpm() { test "$1" = -ivh && test -s "$2" && echo "installed:$2"; }; '
                           f'Download_And_Install_RPM {shlex.quote(self.url)}', cwd=self.root)
        self.assertIn("installed:archive.tar.gz", result.stdout)
        self.assertEqual(self.records()[0]["sha256"], DIGEST)
        self.assertEqual(self.records()[0]["path"], str(self.src / "archive.tar.gz"))

    def test_concurrent_appends(self):
        (self.src / "archive.tar.gz").write_bytes(PAYLOAD)
        self.bash(f'for i in {{1..16}}; do Download_Files {shlex.quote(self.url)} archive.tar.gz & done; wait')
        records = self.records()
        self.assertEqual(len(records), 16)
        self.assertTrue(all(record["sha256"] == DIGEST for record in records))

    def test_hashing_even_when_checksum_verification_is_disabled(self):
        self.bash('Enable_Download_Checksum=n; '
                  f'Download_Files {shlex.quote(self.url)} archive.tar.gz')
        self.assertEqual(self.records()[0]["sha256"], DIGEST)

    def test_hash_fallback_and_unavailable_hash(self):
        (self.src / "archive.tar.gz").write_bytes(PAYLOAD)
        # Hide coreutils/perl hash tools to exercise the OpenSSL fallback.
        hide_tools = '''
command() {
    if [ "$1" = -v ] && { [ "$2" = sha256sum ] || [ "$2" = shasum ]; }; then return 1; fi
    builtin command "$@"
}
'''
        self.bash(hide_tools + f'Download_Files {shlex.quote(self.url)} archive.tar.gz')
        self.assertEqual(self.records()[0]["sha256"], DIGEST)
        result = self.bash('Download_File_SHA256() { return 1; }; '
                           f'Download_Files {shlex.quote(self.url)} archive.tar.gz')
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.records()[1]["sha256"], "-")

    def test_rpm_download_failure_does_not_install(self):
        result = self.bash('wget() { return 4; }; rpm() { echo unexpected-install; }; '
                           f'Download_And_Install_RPM {shlex.quote(self.url)}', check=False)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("unexpected-install", result.stdout)
        self.assertEqual(self.records()[0]["sha256"], "-")
        self.assertEqual(self.records()[0]["status"], "download_failed")


if __name__ == "__main__":
    unittest.main()
