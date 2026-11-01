#!/usr/bin/env python3
"""Servidor local do Warframe Profile. Uso: python3 server.py  ->  http://localhost:8000"""
import hmac, json, math, os, re, traceback, urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import market
import auth
from http.cookies import SimpleCookie

BASE = Path(os.environ.get("WF_HOME") or Path(__file__).parent)
APP_TOKEN = os.environ.get("WF_TOKEN", "")   # modo app: só a WebView do próprio app consegue abrir o servidor local
DATA_FILE = BASE / "lastData_decoded.json"
PORT = 8000
SERVER_VERSION = "2026.11.01-app1"

_cache = {"mtime": 0, "data": None, "catalog": None, "archon": None, "langs": None, "nodes": None, "missions": None, "syndicates": None, "regions": None, "factions": None}

def load():
    m = DATA_FILE.stat().st_mtime
    if m != _cache["mtime"]:
        _cache["data"] = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        _cache["mtime"] = m
    return _cache["data"]

def _json(path):
    p = BASE / path
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def catalog():
    if _cache["catalog"] is None:
        cpath = BASE / "data" / "catalog.json"
        _cache["catalog"] = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else False
    return _cache["catalog"] or None

def archon_db():
    if _cache["archon"] is None:
        _cache["archon"] = _json("archonShards.json") or {}
    return _cache["archon"]

def langs():
    if _cache["langs"] is None:
        _cache["langs"] = _json("languages.json") or {}
    return _cache["langs"]

def nodes():
    if _cache["nodes"] is None:
        _cache["nodes"] = _json("solNodes.json") or {}
    return _cache["nodes"]

def synd_db():
    if _cache["syndicates"] is None:
        _cache["syndicates"] = _json("syndicatesData.json") or {}
    return _cache["syndicates"]

def mission_types():
    if _cache["missions"] is None:
        _cache["missions"] = _json("missionTypes.json") or {}
    return _cache["missions"]

def factions():
    if _cache["factions"] is None:
        _cache["factions"] = _json("factionsData.json") or {}
    return _cache["factions"]

_SKIP_JSON = {"lastData_decoded.json", "languages.json", "catalog.json", "archonShards.json",
              "factionsData.json", "missionTypes.json", "syndicatesData.json", "solNodes.json"}

def regions_raw():
    """Nós no formato 'cru' do jogo (SolNodeXXX -> name/systemName/missionType/faction...).
    Procura automaticamente qualquer .json da pasta (ou de data/) nesse formato e junta tudo;
    solNodesExtra.json entra primeiro, então um arquivo completo seu sobrescreve o trecho."""
    if _cache["regions"] is None:
        cands = []
        for folder in (BASE, BASE / "data"):
            if folder.exists():
                cands += [p for p in folder.glob("*.json") if p.name not in _SKIP_JSON and p.stat().st_size < 12_000_000]
        cands.sort(key=lambda p: (p.name != "solNodesExtra.json", p.name))
        merged = {}
        for p in cands:
            try:
                j = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(j, dict) and any(isinstance(v, dict) and "missionType" in v and "systemName" in v
                                           for v in list(j.values())[:40]):
                merged.update({k: v for k, v in j.items() if isinstance(v, dict)})
        _cache["regions"] = merged
    return _cache["regions"]

# nomes de locais/missões que não existem no languages.json
LANG_FIX = {
    "indexlowrisk": "Index – Low Risk", "indexmediumrisk": "Index – Medium Risk", "indexhighrisk": "Index – High Risk",
    "golemassassinatekey": "Golem Assassinate", "infestedaladassassinatekey": "Mutalist Alad V Assassinate",
}

def lang_text(path):
    """Texto legível de um caminho /Lotus/Language/...; sem tradução, humaniza o último trecho."""
    if not path:
        return ""
    v = langs().get(path.lower())
    if isinstance(v, dict) and v.get("value"):
        return v["value"]
    last = path.rstrip("/").split("/")[-1]
    last = re.sub(r"^MissionName_", "", last)
    fixed = LANG_FIX.get(last.lower())
    if fixed:
        return fixed
    last = re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z])(?=[A-Z][a-z])", " ", last).replace("_", " ")
    last = re.sub(r"RJ ?Mission Name", "Railjack Mission", last)
    last = re.sub(r"^Nemesis Showdown Node (\w+)$", r"Nemesis Showdown – \1", last)
    return re.sub(r"\s+", " ", last).strip()

def region_info(tag):
    """(nome, tipo, inimigo) de um nó a partir do JSON cru, ou do catálogo oficial se existir."""
    r = regions_raw().get(tag)
    if r:
        name, system = lang_text(r.get("name")), lang_text(r.get("systemName"))
        system = re.sub(r"\s*SPACE$", "", system)
        if system and name:
            if name.lower() == system.lower():
                pass
            elif name.lower().endswith(system.lower()):
                name = name[:-len(system)].strip()
            elif name.lower().startswith(system.lower()):
                name = name[len(system):].strip()
        if system and name and name.lower() != system.lower():
            name = f"{name} ({system})"
        mt = r.get("missionType")
        typ = (mission_types().get(mt) or {}).get("value") or lang_text(r.get("missionName")) \
            or (mt or "").replace("MT_", "").replace("_", " ").title()
        enemy = (factions().get(r.get("faction")) or {}).get("value") or \
            (r.get("faction") or "").replace("FC_", "").replace("_", " ").title()
        return name, typ, enemy
    cat = catalog()
    cr = ((cat or {}).get("regions") or {}).get(tag)
    if cr and cr.get("n"):
        return (f"{cr['n']} ({cr['s']})" if cr.get("s") and cr["s"] != cr["n"] else cr["n"]), "", ""
    return None

def pretty(path: str) -> str:
    if not path:
        return "?"
    cat = catalog()
    if cat:
        items = cat.get("items", {})
        ent = items.get(path) or items.get(path.replace("/Lotus/StoreItems/", "/Lotus/", 1))
        if ent and ent.get("n"):
            return ent["n"]
    L = langs()
    variants = [path.lower(), path.replace("/Lotus/Types/", "/Lotus/StoreItems/Types/").lower(),
                path.replace("/Lotus/StoreItems/", "/Lotus/").lower()]
    for key in variants:
        if key in L and isinstance(L[key], dict) and L[key].get("value"):
            return L[key]["value"]
    name = path.rstrip("/").split("/")[-1]
    name = re.sub(r"(PlayerWep|PowerSuit|Powersuit|Blueprint)$", "", name) or path.split("/")[-1]
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " ")
    return name.strip()

def icon_of(path: str):
    cat = catalog()
    if not cat:
        return None
    items = cat.get("items", {})
    ent = items.get(path) or items.get(path.replace("/Lotus/StoreItems/", "/Lotus/", 1))
    loc = (ent or {}).get("i")
    if not loc:
        return None
    if loc.startswith("http"):
        return loc
    return "https://content.warframe.com/PublicExport" + (loc if loc.startswith("/") else "/" + loc)

def date_of(v):
    try:
        return datetime.fromtimestamp(int(v["$date"]["$numberLong"]) / 1000, timezone.utc).strftime("%d/%m/%Y")
    except Exception:
        return None

ITEM_CATS = {
    "warframes": ("Suits", 1000, "Warframe"),
    "primary": ("LongGuns", 500, "Primaria"),
    "secondary": ("Pistols", 500, "Secundaria"),
    "melee": ("Melee", 500, "Corpo a corpo"),
    "companions": (None, 1000, "Companheiro"),
    "archwing": ("SpaceSuits", 1000, "Archwing"),
    "necramechs": ("MechSuits", 1000, "Necramech"),
    "robotic": ("SentinelWeapons", 500, "Robotica"),
    "amps": ("OperatorAmps", 2250, "Amp"),
}

INV_CATS = {
    "resources": "MiscItems",
    "mods": "RawUpgrades",
    "arcanes": "RawUpgrades",
    "blueprints": "Recipes",
    "recipes": "Recipes",
    "consumables": "Consumables",
    "cosmetics": "FlavourItems",
    "skins": "WeaponSkins",
}

COLOR_MAP = {
    "ACC_RED": ("red", "Crimson"),
    "ACC_YELLOW": ("yellow", "Amber"),
    "ACC_BLUE": ("blue", "Azure"),
    "ACC_ORANGE": ("orange", "Topaz"),
    "ACC_PURPLE": ("purple", "Violet"),
    "ACC_GREEN": ("green", "Emerald"),
    "ACC_VIOLET": ("purple", "Violet"),
}

INV_SHARD = {
    "ArchonCrystalAmar": ("red", False),
    "ArchonCrystalAmarMythic": ("red", True),
    "ArchonCrystalNira": ("yellow", False),
    "ArchonCrystalNiraMythic": ("yellow", True),
    "ArchonCrystalBoreal": ("blue", False),
    "ArchonCrystalBorealMythic": ("blue", True),
    "ArchonCrystalGreen": ("green", False),
    "ArchonCrystalGreenMythic": ("green", True),
    "ArchonCrystalViolet": ("purple", False),
    "ArchonCrystalVioletMythic": ("purple", True),
    "ArchonCrystalOrange": ("orange", False),
    "ArchonCrystalOrangeMythic": ("orange", True),
}

# tipos que NÃO têm slot Exilus nem Adaptador de arcano
NO_EXILUS_ARCANE = {"Companheiro", "Sentinela", "MOA", "Archwing", "Necramech"}

KEY_ITEMS = ["Forma", "FormaAura", "FormaStance", "FormaUmbra", "Kuva", "RivenSliver", "OrokinCatalyst", "OrokinReactor", "Aya"]

INTRINSICS = {
    "LPS_GUNNERY": "Artilharia",
    "LPS_PILOTING": "Pilotagem",
    "LPS_TACTICAL": "Tatica",
    "LPS_ENGINEERING": "Engenharia",
    "LPS_COMMAND": "Comando",
}
DRIFTER = {
    "LPS_DRIFT_RIDING": "Pilotagem",
    "LPS_DRIFT_COMBAT": "Combate",
    "LPS_DRIFT_ENDURANCE": "Resistencia",
    "LPS_DRIFT_OPPORTUNITY": "Oportunidade",
}

def xp_map(d):
    return {x["ItemType"]: x.get("XP", 0) for x in d.get("XPInfo", [])}

def rank_of(xp, mult):
    if not xp or not mult:
        return 0
    return min(30, int(math.sqrt(max(0, xp) / mult)))

def parse_color(color):
    key = color or ""
    tau = key.endswith("_MYTHIC")
    if tau:
        key = key[:-7]
    mapped = COLOR_MAP.get(key)
    if mapped:
        return mapped[0], mapped[1], tau
    return "blue", key or "Shard", tau

def shard_effect(color_key, upgrade):
    db = archon_db()
    base = (color_key or "").replace("_MYTHIC", "")
    info = db.get(color_key) or db.get(base) or {}
    ups = info.get("upgradeTypes") or {}
    if upgrade in ups:
        v = ups[upgrade]
        return v.get("value") if isinstance(v, dict) else str(v)
    return pretty(upgrade) if upgrade else ""

SHARD_PATH = {"red": "Amar", "yellow": "Nira", "blue": "Boreal", "green": "Green", "purple": "Violet", "orange": "Orange"}

def shard_icon(color, tau=False):
    """Ícone oficial do Archon Shard (normal ou Tauforged) a partir do catálogo."""
    k = SHARD_PATH.get(color)
    if not k:
        return None
    return icon_of("/Lotus/Types/Gameplay/NarmerSorties/ArchonCrystal" + k + ("Mythic" if tau else ""))

def item_shards(it):
    out = []
    for u in it.get("ArchonCrystalUpgrades") or []:
        if not isinstance(u, dict):
            continue
        raw = u.get("Color") or ""
        color, name, tau = parse_color(raw)
        out.append({
            "color": color,
            "name": name,
            "tau": tau,
            "icon": shard_icon(color, False),
            "glow": shard_icon(color, True) if tau else None,
            "effect": shard_effect(raw, u.get("UpgradeType")),
        })
    return out

def features(it):
    f = it.get("Features") or 0
    return {
        "reactor": bool(f & 1),
        "exilus": bool(f & 2),
        "arcane_slot": bool(f & 4),
    }

def enrich(d, it, kind, mult, xpmap):
    t = it.get("ItemType", "")
    xp = xpmap.get(t, it.get("XP", 0)) or 0
    feat = features(it)
    shards = item_shards(it)
    has_slots = kind not in NO_EXILUS_ARCANE
    name = pretty(t)
    return {
        "name": name,
        "path": t,
        "kind": kind,
        "xp": xp,
        "rank": rank_of(xp, mult),
        "forma": it.get("Polarized", 0) or 0,
        "polarized": it.get("Polarized", 0) or 0,
        "reactor": feat["reactor"],
        "exilus": feat["exilus"] and has_slots,
        "arcane_slot": feat["arcane_slot"] and has_slots,
        "has_exilus": has_slots,
        "has_arcane": has_slots,
        "shards": shards,
        "polarities": [str(p.get("Value") or p.get("Slot") or "") for p in (it.get("Polarity") or []) if isinstance(p, dict)],
        "lens": pretty(it["FocusLens"]) if it.get("FocusLens") else None,
        "prime": ("Prime" in name) or t.endswith("Prime"),
        "icon": icon_of(t),
        "mr": None,
    }

def list_items(d, cat):
    spec = ITEM_CATS.get(cat)
    if not spec:
        return []
    key, mult, kind = spec
    xpmap = xp_map(d)
    if cat == "companions":
        bags = []
        for k, kn in (("Sentinels", "Sentinela"), ("KubrowPets", "Companheiro"), ("MoaPets", "MOA")):
            bags.extend(enrich(d, it, kn, 1000, xpmap) for it in d.get(k, []))
        return sorted(bags, key=lambda i: (-i["rank"], i["name"]))
    return sorted((enrich(d, it, kind, mult, xpmap) for it in d.get(key, [])), key=lambda i: (-i["rank"], i["name"]))

EXTRA_INV = {"archon", "relics", "primeparts", "primesets"}
PRIME_RE = re.compile(r"\bPrime\b")

def _entry(t, count, rank=None, **kw):
    e = {"name": pretty(t), "path": t, "count": count, "icon": icon_of(t), "rank": rank, "rarity": None,
         "slug": None, "pr": "any", "sub": None}
    e.update(kw)
    return e

def _priced(e, pr="any", sub=None):
    e["slug"] = market.resolve(e["path"], e["name"])
    e["pr"], e["sub"] = pr, sub
    return e

def prime_parts(d):
    seen, out = set(), []
    for key in ("Recipes", "MiscItems"):
        for i in d.get(key, []):
            t = i.get("ItemType", "")
            if "/Types/Recipes/" not in t or t in seen:
                continue
            nm = pretty(t)
            if not PRIME_RE.search(nm) or "Primed" in nm or (i.get("ItemCount") or 0) <= 0:
                continue
            seen.add(t)
            out.append(_priced(_entry(t, i.get("ItemCount", 1))))
    return sorted(out, key=lambda x: (-x["count"], x["name"]))

def set_of(name):
    m = re.match(r"(.+?\bPrime)\b", name)
    return m.group(1) if m else name

_BADPATH = ("/Types/Recipes/", "/Skins/", "/Cosmetics/", "Ephemera", "Glyph")

def set_icon(sname, parts):
    """Imagem principal do set: o próprio Warframe/arma/sentinela (como na aba Warframes); senão o blueprint principal."""
    cat = catalog().get("items", {})
    best = None
    for p, v in cat.items():
        if v.get("n") == sname and v.get("i") and not any(b in p for b in _BADPATH):
            if best is None or len(p) < len(best[0]):
                best = (p, v["i"])
    if best:
        return icon_of(best[0])
    for p in parts:
        if p["name"] == sname + " Blueprint" and p.get("icon"):
            return p["icon"]
    return parts[0]["icon"]

def prime_sets(d):
    groups = {}
    for p in prime_parts(d):
        groups.setdefault(set_of(p["name"]), []).append(p)
    out = []
    for sname, parts in groups.items():
        sset = _entry(parts[0]["path"], sum(p["count"] for p in parts))
        sset.update(name=sname, path="set:" + sname, icon=set_icon(sname, parts), parts=sorted(parts, key=lambda x: x["name"]), n_parts=len(parts))
        sset["slug"] = market.resolve("set:" + sname, sname + " Set")
        out.append(sset)
    return sorted(out, key=lambda x: (-x["n_parts"], x["name"]))

def archon_inv(d):
    out = []
    for i in d.get("MiscItems", []):
        t = i.get("ItemType", "")
        last = t.split("/")[-1]
        if last not in INV_SHARD:
            continue
        color, tau = INV_SHARD[last]
        e = _entry(t, i.get("ItemCount", 1), color=color, tau=tau, icon=shard_icon(color, False), glow=shard_icon(color, True) if tau else None)
        out.append(_priced(e))
    return sorted(out, key=lambda x: (-x["count"], x["name"]))

def relics_inv(d):
    out = []
    for r in relics_api(d):
        tier = r.get("tier") or ""
        nm = r["name"] if r["name"].startswith(tier) else (tier + " " + r["name"]).strip()
        e = {"name": nm, "path": r.get("path"), "count": r["total"], "icon": r.get("icon"), "rank": None, "rarity": None,
             "slug": None, "pr": "any", "sub": "intact", "counts": r.get("counts"), "tier": tier}
        e["slug"] = market.resolve(r.get("path"), nm + " Relic")
        out.append(e)
    return sorted(out, key=lambda x: (-x["count"], x["name"]))

def _with_max(e, kind):
    """Rank máximo: catálogo (fl) -> índice do warframe.market -> 5 para arcanos (padrão do jogo)."""
    item = (catalog().get("items", {}) or {}).get(e["path"]) or {}
    mx = item.get("fl")
    if mx is None and e.get("slug"):
        mx = market.max_rank(e["slug"])
    if not mx:  # 0 = sem rank (ex.: Riven) -> desconhecido
        mx = None
    if mx is None and kind == "arcane":
        mx = 5
    e["max"] = mx
    if e.get("rank") not in (None, 0, mx):  # rank intermediário quase não tem ordens: não gasta consulta no mercado
        e["slug"], e["note"] = None, "rank intermediário · sem preço"
    return e

def inventory(d, cat):
    if cat == "archon":
        return archon_inv(d)
    if cat == "relics":
        return relics_inv(d)
    if cat == "primeparts":
        return prime_parts(d)
    if cat == "primesets":
        return prime_sets(d)
    isarc = lambda i: "/CosmeticEnhancers/" in i.get("ItemType", "") or "Arcane" in i.get("ItemType", "")
    if cat == "arcanes":
        # Arcanos ficam em /Lotus/Upgrades/CosmeticEnhancers/ (a maioria não tem "Arcane" no caminho)
        out = [_with_max(_priced(_entry(i["ItemType"], i.get("ItemCount", 1)), 0), "arcane") for i in d.get("RawUpgrades", []) if isarc(i)]
        ranked = {}  # arcanos já ranqueados (um por unidade) agrupados por tipo + rank
        for i in d.get("Upgrades", []):
            if isarc(i):
                t = i.get("ItemType", "")
                try:
                    lvl = int(json.loads(i.get("UpgradeFingerprint") or "{}").get("lvl", 0))
                except Exception:
                    lvl = 0
                ranked[(t, lvl)] = ranked.get((t, lvl), 0) + 1
        for (t, lvl), n in ranked.items():
            out.append(_with_max(_priced(_entry(t, n, lvl), lvl), "arcane"))
        return sorted(out, key=lambda i: (-(i["count"] or 0), i["name"]))
    if cat == "mods":
        # Uma linha por mod. Sem rank (estoque) e ranqueados ficam juntos na mesma entrada; a tela decide o que mostrar.
        raw, ranked = {}, {}
        for i in d.get("RawUpgrades", []):
            if not isarc(i):
                raw[i["ItemType"]] = raw.get(i["ItemType"], 0) + i.get("ItemCount", 1)
        for i in d.get("Upgrades", []):
            t = i.get("ItemType", "")
            if "/Upgrades/Mods/" not in t:
                continue
            try:
                lvl = int(json.loads(i.get("UpgradeFingerprint") or "{}").get("lvl", 0))
            except Exception:
                lvl = 0
            ranked.setdefault(t, {})[lvl] = ranked.get(t, {}).get(lvl, 0) + 1
        out = []
        for t in set(raw) | set(ranked):
            rk = ranked.get(t, {})
            e = _with_max(_priced(_entry(t, raw.get(t, 0) + sum(rk.values())), 0), "mod")  # preço: sempre do rank 0 (uma consulta por mod)
            e["unranked"] = raw.get(t, 0)
            e["ranked"] = sorted(([l, n] for l, n in rk.items() if l > 0), reverse=True)
            e["total_ranked"] = sum(n for l, n in rk.items() if l > 0)
            e["at_max"] = rk.get(e["max"], 0) if e["max"] else 0
            out.append(e)
        return sorted(out, key=lambda i: (-i["unranked"], i["name"]))
    key = INV_CATS.get(cat)
    lst = d.get(key, []) if key else []
    out = [_entry(i.get("ItemType", ""), i.get("ItemCount", 1)) for i in lst]
    return sorted(out, key=lambda i: -(i["count"] or 0))

def count_key(d, suffix):
    n = 0
    for i in d.get("MiscItems", []):
        t = i.get("ItemType", "")
        if t.endswith("/" + suffix) or t.endswith(suffix):
            n += i.get("ItemCount", 0)
    return n

def region_name(v):
    """'SolarMapDeimosName' -> 'Deimos'; valores já legíveis ('Ceres') ficam como estão."""
    if not v:
        return v
    s = re.sub(r"^SolarMap", "", str(v))
    s = re.sub(r"Name$", "", s)
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s).strip() or v

def summary(d):
    skills = d.get("PlayerSkills") or {}
    all_equip = []
    for cat in ITEM_CATS:
        all_equip.extend(list_items(d, cat))
    forma_total = sum(x["forma"] for x in all_equip)
    maxed = sum(1 for x in all_equip if x["rank"] >= 30)
    shards_installed = sum(len(x["shards"]) for x in all_equip)
    inv_shards = 0
    relic_total = 0
    for i in d.get("MiscItems", []):
        last = i.get("ItemType", "").split("/")[-1]
        if last in INV_SHARD:
            inv_shards += i.get("ItemCount", 0)
        if "VoidProjection" in i.get("ItemType", "") or "Relic" in i.get("ItemType", ""):
            relic_total += i.get("ItemCount", 0)

    key_items = []
    seen = set()
    for suffix in KEY_ITEMS:
        n = count_key(d, suffix)
        if n:
            key_items.append({"name": pretty("/Lotus/Types/Items/MiscItems/" + suffix), "count": n, "path": suffix})
            seen.add(suffix)
    for extra in ("Vosfor", "SteelEssence", "PathosClamp"):
        n = count_key(d, extra)
        if n and extra not in seen:
            key_items.append({"name": pretty("/Lotus/Types/Items/MiscItems/" + extra), "count": n, "path": extra})

    focus = None
    fu = d.get("FocusUpgrades") or []
    if fu:
        focus = pretty(fu[0].get("ItemType", ""))

    return {
        "catalog": bool(catalog()),
        "mastery": d.get("PlayerLevel"),
        "created": date_of(d.get("Created", {})),
        "region": region_name(d.get("LastRegionPlayed")),
        "credits": d.get("RegularCredits"),
        "platinum": (d.get("PremiumCredits") or 0) + (d.get("PremiumCreditsFree") or 0),
        "endo": d.get("FusionPoints"),
        "focus_daily": d.get("DailyFocus"),
        "focus_school": focus,
        "trades": d.get("TradesRemaining"),
        "gifts": d.get("GiftsRemaining"),
        "alignment": d.get("Alignment"),
        "skills": skills,
        "intrinsics": {lab: skills.get(k, 0) for k, lab in INTRINSICS.items()},
        "drifter": {lab: skills.get(k, 0) for k, lab in DRIFTER.items()},
        "counts": {
            "warframes": len(d.get("Suits", [])),
            "primary": len(d.get("LongGuns", [])),
            "secondary": len(d.get("Pistols", [])),
            "melee": len(d.get("Melee", [])),
            "companions": len(d.get("Sentinels", [])) + len(d.get("KubrowPets", [])) + len(d.get("MoaPets", [])),
            "archwing": len(d.get("SpaceSuits", [])),
            "necramechs": len(d.get("MechSuits", [])),
            "resources": len(d.get("MiscItems", [])),
            "mods": len(d.get("RawUpgrades", [])),
            "recipes": len(d.get("Recipes", [])),
            "consumables": len(d.get("Consumables", [])),
            "cosmetics": len(d.get("FlavourItems", [])),
            "skins": len(d.get("WeaponSkins", [])),
        },
        "boosters": [{"name": pretty(b.get("ItemType", "")), "expiry": b.get("ExpiryDate")} for b in d.get("Boosters", [])],
        "key_items": key_items,
        "forma_total": forma_total,
        "maxed": maxed,
        "shards": shards_installed,
        "shards_inv": inv_shards,
        "relic_total": relic_total,
        "mission_completes": sum(m.get("Completes", 0) for m in d.get("Missions", [])),
        "nodes_played": len(d.get("Missions", [])),
        "focus_xp": d.get("FocusXP") or {},
        "focus_ability": pretty(d["FocusAbility"]) if d.get("FocusAbility") else None,
        "has_guild": bool(d.get("GuildId")),
        "account_id": None,
    }

def archon_api(d):
    frames = []
    installed_acc = {}
    for it in list_items(d, "warframes"):
        if not it["shards"]:
            continue
        frames.append({"name": it["name"], "icon": it["icon"], "shards": it["shards"], "path": it["path"]})
        for s in it["shards"]:
            k = s["color"]
            rec = installed_acc.setdefault(k, {"color": s["color"], "name": s["name"], "normal": 0, "tau": 0,
                                               "icon": shard_icon(k), "icon_tau": shard_icon(k, True)})
            if s["tau"]:
                rec["tau"] += 1
            else:
                rec["normal"] += 1
    inv_acc = {}
    for i in d.get("MiscItems", []):
        last = i.get("ItemType", "").split("/")[-1]
        if last not in INV_SHARD:
            continue
        color, tau = INV_SHARD[last]
        name = {"red": "Crimson", "yellow": "Amber", "blue": "Azure", "green": "Emerald", "purple": "Violet", "orange": "Topaz"}.get(color, color)
        rec = inv_acc.setdefault(color, {"color": color, "name": name, "normal": 0, "tau": 0,
                                         "icon": shard_icon(color), "icon_tau": shard_icon(color, True)})
        if tau:
            rec["tau"] += i.get("ItemCount", 0)
        else:
            rec["normal"] += i.get("ItemCount", 0)
    installed = sorted(installed_acc.values(), key=lambda x: -(x["normal"] + x["tau"]))
    inventory_rows = sorted(inv_acc.values(), key=lambda x: -(x["normal"] + x["tau"]))
    return {
        "installed": installed,
        "inventory": inventory_rows,
        "frames": frames,
        "total_installed": sum(r["normal"] + r["tau"] for r in installed),
        "total_inventory": sum(r["normal"] + r["tau"] for r in inventory_rows),
    }

def relics_api(d):
    QUAL = {"Bronze": "Intact", "Silver": "Exceptional", "Gold": "Flawless", "Platinum": "Radiant"}
    TIER = {"T1": "Lith", "T2": "Meso", "T3": "Neo", "T4": "Axi", "T5": "Requiem"}
    cat = catalog() or {}
    relic_info = cat.get("relics") or {}
    bags = {}
    for i in d.get("MiscItems", []):
        tpath = i.get("ItemType", "")
        if "VoidProjection" not in tpath and "Relic" not in tpath:
            continue
        raw = pretty(tpath)
        quality = "Intact"
        for suf, qn in QUAL.items():
            if tpath.endswith(suf) or suf in raw:
                quality = qn
                break
        tier = "Outro"
        for code, name in TIER.items():
            if f"/{code}Void" in tpath or tpath.split("/")[-1].startswith(code):
                tier = name
                break
        if tier == "Outro":
            for cand in ("Lith", "Meso", "Neo", "Axi", "Requiem"):
                if cand in raw:
                    tier = cand
                    break
        name = raw
        name = re.sub(r"\s*\((Intact|Exceptional|Flawless|Radiant)\)\s*", " ", name).strip()
        name = re.sub(r"\s*Relic\s*", " ", name).strip()
        last = tpath.split("/")[-1]
        base = re.sub(r"(Bronze|Silver|Gold|Platinum)$", "", last)
        rec = bags.setdefault(base, {
            "name": name or base,
            "tier": tier,
            "tier_n": ["Lith", "Meso", "Neo", "Axi", "Requiem", "Outro"].index(tier) if tier in ["Lith", "Meso", "Neo", "Axi", "Requiem", "Outro"] else 9,
            "counts": {},
            "total": 0,
            "icon": icon_of(tpath),
            "vault": "Vault" in tpath or "Vault" in raw,
            "rewards": [],
            "path": tpath,
        })
        rec["counts"][quality] = rec["counts"].get(quality, 0) + i.get("ItemCount", 0)
        rec["total"] += i.get("ItemCount", 0)
        info = relic_info.get(tpath) or relic_info.get(tpath.replace("/Lotus/Types/", "/Lotus/StoreItems/Types/"))
        if info and not rec["rewards"]:
            rec["rewards"] = [{"name": pretty(r[0]), "rarity": str(r[1] or "").lower(), "count": r[2], "icon": icon_of(r[0])} for r in info.get("rw", [])]
    return sorted(bags.values(), key=lambda r: -r["total"])

def forma_api(d):
    by_cat = {}
    top = []
    for cat in ITEM_CATS:
        items = list_items(d, cat)
        by_cat[cat] = sum(x["forma"] for x in items)
        top.extend(items)
    top = sorted([x for x in top if x["forma"]], key=lambda x: -x["forma"])[:40]
    return {"total": sum(by_cat.values()), "by_cat": by_cat, "top": top}

# Standing máximo DENTRO de cada rank (tabela oficial) e onde cada rank começa (acumulado)
SYN_CAP = {-2: 44000, -1: 22000, 0: 5000, 1: 22000, 2: 44000, 3: 70000, 4: 99000, 5: 132000}
SYN_BASE = {-2: 27000, -1: 5000, 0: 0, 1: 5000, 2: 27000, 3: 71000, 4: 141000, 5: 240000}  # |standing| ao entrar no rank

def syn_progress(standing, title):
    """Progresso dentro do rank atual. Ex.: Vox Solaris 352.000 no rank 5 -> 112.000 / 132.000.
    Retorna None quando os números não batem com a tabela padrão (sindicatos com escala própria)."""
    if standing is None or title not in SYN_CAP:
        return None
    neg = standing < 0 or title < 0
    mag = abs(standing)
    cur = mag - SYN_BASE[title] if title != 0 else mag
    cap = SYN_CAP[title]
    if cur < 0 or cur > cap:
        return None
    return {"rank": title, "cur": cur, "cap": cap, "neg": neg and cur > 0, "maxed": title == 5 and cur >= cap}

def syndicates_api(d):
    db = synd_db()
    out = []
    for a in d.get("Affiliations", []):
        tag = a.get("Tag", "")
        if tag.startswith("RadioLegion"):  # Nightwave: só ruído nesta tela
            continue
        info = db.get(tag) or {}
        name = info.get("name") if isinstance(info, dict) else None
        standing = a.get("Standing")
        prog = syn_progress(standing, a.get("Title")) or {}
        out.append({
            "name": name or pretty(tag).replace(" Syndicate", ""),
            "standing": standing or 0,
            "title": a.get("Title"),
            "tag": tag,
            "rank": prog.get("rank"),
            "cur": prog.get("cur"),
            "cap": prog.get("cap"),
            "neg": prog.get("neg", False),
            "maxed": prog.get("maxed", False),
        })
    return sorted(out, key=lambda a: -abs(a["standing"]))

EXTRA_NODES = {
    "CetusHub4": ("Cetus (Earth)", "Hub", "Tenno"),
    "CetusHub3": ("Cetus (Earth)", "Hub", "Tenno"),
    "CetusHub1": ("Cetus (Earth)", "Hub", "Tenno"),
    "SolarisUnitedHub1": ("Fortuna (Venus)", "Hub", "Corpus"),
    "DeimosHub": ("Necralisk (Deimos)", "Hub", "Entrati"),
    "EntratiLabHub": ("Sanctum Anatomica (Deimos)", "Hub", "Entrati"),
    "1999Hub": ("Höllvania Central Mall", "Hub", "The Hex"),
    "SolNode850": ("Höllvania (1999)", "Mission", "Scaldra/Techrot"),
    "SolNode851": ("Höllvania (1999)", "Mission", "Scaldra/Techrot"),
    "SolNode852": ("Höllvania (1999)", "Mission", "Scaldra/Techrot"),
    "SolNode853": ("Höllvania (1999)", "Mission", "Scaldra/Techrot"),
    "SolNode854": ("Höllvania (1999)", "Mission", "Scaldra/Techrot"),
    "SolNode855": ("Höllvania (1999)", "Mission", "Scaldra/Techrot"),
    "SolNode856": ("Höllvania (1999)", "Mission", "Scaldra/Techrot"),
    "SolNode857": ("Höllvania (1999)", "Mission", "Scaldra/Techrot"),
    "SolNode858": ("Höllvania (1999)", "Mission", "Scaldra/Techrot"),
    "SolNode860": ("Höllvania (1999)", "Mission", "Scaldra/Techrot"),

    "ZarimanHub": ("Chrysalith (Zariman)", "Hub", "Tenno"),
    "NokkoColony": ("Deepmines (Venus)", "Free Roam", "Corpus"),
    "SolNode801": ("Sanctuary Onslaught", "Onslaught", "Corrupted"),
    "SolNode802": ("Elite Sanctuary Onslaught", "Onslaught", "Corrupted"),
    "EarthToVenusJunction": ("Venus Junction (Earth)", "Junction", "Tenno"),
    "VenusToMercuryJunction": ("Mercury Junction (Venus)", "Junction", "Tenno"),
    "MercuryToMarsJunction": ("Mars Junction (Mercury)", "Junction", "Tenno"),
    "MarsToPhobosJunction": ("Phobos Junction (Mars)", "Junction", "Tenno"),
    "MarsToCeresJunction": ("Ceres Junction (Mars)", "Junction", "Tenno"),
    "JupiterToEuropaJunction": ("Europa Junction (Jupiter)", "Junction", "Tenno"),
    "SaturnToUranusJunction": ("Uranus Junction (Saturn)", "Junction", "Tenno"),
    "UranusToNeptuneJunction": ("Neptune Junction (Uranus)", "Junction", "Tenno"),
    "NeptuneToPlutoJunction": ("Pluto Junction (Neptune)", "Junction", "Tenno"),
    "PlutoToErisJunction": ("Eris Junction (Pluto)", "Junction", "Tenno"),
    "PlutoToSednaJunction": ("Sedna Junction (Pluto)", "Junction", "Tenno"),
    "EarthToMarsJunction": ("Mars Junction (Earth)", "Junction", "Tenno"),
    "CeresToJupiterJunction": ("Jupiter Junction (Ceres)", "Junction", "Tenno"),
    "JupiterToSaturnJunction": ("Saturn Junction (Jupiter)", "Junction", "Tenno"),
    "ErisToSednaJunction": ("Sedna Junction (Eris)", "Junction", "Tenno"),
    "ErisToHadesJunction": ("Hades Junction (Eris)", "Junction", "Tenno"),
}

def human_tag(tag):
    if not tag:
        return "?"
    last = tag.rstrip("/").split("/")[-1]
    last = re.sub(r"WeeklyMissions?", "", last)
    last = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", last)
    last = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", last)
    last = last.replace("_", " ").replace("-", " ")
    last = re.sub(r"\s+", " ", last).strip()
    last = re.sub(r"Hub\s*\d*$", "Hub", last)
    return last

def missions_api(d):
    nd = nodes()
    out = []
    for m in d.get("Missions", []):
        tag = m.get("Tag", "")
        extra = EXTRA_NODES.get(tag)
        info = nd.get(tag) or {}
        if not isinstance(info, dict):
            info = {}
        if extra:
            name, typ, enemy = extra
        else:
            name = info.get("value") or ""
            if name == tag:
                name = ""
            typ = info.get("type") or ""
            enemy = info.get("enemy") or ""
            if not (name and typ and enemy):
                ri = region_info(tag)
                if ri:
                    name, typ, enemy = name or ri[0], typ or ri[1], enemy or ri[2]
            if (not name) or name == tag:
                name = human_tag(tag)
            if tag.endswith("Junction") and not typ:
                typ = "Junction"
            if "Hub" in tag and not typ:
                typ = "Hub"
            if tag.startswith("CrewBattleNode") and not typ:
                typ = "Railjack"
                enemy = enemy or "Grineer/Corpus"
        out.append({
            "name": name,
            "node": name,
            "tag": tag,
            "type": typ,
            "enemy": enemy,
            "completes": m.get("Completes", 0),
            "steel_path": m.get("Tier", 0) == 1,
        })
    return sorted(out, key=lambda m: -m["completes"])


# ---------------------------------------------------------------- perfil público (opcional)
_pv_cache = {}
PV_LOCAL = ("profileViewingData.json", "data/profile_viewing.json")

def pv_fetch(pid):
    hit = _pv_cache.get(pid)
    if hit and datetime.now().timestamp() - hit[0] < 600:
        return hit[1]
    url = "https://api.warframe.com/cdn/getProfileViewingData.php?playerId=" + pid
    err = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 warframe-profile-local"})
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        _pv_cache[pid] = (datetime.now().timestamp(), j)
        return j
    except Exception as e:
        err = e
    for rel in PV_LOCAL:  # plano B: arquivo salvo à mão ao lado do server.py
        p = BASE / rel
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    raise RuntimeError("não consegui acessar api.warframe.com (%s)" % err)

def _clean(s):
    return re.sub(r"[\ue000-\uf8ff]", "", s or "").strip()

KIND_OF = {"Suits": "Warframe", "SpaceSuits": "Archwing", "MechSuits": "Necramech", "Sentinels": "Sentinela", "KubrowPets": "Companheiro",
           "LongGuns": "Primária", "Pistols": "Secundária", "Melee": "Melee", "SentinelWeapons": "Arma de sentinela",
           "CrewShipWeapons": "Railjack", "SpaceGuns": "Archwing", "SpaceMelee": "Archwing", "OperatorAmps": "Amp"}
GUILD_TIER = {1: "Ghost", 2: "Shadow", 3: "Storm", 4: "Mountain", 5: "Moon"}
DAILY_LABELS = [("DailyAffiliation", "Relays (Suda, Arbiters…)"), ("DailyAffiliationCetus", "Ostron"), ("DailyAffiliationSolaris", "Solaris United"),
                ("DailyAffiliationVentkids", "Ventkids"), ("DailyAffiliationVox", "Vox Solaris"), ("DailyAffiliationEntrati", "Entrati"),
                ("DailyAffiliationNecraloid", "Necraloid"), ("DailyAffiliationZariman", "Holdfasts"), ("DailyAffiliationQuills", "Quills"),
                ("DailyAffiliationKahl", "Kahl"), ("DailyAffiliationCavia", "Cavia"), ("DailyAffiliationHex", "The Hex"),
                ("DailyAffiliationLibrary", "Simaris"), ("DailyAffiliationPvp", "Conclave")]

def _item(t):
    return {"name": pretty(t), "icon": icon_of(t)}

FACTIONS = {"grineer": "Grineer", "corpus": "Corpus", "infested": "Infestado", "infestation": "Infestado", "orokin": "Orokin",
            "sentient": "Sentient", "narmer": "Narmer", "corrupted": "Corrompido", "wf1999infested": "Infestado 1999", "techrot": "Techrot",
            "mitw": "Man in the Wall", "manInTheWall".lower(): "Man in the Wall", "stalker": "Stalker", "tenno": "Tenno"}
_enemies = {}

def enemies_db():
    """data/enemies.json (gerado por build_enemies.py a partir do ExportEnemies.json): tipo do inimigo -> chave do nome + facção."""
    if "db" not in _enemies:
        p = BASE / "data" / "enemies.json"
        try:
            _enemies["db"] = {k.lower(): v for k, v in json.loads(p.read_text(encoding="utf-8")).items()}
        except Exception:
            _enemies["db"] = {}
    return _enemies["db"]

def _words(s):
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", s)
    return re.sub(r"(?<=[A-Za-z])(\d)", r" \1", s).replace("_", " ").replace("  ", " ").strip()

def enemy_name(path):
    """(nome, facção). Ordem: ExportEnemies (chave de nome + facção) -> dicionário -> ID interno limpo."""
    ent = enemies_db().get((path or "").lower())
    parts = [p for p in (path or "").split("/") if p]
    fac = ""
    if ent:
        fac = FACTIONS.get(str(ent.get("f") or "").lower(), ent.get("f") or "")
        key = ent.get("n") or ""
        v = langs().get(key.lower())
        nm = v.get("value") if isinstance(v, dict) else None
        if not nm:
            seg = key.rstrip("/").split("/")[-1]
            seg = re.sub(r"(Name|Avatar)$", "", seg) or seg
            nm = _words(seg)
    else:
        nm = _words(re.sub(r"Avatars?$", "", pretty(path).replace(" ", "")) if False else re.sub(r"\s*Avatars?$", "", pretty(path)))
        for i, p in enumerate(parts):
            if p.lower() == "enemies" and i + 1 < len(parts) - 1:
                fac = FACTIONS.get(parts[i + 1].lower(), _words(parts[i + 1]))
                break
    nm = re.sub(r"^MITW\s*", "", nm).strip()
    nm = re.sub(r"\s*(\d{4})$", r" (\1)", nm)
    return nm or (parts[-1] if parts else "?"), fac

def pv_summary(j):
    res = (j.get("Results") or [{}])[0]
    S = j.get("Stats") or {}
    inv = res.get("LoadOutInventory") or {}
    cat = catalog().get("items", {})
    enemies = S.get("Enemies") or []
    kills = sum(e.get("kills", 0) for e in enemies)
    heads = sum(e.get("headshots", 0) for e in enemies)
    xp = {x.get("ItemType"): x.get("XP", 0) for x in inv.get("XPInfo", [])}
    equip = []
    for w in S.get("Weapons") or []:
        t = w.get("type", "")
        c = (cat.get(t) or {}).get("c")
        hours = round((w.get("equipTime") or 0) / 3600, 1)
        if not c and hours < 1 and (w.get("kills") or 0) < 100:
            continue  # ruído (variantes internas sem nome no catálogo)
        if hours <= 0 and not w.get("kills"):
            continue
        equip.append({"name": pretty(t), "icon": icon_of(t), "kind": KIND_OF.get(c, "Outro"), "hours": hours, "kills": w.get("kills", 0),
                      "hs": w.get("headshots", 0), "assists": w.get("assists", 0), "xp": xp.get(t, w.get("xp", 0))})
    frames = sorted((x for x in equip if x["kind"] == "Warframe"), key=lambda x: -x["hours"])[:6]
    guns = sorted((x for x in equip if x["kind"] not in ("Warframe", "Archwing", "Necramech", "Sentinela", "Companheiro")), key=lambda x: -x["kills"])[:8]
    foes = {}
    for e in enemies:
        if e.get("kills", 0) > 0:
            nm, fac = enemy_name(e.get("type", ""))
            f = foes.setdefault(nm, {"name": nm, "faction": fac, "kills": 0, "hs": 0, "types": 0})
            f["kills"] += e["kills"]; f["hs"] += e.get("headshots", 0); f["types"] += 1
    foes = sorted(foes.values(), key=lambda x: -x["kills"])
    skills = res.get("PlayerSkills") or {}
    mr = res.get("PlayerLevel") or S.get("PlayerLevel") or 0
    cap = 16000 + 500 * mr
    daily = [{"name": lab, "left": res.get(k), "cap": cap} for k, lab in DAILY_LABELS if res.get(k) is not None]
    loadout = []
    for lab, key in (("Warframe", "Suits"), ("Primária", "LongGuns"), ("Secundária", "Pistols"), ("Melee", "Melee")):
        for it in (inv.get(key) or [])[:1]:
            loadout.append(dict(_item(it.get("ItemType", "")), slot=lab))
    gname = _clean(res.get("GuildName") or S.get("GuildName"))
    return {
        "name": _clean(res.get("DisplayName")), "mr": mr,
        "hours": round((S.get("TimePlayedSec") or 0) / 3600),
        "missions": {"done": S.get("MissionsCompleted", 0), "failed": S.get("MissionsFailed", 0), "quit": S.get("MissionsQuit", 0),
                     "dumped": S.get("MissionsDumped", 0), "interrupted": S.get("MissionsInterrupted", 0)},
        "deaths": S.get("Deaths", 0), "revives": S.get("ReviveCount", 0), "kills": kills, "headshots": heads,
        "melee_kills": S.get("MeleeKills", 0), "income": S.get("Income", 0), "pickups": S.get("PickupCount", 0),
        "heal": S.get("HealCount", 0), "scans": sum(x.get("scans", 0) for x in S.get("Scans") or []), "fish": S.get("FishCount", 0),
        "ciphers": S.get("CiphersSolved", 0), "ciphers_failed": S.get("CiphersFailed", 0), "destroyed": S.get("DestroyCount", 0),
        "created": date_of(res.get("Created", {})),
        "guild": {"name": gname, "tier": res.get("GuildTier"), "tier_name": GUILD_TIER.get(res.get("GuildTier"), ""), "xp": res.get("GuildXp")} if gname else None,
        "mastered_items": len(xp),
        "top_frames": frames, "top_weapons": guns, "equipment": sorted(equip, key=lambda x: -x["hours"]),
        "enemies": foes[:150], "loadout": loadout, "daily": daily,
        "intrinsics": {lab: skills.get(k, 0) for k, lab in INTRINSICS.items()},
        "drifter": {lab: skills.get(k, 0) for k, lab in DRIFTER.items()},
    }

def pv_res(pid):
    """Results[0] do perfil público (mesmo formato do lastData para Affiliations/Missions)."""
    return (pv_fetch(pid).get("Results") or [{}])[0]

STATIC_OK = {"/", "/index.html", "/app.js", "/style.css"}

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(BASE), **k)

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def end_headers(self):
        # nunca deixa o navegador reutilizar app.js/style.css antigos
        if not getattr(self, "_cc", False):
            self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    # ---------------------------------------------------------- login / sessões
    def _ip(self):
        ip = self.client_address[0]
        if ip in ("127.0.0.1", "::1"):  # atrás de proxy reverso local: confia no X-Forwarded-For
            ip = (self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or ip)
        return ip

    def _token(self):
        try:
            m = SimpleCookie(self.headers.get("Cookie", "")).get("wfsid")
            return m.value if m else None
        except Exception:
            return None

    def _gate(self):
        """Modo app: exige o token aleatório do app (outros apps do celular também alcançam 127.0.0.1)."""
        if not APP_TOKEN:
            return True
        u = urlparse(self.path)
        k = (parse_qs(u.query).get("k") or [""])[0]
        if k and hmac.compare_digest(k, APP_TOKEN):
            self._cc = True
            self.send_response(302)
            self.send_header("Location", u.path or "/")
            self.send_header("Set-Cookie", "wfapp=%s; Path=/; HttpOnly; SameSite=Strict" % APP_TOKEN)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return False
        try:
            m = SimpleCookie(self.headers.get("Cookie", "")).get("wfapp")
        except Exception:
            m = None
        if m and hmac.compare_digest(m.value, APP_TOKEN):
            return True
        self.send_error(403)
        return False

    def _sess(self):
        if auth.APP_MODE:
            return auth.app_session()
        if not auth.configured():
            return {"kind": "legacy", "user": "local", "key": "legacy", "has_data": True}  # modo antigo, sem login
        return auth.get_session(self._token())

    def _data(self, sess):
        return load() if sess["kind"] == "legacy" else auth.load_data(sess)

    def _cookie(self, token, ttl, persistent):
        c = "wfsid=%s; Path=/; HttpOnly; SameSite=Lax" % token
        if persistent:
            c += "; Max-Age=%d" % int(ttl)
        if self.headers.get("X-Forwarded-Proto") == "https":
            c += "; Secure"
        return ("Set-Cookie", c)

    def _auth_info(self):
        cfg = auth.config()
        return {"auth": auth.configured(), "discord": cfg.get("discord", ""), "visitor_minutes": auth.VISITOR_TTL // 60, "app": auth.APP_MODE}

    def do_HEAD(self):
        if not self._gate():
            return
        p = urlparse(self.path).path
        if p in STATIC_OK:
            return super().do_HEAD()
        self.send_error(404)

    def do_POST(self):
        if not self._gate():
            return
        u = urlparse(self.path)
        if auth.APP_MODE and (u.path.startswith("/api/auth/") or u.path == "/api/account/delete"):
            return self.send_json({"error": "indisponível no app"}, 404)
        q = parse_qs(u.query)
        if not auth.configured():
            return self.send_json({"error": "login desativado (rode python3 manage.py setup)"}, 404)
        try:
            n = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            n = 0
        up = u.path == "/api/data/upload"
        if n > (auth.MAX_UPLOAD if up else 10_000):
            self.rfile.read(0)
            return self.send_json({"error": "arquivo grande demais"}, 413)
        body = self.rfile.read(n) if n else b""
        ip = self._ip()
        try:
            if u.path.startswith("/api/auth/") and u.path != "/api/auth/logout":
                j = json.loads(body.decode("utf-8") or "{}") if body else {}
                if u.path == "/api/auth/login":
                    tok, ttl, rem = auth.login(j.get("username"), j.get("password"), bool(j.get("remember")), ip)
                elif u.path == "/api/auth/register":
                    tok, ttl, rem = auth.register(j.get("code"), j.get("username"), j.get("password"), j.get("player_id"), bool(j.get("remember")), ip)
                elif u.path == "/api/auth/visitor":
                    tok, ttl, rem = auth.start_visitor(j.get("code"), j.get("player_id"), ip)
                    rem = True  # visitante: o cookie dura exatamente o tempo da sessão (2h)
                else:
                    return self.send_json({"error": "rota invalida"}, 404)
                return self.send_json({"ok": True}, headers=[self._cookie(tok, ttl, rem)])
            if u.path == "/api/auth/logout":
                auth.logout(self._token())
                return self.send_json({"ok": True}, headers=[("Set-Cookie", "wfsid=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")])
            sess = self._sess()
            if sess is None:
                return self.send_json({"error": "auth"}, 401)
            if up:
                pid = (q.get("pid", [""])[0] or "").strip().lower()
                if pid:
                    auth.set_player_id(sess, pid)
                ts = auth.save_data(sess, body)
                return self.send_json({"ok": True, "uploaded_at": ts})
            j = json.loads(body.decode("utf-8") or "{}") if body else {}
            if u.path == "/api/data/delete":
                auth.delete_data(sess)
                return self.send_json({"ok": True})
            if u.path == "/api/account/player_id":
                auth.set_player_id(sess, j.get("player_id"))
                return self.send_json({"ok": True})
            if u.path == "/api/account/delete" and sess["kind"] == "account":
                acc = auth.list_accounts().get(sess["key"])
                if not acc or not auth.check_secret(j.get("password") or "", acc["pw"]):
                    return self.send_json({"error": "Senha incorreta."}, 401)
                auth.delete_account(sess["key"])
                return self.send_json({"ok": True}, headers=[("Set-Cookie", "wfsid=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")])
            self.send_json({"error": "rota invalida"}, 404)
        except auth.AuthError as e:
            self.send_json({"error": str(e)}, e.code)
        except Exception as e:
            traceback.print_exc()
            self.send_json({"error": "erro interno"}, 500)

    def send_json(self, obj, code=200, headers=()):
        self._cc = True
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._gate():
            return
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not u.path.startswith("/api/"):
            if u.path not in STATIC_OK:      # nada além do site em si (lastData, contas, chaves etc. nunca são servidos)
                return self.send_error(404)
            return super().do_GET()
        if u.path == "/api/version":
            return self.send_json({"version": SERVER_VERSION})
        sess = self._sess()
        if u.path == "/api/auth/me":
            if sess and sess["kind"] == "legacy":
                try:
                    up = DATA_FILE.stat().st_mtime
                except OSError:
                    up = None
                return self.send_json(dict({"authenticated": True, "kind": "legacy", "user": "local", "has_data": True, "player_id": "", "uploaded_at": up}, **self._auth_info()))
            return self.send_json(dict(auth.me(sess), **self._auth_info()))
        if sess is None:
            return self.send_json({"error": "auth"}, 401)
        if u.path == "/api/market/status":
            return self.send_json(dict(market.status(), **market.info()))
        if u.path == "/api/market/prices":
            try:
                prio = int(q.get("p", ["0"])[0])
            except ValueError:
                prio = 1
            return self.send_json(market.batch(q.get("k", []), prio))
        if u.path == "/api/pv":
            pid = (q.get("playerId", [""])[0] or sess.get("player_id") or "").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{24}", pid):
                return self.send_json({"error": "ID inválido (são 24 caracteres: números e letras de a a f)"}, 400)
            try:
                return self.send_json(pv_summary(pv_fetch(pid)))
            except Exception as e:
                return self.send_json({"error": str(e)}, 502)
        pid = (q.get("pid", [""])[0] or "").strip().lower()
        if pid:
            if not re.fullmatch(r"[0-9a-f]{24}", pid):
                return self.send_json({"error": "ID inválido"}, 400)
            try:
                if u.path == "/api/syndicates":
                    return self.send_json(syndicates_api(pv_res(pid)))
                if u.path == "/api/missions":
                    return self.send_json(missions_api(pv_res(pid)))
            except Exception as e:
                return self.send_json({"error": str(e)}, 502)
        try:
            d = self._data(sess)
            if d is None:
                return self.send_json({"error": "nodata"}, 409)
            if u.path == "/api/summary":
                return self.send_json(summary(d))
            cat = q.get("cat", [""])[0]
            if u.path == "/api/items" and cat in ITEM_CATS:
                return self.send_json(list_items(d, cat))
            if u.path == "/api/inventory" and (cat in INV_CATS or cat in EXTRA_INV):
                return self.send_json(inventory(d, cat))
            if u.path == "/api/syndicates":
                return self.send_json(syndicates_api(d))
            if u.path == "/api/missions":
                return self.send_json(missions_api(d))
            if u.path == "/api/archon":
                return self.send_json(archon_api(d))
            if u.path == "/api/relics":
                return self.send_json(relics_api(d))
            if u.path == "/api/forma":
                return self.send_json(forma_api(d))
            self.send_json({"error": "rota invalida"}, 404)
        except Exception as e:
            traceback.print_exc()
            self.send_json({"error": str(e)}, 500)

if __name__ == "__main__":
    if auth.configured():
        print("Login ATIVO (contas em data/accounts.json). Código de acesso: python3 manage.py code")
    else:
        load()
        print("ATENÇÃO: modo sem login (qualquer um com acesso à rede vê seus dados). Para ativar contas: python3 manage.py setup")
    print("http://localhost:%s" % PORT)
   # ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
