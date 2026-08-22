#!/usr/bin/env python3
"""Garasjeport Web - nettside med en knapp som apner garasjeporten.

"Auth" er kun brukernavn, uten passord. Brukernavnet er derfor i praksis et
delt passord, og lengden pa det er hele sikkerheten. Hver bruker i lista
identifiseres ved sitt brukernavn, og alt som skjer havner i adgangsloggen.

Konfigurasjon leses fra /data/options.json (add-on-standard). Miljovariabler
med GP_-prefiks overstyrer, slik at appen kan kjores og testes utenfor HA.
"""
import http.server
import json
import os
import secrets
import socketserver
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

OPTIONS_FILE = os.environ.get("GP_OPTIONS", "/data/options.json")
LOG_FILE = os.environ.get("GP_LOG", "/data/access.log")
HA_URL = os.environ.get("GP_HA_URL", "http://supervisor/core/api")
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
COOKIE = "gp_user"

_lock = threading.Lock()
_last_open = 0.0


# --------------------------------------------------------------- config ----
def load_options():
    opts = {}
    try:
        with open(OPTIONS_FILE) as f:
            opts = json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        print("Kunne ikke lese %s: %s" % (OPTIONS_FILE, e), flush=True)

    users = []
    if os.environ.get("GP_USERS"):  # testing: JSON-liste
        users = json.loads(os.environ["GP_USERS"])
    else:
        users = opts.get("users") or []
        # bakoverkompatibelt med v1.x som hadde en enkelt "username"
        if not users and opts.get("username"):
            users = [{"username": opts["username"], "label": "bruker"}]

    clean = []
    for u in users:
        name = str(u.get("username", "")).strip()
        if not name or not u.get("enabled", True):
            continue
        clean.append({"username": name,
                      "label": str(u.get("label") or name).strip()})

    return {
        "users": clean,
        "entity_id": os.environ.get("GP_ENTITY")
                     or opts.get("entity_id", "button.garasjeport_garasjeport_apne"),
        "cooldown": int(os.environ.get("GP_COOLDOWN") or opts.get("cooldown_seconds", 5)),
        "log_max": int(os.environ.get("GP_LOG_MAX") or opts.get("log_max_lines", 5000)),
    }


CFG = load_options()


def whoami(given):
    """Finn brukeren som matcher. Konstant-tid, og sjekker alle for a unnga
    at man kan lese ut treff pa responstiden."""
    if not given:
        return None
    given = given.strip()
    found = None
    for u in CFG["users"]:
        if secrets.compare_digest(given, u["username"]):
            found = found or u
    return found


# ------------------------------------------------------------------ logg ----
def logg(event, user, ip, detail=""):
    """Skriv til add-on-loggen og til /data/access.log (JSONL, roteres)."""
    rec = {
        "t": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "event": event,
        "user": user or "-",
        "ip": ip,
        "detail": detail,
    }
    print("[%s] %-11s user=%-14s ip=%-15s %s"
          % (rec["t"], event, rec["user"], ip, detail), flush=True)
    try:
        with _lock:
            with open(LOG_FILE, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            # enkel rotasjon: behold de nyeste log_max linjene
            with open(LOG_FILE) as f:
                lines = f.readlines()
            if len(lines) > CFG["log_max"]:
                with open(LOG_FILE, "w") as f:
                    f.writelines(lines[-CFG["log_max"]:])
    except Exception as e:
        print("Loggskriving feilet: %s" % e, flush=True)


def les_logg(n=100):
    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    out = []
    for ln in lines[-n:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    out.reverse()
    return out


# ---------------------------------------------------------------- trykk ----
def _get_state():
    req = urllib.request.Request(
        HA_URL + "/states/" + urllib.parse.quote(CFG["entity_id"]),
        headers={"Authorization": "Bearer " + SUPERVISOR_TOKEN},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True, json.loads(r.read()).get("state")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, None
        raise


def press():
    """Trykk knappen i HA. Returnerer (ok, melding).

    HA svarer 2xx pa button.press ogsa nar entity_id ikke finnes, sa vi maa
    sjekke eksistens selv. Etterpa leses state igjen: button-entiteter far
    nytt tidsstempel ved trykk, sa en endring bekrefter at det skjedde.
    """
    global _last_open
    now = time.monotonic()
    if CFG["cooldown"] and (now - _last_open) < CFG["cooldown"]:
        return False, "Vent %d s (sperre mot dobbelttrykk)" % (
            int(CFG["cooldown"] - (now - _last_open)) + 1)

    try:
        finnes, before = _get_state()
    except Exception as e:
        return False, "Naadde ikke HA: %s" % e
    if not finnes:
        return False, "Entiteten '%s' finnes ikke i HA" % CFG["entity_id"]

    req = urllib.request.Request(
        HA_URL + "/services/button/press",
        data=json.dumps({"entity_id": CFG["entity_id"]}).encode(),
        method="POST",
        headers={"Authorization": "Bearer " + SUPERVISOR_TOKEN,
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            if not (200 <= r.status < 300):
                return False, "HA svarte HTTP %d" % r.status
    except urllib.error.HTTPError as e:
        return False, "HA-feil HTTP %d: %s" % (
            e.code, e.read()[:200].decode("utf-8", "replace"))
    except Exception as e:
        return False, "Naadde ikke HA: %s" % e

    _last_open = now
    try:
        _, after = _get_state()
    except Exception:
        after = None
    if after and after != before:
        return True, "Signal sendt - bekreftet av HA"
    return True, "Signal sendt (ikke bekreftet av HA)"


# ----------------------------------------------------------------- html ----
PAGE = """<!doctype html>
<html lang="no"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Garasjeport</title>
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
.card.wide{max-width:640px;text-align:left}
h1{margin:0 0 4px;font-size:20px;letter-spacing:-.01em}
p.sub{margin:0 0 26px;color:var(--dim);font-size:14px}
button.big{width:180px;height:180px;border-radius:50%;border:none;cursor:pointer;
      background:var(--accent);color:#fff;font-size:17px;font-weight:600;
      transition:transform .08s,background .15s;-webkit-tap-highlight-color:transparent}
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
table{width:100%;border-collapse:collapse;font-size:13px;
      font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);
      white-space:nowrap}
th{color:var(--dim);font-weight:600;font-size:11px;text-transform:uppercase;
   letter-spacing:.04em}
td.d{white-space:normal;color:var(--dim)}
.wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tag{display:inline-block;padding:1px 7px;border-radius:5px;font-size:11px;
     font-weight:600}
.t-open{background:rgba(21,128,61,.14);color:var(--ok)}
.t-fail{background:rgba(185,28,28,.14);color:var(--err)}
.t-in{background:rgba(113,113,122,.16);color:var(--dim)}
</style></head><body><div class="card __WIDE__">__BODY__</div>
<script>
var b=document.getElementById('open');
if(b){b.addEventListener('click',function(){
  var m=document.getElementById('msg');
  b.disabled=true;m.className='';m.textContent='Sender...';
  fetch('open',{method:'POST'}).then(function(r){return r.json()})
  .then(function(d){m.className=d.ok?'ok':'err';m.textContent=(d.ok?'\\u2713 ':'\\u2717 ')+d.msg})
  .catch(function(){m.className='err';m.textContent='\\u2717 Nettverksfeil'})
  .then(function(){setTimeout(function(){b.disabled=false},2000)})
})}
</script></body></html>"""

LOGIN = """<h1>Garasjeport</h1><p class="sub">Skriv inn brukernavn</p>
<form method="POST" action="login">
<input name="u" autocomplete="off" autocapitalize="off" autocorrect="off"
       spellcheck="false" placeholder="brukernavn" autofocus>
<button class="go" type="submit">Fortsett</button></form>__ERR__"""

BUTTON = """<h1>Garasjeport</h1>
<p class="sub">1A &middot; innlogget som <strong>__WHO__</strong></p>
<button class="big" id="open"><span class="icon">&#9650;</span>APNE</button>
<div id="msg"></div>
<footer>Porten lukker seg selv &middot; <a href="logg">logg</a>
 &middot; <a href="logout">logg ut</a></footer>"""


def logg_html(rows, who):
    tags = {"open_ok": ("t-open", "APNET"), "open_fail": ("t-fail", "FEIL"),
            "login_ok": ("t-in", "LOGG INN"), "login_fail": ("t-fail", "AVVIST"),
            "logout": ("t-in", "LOGG UT")}
    body = ['<h1>Adgangslogg</h1><p class="sub">Nyeste først &middot; innlogget som '
            '<strong>%s</strong></p><div class="wrap"><table>'
            '<tr><th>Tid</th><th>Hendelse</th><th>Bruker</th><th>IP</th>'
            '<th>Detalj</th></tr>' % esc(who)]
    if not rows:
        body.append('<tr><td colspan="5" class="d">Ingen oppføringer ennå</td></tr>')
    for r in rows:
        cls, txt = tags.get(r.get("event"), ("t-in", r.get("event", "?")))
        body.append("<tr><td>%s</td><td><span class='tag %s'>%s</span></td>"
                    "<td>%s</td><td>%s</td><td class='d'>%s</td></tr>"
                    % (esc(r.get("t", "")), cls, txt, esc(r.get("user", "-")),
                       esc(r.get("ip", "")), esc(r.get("detail", ""))))
    body.append('</table></div><footer><a href="./">&larr; tilbake</a></footer>')
    return "".join(body)


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------- server ----
class H(http.server.BaseHTTPRequestHandler):
    server_version = "gp/2.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        pass  # vi logger selv, mer lesbart

    def client_ip(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        if fwd:
            return fwd.split(",")[0].strip() + " (via proxy)"
        return self.client_address[0]

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

    def _page(self, inner, extra=None, code=200, wide=False):
        html = PAGE.replace("__BODY__", inner).replace("__WIDE__", "wide" if wide else "")
        self._send(code, html, extra=extra)

    def _user(self):
        for part in self.headers.get("Cookie", "").split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k == COOKIE:
                    return whoami(urllib.parse.unquote(v))
        return None

    def _cookie(self, value):
        return [("Set-Cookie", "%s=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000"
                 % (COOKIE, urllib.parse.quote(value)))]

    def _login_ok(self, user, extra_cookie=True):
        logg("login_ok", user["label"], self.client_ip())
        self._page(BUTTON.replace("__WHO__", esc(user["label"])),
                   extra=self._cookie(user["username"]) if extra_cookie else None)

    def _login_fail(self, attempted):
        time.sleep(1)  # bremser gjetting
        logg("login_fail", None, self.client_ip(),
             "forsøkte: %s" % (attempted[:40] or "(tom)"))
        self._page(LOGIN.replace(
            "__ERR__", '<div id="msg" class="err">Ukjent brukernavn</div>'), code=401)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        route = p.path.rstrip("/") or "/"
        if route == "/health":
            self._send(200, json.dumps({"ok": True, "users": len(CFG["users"])}),
                       "application/json")
            return
        if route == "/logout":
            u = self._user()
            if u:
                logg("logout", u["label"], self.client_ip())
            self._page(LOGIN.replace("__ERR__", ""),
                       extra=[("Set-Cookie", "%s=; Path=/; Max-Age=0" % COOKIE)])
            return
        if route == "/logg":
            u = self._user()
            if not u:
                self._page(LOGIN.replace("__ERR__", ""), code=401)
                return
            self._page(logg_html(les_logg(150), u["label"]), wide=True)
            return
        if route != "/":
            self._send(404, "<h1>404</h1>")
            return
        q = urllib.parse.parse_qs(p.query).get("u", [""])[0]
        if q:
            u = whoami(q)
            if u:
                self._login_ok(u)
            else:
                self._login_fail(q)
            return
        u = self._user()
        if u:
            self._page(BUTTON.replace("__WHO__", esc(u["label"])))
        else:
            self._page(LOGIN.replace("__ERR__", ""))

    def do_POST(self):
        route = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        if route == "/login":
            given = urllib.parse.parse_qs(raw).get("u", [""])[0]
            u = whoami(given)
            if u:
                self._login_ok(u)
            else:
                self._login_fail(given)
            return
        if route == "/open":
            u = self._user()
            if not u:
                logg("open_fail", None, self.client_ip(), "ikke innlogget")
                self._send(401, json.dumps({"ok": False, "msg": "Ikke innlogget"}),
                           "application/json")
                return
            ok, msg = press()
            logg("open_ok" if ok else "open_fail", u["label"], self.client_ip(), msg)
            self._send(200 if ok else 503, json.dumps({"ok": ok, "msg": msg}),
                       "application/json")
            return
        self._send(404, json.dumps({"ok": False, "msg": "ukjent"}), "application/json")


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    if not CFG["users"]:
        print("ADVARSEL: ingen brukere konfigurert - alle blir avvist", flush=True)
    else:
        print("Brukere: %s" % ", ".join(u["label"] for u in CFG["users"]), flush=True)
    print("Lytter på :8099, entity=%s, cooldown=%ds, logg=%s"
          % (CFG["entity_id"], CFG["cooldown"], LOG_FILE), flush=True)
    Server(("0.0.0.0", 8099), H).serve_forever()
