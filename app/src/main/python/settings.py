"""Configurações do app (data/settings.json), gravadas de forma atômica."""
import json, os, threading
from pathlib import Path

BASE = Path(os.environ.get("WF_HOME") or Path(__file__).parent)
F = BASE / "data" / "settings.json"
DEFAULTS = {"price_ttl_h": 24, "wfm_status": ""}
_lock = threading.Lock()
_cur = {}


def _load():
    if not _cur:
        try:
            _cur.update(json.loads(F.read_text(encoding="utf-8")))
        except Exception:
            pass
        for k, v in DEFAULTS.items():
            _cur.setdefault(k, v)
    return _cur


def get(key=None):
    with _lock:
        d = _load()
        return d.get(key, DEFAULTS.get(key)) if key else dict(d)


def update(patch):
    with _lock:
        d = _load()
        if "price_ttl_h" in patch:
            try:
                v = int(patch["price_ttl_h"])
            except Exception:
                raise ValueError("Frequência inválida.")
            if not 1 <= v <= 720:
                raise ValueError("Frequência fora do limite (1 a 720 horas).")
            d["price_ttl_h"] = v
        if "wfm_status" in patch:
            if patch["wfm_status"] not in ("", "online", "ingame", "invisible"):
                raise ValueError("Status inválido.")
            d["wfm_status"] = patch["wfm_status"]
        F.parent.mkdir(parents=True, exist_ok=True)
        tmp = F.with_name(F.name + ".tmp")
        tmp.write_text(json.dumps(d), encoding="utf-8")
        os.replace(tmp, F)
        return dict(d)
