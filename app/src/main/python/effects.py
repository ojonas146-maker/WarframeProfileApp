"""Efeitos de mods e arcanos (por rank), a partir do Public Export oficial da Digital Extremes.
Gera data/effects.json: { uniqueName: {n, d(drain), p(polaridade), r(raridade), t(tipo), s[por rank], x[descrição]} }"""
import json, os, re, threading, time, urllib.request
from pathlib import Path

BASE = Path(os.environ.get("WF_HOME") or Path(__file__).parent)
OUT = BASE / "data" / "effects.json"
ORIGIN = "https://origin.warframe.com/PublicExport/index_en.txt.lzma"
CONTENT = "https://content.warframe.com/PublicExport/Manifest/"
UA = {"User-Agent": "Mozilla/5.0 warframe-profile"}
_st = {"busy": False, "err": "", "data": None, "ts": 0}


def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()


def _clean(s):
    s = re.sub(r"<[^>]+>\s*", "", s or "").replace("\r", "")
    return re.sub(r"\n{2,}", "\n", s).strip()


def build():
    import lzma
    index = lzma.LZMADecompressor(format=lzma.FORMAT_AUTO).decompress(_get(ORIGIN)).decode().split()
    files = {l.split("!")[0]: l for l in index}
    out = {}
    for fname, key in (("ExportUpgrades_en.json", "ExportUpgrades"), ("ExportRelicArcane_en.json", "ExportRelicArcane")):
        j = json.loads(_get(CONTENT + files[fname]).decode("utf-8", "replace"), strict=False)
        for e in j.get(key, []):
            ls = e.get("levelStats") or []
            desc = [_clean(x) for x in (e.get("description") or [])]
            if not ls and not desc:
                continue
            out[e["uniqueName"]] = {"n": _clean(e.get("name")), "d": e.get("baseDrain"), "p": e.get("polarity"), "r": e.get("rarity"),
                                    "t": e.get("type") or e.get("compatName"),
                                    "s": ["\n".join(_clean(x) for x in lv.get("stats", [])) for lv in ls], "x": desc}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    _st["data"] = out
    return len(out)


def _load():
    if _st["data"] is None and OUT.exists():
        try:
            _st["data"] = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            _st["data"] = None
    return _st["data"]


def get(path):
    """-> (dict|None, status) status: ok | building | error:<msg>"""
    d = _load()
    if d is not None:
        e = d.get(path) or d.get(path.replace("/Lotus/StoreItems/", "/Lotus/", 1))
        return (e, "ok") if e else (None, "notfound")
    if _st["err"] and not _st["busy"] and time.time() - _st["ts"] < 120:
        return None, "error:" + _st["err"]
    if not _st["busy"]:
        _st["busy"] = True
        _st["err"] = ""
        _st["ts"] = time.time()

        def run():
            try:
                build()
            except ImportError:
                _st["err"] = "Este Python não tem lzma. No Termux rode: python3 tools/effects_build.py e suba o arquivo gerado."
            except Exception as e:
                _st["err"] = "Falha ao baixar os efeitos: %s" % e
            finally:
                _st["busy"] = False
        threading.Thread(target=run, daemon=True).start()
        return None, "building"
    return (None, "building") if _st["busy"] else (None, "error:" + (_st["err"] or "erro"))


if __name__ == "__main__":
    print("efeitos:", build(), "->", OUT)
