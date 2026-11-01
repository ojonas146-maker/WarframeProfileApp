# Warframe Profile (app Android)

O mesmo site/servidor do Profile, empacotado como app: o `server.py` roda **dentro do celular** (Python via
Chaquopy, só em 127.0.0.1) e uma WebView mostra o site. Não precisa de Termux nem de servidor.

## Compilar
1. Suba esta pasta inteira para um repositório no GitHub (branch principal).
2. Aba **Actions → Compilar APK → Run workflow**.
3. Quando terminar, baixe o artefato **WarframeProfile-apk** (zip com o `.apk`) e instale.

## Usar
Na primeira vez o app pede o `lastData.dat` do AlecaFrame (ou o JSON já descriptografado). Ele é
descriptografado no aparelho e guardado só nele. Para atualizar: botão **Atualizar dados**.

## Estrutura
- `app/src/main/python/` — `server.py`, `auth.py`, `market.py` (seu código) + `wf_app.py` (liga o servidor)
- `app/src/main/assets/wf/` — `index.html`, `app.js`, `style.css` e os JSONs/catálogo
- `app/src/main/java/.../MainActivity.kt` — WebView + upload de arquivo
- `tools/` — `fetch_data.py`, `build_enemies.py`, `manage.py` (uso no PC/Termux, não vão no app)

## Atualizar o app
Mudou `app.js`/`style.css`/JSON ou o Python? Edite, faça commit e rode o workflow de novo. **Aumente o
`versionCode` em `app/build.gradle.kts`** para o app recopiar os arquivos do site. O APK novo instala por cima
do antigo e mantém seus dados (a assinatura é fixa).
