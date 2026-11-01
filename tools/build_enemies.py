#!/usr/bin/env python3
"""Converte o ExportEnemies.json (Public Export da DE) no arquivo enxuto data/enemies.json usado pelo site.
Uso:  python3 build_enemies.py [caminho/ExportEnemies.json]      (padrão: ./ExportEnemies.json)"""
import json, sys
from pathlib import Path
src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "ExportEnemies.json"
j = json.loads(src.read_text(encoding="utf-8", errors="replace"), strict=False)
out = {k: {"n": v.get("name"), "f": v.get("faction")} for k, v in (j.get("avatars") or {}).items() if v.get("name")}
dst = Path(__file__).parent / "data" / "enemies.json"
dst.parent.mkdir(exist_ok=True)
dst.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print("ok:", len(out), "inimigos ->", dst)
