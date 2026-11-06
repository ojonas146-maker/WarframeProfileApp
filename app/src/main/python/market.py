"""Integração com o warframe.market (preços em platina).
- Os visitantes NUNCA esperam a rede: o servidor responde na hora com o que está em cache (mesmo velho) e
  um único worker em segundo plano busca o que falta, respeitando o limite do site.
- Prioridade da fila: 0 = itens visíveis do visitante, 1 = resto do inventário dele, 2 = faxina diária do cache.
- Passou 1 dia desde a última faxina: o próximo acesso dispara a renovação (primeiro os itens da pessoa, depois o resto do cache).
- Índice de itens (slug/gameRef) vem de /v2/items e fica em cache por 7 dias (data/market_index.json).
- Preço de cada item = menor venda de jogador online/in-game (e maior compra), cache em data/market_cache.json.
- Todas as chamadas passam por um limitador global (~2,5 req/s, o limite do site é 3/s)."""
import settings
import heapq, itertools, json, os, re, shutil, threading, time, urllib.request, urllib.error
from pathlib import Path

BASE = Path(os.environ.get("WF_HOME") or Path(__file__).parent)
DATA = BASE / "data"
INDEX_FILE = DATA / "market_index.json"
CACHE_FILE = DATA / "market_cache.json"
API2 = "https://api.warframe.market/v2"
API1 = "https://api.warframe.market/v1"
HEAD = {"Accept": "application/json", "Language": "en", "Platform": "pc", "Crossplay": "true",
        "User-Agent": "warframe-profile-local/1.0"}
DAY = 24 * 3600          # padrão; o valor real vem de settings (price_ttl_h)


def _ttl():
    try:
        return max(1, int(settings.get("price_ttl_h") or 24)) * 3600
    except Exception:
        return DAY
MAX_QUEUE = 6000
MAX_BATCH = 80
INDEX_TTL = 7 * 86400
MIN_GAP = 0.4

_net = threading.Lock()
_last = [0.0]
_mem = threading.Lock()
_state = {"by_ref": {}, "slugs": {}, "ts": 0, "fail": 0, "error": "", "prices": None, "saved": 0}


def slugify(name):
    s = (name or "").lower().replace("&", "and").replace("'", "").replace("\u2019", "")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s)).strip("_")


def _http(url):
    with _net:
        wait = MIN_GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers=HEAD)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        finally:
            _last[0] = time.time()


_bak = [0.0]


def _read(p):
    """Lê o JSON; se o arquivo estiver corrompido/vazio (app encerrado no meio da gravação), usa o .bak."""
    for q in (p, p.with_name(p.name + ".bak")):
        try:
            v = json.loads(q.read_text(encoding="utf-8"))
            if v:
                return v
        except Exception:
            pass
    return None


def _write(p, obj, backup=False):
    """Gravação atômica (arquivo temporário + rename): nunca deixa o cache pela metade."""
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        if backup and p.exists() and time.time() - _bak[0] > 600:
            try:
                if json.loads(p.read_text(encoding="utf-8")):
                    shutil.copyfile(p, p.with_name(p.name + ".bak"))
                    _bak[0] = time.time()
            except Exception:
                pass
        tmp = p.with_name(p.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except Exception as e:
        print("market: falha ao gravar", p.name, e)


def load_index(force=False):
    """Carrega o índice (disco -> rede). Em falha, tenta de novo só depois de 5 min."""
    with _mem:
        if _state["slugs"] and not force and time.time() - _state["ts"] < INDEX_TTL:
            return True
        disk = _read(INDEX_FILE)
        if disk and not force and time.time() - disk.get("ts", 0) < INDEX_TTL:
            _state["by_ref"], _state["slugs"], _state["ts"] = disk["by_ref"], disk["slugs"], disk["ts"]
            return True
        if time.time() - _state["fail"] < 300 and not force:
            if disk:  # usa o índice velho enquanto a rede não volta
                _state["by_ref"], _state["slugs"] = disk["by_ref"], disk["slugs"]
            return bool(_state["slugs"])
        try:
            j = _http(API2 + "/items")
            items = j.get("data") if isinstance(j, dict) else j
            by_ref, slugs = _build(items or [])
            if not slugs:
                raise ValueError("lista de itens vazia")
            _state.update(by_ref=by_ref, slugs=slugs, ts=time.time(), error="", fail=0)
            _write(INDEX_FILE, {"ts": _state["ts"], "by_ref": by_ref, "slugs": slugs})
            return True
        except Exception as e:
            _state["fail"] = time.time()
            _state["error"] = "não consegui carregar a lista do warframe.market (%s)" % e
            if disk:
                _state["by_ref"], _state["slugs"] = disk["by_ref"], disk["slugs"]
            return bool(_state["slugs"])


def resolve(path, name):
    """slug do item no mercado: pelo caminho do jogo (gameRef) ou pelo nome. None = não existe lá."""
    ok = load_index()
    if ok:
        sl = _state["by_ref"].get(path) or _state["by_ref"].get((path or "").replace("/Lotus/StoreItems/", "/Lotus/", 1))
        if sl:
            return sl
        s = slugify(name)
        return s if s in _state["slugs"] else None
    return slugify(name) or None  # sem índice: tenta pelo nome mesmo


def status():
    load_index()
    return {"ok": bool(_state["slugs"]), "items": len(_state["slugs"]), "error": _state["error"]}


def _load_cache():
    raw = _read(CACHE_FILE) or {}
    if "prices" in raw:
        return raw.get("prices") or {}, raw.get("meta") or {}
    return raw, {}  # formato antigo: só os preços


_meta = {}


def _prices():
    if _state["prices"] is None:
        _state["prices"], m = _load_cache()
        _meta.update(m)
    return _state["prices"]


def _save(force=False):
    if force or time.time() - _state["saved"] > 8:
        _state["saved"] = time.time()
        _write(CACHE_FILE, {"meta": _meta, "prices": _prices()}, backup=True)


def _orders(slug):
    """Lista de ordens normalizada: (tipo, plat, status, rank, subtype, visível). Tenta v2 e cai para v1."""
    out = []
    try:
        j = _http("%s/orders/item/%s" % (API2, slug))
        data = j.get("data") if isinstance(j, dict) else None
        if isinstance(data, dict):  # formato /top
            data = [dict(o, type=t) for t in ("sell", "buy") for o in (data.get(t) or [])]
        for o in data or []:
            u = o.get("user") or {}
            out.append(((o.get("type") or "").lower(), int(o.get("platinum") or 0), (u.get("status") or "").lower(),
                        o.get("rank"), o.get("subtype"), o.get("visible", True)))
        return out
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise
    except Exception:
        pass
    j = _http("%s/items/%s/orders" % (API1, slug))
    for o in ((j.get("payload") or {}).get("orders") or []):
        u = o.get("user") or {}
        out.append(((o.get("order_type") or "").lower(), int(o.get("platinum") or 0), (u.get("status") or "").lower(),
                    o.get("mod_rank"), o.get("subtype"), o.get("visible", True)))
    return out


def _compute(slug, rank, sub):
    """Busca na rede e calcula o preço. Devolve dict com 'sell'/'buy'/'none' ou {'error': ...}."""
    try:
        orders = _orders(slug)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"none": True, "ts": time.time()}
        return {"error": "warframe.market respondeu HTTP %s" % e.code}
    except Exception as e:
        return {"error": "não consegui falar com o warframe.market (%s)" % e}

    def keep(o):
        t, p, st, rk, sb, vis = o
        if not vis or p <= 0:
            return False
        if rank != "any" and rk is not None and str(rk) != str(rank):
            return False
        if sub and sb and sb != sub:
            return False
        return True
    ords = [o for o in orders if keep(o)]
    live = [o for o in ords if o[2] in ("ingame", "online")]
    offline = False
    if not live and ords:
        live, offline = ords, True
    sell = sorted(o[1] for o in live if o[0] == "sell")
    buy = sorted((o[1] for o in live if o[0] == "buy"), reverse=True)
    res = {"ts": time.time(), "sell": sell[0] if sell else None, "buy": buy[0] if buy else None,
           "n_sell": len(sell), "n_buy": len(buy), "offline": offline}
    if not sell and not buy:
        res["none"] = True
    return res


# ------------------------------------------------------------------ fila + worker
_cv = threading.Condition()
_heap, _want, _seq = [], {}, itertools.count()
_fail = {}
_started = [False]


def _enqueue(key, prio):
    with _cv:
        cur = _want.get(key)
        if cur is None and len(_want) >= MAX_QUEUE:
            return
        if cur is None or prio < cur:
            _want[key] = prio
            heapq.heappush(_heap, (prio, next(_seq), key))
            _cv.notify()


def _worker():
    while True:
        with _cv:
            key = None
            while key is None:
                while _heap:
                    prio, _, k = heapq.heappop(_heap)
                    if _want.get(k) == prio:
                        key = k
                        break
                if key is None:
                    _cv.wait()
        slug, rank, sub = (key.split("|") + ["", ""])[:3]
        res = _compute(slug, rank, sub or None)
        with _mem:
            if "error" in res:
                _fail[key] = (time.time(), res["error"])
            else:
                _prices()[key] = res
                _fail.pop(key, None)
                _save()
        with _cv:
            _want.pop(key, None)
        if "error" in res:
            time.sleep(3)


def start():
    if not _started[0]:
        _started[0] = True
        threading.Thread(target=_worker, daemon=True, name="market-worker").start()


def _maybe_sweep():
    """1x por dia: reenfileira (prioridade baixa) todo preço do cache que passou de 24h."""
    now = time.time()
    with _mem:
        P = _prices()
        if now - _meta.get("last_sweep", 0) < 600:
            return
        _meta["last_sweep"] = now
        ttl = _ttl()
        stale = [k for k, e in P.items() if now - e.get("ts", 0) > ttl]
        _save(True)
    for k in stale:
        _enqueue(k, 2)


_KEY = re.compile(r"^([a-z0-9_]{1,80})\|(any|\d{1,2})\|([a-z]{0,12})$")


def batch(keys, prio=0):
    """Resposta imediata: {chave: preço | {'pending':True} | {'error':...}}. Chave = 'slug|rank|sub'."""
    start()
    _maybe_sweep()
    prio = 0 if prio == 0 else 1
    now = time.time()
    out = {}
    slugs = _state["slugs"]
    with _mem:
        P = _prices()
        for k in keys[:MAX_BATCH]:
            m = _KEY.match(k)
            if not m:
                continue
            if slugs and m.group(1) not in slugs:
                out[k] = {"none": True}
                continue
            e = P.get(k)
            if e:
                stale = now - e.get("ts", 0) > _ttl()
                out[k] = dict(e, stale=stale)
                if stale:
                    _enqueue(k, prio)
                continue
            f = _fail.get(k)
            if f and now - f[0] < 60:
                out[k] = {"error": f[1]}
                continue
            _enqueue(k, prio)
            out[k] = {"pending": True}
    return out


def refresh_all():
    """Renova TODOS os preços guardados, em segundo plano. Os valores antigos continuam valendo até serem trocados."""
    start()
    with _mem:
        keys = list(_prices().keys())
        _meta["last_sweep"] = time.time()
    for k in keys:
        _enqueue(k, 2)
    return len(keys)


def info():
    with _cv:
        q = len(_want)
    return {"queue": q, "last_sweep": _meta.get("last_sweep"), "cached": len(_prices())}


def max_rank(slug):
    """Rank máximo do item segundo o índice do mercado (None se desconhecido)."""
    try:
        return (_state["slugs"].get(slug) or {}).get("max")
    except Exception:
        return None
