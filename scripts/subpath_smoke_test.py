#!/usr/bin/env python3
"""Exercise the actual image behind a prefix-preserving proxy, then upgrade real DB data."""

import base64
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = Path(__file__).resolve().parents[1]
MOUNT = "/memo"
USERNAME = "subpath-admin"
PASSWORD = "subpath-test-password"


class IdentityProvider(BaseHTTPRequestHandler):
    """Test-only OAuth authorization code, PKCE, token and OIDC UserInfo endpoints."""

    codes = {}

    def log_message(self, *_):
        pass  # Do not log authorization codes or state.

    def do_GET(self):
        request = urllib.parse.urlsplit(self.path)
        if request.path == "/oidc/auth":
            params = dict(urllib.parse.parse_qsl(request.query))
            callback = urllib.parse.urlsplit(params["redirect_uri"])
            assert callback.hostname == "127.0.0.1" and callback.path == MOUNT + "/auth/callback"
            assert params["client_id"] == "subpath-test" and params["response_type"] == "code"
            assert params["code_challenge_method"] == "S256"
            assert "openid" in params["scope"].split()
            code = uuid.uuid4().hex
            self.codes[code] = (params["redirect_uri"], params["code_challenge"])
            query = urllib.parse.urlencode({"code": code, "state": params["state"]})
            self.send_response(302)
            self.send_header("Location", f"{params['redirect_uri']}?{query}")
            self.end_headers()
        elif request.path == "/oidc/me" and self.headers.get("Authorization") == "Bearer fixture-access-token":
            self.respond({"sub": "oidc-user", "name": "OIDC Test User"})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/oidc/token":
            self.send_error(404)
            return
        form = dict(urllib.parse.parse_qsl(self.rfile.read(int(self.headers["Content-Length"])).decode()))
        basic = "Basic " + base64.b64encode(b"subpath-test:fixture-client-secret").decode()
        assert self.headers.get("Authorization") == basic
        assert form["grant_type"] == "authorization_code"
        expected = self.codes.pop(form["code"])
        challenge = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest()).decode().rstrip("=")
        assert expected == (form["redirect_uri"], challenge)
        self.respond({"access_token": "fixture-access-token", "token_type": "Bearer"})

    def respond(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


class Client:
    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.token = ""

    def open(self, path, data=None, headers=None):
        headers = dict(headers or {})
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        if data is not None:
            headers.setdefault("Content-Type", "application/json")
            data = json.dumps(data).encode()
        request = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            return self.http.open(request, timeout=12)
        except urllib.error.HTTPError as response:
            return response

    def request(self, path, data=None, headers=None, status=200):
        with self.open(path, data, headers) as response:
            assert response.status == status, f"{path}: expected {status}, got {response.status}"
            return response.read(), response.headers

    def api(self, path, data=None):
        body, _ = self.request("/api" + path, data)
        return json.loads(body)

    def create_admin(self):
        assert self.api("/users", {"username": USERNAME, "password": PASSWORD})["role"] == "ADMIN"

    def signin(self):
        data = {"passwordCredentials": {"username": USERNAME, "password": PASSWORD}}
        body, headers = self.request("/api/auth/signin", data)
        self.token = json.loads(body)["accessToken"]
        return headers

    def memo(self, memo_id, content):
        memo = self.api(f"/memos?memoId={memo_id}", {"content": content, "visibility": "PRIVATE"})
        assert memo["name"] == f"memos/{memo_id}"


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def wait_ready(client):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with client.open("/healthz") as response:
                if response.status == 200 and response.read() == b"Service ready.":
                    return
        except OSError:
            pass
        time.sleep(1)
    raise AssertionError(f"{client.base}/healthz did not become ready")


def proxy_checks(origin):
    client = Client(origin + MOUNT)
    outside = Client(origin)
    outside.request("/healthz", status=404)
    outside.request("/memo-other/healthz", status=404)
    outside.request("/memo%2Fhealthz", status=404)
    with outside.open(MOUNT + "?source=smoke") as response:
        assert response.url == client.base + "/?source=smoke"
    for path in ("/", "/memos/smoke", "/auth/callback", "/spaces/example/views"):
        html, headers = client.request(path)
        assert "text/html" in headers["Content-Type"] and b'id="root"' in html
        script = re.search(rb'src="(/memo/assets/[^"]+\.js)"', html)[1].decode()
        _, js_headers = outside.request(script)
        assert "javascript" in js_headers["Content-Type"]
        assert "immutable" in js_headers["Cache-Control"]
    manifest = json.loads(client.request("/site.webmanifest")[0])
    for field in ("scope", "start_url"):
        assert urllib.parse.urljoin(client.base + "/site.webmanifest", manifest[field]) == client.base + "/"
    for icon in manifest["icons"]:
        _, headers = client.request("/" + icon["src"].removeprefix("./"))
        assert headers["Content-Type"] == "image/png"
    client.create_admin()
    headers = client.signin()
    cookie = headers["Set-Cookie"]
    assert f"Path={MOUNT};" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
    old = next(iter(client.jar)).value
    assert client.api("/auth/refresh", {})["accessToken"] and next(iter(client.jar)).value != old

    connect = {"Connect-Protocol-Version": "1"}
    with client.open("/api/sse") as stream:
        assert stream.status == 200 and stream.headers["Content-Type"] == "text/event-stream"
        assert stream.readline() == b": connected\n" and stream.readline() == b"\n"
        client.memo("smoke", "Subpath browser smoke")
        assert b"memo.changed" in stream.readline()

    content = b"attachment smoke bytes"
    body, _ = client.request("/memos.api.AttachmentService/UploadAttachment", {
        "spec": {"attachment": {"filename": "notes #1.txt", "type": "text/plain"}, "totalSize": str(len(content))},
        "data": base64.b64encode(content).decode(),
        "finishWrite": True,
    }, connect)
    attachment = json.loads(body)["attachment"]
    path = f"/file/{attachment['name']}/{urllib.parse.quote(attachment['filename'])}"
    assert client.request(path)[0] == content
    Client(client.base).request(path, status=404)
    share = client.api("/memos/smoke/shares", {})
    share_token = share["name"].split("/")[-1]
    assert Client(client.base).api(f"/shares/{share_token}/memo")["name"] == "memos/smoke"

    tool = "memo_list_memos"
    body, _ = client.request("/mcp", {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool, "arguments": {}, "_meta": {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientInfo": {"name": "subpath-smoke", "version": "1.0.0"},
            "io.modelcontextprotocol/clientCapabilities": {},
        }},
    }, {"Mcp-Method": "tools/call", "Mcp-Name": tool, "Accept": "application/json, text/event-stream"})
    assert any(m["name"] == "memos/smoke" for m in json.loads(body)["result"]["structuredContent"]["memos"])

    client.request("/api/auth/signout", {})
    assert not list(client.jar)
    client.request("/api/auth/refresh", {}, status=401)
    print("PASS SQLite, prefixed proxy, PWA assets, auth cookies, refresh, sign-out, REST, Connect upload, attachment ACL, sharing, SSE and MCP", flush=True)


def test_image(image, browser):
    network = "memos-subpath-" + uuid.uuid4().hex[:12]
    containers = []
    docker("network", "create", network)

    def start(alias, image_name, port=None, options=(), command=()):
        name = f"{network}-{alias}"
        published = ["-p", f"127.0.0.1::{port}"] if port else []
        docker("run", "-d", "--name", name, "--network", network, "--network-alias", alias,
               *published, *options, image_name, *command)
        containers.append(name)
        origin = "http://" + docker("port", name, f"{port}/tcp") if port else None
        return name, origin

    try:
        _, direct = start("app", image, 5230, ["-e", "MEMOS_INSTANCE_URL=http://localhost", "-e", "NO_PROXY=localhost,127.0.0.1,oidc"])
        wait_ready(Client(direct + MOUNT))
        nginx = """server {
            listen 80;
            location / {
                proxy_pass http://app:5230;
                proxy_http_version 1.1;
                proxy_set_header Host $http_host;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_buffering off;
            }
        }"""
        _, origin = start("proxy", "nginx:alpine", 80,
                          command=["sh", "-c", 'printf "%s" "$1" > /etc/nginx/conf.d/default.conf; exec nginx -g "daemon off;"', "nginx", nginx])
        wait_ready(Client(origin + MOUNT))
        proxy_checks(origin)

        if browser:
            _, idp = start("oidc", "python:3.12-alpine", 8000, [
                "--mount", f"type=bind,src={Path(__file__).resolve()},dst=/smoke.py,readonly",
            ], ["python", "/smoke.py", "--idp"])
            client = Client(origin + MOUNT)
            client.signin()
            result = client.api("/identity-providers?identityProviderId=smoke", {
                "type": "OAUTH2", "title": "Test OIDC", "config": {"oauth2Config": {
                    "clientId": "subpath-test", "clientSecret": "fixture-client-secret",
                    "authUrl": idp + "/oidc/auth", "tokenUrl": "http://oidc:8000/oidc/token",
                    "userInfoUrl": "http://oidc:8000/oidc/me", "scopes": ["openid", "profile"],
                    "fieldMapping": {"identifier": "sub", "displayName": "name"},
                }},
            })
            assert result["name"] == "identity-providers/smoke"
            env = dict(os.environ, MEMOS_SMOKE_ORIGIN=origin, MEMOS_SMOKE_USERNAME=USERNAME, MEMOS_SMOKE_PASSWORD=PASSWORD)
            subprocess.run(["pnpm", "exec", "playwright", "test", "--config", "tests/browser/subpath.config.ts"],
                           cwd=ROOT / "web", env=env, check=True)
            print("PASS browser password login, deep refresh, OAuth callback, PKCE and token/UserInfo exchange", flush=True)

        pg, _ = start("postgres", "postgres:17-alpine", options=[
            "-e", "POSTGRES_USER=memos", "-e", "POSTGRES_PASSWORD=fixture-password", "-e", "POSTGRES_DB=memos",
        ])
        pg_dsn = "postgresql://memos:fixture-password@postgres:5432/memos?sslmode=disable"
        db_options = ["-e", "MEMOS_DRIVER=postgres", "-e", f"MEMOS_DSN={pg_dsn}"]
        for _ in range(90):
            probe = subprocess.run(["docker", "exec", pg, "pg_isready", "-h", "127.0.0.1", "-U", "memos"],
                                   stdout=subprocess.DEVNULL)
            if probe.returncode == 0:
                break
            time.sleep(1)
        else:
            raise AssertionError("PostgreSQL did not become ready")
        old_name, old_origin = start("previous", "ghcr.io/usememos/memos:26.10.0", 5230, db_options)
        old_client = Client(old_origin)
        wait_ready(old_client)
        old_client.create_admin()
        old_client.signin()
        old_client.memo("before-upgrade", "PostgreSQL data before upgrade")
        old_attachment = old_client.api("/attachments?attachmentId=historical", {
            "filename": "old.txt", "type": "text/plain", "content": base64.b64encode(b"historical attachment").decode(),
        })
        docker("rm", "-fv", old_name)
        containers.remove(old_name)
        current_name, current_origin = start("upgraded", image, 5230, db_options)
        upgraded = Client(current_origin + MOUNT)
        wait_ready(upgraded)
        migration_log = subprocess.check_output(["docker", "logs", current_name], stderr=subprocess.STDOUT, text=True)
        assert "migration completed" in migration_log, "no incremental migrations were applied"
        upgraded.signin()
        assert upgraded.api("/memos/before-upgrade")["content"] == "PostgreSQL data before upgrade"
        assert upgraded.request(f"/file/{old_attachment['name']}/old.txt")[0] == b"historical attachment"
        print("PASS PostgreSQL incremental migration from 26.10.0, pre-existing memo and attachment", flush=True)

        mysql_name, _ = start("mysql", "mysql:8.4", options=[
            "-e", "MYSQL_ROOT_PASSWORD=fixture-root", "-e", "MYSQL_USER=memos",
            "-e", "MYSQL_PASSWORD=fixture-password", "-e", "MYSQL_DATABASE=memos",
        ])
        for _ in range(120):
            probe = subprocess.run(["docker", "exec", mysql_name, "mysqladmin", "ping", "-h", "127.0.0.1", "--silent"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if probe.returncode == 0:
                break
            time.sleep(1)
        else:
            raise AssertionError("MySQL did not become ready")
        _, mysql_origin = start("mysql-app", image, 5230, [
            "-e", "MEMOS_DRIVER=mysql", "-e", "MEMOS_DSN=memos:fixture-password@tcp(mysql:3306)/memos",
        ])
        mysql = Client(mysql_origin + MOUNT)
        wait_ready(mysql)
        mysql.create_admin()
        mysql.signin()
        mysql.memo("mysql-smoke", "MySQL memo")
        assert mysql.api("/memos/mysql-smoke")["content"] == "MySQL memo"
        print("PASS MySQL fresh schema and memo round trip", flush=True)
    except Exception:
        for name in containers:
            subprocess.run(["docker", "logs", "--tail", "30", name], check=False)
        raise
    finally:
        for name in reversed(containers):
            subprocess.run(["docker", "rm", "-fv", name], stdout=subprocess.DEVNULL, check=False)
        subprocess.run(["docker", "network", "rm", network], stdout=subprocess.DEVNULL, check=False)


if __name__ == "__main__":
    if sys.argv[1:] == ["--idp"]:
        HTTPServer(("0.0.0.0", 8000), IdentityProvider).serve_forever()
    elif len(sys.argv) in (2, 3) and (len(sys.argv) == 2 or sys.argv[2] == "--browser"):
        test_image(sys.argv[1], len(sys.argv) == 3)
    else:
        sys.exit(f"Usage: {sys.argv[0]} IMAGE [--browser]")
