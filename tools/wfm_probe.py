#!/usr/bin/env python3
"""Diagnóstico da conta do warframe.market (Termux/PC). Mostra só a ESTRUTURA das respostas (sem textos de mensagens).
Uso:  python3 tools/wfm_probe.py SEU_TOKEN_JWT      (o token é o cookie JWT do site; não é salvo em lugar nenhum)"""
import os, sys, tempfile
from pathlib import Path
os.environ["WF_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app/src/main/python"))
import wfmacct
if len(sys.argv) < 2:
    sys.exit(__doc__)
wfmacct._save_token(wfmacct.clean_token(sys.argv[1]))
txt = wfmacct.debug()
Path("wfm_probe.txt").write_text(txt, encoding="utf-8")
print(txt)
print("\n>> salvo em wfm_probe.txt — cole esse conteúdo no chat")
