import http.server
import socket
import threading
import unittest
from types import SimpleNamespace

from kisenone_status.services import check_http, check_systemd, check_tcp, services_section
from kisenone_status.timeutil import fixed_tz

JST = fixed_tz(540)
NOW = 1794711600  # 2026-11-15 12:00 JST


def fake_systemctl(stdout):
    return lambda *args, **kwargs: SimpleNamespace(stdout=stdout)


class SystemdTest(unittest.TestCase):
    def test_states(self):
        cases = {
            "LoadState=loaded\nActiveState=active\nResult=success\n": True,
            # timer で動く oneshot が成功して終わった後
            "LoadState=loaded\nActiveState=inactive\nResult=success\n": True,
            "LoadState=loaded\nActiveState=failed\nResult=exit-code\n": False,
            "LoadState=loaded\nActiveState=inactive\nResult=exit-code\n": False,
            # 存在しない unit
            "LoadState=not-found\nActiveState=inactive\nResult=success\n": False,
        }
        for stdout, up in cases.items():
            with self.subTest(stdout=stdout):
                self.assertEqual(check_systemd("x.service", run=fake_systemctl(stdout)), up)

    def test_systemctl_missing_is_down(self):
        def run(*args, **kwargs):
            raise FileNotFoundError("systemctl")

        self.assertFalse(check_systemd("x.service", run=run))


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.end_headers()
            return
        if self.path == "/needs-header":
            self.send_response(200 if self.headers.get("X-Forwarded-Proto") == "https" else 301)
            if self.headers.get("X-Forwarded-Proto") != "https":
                self.send_header("Location", "https://127.0.0.1:1/")
            self.end_headers()
            return
        if self.path == "/needs-ua":
            self.send_response(403 if self.headers.get("User-Agent", "").startswith("Python-urllib") else 200)
            self.end_headers()
            return
        self.send_response(200 if self.path == "/ok" else 404)
        self.end_headers()

    def log_message(self, *args):
        pass


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class HttpTcpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_http_status(self):
        self.assertTrue(check_http(f"{self.base}/ok"))
        self.assertTrue(check_http(f"{self.base}/redirect"))
        self.assertFalse(check_http(f"{self.base}/missing"))
        self.assertFalse(check_http(f"http://127.0.0.1:{free_port()}/"))

    def test_http_extra_headers_are_sent(self):
        self.assertFalse(check_http(f"{self.base}/needs-header"))
        self.assertTrue(check_http(f"{self.base}/needs-header", {"X-Forwarded-Proto": "https"}))

    def test_default_user_agent_is_not_python_urllib(self):
        self.assertTrue(check_http(f"{self.base}/needs-ua"))

    def test_tcp(self):
        self.assertTrue(check_tcp(f"127.0.0.1:{self.server.server_port}"))
        self.assertFalse(check_tcp(f"127.0.0.1:{free_port()}"))


class ServicesSectionTest(unittest.TestCase):
    def test_entries_keep_order_and_flags(self):
        services = [
            {"name": "qkjudge", "url": "https://q.example/", "private": False, "event_only": False, "check": {"type": "http", "target": "up"}},
            {"name": "wakapi", "url": None, "private": True, "event_only": False, "check": {"type": "systemd", "target": "down"}},
            {"name": "inucon", "url": "https://i.example/", "private": False, "event_only": True, "check": {"type": "http", "target": "down"}},
        ]
        section = services_section(services, NOW, JST, check_fn=lambda c: c["target"] == "up")
        at = "2026-11-15T12:00:00+09:00"
        self.assertEqual(
            section,
            [
                {"name": "qkjudge", "up": True, "checked_at": at, "url": "https://q.example/"},
                {"name": "wakapi", "up": False, "checked_at": at, "private": True},
                {"name": "inucon", "up": False, "checked_at": at, "url": "https://i.example/", "event_only": True},
            ],
        )


if __name__ == "__main__":
    unittest.main()
