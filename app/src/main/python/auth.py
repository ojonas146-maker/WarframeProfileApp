"""Contas, sessões, visitantes e upload do lastData.

- Conta própria: usuário + senha (PBKDF2). O lastData descriptografado fica em data/users/<usuário>.z (comprimido).
- Visitante: precisa do código de acesso; o lastData fica SÓ NA MEMÓRIA por 2 horas e depois é apagado sozinho
  (nada vai para o disco). Dá para ter vários visitantes ao mesmo tempo, cada um com sua sessão isolada.
- Sem data/config.json o servidor roda no modo antigo (sem login). Para ativar: python3 manage.py setup
"""
import hashlib, hmac, json, os, re, secrets, threading, time, zlib
from collections import OrderedDict
from pathlib import Path
from urllib.request import urlopen

BASE = Path(os.environ.get("WF_HOME") or Path(__file__).parent)
APP_MODE = os.environ.get("WF_APP") == "1"   # app Android: uma conta local única, sem login
DATA = BASE / "data"
UDIR = DATA / "users"
CONFIG_F, ACC_F, SESS_F, KEY_F = DATA / "config.json", DATA / "accounts.json", DATA / "sessions.json", DATA / "keys.json"
VISITOR_TTL = 2 * 3600          # visitante: 2 horas
REMEMBER_TTL = 30 * 86400       # "manter conectado"
SHORT_TTL = 12 * 3600           # sem "manter conectado"
MAX_UPLOAD = 40 * 1024 * 1024
MAX_VISITORS = 60
KEY_URL = "https://gist.githubusercontent.com/nrbdev/cd73cc5c02ee5e23aca3251423aa85b0/raw/"
IV_URL = "https://gist.githubusercontent.com/nrbdev/8ebb6a1849ebbf80724b26faf30451a1/raw/"
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
PID_RE = re.compile(r"^[0-9a-f]{24}$")

_lock = threading.RLock()
_vis = {}                        # token_hash -> sessão de visitante (só RAM)
_lru = OrderedDict()             # (chave) -> dict já interpretado (máx. 8)
_fails = {}                      # limitador de tentativas


class AuthError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


# ---------------------------------------------------------------- arquivos
def _read(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(p, obj):
    DATA.mkdir(exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    os.replace(tmp, p)


def configured():
    return APP_MODE or CONFIG_F.exists()


def app_session():
    """Modo app: sessão fixa da conta local (criada na primeira vez), sem senha."""
    with _lock:
        acc = _read(ACC_F, {})
        if "local" not in acc:
            acc["local"] = {"name": "local", "pw": None, "player_id": "", "created": time.time(), "uploaded_at": None, "admin": False}
            _write(ACC_F, acc)
        a = acc["local"]
    return {"kind": "account", "user": "local", "key": "local", "exp": time.time() + 86400 * 365,
            "player_id": a.get("player_id", ""), "uploaded_at": a.get("uploaded_at"),
            "has_data": (UDIR / "local.z").exists(), "admin": False}


def config():
    return _read(CONFIG_F, {})


def _th(token):
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------- senhas
def hash_secret(secret, salt=None, iters=200_000):
    salt = salt or secrets.token_bytes(16)
    return {"s": salt.hex(), "h": hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, iters).hex(), "i": iters}


def check_secret(secret, rec):
    try:
        h = hashlib.pbkdf2_hmac("sha256", secret.encode(), bytes.fromhex(rec["s"]), int(rec["i"])).hex()
        return hmac.compare_digest(h, rec["h"])
    except Exception:
        return False


# ---------------------------------------------------------------- limitador (anti força bruta)
def _blocked(key):
    f = _fails.get(key)
    return bool(f and f[0] >= 6 and time.time() - f[1] < 600)


def _fail(key):
    n, t = _fails.get(key, (0, 0))
    _fails[key] = (1 if time.time() - t > 600 else n + 1, time.time())


def _ok(key):
    _fails.pop(key, None)


def _guard(key):
    if _blocked(key):
        raise AuthError("Muitas tentativas. Espere alguns minutos e tente de novo.", 429)


# ---------------------------------------------------------------- contas
def _accounts():
    return _read(ACC_F, {})


def _valid_pass(pw):
    if not isinstance(pw, str) or len(pw) < 6:
        raise AuthError("A senha precisa ter pelo menos 6 caracteres.")
    if len(pw) > 200:
        raise AuthError("Senha muito longa.")


def create_account(name, pw, player_id="", admin=False):
    if not NAME_RE.match(name or ""):
        raise AuthError("Usuário: 3 a 24 caracteres (letras, números, ponto, hífen e _).")
    _valid_pass(pw)
    pid = (player_id or "").strip().lower()
    if pid and not PID_RE.match(pid):
        raise AuthError("ID da conta inválido (são 24 caracteres: números e letras de a a f).")
    with _lock:
        acc = _accounts()
        if name.lower() in acc:
            raise AuthError("Esse usuário já existe.", 409)
        acc[name.lower()] = {"name": name, "pw": hash_secret(pw), "player_id": pid, "created": time.time(),
                             "uploaded_at": None, "admin": bool(admin)}
        _write(ACC_F, acc)
    return name.lower()


def set_password(name, pw):
    _valid_pass(pw)
    with _lock:
        acc = _accounts()
        if name.lower() not in acc:
            raise AuthError("Usuário não existe.", 404)
        acc[name.lower()]["pw"] = hash_secret(pw)
        _write(ACC_F, acc)
        # derruba as sessões antigas dessa conta
        s = _read(SESS_F, {})
        _write(SESS_F, {k: v for k, v in s.items() if v.get("user") != name.lower()})


def delete_account(name):
    with _lock:
        acc = _accounts()
        acc.pop(name.lower(), None)
        _write(ACC_F, acc)
        s = _read(SESS_F, {})
        _write(SESS_F, {k: v for k, v in s.items() if v.get("user") != name.lower()})
    try:
        (UDIR / (name.lower() + ".z")).unlink()
    except FileNotFoundError:
        pass
    for k in [k for k in _lru if k[1] == name.lower()]:
        _lru.pop(k, None)


def list_accounts():
    return _accounts()


# ---------------------------------------------------------------- sessões
def _new_token():
    return secrets.token_urlsafe(32)


def login(name, pw, remember, ip):
    key = "login:%s:%s" % (ip, (name or "").lower())
    _guard(key)
    acc = _accounts().get((name or "").lower())
    if not acc or not check_secret(pw or "", acc["pw"]):
        _fail(key)
        raise AuthError("Usuário ou senha incorretos.", 401)
    _ok(key)
    return _start_account_session(name.lower(), remember)


def _start_account_session(user, remember):
    token, ttl = _new_token(), (REMEMBER_TTL if remember else SHORT_TTL)
    with _lock:
        s = _read(SESS_F, {})
        now = time.time()
        s = {k: v for k, v in s.items() if v.get("exp", 0) > now}
        s[_th(token)] = {"kind": "account", "user": user, "exp": now + ttl}
        _write(SESS_F, s)
    return token, ttl, remember


def check_code(code, ip):
    key = "code:" + ip
    _guard(key)
    rec = config().get("code")
    if not rec or not check_secret((code or "").strip(), rec):
        _fail(key)
        raise AuthError("Código de acesso incorreto.", 401)
    _ok(key)


def register(code, name, pw, player_id, remember, ip):
    check_code(code, ip)
    user = create_account(name, pw, player_id)
    return _start_account_session(user, remember)


def start_visitor(code, player_id, ip):
    check_code(code, ip)
    pid = (player_id or "").strip().lower()
    if pid and not PID_RE.match(pid):
        raise AuthError("ID da conta inválido (são 24 caracteres: números e letras de a a f).")
    purge()
    with _lock:
        if len(_vis) >= MAX_VISITORS:
            raise AuthError("Muitos visitantes agora. Tente de novo em alguns minutos.", 503)
        token = _new_token()
        _vis[_th(token)] = {"kind": "visitor", "user": "visitante", "exp": time.time() + VISITOR_TTL,
                            "player_id": pid, "blob": None, "uploaded_at": None}
    return token, VISITOR_TTL, False


def get_session(token):
    """Sessão válida (dict) ou None."""
    if not token:
        return None
    th = _th(token)
    now = time.time()
    v = _vis.get(th)
    if v:
        if v["exp"] <= now:
            _drop_visitor(th)
            return None
        return {"kind": "visitor", "user": v["user"], "key": th, "exp": v["exp"], "player_id": v["player_id"],
                "uploaded_at": v["uploaded_at"], "has_data": v["blob"] is not None, "admin": False}
    s = _read(SESS_F, {}).get(th)
    if not s or s.get("exp", 0) <= now:
        return None
    acc = _accounts().get(s["user"])
    if not acc:
        return None
    return {"kind": "account", "user": acc["name"], "key": s["user"], "exp": s["exp"], "player_id": acc.get("player_id", ""),
            "uploaded_at": acc.get("uploaded_at"), "has_data": (UDIR / (s["user"] + ".z")).exists(), "admin": acc.get("admin", False)}


def logout(token):
    if not token:
        return
    th = _th(token)
    if th in _vis:
        _drop_visitor(th)
        return
    with _lock:
        s = _read(SESS_F, {})
        if s.pop(th, None) is not None:
            _write(SESS_F, s)


def _drop_visitor(th):
    v = _vis.pop(th, None)
    if v:
        v["blob"] = None
    for k in [k for k in _lru if k[0] == "v" and k[1] == th]:
        _lru.pop(k, None)


def purge():
    """Apaga visitantes vencidos (lastData some da memória) e sessões antigas."""
    now = time.time()
    for th in [th for th, v in list(_vis.items()) if v["exp"] <= now]:
        _drop_visitor(th)
    with _lock:
        s = _read(SESS_F, {})
        keep = {k: v for k, v in s.items() if v.get("exp", 0) > now}
        if len(keep) != len(s):
            _write(SESS_F, keep)


def _janitor():
    while True:
        time.sleep(60)
        try:
            purge()
        except Exception:
            pass


threading.Thread(target=_janitor, daemon=True, name="auth-janitor").start()


# ---------------------------------------------------------------- dados do jogador
def set_player_id(sess, pid):
    pid = (pid or "").strip().lower()
    if pid and not PID_RE.match(pid):
        raise AuthError("ID da conta inválido (são 24 caracteres: números e letras de a a f).")
    if sess["kind"] == "visitor":
        if sess["key"] in _vis:
            _vis[sess["key"]]["player_id"] = pid
        return
    with _lock:
        acc = _accounts()
        acc[sess["key"]]["player_id"] = pid
        _write(ACC_F, acc)


def _fetch_bytes(url):
    raw = urlopen(url, timeout=30).read().decode().strip()
    return bytes(int(x) for x in raw[1:-1].split(","))


def _key_iv():
    j = _read(KEY_F, None)
    if j and j.get("key") and j.get("iv"):
        return bytes(j["key"]), bytes(j["iv"])
    try:
        key, iv = _fetch_bytes(KEY_URL), _fetch_bytes(IV_URL)
    except Exception as e:
        raise AuthError("Não consegui baixar a chave de descriptografia (%s)." % e, 502)
    _write(KEY_F, {"key": list(key), "iv": list(iv)})
    return key, iv


def _aes_cbc_decrypt(key, iv, data):
    if len(data) % 16:
        raise AuthError("O arquivo não parece um lastData.dat (tamanho inválido).")
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        return unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(data), 16)
    except ImportError:
        pass
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        raise AuthError("Falta a biblioteca de criptografia no servidor: python3 -m pip install pycryptodome", 500)
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    raw = dec.update(data) + dec.finalize()
    pad = raw[-1] if raw else 0
    if not 1 <= pad <= 16:
        raise ValueError("padding inválido")
    return raw[:-pad]


def decrypt_lastdata(blob):
    """Aceita o lastData.dat (criptografado) ou o JSON já descriptografado."""
    try:
        if blob[:1] in (b"{", b"["):
            data = json.loads(blob.decode("utf-8"))
        else:
            key, iv = _key_iv()
            try:
                data = json.loads(_aes_cbc_decrypt(key, iv, blob).decode("utf-8"))
            except AuthError:
                raise
            except Exception:
                raise AuthError("Não consegui descriptografar. Esse é mesmo o lastData.dat do AlecaFrame?")
        if isinstance(data, dict) and "InventoryJson" in data:  # arquivos antigos vinham encapsulados
            data = json.loads(data["InventoryJson"])
    except AuthError:
        raise
    except Exception:
        raise AuthError("Arquivo inválido. Envie o lastData.dat do AlecaFrame.")
    if not isinstance(data, dict) or not any(k in data for k in ("Suits", "RawUpgrades", "MiscItems", "LongGuns")):
        raise AuthError("Esse arquivo não parece um lastData do Warframe.")
    return data


def save_data(sess, blob):
    """Descriptografa e guarda: conta -> disco (substitui o anterior); visitante -> só memória."""
    data = decrypt_lastdata(blob)
    z = zlib.compress(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 6)
    now = time.time()
    if sess["kind"] == "visitor":
        v = _vis.get(sess["key"])
        if not v:
            raise AuthError("Sessão de visitante expirada.", 401)
        v["blob"], v["uploaded_at"] = z, now
        for k in [k for k in _lru if k[0] == "v" and k[1] == sess["key"]]:
            _lru.pop(k, None)
        return now
    UDIR.mkdir(parents=True, exist_ok=True)
    p = UDIR / (sess["key"] + ".z")
    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(z)
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    os.replace(tmp, p)
    with _lock:
        acc = _accounts()
        acc[sess["key"]]["uploaded_at"] = now
        _write(ACC_F, acc)
    for k in [k for k in _lru if k[0] == "a" and k[1] == sess["key"]]:
        _lru.pop(k, None)
    return now


def delete_data(sess):
    if sess["kind"] == "visitor":
        v = _vis.get(sess["key"])
        if v:
            v["blob"], v["uploaded_at"] = None, None
    else:
        try:
            (UDIR / (sess["key"] + ".z")).unlink()
        except FileNotFoundError:
            pass
        with _lock:
            acc = _accounts()
            if sess["key"] in acc:
                acc[sess["key"]]["uploaded_at"] = None
                _write(ACC_F, acc)
    for k in [k for k in _lru if k[1] == sess["key"]]:
        _lru.pop(k, None)


def load_data(sess):
    """lastData da sessão já interpretado (com cache LRU de 8, para vários usuários ao mesmo tempo) ou None."""
    ck = ("v" if sess["kind"] == "visitor" else "a", sess["key"], sess.get("uploaded_at"))
    with _lock:
        if ck in _lru:
            _lru.move_to_end(ck)
            return _lru[ck]
        if sess["kind"] == "visitor":
            v = _vis.get(sess["key"])
            z = v["blob"] if v else None
        else:
            p = UDIR / (sess["key"] + ".z")
            z = p.read_bytes() if p.exists() else None
    if z is None:
        return None
    data = json.loads(zlib.decompress(z).decode("utf-8"))
    with _lock:
        _lru[ck] = data
        while len(_lru) > 8:
            _lru.popitem(last=False)
    return data


def me(sess):
    if not sess:
        return {"authenticated": False}
    return {"authenticated": True, "kind": sess["kind"], "user": sess["user"], "player_id": sess.get("player_id", ""),
            "uploaded_at": sess.get("uploaded_at"), "has_data": sess.get("has_data", False),
            "expires_at": sess["exp"] if sess["kind"] == "visitor" else None, "admin": sess.get("admin", False)}
