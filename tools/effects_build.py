#!/usr/bin/env python3
"""Gera app/src/main/assets/wf/data/effects.json (efeitos de mods e arcanos por rank). Rode no Termux/PC e faça commit."""
import os, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent / "app/src/main"
os.environ["WF_HOME"] = str(root / "assets/wf")
sys.path.insert(0, str(root / "python"))
import effects
print("efeitos:", effects.build(), "->", effects.OUT)
