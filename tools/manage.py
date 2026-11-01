#!/usr/bin/env python3
"""Administração do Warframe Profile (contas e código de acesso).

  python3 manage.py setup            primeira configuração (código de acesso, Discord e a SUA conta de admin)
  python3 manage.py code             troca o código de acesso que você passa para os amigos
  python3 manage.py discord ID       troca o ID do Discord mostrado na tela de login
  python3 manage.py users            lista as contas
  python3 manage.py passwd USUARIO   define uma nova senha para alguém (se esquecer)
  python3 manage.py delete USUARIO   apaga a conta e os dados dela
"""
import getpass, sys, time
import auth

def ask_secret(label):
    while True:
        a = getpass.getpass(label + ": ")
        if len(a) < 6:
            print("   mínimo 6 caracteres"); continue
        if a == getpass.getpass("   repita: "):
            return a
        print("   não conferem")

def set_config(**kw):
    c = auth.config(); c.update(kw); auth._write(auth.CONFIG_F, c)

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "setup":
        print("== Configuração inicial ==")
        set_config(code=auth.hash_secret(ask_secret("Código de acesso (o que você passa para os amigos)")),
                   discord=input("ID do Discord para pedirem o código [cyber100]: ").strip() or "cyber100")
        name = input("Seu usuário (admin): ").strip()
        pid = input("ID da sua conta Warframe (24 caracteres, Enter para pular): ").strip()
        auth.create_account(name, ask_secret("Sua senha"), pid, admin=True)
        old = auth.BASE / "lastData_decoded.json"
        if old.exists() and input("Importar o lastData_decoded.json atual para a sua conta? [S/n] ").strip().lower() != "n":
            class S(dict): pass
            sess = {"kind": "account", "key": name.lower()}
            auth.save_data(sess, old.read_bytes())
            print("   lastData importado.")
        print("Pronto. Agora rode: python3 server.py")
    elif cmd == "code":
        set_config(code=auth.hash_secret(ask_secret("Novo código de acesso"))); print("ok")
    elif cmd == "discord" and len(sys.argv) > 2:
        set_config(discord=sys.argv[2]); print("ok")
    elif cmd == "users":
        for k, v in auth.list_accounts().items():
            up = time.strftime("%d/%m/%Y %H:%M", time.localtime(v["uploaded_at"])) if v.get("uploaded_at") else "sem dados"
            print("%-24s %s%s  dados: %s" % (v["name"], "admin " if v.get("admin") else "", "ID✓" if v.get("player_id") else "", up))
    elif cmd == "passwd" and len(sys.argv) > 2:
        auth.set_password(sys.argv[2], ask_secret("Nova senha")); print("ok (sessões antigas dessa conta foram encerradas)")
    elif cmd == "delete" and len(sys.argv) > 2:
        if input("Apagar %s e todos os dados dela? digite SIM: " % sys.argv[2]) == "SIM":
            auth.delete_account(sys.argv[2]); print("apagado")
    else:
        print(__doc__)

if __name__ == "__main__":
    try:
        main()
    except auth.AuthError as e:
        sys.exit("erro: %s" % e)
