"""Read-only virtual host certificate reports, using real local X.509 fixtures."""

from datetime import datetime, timezone
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "include/vhost-ssl.sh"


class VHostSSLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory(prefix="lnmp-certs-")
        cls.fixture = Path(cls.fixtures.name)
        cls.certificate = cls.fixture / "leaf.pem"
        cls.key = cls.fixture / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "90",
                        "-subj", "/O=Let's Encrypt/CN=E12", "-keyout", str(cls.key),
                        "-out", str(cls.certificate)], check=True, capture_output=True)
        cls.other = cls.fixture / "cn-only.pem"
        subprocess.run(["openssl", "req", "-x509", "-new", "-key", str(cls.key), "-days", "10",
                        "-subj", "/CN=CN Only Authority", "-out", str(cls.other)], check=True, capture_output=True)
        dates = subprocess.check_output(["openssl", "x509", "-in", str(cls.certificate),
                                         "-noout", "-dates"], text=True).splitlines()
        cls.begin, cls.end = [int(datetime.strptime(line.split("=", 1)[1], "%b %d %H:%M:%S %Y GMT")
                                 .replace(tzinfo=timezone.utc).timestamp()) for line in dates]

    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lnmp ssl ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.nginx = self.root / "nginx/conf"
        self.apache = self.root / "apache"
        for directory in (self.nginx / "vhost", self.apache / "conf/vhost", self.root / "lib/lnmp"):
            directory.mkdir(parents=True)
        self.cert = self.root / "certificate with spaces.pem"
        shutil.copy(self.certificate, self.cert)
        self.env = dict(os.environ, TERM="xterm", TZ="Asia/Shanghai")
        self.env.pop("NO_COLOR", None)
        self.env.pop("FORCE_COLOR", None)

    def bash(self, script, *, env=None):
        result = subprocess.run(["bash", "-c", f'source {shlex.quote(str(HELPER))}\n{script}'],
                                env=env or self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def report(self, kind="nginx", env=None):
        directory, base = ((self.nginx / "vhost", self.nginx) if kind == "nginx"
                           else (self.apache / "conf/vhost", self.apache))
        return self.bash(f'List_VHost_SSL {kind} {shlex.quote(str(directory))} {shlex.quote(str(base))}', env=env)

    def test_thresholds_expiry_and_future_validity(self):
        for seconds, color, text in ((31 * 86400, "32", "31 days"), (31 * 86400 - 1, "33", "30 days"),
                                     (14 * 86400, "33", "14 days"), (14 * 86400 - 1, "31", "13 days"),
                                     (86400, "31", "1 day"), (86399, "37", "<1 day"),
                                     (1, "37", "<1 day"), (0, "37", "Expired <1 day ago"),
                                     (-1, "37", "Expired <1 day ago"), (-86400, "37", "Expired 1 day ago")):
            with self.subTest(seconds=seconds):
                row = self.bash(f'VHost_SSL_Certificate_Row domain {shlex.quote(str(self.cert))} {self.end - seconds}')
                self.assertEqual(row.strip().split("\t")[0], color)
                self.assertEqual(row.strip().split("\t")[-1], text)
        row = self.bash(f'VHost_SSL_Certificate_Row domain {shlex.quote(str(self.cert))} {self.begin - 1}')
        self.assertTrue(row.startswith("37\t"))
        self.assertIn("Not valid yet", row)

    def test_issuer_and_utc_dates_from_leaf_in_fullchain(self):
        fullchain = self.root / "fullchain.pem"
        fullchain.write_bytes(self.cert.read_bytes() + self.other.read_bytes())
        row = self.bash(f'VHost_SSL_Certificate_Row example {shlex.quote(str(fullchain))} {self.begin + 1}')
        self.assertIn("Let's Encrypt / E12", row)
        self.assertNotIn("CN Only Authority", row)
        self.assertIn(datetime.fromtimestamp(self.begin, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), row)
        self.assertIn(datetime.fromtimestamp(self.end, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), row)
        row = self.bash(f'VHost_SSL_Certificate_Row example {shlex.quote(str(self.other))} {self.begin + 1}')
        self.assertIn("CN Only Authority", row)

    def test_nginx_quoted_multiline_inline_comments_and_private_key(self):
        (self.nginx / "vhost/example.conf").write_text(
            f'# ssl_certificate /nonexistent;\nserver {{ listen 443 ssl; ssl_certificate_key /private.key;\n'
            f'ssl_certificate\n "{self.cert}"; # comment\n}}\n')
        output = self.report()
        self.assertIn("example", output)
        self.assertIn("Let's Encrypt / E12", output)
        self.assertIn("Not Before (UTC)", output)
        self.assertNotIn("missing", output)
        self.assertNotIn("\x1b[", output)

    def test_includes_relative_paths_multiple_certificates_and_deduplication(self):
        (self.nginx / "snippets").mkdir()
        shutil.copy(self.other, self.nginx / "second.pem")
        (self.nginx / "snippets/ssl.inc").write_text(
            f'ssl_certificate "{self.cert}";\nssl_certificate second.pem;\n')
        (self.nginx / "vhost/site.conf").write_text(
            f'include snippets/*.inc;\nssl_certificate "{self.cert}";\n')
        output = self.report()
        self.assertEqual(output.count("Let's Encrypt / E12"), 1)
        self.assertIn("CN Only Authority", output)

    def test_apache_directives_and_optional_includes(self):
        (self.apache / "ssl").mkdir()
        shutil.copy(self.cert, self.apache / "ssl/leaf.pem")
        (self.apache / "conf/ssl.inc").write_text('sslcertificatefile "ssl/leaf.pem"\n')
        (self.apache / "conf/vhost/site.conf").write_text(
            '# SSLCertificateFile /comment.pem\n<VirtualHost *:443>\n'
            'IncludeOptional conf/missing/*.conf\nInclude "conf/ssl.inc"\n'
            'SSLCertificateKeyFile /private.key\n</VirtualHost>\n')
        output = self.report("apache")
        self.assertIn("Let's Encrypt / E12", output)
        self.assertNotIn("missing", output)

    def test_no_ssl_missing_broken_dynamic_and_empty_directory(self):
        self.assertNotIn("*.conf", self.report())
        (self.nginx / "vhost/01-http.conf").write_text("server { listen 80; }\n")
        (self.nginx / "vhost/02-missing.conf").write_text("ssl_certificate /missing.pem;\n")
        (self.root / "broken.pem").write_text("not a certificate")
        (self.nginx / "vhost/03-broken.conf").write_text(f'ssl_certificate "{self.root}/broken.pem";\n')
        (self.nginx / "vhost/04-dynamic.conf").write_text('ssl_certificate "$ssl_server_name.pem";\n')
        (self.nginx / "vhost/05-valid.conf").write_text(f'ssl_certificate "{self.cert}";\n')
        output = self.report()
        for text in ("No SSL", "Certificate missing", "Invalid certificate", "Dynamic certificate", "Let's Encrypt / E12"):
            self.assertIn(text, output)

    def test_include_loops_and_missing_required_include(self):
        (self.nginx / "loop.inc").write_text("include loop.inc;\n")
        (self.nginx / "vhost/loop.conf").write_text("include loop.inc;\n")
        (self.nginx / "vhost/missing.conf").write_text("include missing.inc;\n")
        output = self.report()
        self.assertIn("include loop/depth limit", output)
        self.assertIn("include missing", output)

    def test_ansi_colors_and_no_color(self):
        (self.nginx / "vhost/example.conf").write_text(f'ssl_certificate "{self.cert}";\n')
        output = self.report(env=dict(self.env, FORCE_COLOR="1"))
        self.assertIn("\x1b[32mexample", output)
        self.assertIn("\x1b[0m", output)
        self.assertIn("\x1b[32m", self.report(env=dict(self.env, FORCE_COLOR="1", TERM="dumb")))
        self.assertNotIn("\x1b[", self.report(env=dict(self.env, FORCE_COLOR="1", NO_COLOR="1")))

    def test_manager_entrypoints_all_stacks(self):
        # The existing managers contain fixed unquoted paths in unrelated functions.
        # Map those paths through a space-free symlink; certificate paths still have spaces.
        manager_tmp = tempfile.TemporaryDirectory(prefix="lnmp-manager-")
        self.addCleanup(manager_tmp.cleanup)
        prefix = Path(manager_tmp.name) / "root"
        prefix.symlink_to(self.root, target_is_directory=True)
        shutil.copy(HELPER, self.root / "lib/lnmp/vhost-ssl.sh")
        (self.nginx / "vhost/secure.conf").write_text(f'ssl_certificate "{self.cert}";\n')
        (self.apache / "conf/vhost/secure.conf").write_text(f'SSLCertificateFile "{self.cert}"\n')
        for stack in ("lnmp", "lnmpa", "lamp"):
            with self.subTest(stack=stack):
                manager = self.root / stack
                script = (REPO / "conf" / stack).read_text()
                script = script.replace("/usr/local/nginx", str(prefix / "nginx"))
                script = script.replace("/usr/local/apache", str(prefix / "apache"))
                script = script.replace("/usr/local/lib/lnmp", str(prefix / "lib/lnmp"))
                script = script.replace('$(id -u)', '0')
                manager.write_text(script)
                result = subprocess.run(["bash", str(manager), "vhost", "list"], env=self.env,
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertIn("Let's Encrypt / E12", result.stdout)
                self.assertIn("Not After (UTC)", result.stdout)

    def test_helper_installation(self):
        destination = self.root / "installed"
        self.bash(f'source {shlex.quote(str(REPO / "include/main.sh"))}; '
                  f'cur_dir={shlex.quote(str(REPO))}; Install_VHost_SSL_Helper {shlex.quote(str(destination))}')
        installed = destination / "vhost-ssl.sh"
        self.assertEqual(installed.read_bytes(), HELPER.read_bytes())
        self.assertEqual(installed.stat().st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
