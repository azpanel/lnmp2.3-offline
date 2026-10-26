"""Run with python3 -m unittest discover -s tests -v.

Optional integration tools: LNMP_TEST_TOOLS points to an extracted Debian package
root containing nginx, apache2-bin, nginx-common, php8.4-fpm and mod_php8.4.
Tests use temporary configs, ports and document roots, never system services.
"""

import base64
from datetime import datetime
import http.client
import os
from pathlib import Path
import shlex
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
TOOLS = Path(os.environ.get("LNMP_TEST_TOOLS", "/nonexistent"))


class SecurityFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lnmp-security-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o755)
        self.web = self.root / "web"
        self.web.mkdir()
        self.security = self.root / "security"
        self.env = dict(os.environ, LNMP_Security_Dir=str(self.security),
                        Default_Website_Dir=str(self.web), Default_Server_IP="127.0.0.1",
                        PhpMyAdmin_Mode="random", LNMP_Auto="y")
        for name in ("PhpMyAdmin_Auth_User", "PhpMyAdmin_Auth_Password", "PhpMyAdmin_Dir"):
            self.env.pop(name, None)

    def bash(self, script, *, env=None, input=None, check=True):
        # Installed stacks use www; the isolated test uses the local test user's group.
        chown = ('chown() { local -a args=("${@//www/www-data}"); command chown "${args[@]}"; }'
                 if os.geteuid() == 0 else 'chown() { :; }')
        result = subprocess.run(["bash", "-c", f"source {shlex.quote(str(REPO / 'include/security.sh'))}\n"
                                 f"{chown}\n{script}"], env=env or self.env,
                                input=input, text=True, capture_output=True)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def prepare(self, mode="random"):
        self.env.update(PhpMyAdmin_Mode=mode, PhpMyAdmin_Auth_User="admin",
                        PhpMyAdmin_Auth_Password="se cret:$quote'\\")
        result = self.bash('Default_Security_Selection && Prepare_Default_Security && '
                           'Create_Default_Certificate && Save_Default_Security && '
                           'printf "ENTRY=%s\\n" "$PhpMyAdmin_Dir"')
        self.entry = result.stdout.split("ENTRY=")[1].strip()
        return self.entry


class SecurityTests(SecurityFixture):
    def test_random_certificate_and_saved_location(self):
        entry = self.prepare()
        self.assertRegex(entry, r"^[0-9a-f]{32}$")
        self.assertNotEqual(entry, self.prepare())
        self.assertEqual((self.security / "default.key").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.security / "security.conf").stat().st_mode & 0o777, 0o600)
        certificate = subprocess.check_output(["openssl", "x509", "-in", str(self.security / "default.crt"),
                                               "-noout", "-text"], text=True)
        self.assertIn("IP Address:127.0.0.1", certificate)
        self.assertIn("sha256WithRSAEncryption", certificate)
        self.assertIn("2048 bit", certificate)
        dates = subprocess.check_output(["openssl", "x509", "-in", str(self.security / "default.crt"),
                                         "-noout", "-dates"], text=True).splitlines()
        start, end = [datetime.strptime(value.split("=", 1)[1], "%b %d %H:%M:%S %Y GMT") for value in dates]
        self.assertEqual((end - start).days, 365)
        saved = (self.security / "security.conf").read_text()
        self.assertNotIn("Password", saved)
        self.assertNotIn(self.env["PhpMyAdmin_Auth_Password"], saved)

    def test_basic_credentials_and_validation(self):
        self.prepare("basic")
        self.assertEqual(self.entry, "phpmyadmin")
        password_file = self.security / "phpmyadmin.htpasswd"
        self.assertTrue(password_file.read_text().startswith("admin:$apr1$"))
        self.assertEqual(password_file.stat().st_mode & 0o777, 0o640)
        self.assertNotIn(self.env["PhpMyAdmin_Auth_Password"], password_file.read_text())
        self.env.pop("PhpMyAdmin_Auth_Password")
        self.assertNotEqual(self.bash("Default_Security_Selection", check=False).returncode, 0)
        self.env["PhpMyAdmin_Auth_Password"] = "a\nb"
        self.assertNotEqual(self.bash("Default_Security_Selection", check=False).returncode, 0)
        self.env["PhpMyAdmin_Mode"] = "invalid"
        self.assertNotEqual(self.bash("Default_Security_Selection", check=False).returncode, 0)

    def test_ipv4_and_interactive_retry(self):
        self.bash('for ip in 127.0.0.1 203.0.113.1 10.0.0.1; do Valid_Server_IP "$ip" || exit 1; done; '
                  'for ip in 256.1.1.1 01.2.3.4 0.0.0.0 1.2.3 1.2.3.4x; do Valid_Server_IP "$ip" && exit 1; done; :')
        env = dict(self.env, LNMP_Auto="", PhpMyAdmin_Mode="", Default_Server_IP="bad")
        result = self.bash('Default_Security_Selection && echo "MODE=$PhpMyAdmin_Mode IP=$Default_Server_IP"',
                           env=env, input="9\n\n203.0.113.4\n")
        self.assertIn("MODE=random IP=203.0.113.4", result.stdout)
        env.update(PhpMyAdmin_Mode="basic", PhpMyAdmin_Auth_User="admin", Default_Server_IP="127.0.0.1")
        result = self.bash("Default_Security_Selection", env=env, input="a\nb\nsecret\nsecret\n")
        self.assertIn("Passwords do not match", result.stdout)

    def test_security_files_cannot_be_in_document_root(self):
        self.env["LNMP_Security_Dir"] = str(self.web / "secrets")
        self.assertNotEqual(self.bash("Prepare_Default_Security", check=False).returncode, 0)

    def test_certificate_and_config_failure(self):
        self.security.mkdir()
        result = self.bash('openssl() { return 1; }; Configure_Default_Security', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.security / "security.conf").exists())
        self.assertNotEqual(self.bash('Configure_Default_Nginx /nonexistent/path', check=False).returncode, 0)
        self.env["Stack"] = "lnmp"
        result = self.bash('Create_Default_Certificate() { :; }; Configure_Default_Nginx() { :; }; '
                           '/usr/local/nginx/sbin/nginx() { return 1; }; Configure_Default_Security', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.security / "security.conf").exists())

    def test_apache22_configuration_branch(self):
        self.prepare("basic")
        conf = self.root / "apache22"
        (conf / "extra").mkdir(parents=True)
        (conf / "httpd.conf").write_text("#Include conf/extra/httpd-ssl.conf\n")
        self.env["ApacheSelect"] = "1"
        self.bash(f'Configure_Default_Apache {shlex.quote(str(conf))}')
        vhosts = (conf / "extra/httpd-vhosts.conf").read_text()
        self.assertTrue(vhosts.startswith("NameVirtualHost *:80"))
        self.assertIn("Order allow,deny", vhosts)
        self.assertNotIn("Require all granted", vhosts)
        self.assertIn("Require valid-user", vhosts)
        self.assertEqual((conf / "httpd.conf").read_text(), "Include conf/extra/httpd-ssl.conf\n")

    def test_install_tools_and_upgrade_preserve_both_modes_and_legacy(self):
        for mode in ("random", "basic", "legacy"):
            with self.subTest(mode=mode):
                self.run_upgrade_case(mode)

    def run_upgrade_case(self, mode):
        # Exercise the real installer tool extraction, homepage handling and upgrader.
        if self.security.exists():
            shutil.rmtree(self.security)
        shutil.rmtree(self.web)
        self.web.mkdir()
        fixture = self.root / "fixture"
        fixture.mkdir(exist_ok=True)
        (fixture / "src").mkdir(exist_ok=True)
        (fixture / "conf").mkdir(exist_ok=True)
        for name in ("index.html", "config.inc.php", "lnmp.gif", "ocp.php"):
            shutil.copy(REPO / "conf" / name, fixture / "conf" / name)
        version = "phpMyAdmin-5.2.3-all-languages"
        package = fixture / "src" / version
        package.mkdir(exist_ok=True)
        (package / "index.php").write_text("<?php echo 'original';")
        subprocess.run(["tar", "cJf", str(fixture / "src" / f"{version}.tar.xz"), "-C",
                        str(fixture / "src"), version], check=True)
        shutil.rmtree(package)
        self.env.update(PhpMyAdmin_Mode="random" if mode == "legacy" else mode,
                        PhpMyAdmin_Auth_User="admin", PhpMyAdmin_Auth_Password="secret")
        result = self.bash(f'cur_dir={shlex.quote(str(fixture))}; PHPSelect=14; PhpMyAdmin_Ver={version}; '
                           f'source {shlex.quote(str(REPO / "include/php.sh"))}; '
                           'Default_Security_Selection && Creat_PHP_Tools && Save_Default_Security && '
                           'echo "ENTRY=$PhpMyAdmin_Dir"')
        entry = result.stdout.split("ENTRY=")[1].strip()
        homepage = (self.web / "index.html").read_text()
        if mode != "basic":
            self.assertNotIn(entry, homepage)
            self.assertNotIn("/phpmyadmin/", homepage)
            self.assertFalse((self.web / "phpmyadmin").exists())
        self.assertIn("'auth_type'] = 'cookie'", (self.web / entry / "config.inc.php").read_text())
        if mode == "legacy":
            (self.web / entry).rename(self.web / "phpmyadmin")
            (self.security / "security.conf").unlink()
            entry = "phpmyadmin"
        original_config = (self.web / entry / "config.inc.php").read_bytes()
        new_version = "phpMyAdmin-5.2.4-all-languages"
        package = fixture / "src" / new_version
        package.mkdir(exist_ok=True)
        (package / "index.php").write_text("<?php echo 'updated';")
        subprocess.run(["tar", "cJf", str(fixture / "src" / f"{new_version}.tar.xz"), "-C",
                        str(fixture / "src"), new_version], check=True)
        shutil.rmtree(package)
        auth_before = ((self.security / "phpmyadmin.htpasswd").read_bytes() if mode == "basic" else None)
        self.bash(f'cur_dir={shlex.quote(str(fixture))}; Upgrade_Date=20261026; '
                  f'source {shlex.quote(str(REPO / "include/upgrade_phpmyadmin.sh"))}; '
                  'Press_Start() { :; }; Verify_Download_File() { :; }; Echo_Green() { echo "$*"; }; '
                  'Upgrade_phpMyAdmin', input="5.2.4\n")
        self.assertIn("updated", (self.web / entry / "index.php").read_text())
        self.assertEqual(original_config, (self.web / entry / "config.inc.php").read_bytes())
        self.assertEqual(len(list((self.security / "backups").glob("*/phpmyadmin/index.php"))), 1)
        if mode == "basic":
            self.assertEqual(auth_before, (self.security / "phpmyadmin.htpasswd").read_bytes())
            # A failed extraction must leave the installed directory untouched.
            (fixture / "src" / f"{new_version}.tar.xz").write_bytes(b"broken archive")
            result = self.bash(f'cur_dir={shlex.quote(str(fixture))}; Upgrade_Date=20261026; '
                               f'source {shlex.quote(str(REPO / "include/upgrade_phpmyadmin.sh"))}; '
                               'Press_Start() { :; }; Verify_Download_File() { :; }; '
                               'Upgrade_phpMyAdmin', input="5.2.4\n", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("updated", (self.web / entry / "index.php").read_text())
        else:
            self.assertNotIn(entry, (self.web / "index.html").read_text())


@unittest.skipUnless((TOOLS / "usr/sbin/nginx").exists() and os.geteuid() == 0,
                     "Set LNMP_TEST_TOOLS to extracted server packages; integration requires root")
class ServerIntegrationTests(SecurityFixture):
    # Keep unit tests in their own class, sharing only the fixture helpers.
    def setUp(self):
        super().setUp()
        self.env["LD_LIBRARY_PATH"] = str(TOOLS / "usr/lib/x86_64-linux-gnu")
        self.processes = []
        self.addCleanup(self.stop_servers)

    def stop_servers(self):
        for process, log in reversed(self.processes):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            log.close()

    def port(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def start(self, command, port):
        log = (self.root / f"process-{port}.log").open("w+")
        process = subprocess.Popen(command, env=self.env, stdout=log, stderr=log, start_new_session=True)
        self.processes.append((process, log))
        for _ in range(100):
            if process.poll() is not None:
                log.seek(0)
                self.fail(log.read())
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    return
            except OSError:
                time.sleep(0.03)
        self.fail("Server did not start")

    def request(self, port, path, *, tls=True, auth=None):
        connection = (http.client.HTTPSConnection("127.0.0.1", port, context=ssl._create_unverified_context())
                      if tls else http.client.HTTPConnection("127.0.0.1", port))
        headers = {"Host": "127.0.0.1"}
        if auth:
            headers["Authorization"] = "Basic " + base64.b64encode(auth.encode()).decode()
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode()
        connection.close()
        return result

    def apache(self, port, *, frontend=False):
        conf = self.root / f"apache-{port}" / "conf"
        (conf / "extra").mkdir(parents=True)
        modules = TOOLS / "usr/lib/apache2/modules"
        module_names = ["mpm_prefork", "authn_core", "authn_file", "authz_core", "authz_host",
                        "authz_user", "auth_basic", "access_compat", "dir", "mime", "rewrite",
                        "ssl", "socache_shmcb", "setenvif", "filter", "deflate"]
        text = f'ServerRoot "{conf.parent}"\nServerName 127.0.0.1\nPidFile "{conf}/pid"\n'
        text += f'Listen 127.0.0.1:{port}\nErrorLog "{conf}/error.log"\nUser www-data\nGroup www-data\n'
        text += "".join(f'LoadModule {name}_module "{modules}/mod_{name}.so"\n' for name in module_names)
        text += f'LoadModule php_module "{modules}/libphp8.4.so"\n'
        text += 'TypesConfig /etc/mime.types\nAddType application/x-httpd-php .php\n'
        text += '<FilesMatch "\\.php$">\nSetHandler application/x-httpd-php\n</FilesMatch>\n'
        if frontend:
            (conf / "extra/httpd-ssl.conf").write_text(f"Listen 127.0.0.1:{self.https}\nSSLSessionCache none\n")
            (conf / "httpd.conf").write_text(text + '#Include conf/extra/httpd-ssl.conf\nInclude conf/extra/httpd-vhosts.conf\n')
            self.env.update(ApacheSelect="2", Stack="lamp")
            self.bash(f'Configure_Default_Apache {shlex.quote(str(conf))}')
            generated = (conf / "extra/httpd-vhosts.conf").read_text()
            generated = generated.replace("*:80", f"*:{port}").replace("*:443", f"*:{self.https}")
            generated = generated.replace("/home/wwwlogs", str(conf))
            (conf / "extra/httpd-vhosts.conf").write_text(generated)
        else:
            # Use the repo's backend virtual host and HTTPS propagation setting.
            backend = (REPO / "conf/httpd-vhosts-lnmpa.conf").read_text()
            backend = backend.replace("NameVirtualHost *:88", "").replace("*:88", f"*:{port}")
            backend = backend.replace("/home/wwwroot/default", str(self.web)).replace("/home/wwwlogs", str(conf))
            (conf / "httpd.conf").write_text(text + 'SetEnvIf X-Forwarded-Proto https HTTPS=on\n' + backend)
        result = subprocess.run([str(TOOLS / "usr/sbin/apache2"), "-t", "-f", str(conf / "httpd.conf")],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.start([str(TOOLS / "usr/sbin/apache2"), "-f", str(conf / "httpd.conf"), "-DFOREGROUND"], port)

    def nginx(self, stack):
        conf = self.root / "nginx"
        conf.mkdir()
        (conf / "vhost").mkdir()
        source = "nginx_a.conf" if stack == "lnmpa" else "nginx.conf"
        text = (REPO / "conf" / source).read_text()
        text = text.replace("www www", "www-data www-data").replace("/home/wwwroot/default", str(self.web))
        text = text.replace("/home/wwwlogs", str(conf)).replace("/usr/local/nginx/logs/nginx.pid", str(conf / "pid"))
        temp_paths = "".join(f'        {name}_temp_path "{conf}/{name}";\n'
                             for name in ("client_body", "proxy", "fastcgi", "uwsgi", "scgi"))
        text = text.replace('        default_type', temp_paths + '        default_type')
        (conf / "nginx.conf").write_text(text)
        for name in ("enable-php.conf", "proxy-pass-php.conf", "proxy.conf"):
            text = (REPO / "conf" / name).read_text().replace("127.0.0.1:88", f"127.0.0.1:{self.backend}")
            (conf / name).write_text(text)
        for name in ("fastcgi.conf", "mime.types"):
            shutil.copy(TOOLS / "etc/nginx" / name, conf / name)
        (conf / "enable-php.conf").write_text((conf / "enable-php.conf").read_text().replace(
            "unix:/tmp/php-cgi.sock", f"127.0.0.1:{self.backend}"))
        self.env["Stack"] = stack
        self.bash(f'Configure_Default_Nginx {shlex.quote(str(conf))}')
        for name in ("nginx.conf", "default-http.conf", "default-security.conf"):
            path = conf / name
            path.write_text(path.read_text().replace("listen 80 default_server", f"listen 127.0.0.1:{self.http} default_server")
                            .replace("listen 443 ssl default_server", f"listen 127.0.0.1:{self.https} ssl default_server")
                            .replace("127.0.0.1:88", f"127.0.0.1:{self.backend}"))
        command = [str(TOOLS / "usr/sbin/nginx"), "-p", str(conf) + "/", "-c", "nginx.conf"]
        result = subprocess.run(command + ["-t"], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.start(command + ["-g", "daemon off;"], self.http)

    def test_http_https_and_auth_all_stacks(self):
        for stack in ("lnmp", "lnmpa", "lamp"):
            for mode in ("random", "basic"):
                with self.subTest(stack=stack, mode=mode):
                    try:
                        self.run_server_case(stack, mode)
                    finally:
                        self.stop_servers()
                        self.processes.clear()
                        if (self.root / "nginx").exists():
                            shutil.rmtree(self.root / "nginx")
                        shutil.rmtree(self.web)
                        self.web.mkdir()

    def run_server_case(self, stack, mode):
        self.prepare(mode)
        self.http, self.https, self.backend = self.port(), self.port(), self.port()
        entry = self.web / self.entry
        entry.mkdir()
        (self.web / "index.html").write_text("default homepage")
        (self.web / "p.php").write_text("<?php echo 'outside';")
        (entry / "index.php").write_text("<?php echo 'protected-php HTTPS=' . ($_SERVER['HTTPS'] ?? 'off');")
        (entry / "asset.css").write_text("protected-css")
        (entry / ".secret").write_text("hidden")
        (entry / ".htaccess").write_text("Require all granted\n")
        if stack == "lamp":
            self.apache(self.http, frontend=True)
        else:
            if stack == "lnmpa":
                self.apache(self.backend)
            else:
                pool = self.root / "fpm.conf"
                pool.write_text(f"[global]\nerror_log={self.root}/fpm.log\n[www]\nuser=www-data\ngroup=www-data\n"
                                f"listen=127.0.0.1:{self.backend}\npm=static\npm.max_children=1\n")
                self.start([str(TOOLS / "usr/sbin/php-fpm8.4"), "-F", "-y", str(pool), "-n"], self.backend)
            self.nginx(stack)
        path = f"/{self.entry}/"
        status, headers, body = self.request(self.http, path + "?a=1%202&b=x", tls=False)
        self.assertEqual(status, 301)
        self.assertEqual(headers["Location"], f"https://127.0.0.1{path}?a=1%202&b=x")
        self.assertEqual(self.request(self.https, "/")[0], 200)
        self.assertEqual(self.request(self.https, "/p.php")[2], "outside")
        auth = "admin:" + self.env["PhpMyAdmin_Auth_Password"]
        for suffix in ("", "index.php", "asset.css"):
            if mode == "basic":
                self.assertEqual(self.request(self.https, path + suffix)[0], 401)
                self.assertEqual(self.request(self.https, path + suffix, auth="admin:wrong")[0], 401)
            status, _, body = self.request(self.https, path + suffix, auth=auth if mode == "basic" else None)
            self.assertEqual(status, 200, body)
            self.assertIn("protected-css" if suffix == "asset.css" else "protected-php HTTPS=on", body)
        if mode == "random":
            self.assertEqual(self.request(self.https, "/phpmyadmin/")[0], 404)
        else:
            status, headers, _ = self.request(self.https, "/phpmyadmin?x=1")
            self.assertIn(status, (301, 401))
            if status == 301:
                self.assertEqual(headers["Location"], "https://127.0.0.1/phpmyadmin/?x=1")
        if stack != "lamp":
            self.assertEqual(self.request(self.https, path + ".secret", auth=auth)[0], 403)


if __name__ == "__main__":
    unittest.main()
