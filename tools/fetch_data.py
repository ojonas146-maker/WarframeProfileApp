#!/usr/bin/env python3
"""
Baixa o Public Export OFICIAL da Digital Extremes e gera data/catalog.json
(nomes, ícones, relíquias com drops, nós do mapa estelar).

Uso:  python3 fetch_data.py          (nomes em inglês)
      python3 fetch_data.py pt       (nomes em português do Brasil)
Rode de novo quando sair atualização do jogo.
"""
import json, lzma, re, sys, time
from pathlib import Path
from urllib.request import Request, urlopen

LANG = sys.argv[1] if len(sys.argv) > 1 else "en"
ORIGIN = f"https://origin.warframe.com/PublicExport/index_{LANG}.txt.lzma"
CONTENT = "https://content.warframe.com/PublicExport/Manifest/"
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)
WANT = ["ExportWarframes", "ExportWeapons", "ExportSentinels", "ExportUpgrades",
        "ExportResources", "ExportRecipes", "ExportRelicArcane", "ExportGear",
        "ExportKeys", "ExportCustoms", "ExportFlavour", "ExportDrones",
        "ExportSortieRewards", "ExportFusionBundles"]
UA = {"User-Agent": "Mozilla/5.0 warframe-profile"}


def get(url, tries=3):
    for i in range(tries):
        try:
            return urlopen(Request(url, headers=UA), timeout=90).read()
        except Exception as e:
            print(f"   tentativa {i+1} falhou: {e}")
            time.sleep(2)
    sys.exit(f"❌ não consegui baixar {url}")


def parse(raw: bytes):
    # o JSON do export tem caracteres de controle soltos dentro das strings
    return json.loads(raw.decode("utf-8", "replace"), strict=False)


def clean(name):
    name = re.sub(r"<[^>]+>\s*", "", name or "").strip()
    return name.title() if name.isupper() else name


def norm(path):  # "/Lotus/StoreItems/X" -> "/Lotus/X"
    return path.replace("/Lotus/StoreItems/", "/Lotus/", 1)


print(f"📥 índice ({LANG})...")
dec = lzma.LZMADecompressor(format=lzma.FORMAT_AUTO)
index = dec.decompress(get(ORIGIN)).decode().split()
files = {line.split("!")[0]: line for line in index}
print(f"   {len(files)} arquivos no índice")

catalog, relics, regions, textures = {}, {}, {}, {}

# ---- ícones
man = files.get("ExportManifest.json")
if man:
    print("🖼️  manifesto de imagens...")
    for e in parse(get(CONTENT + man)).get("Manifest", []):
        textures[norm(e["uniqueName"])] = e["textureLocation"]
else:
    print("⚠️  sem manifesto de imagens")

# ---- dados
for w in WANT:
    line = files.get(f"{w}_{LANG}.json")
    if not line:
        print(f"   (pulando {w})")
        continue
    print(f"📦 {w}")
    data = parse(get(CONTENT + line))
    for key, lst in data.items():
        if not isinstance(lst, list):
            continue
        for e in lst:
            if not isinstance(e, dict) or "uniqueName" not in e:
                continue
            u = norm(e["uniqueName"])
            ent = catalog.setdefault(u, {})
            if e.get("name"):
                ent["n"] = clean(e["name"])
            if e.get("resultType"):
                ent["r"] = norm(e["resultType"])
            if e.get("rarity"):
                ent["ra"] = e["rarity"]
            if e.get("masteryReq") is not None:
                ent["m"] = e["masteryReq"]
            if e.get("productCategory"):
                ent["c"] = e["productCategory"]
            if e.get("fusionLimit") is not None:
                ent["fl"] = e["fusionLimit"]
            if e.get("relicRewards"):
                relics[u] = {
                    "n": clean(e.get("name", "")),
                    "rw": [[norm(r["rewardName"]), r["rarity"], r.get("itemCount", 1)]
                           for r in e["relicRewards"]],
                }

# ---- mapa estelar
line = files.get(f"ExportRegions_{LANG}.json")
if line:
    print("🗺️  ExportRegions")
    for n in parse(get(CONTENT + line)).get("ExportRegions", []):
        regions[n["uniqueName"]] = {
            "n": n.get("name"), "s": n.get("systemName"),
            "mi": n.get("missionIndex"), "f": n.get("factionIndex"),
            "lv": [n.get("minEnemyLevel"), n.get("maxEnemyLevel")],
        }

# ---- blueprints sem nome ganham "<resultado> Blueprint"; liga ícones
for u, ent in catalog.items():
    if "n" not in ent and ent.get("r") and catalog.get(ent["r"], {}).get("n"):
        ent["n"] = catalog[ent["r"]]["n"] + " Blueprint"
    if u in textures:
        ent["i"] = textures[u]
    elif ent.get("r") in textures:
        ent["i"] = textures[ent["r"]]
for u, t in textures.items():  # itens só com ícone também entram
    catalog.setdefault(u, {}).setdefault("i", t)

out = {"lang": LANG, "items": catalog, "relics": relics, "regions": regions}
(OUT / "catalog.json").write_text(
    json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"✅ data/catalog.json: {len(catalog):,} itens, {len(relics)} relíquias, {len(regions)} nós")
