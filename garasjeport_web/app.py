#!/usr/bin/env python3
"""Garasjeport Web - minimal nettside med en knapp som trykker HA-knappen.

"Auth" er kun brukernavn (bevisst valg). Brukernavnet er i praksis et delt
passord, sa lengden pa det er hele sikkerheten. Sammenligning er
konstant-tid for a unnga at man kan gjette tegn for tegn via timing.
"""
import http.server
import json
import os
import secrets
import socketserver
import time
import urllib.error
import urllib.parse
import urllib.request

USERNAME = os.environ.get("GP_USERNAME", "")
ENTITY = os.environ.get("GP_ENTITY", "button.garasjeport_garasjeport_apne")
COOLDOWN = int(os.environ.get("GP_COOLDOWN", "5") or 0)
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
HA_URL = os.environ.get("GP_HA_URL", "http://supervisor/core/api")
COOKIE = "gp_user"

_last_open = 0.0


def valid(name):
    if not USERNAME or not name:
        return False
    return secrets.compare_digest(name.strip(), USERNAME.strip())


def press():
    """Kall HA-tjenesten. Returnerer (ok, melding)."""
    global _last_open
    now = time.monotonic()
    if COOLDOWN and (now - _last_open) < COOLDOWN:
        venting = int(COOLDOWN - (now - _last_open)) + 1
        return False, "Vent %d s (sperre mot dobbelttrykk)" % venting
    body = json.dumps({"entity_id": ENTITY}).encode()
    req = urllib.request.Request(
        HA_URL + "/services/button/press",
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + SUPERVISOR_TOKEN,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            if 200 <= r.status < 300:
                _last_open = now
                return True, "Signal sendt til porten"
            return False, "HA svarte HTTP %d" % r.status
    except urllib.error.HTTPError as e:
        return False, "HA-feil HTTP %d: %s" % (e.code, e.read()[:200].decode("utf-8", "replace"))
    except Exception as e:  # nettverk, DNS, timeout
        return False, "Naadde ikke HA: %s" % e


PAGE = """<!doctype html>
<html lang="no"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Garasjeport</title>
<style>
:root{--bg:#f4f4f5;--card:#fff;--fg:#18181b;--dim:#71717a;--line:#e4e4e7;
      --accent:#0f766e;--accent2:#115e59;--err:#b91c1c;--ok:#15803d}
@media(prefers-color-scheme:dark){:root{--bg:#09090b;--card:#18181b;--fg:#fafafa;
      --dim:#a1a1aa;--line:#27272a;--accent:#14b8a6;--accent2:#0d9488;
      --err:#f87171;--ok:#4ade80}}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;
     background:var(--bg);color:var(--fg);
     font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;
      padding:32px 28px;width:100%;max-width:380px;text-align:center;
      box-shadow:0 1px 3px rgba(0,0,0,.08)}
h1{margin:0 0 4px;font-size:20px;letter-spacing:-.01em}
p.sub{margin:0 0 26px;color:var(--dim);font-size:14px}
button.big{width:180px;height:180px;border-radius:50%;border:none;cursor:pointer;
      background:var(--accent);color:#fff;font-size:17px;font-weight:600;
      letter-spacing:.01em;transition:transform .08s,background .15s;
      -webkit-tap-highlight-color:transparent}
button.big:hover{background:var(--accent2)}
button.big:active{transform:scale(.96)}
button.big:disabled{opacity:.55;cursor:not-allowed}
.icon{display:block;font-size:40px;margin-bottom:6px;line-height:1}
input{width:100%;padding:12px 14px;font-size:16px;border-radius:10px;
      border:1px solid var(--line);background:var(--bg);color:var(--fg);margin-bottom:12px}
input:focus{outline:2px solid var(--accent);outline-offset:1px}
button.go{width:100%;padding:12px;font-size:16px;font-weight:600;border:none;
      border-radius:10px;background:var(--accent);color:#fff;cursor:pointer}
#msg{margin-top:20px;min-height:22px;font-size:14px;font-weight:500}
.ok{color:var(--ok)}.err{color:var(--err)}
footer{margin-top:22px;font-size:12px;color:var(--dim)}
a{color:var(--dim)}
</style></head><body><div class="card">__BODY__</div>
<script>
var b=document.getElementById('open');
if(b){b.addEventListener('click',function(){
  var m=document.getElementById('msg');
  b.disabled=true;m.className='';m.textContent='Sender...';
  fetch('open',{method:'POST'}).then(function(r){return r.json()})
  .then(function(d){m.className=d.ok?'ok':'err';m.textContent=(d.ok?'\\u2713 ':'\\u2717 ')+d.msg})
  .catch(function(e){m.className='err';m.textContent='\\u2717 Nettverksfeil'})
  .then(function(){setTimeout(function(){b.disabled=false},2000)})
})}
</script></body></html>"""

LOGIN = """<h1>Garasjeport</h1>
<p class="sub">Skriv inn brukernavn</p>
<form method="POST" action="login">
<input name="u" autocomplete="off" autocapitalize="off" autocorrect="off"
       spellcheck="false" placeholder="brukernavn" autofocus>
<button class="go" type="submit">Fortsett</button>
</form>__ERR__"""

BUTTON = """<h1>Garasjeport</h1>
<p class="sub">1A &middot; trykk for a apne</p>
<button class="big" id="open"><span class="icon">&#9650;</span>APNE</button>
<div id="msg"></div>
<footer>Porten lukker seg selv &middot; <a href="logout">logg ut</a></footer>"""


class H(http.server.BaseHTTPRequestHandler):
    server_version = "gp/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):  # kortere logg til add-on-loggen
        print("%s - %s" % (self.address_string(), fmt % a), flush=True)

    # -- hjelpere -------------------------------------------------------
    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        raw = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _page(self, inner, extra=None, code=200):
        self._send(code, PAGE.replace("__BODY__", inner), extra=extra)

    def _authed(self):
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k == COOKIE:
                    return valid(urllib.parse.unquote(v))
        return False

    def _setcookie(self, value, maxage=31536000):
        return [("Set-Cookie",
                 "%s=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=%d"
                 % (COOKIE, urllib.parse.quote(value), maxage))]

    def _path(self):
        return urllib.parse.urlparse(self.path)

    # -- ruter ----------------------------------------------------------
    def do_GET(self):
        p = self._path()
        route = p.path.rstrip("/") or "/"
        if route == "/logout":
            self._page(LOGIN.replace("__ERR__", ""),
                       extra=[("Set-Cookie", "%s=; Path=/; Max-Age=0" % COOKIE)])
            return
        if route == "/health":
            self._send(200, json.dumps({"ok": True}), "application/json")
            return
        if route != "/":
            self._send(404, "<h1>404</h1>", "text/html; charset=utf-8")
            return
        # ?u=<brukernavn> gir ett-klikks bokmerke
        q = urllib.parse.parse_qs(p.query).get("u", [""])[0]
        if q:
            if valid(q):
                self._page(BUTTON, extra=self._setcookie(q))
            else:
                time.sleep(1)
                self._page(LOGIN.replace(
                    "__ERR__", '<div id="msg" class="err">Ukjent brukernavn</div>'),
                    code=401)
            return
        if self._authed():
            self._page(BUTTON)
        else:
            self._page(LOGIN.replace("__ERR__", ""))

    def do_POST(self):
        route = self._path().path.rstrip("/") or "/"
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        if route == "/login":
            name = urllib.parse.parse_qs(raw).get("u", [""])[0]
            if valid(name):
                self._page(BUTTON, extra=self._setcookie(name))
            else:
                time.sleep(1)  # bremser gjetting
                self._page(LOGIN.replace(
                    "__ERR__", '<div id="msg" class="err">Ukjent brukernavn</div>'),
                    code=401)
            return
        if route == "/open":
            if not self._authed():
                self._send(401, json.dumps({"ok": False, "msg": "Ikke innlogget"}),
                           "application/json")
                return
            ok, msg = press()
            print("APNE fra %s -> %s (%s)" % (self.address_string(), ok, msg), flush=True)
            self._send(200 if ok else 503,
                       json.dumps({"ok": ok, "msg": msg}), "application/json")
            return
        self._send(404, json.dumps({"ok": False, "msg": "ukjent"}), "application/json")


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    if not USERNAME or USERNAME.startswith("BYTT-MEG"):
        print("ADVARSEL: brukernavn er ikke satt/endret - alle blir avvist", flush=True)
    print("Lytter på :8099, entity=%s, cooldown=%ds" % (ENTITY, COOLDOWN), flush=True)
    Server(("0.0.0.0", 8099), H).serve_forever()
