"""Conta do warframe.market: ver, anunciar, editar e remover as SUAS ordens.
Só guarda o token de sessão (nunca a senha), em data/wfm_account.json."""
import json, os, re, threading, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

BASE = Path(os.environ.get("WF_HOME") or Path(__file__).parent)
DATA = BASE / "data"
ACC_F, ITEMS_F = DATA / "wfm_account.json", DATA / "wfm_items.json"
API2, API1 = "https://api.warframe.market/v2", "https://api.warframe.market/v1"
UA = "Mozilla/5.0 (Linux; Android 14) WarframeProfileApp"
_lock = threading.Lock()
_me = {"ts": 0, "data": None}


class WfmError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


def _rd(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _token():
    return _rd(ACC_F, {}).get("token", "")


def _save_token(tok):
    DATA.mkdir(parents=True, exist_ok=True)
    ACC_F.write_text(json.dumps({"token": tok, "ts": time.time()}), encoding="utf-8")
    try:
        os.chmod(ACC_F, 0o600)
    except Exception:
        pass
    _me.update(ts=0, data=None)


def clean_token(t):
    t = urllib.parse.unquote(str(t or "")).strip().strip('"\'')
    t = re.sub(r"^(JWT|Bearer)\s+", "", t, flags=re.I).strip()
    if t.count(".") < 2 or len(t) < 40:
        raise WfmError("Isso não parece um token JWT do warframe.market.")
    return t


def _http(method, url, tok=None, body=None, scheme="Bearer", extra=None):
    h = {"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json", "Platform": "pc", "Language": "en"}
    if tok:
        h["Authorization"] = ("Bearer " if scheme == "Bearer" else "JWT ") + tok
        h["Cookie"] = "JWT=" + tok
    h.update(extra or {})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=30)
        raw, code, hd = r.read(), r.status, r.headers
    except urllib.error.HTTPError as e:
        raw, code, hd = e.read(), e.code, e.headers
    except Exception as e:
        raise WfmError("Sem conexão com o warframe.market (%s)." % e, 502)
    try:
        j = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        j = {}
    return code, hd, j


def _err(j, default):
    e = j.get("error") if isinstance(j, dict) else None
    if isinstance(e, dict):
        return str(e.get("message") or e.get("request") or e.get("inputs") or default)
    return str(e or default)


def _authed(method, path, body=None):
    tok = _token()
    if not tok:
        raise WfmError("Você não entrou no warframe.market.", 401)
    for scheme in ("Bearer", "JWT"):
        code, hd, j = _http(method, API2 + path, tok, body, scheme)
        if code != 401:
            break
    if code == 401:
        raise WfmError("Sessão do warframe.market expirada. Entre de novo.", 401)
    if code >= 400:
        raise WfmError(_err(j, "warframe.market respondeu %d" % code), code)
    return j


# ---------------------------------------------------------------- itens (id -> nome/ícone), cache de 3 dias
def items():
    d = _rd(ITEMS_F, None)
    if d and time.time() - d.get("_ts", 0) < 3 * 86400:
        return d["items"]
    try:
        code, _, j = _http("GET", API2 + "/items")
        if code != 200:
            raise WfmError("warframe.market respondeu %d" % code)
        out = {}
        for it in j.get("data", []):
            i18n = (it.get("i18n") or {}).get("en") or {}
            out[it["id"]] = {"id": it["id"], "slug": it.get("slug"), "name": i18n.get("name") or it.get("slug"),
                             "icon": i18n.get("thumb") or i18n.get("icon"), "max": it.get("maxRank") or 0}
        DATA.mkdir(parents=True, exist_ok=True)
        ITEMS_F.write_text(json.dumps({"_ts": time.time(), "items": out}, ensure_ascii=False), encoding="utf-8")
        return out
    except WfmError:
        if d:
            return d["items"]
        raise


def _icon(i):
    return ("https://warframe.market/static/assets/" + i) if i else None


def search(q):
    q = (q or "").strip().lower()
    if len(q) < 2:
        return []
    its = items().values()
    hits = [x for x in its if q in (x["name"] or "").lower()]
    hits.sort(key=lambda x: (not (x["name"] or "").lower().startswith(q), len(x["name"] or "")))
    return [dict(x, icon=_icon(x["icon"])) for x in hits[:25]]


# ---------------------------------------------------------------- conta
def me():
    if not _token():
        return None
    if _me["data"] and time.time() - _me["ts"] < 120:
        return _me["data"]
    try:
        j = _authed("GET", "/me")
    except WfmError as e:
        if e.code == 401:
            return None
        raise
    d = j.get("data") or {}
    _me.update(ts=time.time(), data={
        "name": d.get("ingameName") or d.get("slug") or "?", "slug": d.get("slug"), "status": d.get("status"),
        "avatar": _icon(d.get("avatar")), "about": d.get("about") or "", "reputation": d.get("reputation"),
        "platform": d.get("platform"), "locale": d.get("locale") or d.get("language"), "role": d.get("role"),
        "keys": sorted(d.keys())})
    return _me["data"]


def status():
    try:
        u = me()
    except WfmError as e:
        return {"logged": bool(_token()), "error": str(e)}
    return {"logged": bool(u), "user": u}


def login_password(email, password):
    code, hd, j = _http("POST", API1 + "/auth/signin", body={"email": email, "password": password, "auth_type": "header"},
                        extra={"Authorization": "JWT", "auth_type": "header"})
    tok = (hd.get("Authorization") or "").strip() if hd else ""
    if code != 200 or not tok:
        raise WfmError("O warframe.market não aceitou o login por e-mail/senha aqui (%s). Use \"Entrar pelo site\" ou cole o token." %
                       _err(j, "HTTP %d" % code))
    set_token(tok)


def set_token(tok):
    tok = clean_token(tok)
    _save_token(tok)
    try:
        u = me()
    except WfmError:
        u = None
    if not u:
        _save_token("")
        raise WfmError("Token recusado pelo warframe.market (expirou ou não é de uma sessão válida).", 401)


def logout():
    _save_token("")


# ---------------------------------------------------------------- ordens
def orders():
    j = _authed("GET", "/orders/my")
    its = items()
    out = []
    for o in j.get("data") or []:
        it = its.get(o.get("itemId")) or {}
        out.append({"id": o["id"], "type": o.get("type"), "platinum": o.get("platinum"), "quantity": o.get("quantity"),
                    "visible": o.get("visible", True), "rank": o.get("rank"), "slug": it.get("slug"),
                    "name": it.get("name") or o.get("itemId"), "icon": _icon(it.get("icon")), "max": it.get("max", 0)})
    out.sort(key=lambda o: (o["type"] != "sell", (o["name"] or "").lower()))
    return out


def _int(v, lo=1, hi=999999):
    try:
        v = int(v)
    except Exception:
        raise WfmError("Número inválido.")
    if not lo <= v <= hi:
        raise WfmError("Valor fora do limite (%d a %d)." % (lo, hi))
    return v


def create(j):
    it = items().get(j.get("itemId")) or next((x for x in items().values() if x["slug"] == j.get("slug")), None)
    if not it:
        raise WfmError("Item não encontrado no warframe.market.")
    typ = "buy" if j.get("type") == "buy" else "sell"
    body = {"itemId": it["id"], "type": typ, "platinum": _int(j.get("platinum")), "quantity": _int(j.get("quantity") or 1),
            "visible": j.get("visible", True) is not False}
    if it.get("max") and j.get("rank") not in (None, ""):
        body["rank"] = _int(j.get("rank"), 0, it["max"])
    return _authed("POST", "/order", body).get("data")


def update(j):
    oid = str(j.get("id") or "")
    if not re.fullmatch(r"[0-9a-zA-Z]{8,40}", oid):
        raise WfmError("ID de ordem inválido.")
    body = {}
    if "platinum" in j:
        body["platinum"] = _int(j["platinum"])
    if "quantity" in j:
        body["quantity"] = _int(j["quantity"])
    if "visible" in j:
        body["visible"] = bool(j["visible"])
    if not body:
        raise WfmError("Nada para alterar.")
    return _authed("PATCH", "/order/" + oid, body).get("data")


def delete(j):
    oid = str(j.get("id") or "")
    if not re.fullmatch(r"[0-9a-zA-Z]{8,40}", oid):
        raise WfmError("ID de ordem inválido.")
    _authed("DELETE", "/order/" + oid)
    return {"ok": True}


V1H = {"Origin": "https://warframe.market", "Referer": "https://warframe.market/"}
STATE_F = DATA / "wfm_state.json"
_HIDE = re.compile(r"message|text|raw|content|body|about|email|check", re.I)


def _v1(path):
    """O chat continua na API v1 (Authorization: JWT <token>), igual ao seu wfmb3.js."""
    tok = _token()
    if not tok:
        raise WfmError("Você não entrou no warframe.market.", 401)
    code, hd, j = _http("GET", API1 + path, tok, None, "JWT", V1H)
    if code in (401, 403):
        raise WfmError("Sessão do warframe.market expirada. Entre de novo.", 401)
    if code >= 400:
        raise WfmError(_err(j, "warframe.market respondeu %d" % code), code)
    return j.get("payload") or {}


def _strip(h):
    import html
    return html.unescape(re.sub(r"<[^>]+>", "", h or "")).strip()


def _txt(m):
    return (m.get("raw_message") or _strip(m.get("message")) or "").strip()


def _peer(c):
    name = c.get("chat_name") or "?"
    w = c.get("chat_with") or []
    return name, next((x for x in w if x.get("ingame_name") == name), w[0] if w else {})


def _last(ms):
    return max(ms, key=lambda m: m.get("send_date") or "") if ms else {}


def chats():
    out = []
    for c in _v1("/im/chats").get("chats") or []:
        name, u = _peer(c)
        last = _last(c.get("messages") or [])
        out.append({"id": c.get("id"), "peer": u.get("id"), "name": name, "avatar": _icon(u.get("avatar")), "status": u.get("status"),
                    "reputation": u.get("reputation"), "text": _txt(last)[:300], "unread": int(c.get("unread_count") or 0),
                    "updated": c.get("last_update") or last.get("send_date"),
                    "mine": bool(last and u.get("id") and last.get("message_from") != u.get("id"))})
    out.sort(key=lambda x: x["updated"] or "", reverse=True)
    return out


def chat_messages(cid, peer):
    if not re.fullmatch(r"[0-9a-zA-Z]{8,40}", str(cid or "")):
        raise WfmError("ID de conversa inválido.")
    ms = _v1("/im/chats/" + cid).get("messages") or []
    ms = sorted(ms, key=lambda m: m.get("send_date") or "")
    return [{"id": m.get("id"), "mine": bool(peer) and m.get("message_from") != peer, "text": _txt(m), "time": m.get("send_date")} for m in ms]


def _shape(v, key="", depth=0):
    if isinstance(v, dict):
        return {k: _shape(x, k, depth + 1) for k, x in list(v.items())[:40]} if depth < 6 else "{...}"
    if isinstance(v, list):
        return ["len=%d" % len(v)] + ([_shape(v[0], key, depth + 1)] if v else [])
    if isinstance(v, str):
        return "<texto %d chars>" % len(v) if _HIDE.search(key) else v[:40]
    return v


def debug():
    """Estrutura (sem textos de mensagens) dos endpoints da conta. Nunca inclui o token."""
    lines = []

    def run(label, fn):
        try:
            lines.append("%s -> 200\n%s" % (label, json.dumps(_shape(fn()), ensure_ascii=False, indent=1)))
        except WfmError as e:
            lines.append("%s -> %s: %s" % (label, e.code, e))
    run("GET v2 /me", lambda: _authed("GET", "/me"))
    run("GET v1 /im/chats", lambda: _v1("/im/chats"))
    try:
        cs = _v1("/im/chats").get("chats") or []
        if cs:
            run("GET v1 /im/chats/<id>", lambda: _v1("/im/chats/" + cs[0]["id"]))
    except WfmError:
        pass
    return "\n\n".join(lines)


def poll():
    """Detecta mensagens NOVAS recebidas (como o seu monitor): compara ids de mensagens já vistos."""
    st = _rd(STATE_F, {})
    first = "known" not in st
    known = set(st.get("known") or [])
    new, unread = [], 0
    for c in _v1("/im/chats").get("chats") or []:
        name, u = _peer(c)
        unread += int(c.get("unread_count") or 0)
        for m in sorted(c.get("messages") or [], key=lambda x: x.get("send_date") or ""):
            mid = m.get("id")
            if not mid or mid in known:
                continue
            known.add(mid)
            if u.get("id") and m.get("message_from") == u.get("id"):
                new.append((name, _txt(m)))
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        STATE_F.write_text(json.dumps({"known": list(known)[-3000:]}), encoding="utf-8")
    except Exception:
        pass
    notify = bool(new) and not first
    return {"unread": unread, "notify": notify, "count": len(new) if notify else 0,
            "text": ("%s: %s" % (new[-1][0], new[-1][1][:80])) if notify else ""}


def handle_get(path, q):
    if path == "/api/wfm/poll":
        return poll()
    if path == "/api/wfm/chats":
        return chats()
    if path == "/api/wfm/chat":
        return chat_messages((q.get("id") or [""])[0], (q.get("peer") or [""])[0])
    if path == "/api/wfm/debug":
        return {"text": debug()}
    if path == "/api/wfm/status":
        return status()
    if path == "/api/wfm/orders":
        return orders()
    if path == "/api/wfm/items":
        return search((q.get("q") or [""])[0])
    raise WfmError("rota invalida", 404)


def handle_post(path, j):
    if path == "/api/wfm/token":
        set_token(j.get("token"))
        return status()
    if path == "/api/wfm/login":
        login_password((j.get("email") or "").strip(), j.get("password") or "")
        return status()
    if path == "/api/wfm/logout":
        logout()
        return {"ok": True}
    if path == "/api/wfm/order/create":
        return {"ok": True, "order": create(j)}
    if path == "/api/wfm/order/update":
        return {"ok": True, "order": update(j)}
    if path == "/api/wfm/order/delete":
        return delete(j)
    raise WfmError("rota invalida", 404)
