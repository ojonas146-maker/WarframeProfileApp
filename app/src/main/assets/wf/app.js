"use strict";
const APP_VERSION = "2026.11.01-app1";
/* ================================================================ utilidades */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const fmt = n => (n == null ? "—" : Number(n).toLocaleString("pt-BR"));
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const _c = {};
const get = u => (_c[u] ??= fetch(u).then(r => {
  if (r.status === 401) { location.reload(); throw new Error("sessão expirada"); }
  if (r.status === 409) { delete _c[u]; if (typeof boot === "function") boot(); throw new Error("envie o seu lastData"); }
  if (!r.ok) throw new Error(u + " → " + r.status); return r.json(); }));
const PAGE = 120;
const NO_SLOTS = ["Companheiro", "Sentinela", "MOA", "Archwing", "Necramech"]; // sem Exilus nem Adaptador de arcano
const hasSlots = x => x.has_exilus !== false && !NO_SLOTS.includes(x.kind);

/* ================================================================ ícones */
const SHARD = {
  red: ["Crimson", "#ff7b89", "#b0102a"], yellow: ["Amber", "#ffe98a", "#d99200"], blue: ["Azure", "#9ad7ff", "#1553c9"],
  orange: ["Topaz", "#ffc070", "#d4540a"], purple: ["Violet", "#dbb0ff", "#6a2ac4"], green: ["Emerald", "#86ffc9", "#08885a"],
};
$("#shard-defs").innerHTML = Object.entries(SHARD).map(([k, [, a, b]]) =>
  `<linearGradient id="sg-${k}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient>`).join("");

const shardSvg = (color, tau = false, extra = "") => {
  const st = tau ? "#fff4c2" : "rgba(255,255,255,.45)", sw = tau ? 1.2 : .8, g = `url(#sg-${color})`;
  return `<svg class="shard ${tau ? "tau" : ""} ${extra}" viewBox="0 0 32 32" aria-label="${SHARD[color][0]}${tau ? " Tau" : ""}">` +
  /* fragmentos laterais */
  `<path d="M10.6 16.5L4.6 20.4L6 27.6L10.6 25Z" fill="${g}" stroke="${st}" stroke-width=".6" stroke-linejoin="round"/><path d="M10.6 16.5L4.6 20.4L7.4 21.2Z" fill="#fff" opacity=".35"/>` +
  `<path d="M21.4 13.5L27.2 17.6L25.8 25.6L21.4 23Z" fill="${g}" stroke="${st}" stroke-width=".6" stroke-linejoin="round"/><path d="M21.4 13.5L27.2 17.6L24.4 18.4Z" fill="#fff" opacity=".3"/><path d="M24.4 18.4L27.2 17.6L25.8 25.6L21.4 23Z" fill="#000" opacity=".22"/>` +
  /* cristal principal */
  `<path d="M16 .8L21.6 7.2V24.2L16 31.2L10.4 24.2V7.2Z" fill="${g}" stroke="${st}" stroke-width="${sw}" stroke-linejoin="round"/>` +
  `<path d="M16 .8L10.4 7.2L16 10.4Z" fill="#fff" opacity=".5"/><path d="M16 .8L21.6 7.2L16 10.4Z" fill="#fff" opacity=".15"/>` +
  `<path d="M10.4 7.2L16 10.4V31.2L10.4 24.2Z" fill="#fff" opacity=".16"/><path d="M21.6 7.2L16 10.4V31.2L21.6 24.2Z" fill="#000" opacity=".28"/>` +
  `<path d="M12.6 11.5V21.5" fill="none" stroke="rgba(255,255,255,.7)" stroke-width="1" stroke-linecap="round"/>` +
  (tau ? `<path d="M16 14l2.2 3.6L16 23.5l-2.2-5.9z" fill="#fff" opacity=".55"/><path d="M27 1.5l1.3 2.9 2.9 1.3-2.9 1.3-1.3 2.9-1.3-2.9-2.9-1.3 2.9-1.3z" fill="#fff"/>` : "") + `</svg>`;
};

/* ícone oficial (imagem do catálogo); se não carregar, cai no SVG desenhado */
const shard = (color, tau = false, extra = "", icon = "", glow = "") => {
  if (!icon) return shardSvg(color, tau, extra);
  const nm = SHARD[color][0] + (tau ? " Tau" : ""), d = `data-c="${color}" data-t="${tau ? 1 : 0}" data-x="${esc(extra)}"`;
  const base = `<img class="shard-img" src="${esc(icon)}" alt="${nm}" loading="lazy" onerror="shardFail(this)">`;
  // Tauforged = cristal normal + brilho dourado por cima (o arquivo "MythicGlow" é só o efeito)
  return tau ? `<span class="shard shard-tau ${extra}" ${d}>${base}${glow ? `<img class="gl" src="${esc(glow)}" alt="" loading="lazy" onerror="this.remove()">` : ""}</span>`
             : `<span class="shard ${extra}" ${d}>${base}</span>`;
};
window.shardFail = img => { const w = img.closest(".shard") || img; w.outerHTML = shardSvg(w.dataset.c, w.dataset.t === "1", w.dataset.x); };

const POLAR = {
  AP_ATTACK: "Madurai", AP_DEFENSE: "Vazarin", AP_TACTIC: "Naramon",
  AP_POWER: "Zenurik", AP_WARD: "Unairu", AP_PRECEPT: "Penjaga",
  AP_UMBRA: "Umbra", AP_UNIVERSAL: "Aura", AP_ANY: "Qualquer",
  AP_ATTACK_UMBRA: "Umbra Madurai", AP_DEFENSE_UMBRA: "Umbra Vazarin",
};
const polarName = p => POLAR[p] || String(p||"").replace(/^AP_/, "").replace(/_/g," ");
const relicSvg = `<svg viewBox="0 0 32 32"><path d="M16 2l11 6v16l-11 6-11-6V8z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M16 9l6 3.5v7L16 23l-6-3.5v-7z" fill="currentColor" opacity=".4"/></svg>`;

const NAV = [
  ["perfil", "Perfil", '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7"/>'],
  ["conta", "Conta", '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M6 16c.5-2 5.5-2 6 0M14 10h4M14 14h3"/>'],
  ["warframes", "Warframes", '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>'],
  ["armas", "Armas", '<circle cx="12" cy="12" r="8"/><path d="M12 2v6M12 16v6M2 12h6M16 12h6"/>'],
  ["companheiros", "Companheiros", '<circle cx="7" cy="9" r="2"/><circle cx="12" cy="6" r="2"/><circle cx="17" cy="9" r="2"/><path d="M12 12c-4 0-6 4-5 6s3 2 5 1 4 1 5-1-1-6-5-6z"/>'],
  ["veiculos", "Veículos", '<path d="M12 2c4 2 6 6 6 10l-3 3H9l-3-3c0-4 2-8 6-10z"/><circle cx="12" cy="10" r="2"/><path d="M9 15l-2 5 5-2M15 15l2 5-5-2"/>'],
  ["shards", "Archon Shards", '<path d="M12 2l5.5 5.5v9L12 22l-5.5-5.5v-9z"/><path d="M6.5 7.5L12 11l5.5-3.5M12 11v11"/>'],
  ["reliquias", "Relíquias", '<path d="M12 2l8 4.5v9L12 20l-8-4.5v-9z"/><path d="M12 8v6"/>'],
  ["formas", "Formas", '<path d="M12 2l3 7 7 1-5 5 1 7-6-4-6 4 1-7-5-5 7-1z"/>'],
  ["inventario", "Inventário", '<path d="M3 7l9-4 9 4v10l-9 4-9-4z"/><path d="M3 7l9 4 9-4M12 11v10"/>'],
  ["rivens", "Rivens", '<path d="M5 3h14v18H5z"/><path d="M9 8h6M9 12h6M9 16h4"/>'],
  ["mercado", "Mercado", '<path d="M3 9l2-5h14l2 5"/><path d="M4 9v11h16V9"/><path d="M9 20v-6h6v6"/>'],
  ["sindicatos", "Sindicatos", '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-4 3-6 6-6s6 2 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14c3 0 5 2 5 5"/>'],
  ["missoes", "Missões", '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>'],
];

const ico = (src, name) => `<div class="ico">${src ? `<img loading="lazy" src="${src}" alt="" data-l="${esc((name || "?")[0])}" onerror="imgFail(this)">` : `<span class="mono-l">${esc((name || "?")[0])}</span>`}</div>`;
window.imgFail = img => { img.parentElement.innerHTML = `<span class="mono-l">${img.dataset.l}</span>`; };

/* ================================================================ modal */
const modal = $("#modal");
const openModal = html => { $("#modal-body").innerHTML = html; modal.hidden = false; };
const closeModal = () => { modal.hidden = true; };
$("#modal-x").onclick = closeModal;
modal.onclick = e => { if (e.target === modal) closeModal(); };
addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

function openItem(x) {
  const polCount = {};
  (x.polarities || []).filter(Boolean).forEach(p => { const n = polarName(p); polCount[n] = (polCount[n] || 0) + 1; });
  const pol = Object.entries(polCount).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([n, c]) => `<span class="chip">${esc(n)} <b class="gold">×${c}</b></span>`).join("");
  const hasEx = hasSlots(x), hasArc = hasSlots(x);
  const sh = (x.shards || []).map(s => `<div>${shard(s.color, s.tau, "", s.icon, s.glow)}<span><b>${s.name}${s.tau ? " Tau" : ""}</b><br><span class="mut">${esc(s.effect)}</span></span></div>`).join("");
  openModal(`
    <div class="m-head">${ico(x.icon, x.name)}<div><h2 style="font-size:21px">${esc(x.name)}</h2>
      <div class="chips"><span class="chip">${esc(x.kind)}</span>${x.rank >= 30 ? '<span class="chip gold">Rank máximo</span>' : ""}${x.mr != null ? `<span class="chip">MR ${x.mr}</span>` : ""}</div></div></div>
    <div class="kv">
      <div><small>Rank</small><b>${x.rank}/30</b></div><div><small>Afinidade</small><b>${fmt(x.xp)}</b></div>
      <div><small>Formas</small><b class="gold">${x.forma}</b></div>
      <div><small>Reator / Catalisador</small><b>${x.reactor ? "Instalado" : "—"}</b></div>
      ${hasEx ? `<div><small>Exilus</small><b>${x.exilus ? "Instalado" : "—"}</b></div>` : ""}
      ${hasArc ? `<div><small>Adaptador de arcano</small><b>${x.arcane_slot ? "Instalado" : "—"}</b></div>` : ""}
      <div><small>Polaridades</small><b>${(x.polarities||[]).length}</b></div>
      ${x.prime ? `<div><small>Variante</small><b class="gold">Prime</b></div>` : ""}
      ${x.lens ? `<div><small>Focus Lens</small><b style="font-size:14px">${esc(x.lens)}</b></div>` : ""}
    </div>
    ${pol ? `<div class="sec" style="margin-top:14px"><h2>Polaridades</h2></div><div class="chips" style="margin:0">${pol}</div>` : ""}
    ${sh ? `<div class="sec" style="margin-top:14px"><h2>Archon Shards (${x.shards.length})</h2></div><div class="fx">${sh}</div>` : ""}
    <div class="dim mono" style="margin-top:14px;font-size:11px;word-break:break-all">${esc(x.path)}</div>`);
}

/* ================================================================ router */
const view = $("#view");
$("#nav").innerHTML = NAV.map(([k, l, p]) => `<a href="#/${k}" data-k="${k}"><svg viewBox="0 0 24 24">${p}</svg><span>${l}</span></a>`).join("");
const VIEWS = {};
async function route() {
  if (typeof LOCKED !== "undefined" && LOCKED) return;
  const k = location.hash.replace(/^#\/?/, "") || "perfil";
  const key = VIEWS[k] ? k : "perfil";
  $$("#nav a").forEach(a => a.classList.toggle("on", a.dataset.k === key));
  $("#banner").innerHTML = "";
  view.innerHTML = '<div class="empty">Carregando…</div>';
  scrollTo(0, 0);
  try { await VIEWS[key](view); } catch (e) { view.innerHTML = `<div class="empty">Erro: ${esc(e.message)}</div>`; console.error(e); }
}
addEventListener("hashchange", route);

const head = (t, s = "") => `<div class="page-h"><div><h1>${t}</h1><div class="sub">${s}</div></div></div>`;
const sortBy = (list, key, dir = -1) => list.sort((a, b) => ((typeof a[key] === "string" ? a[key].localeCompare(b[key]) : (a[key] ?? 0) - (b[key] ?? 0)) * dir) || a.name.localeCompare(b.name));
const debounce = (f, ms = 120) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => f(...a), ms); }; };

/* ================================================================ PERFIL */
VIEWS.perfil = async el => {
  const s = await get("/api/summary");
  if (!s || s.error) throw new Error(s && s.error ? s.error : "summary vazio");
  s.counts = s.counts || {};
  s.key_items = s.key_items || [];
  s.boosters = s.boosters || [];
  s.intrinsics = s.intrinsics || {};
  s.drifter = s.drifter || {};
  const banner = $("#banner");
  banner.innerHTML = !s.catalog
    ? `<div class="banner">Modo básico: nomes aproximados e sem ícones. Rode <code>python3 fetch_data.py</code> uma vez para baixar os nomes e ícones oficiais e recarregue.</div>` : "";
  const stat = (l, v, sub = "", cls = "") => `<div class="stat"><span class="l">${l}</span><span class="v ${cls}">${v}</span>${sub ? `<span class="s">${sub}</span>` : ""}</div>`;
  const bars = o => Object.entries(o || {}).map(([k, v]) => `<div class="hbar"><span class="l">${k}</span><div class="bar ${v >= 10 ? "max" : ""}"><i style="width:${(v || 0) * 10}%"></i></div><span class="v">${v ?? 0}/10</span></div>`).join("");
  const nowS = Date.now() / 1000;
  const act = s.boosters.filter(b => b.expiry && b.expiry > nowS).sort((x, y) => x.expiry - y.expiry);
  const dead = s.boosters.length - act.length;
  const left = sec => { const d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60); return d ? `${d}d ${h}h` : h ? `${h}h ${m}min` : `${Math.max(1, m)}min`; };
  const bRow = b => { const sec = b.expiry - nowS, soon = sec < 86400;
    return `<div class="row bst ${soon ? "soon" : ""}"><span class="t">${esc(b.name)}</span><span class="bst-r"><b>${left(sec)}</b><small class="mut">até ${new Date(b.expiry * 1000).toLocaleDateString("pt-BR")}</small></span></div>`; };
  const boostersHtml = `<div class="sec"><h2>Boosters ativos${act.length ? ` (${act.length})` : ""}</h2></div>` +
    (act.length ? `<div class="list">${act.map(bRow).join("")}</div>` : `<div class="panel mut">Nenhum booster ativo no momento.</div>`) +
    (dead ? `<p class="mut" style="margin:6px 2px 0;font-size:12px">${dead} expirado${dead > 1 ? "s" : ""} oculto${dead > 1 ? "s" : ""}.</p>` : "");
  const C = s.counts;
  const coll = [["warframes", "Warframes", C.warframes || 0], ["armas", "Armas", (C.primary || 0) + (C.secondary || 0) + (C.melee || 0)], ["companheiros", "Companheiros", C.companions || 0], ["veiculos", "Veículos", (C.archwing || 0) + (C.necramechs || 0)]];
  const FOCUS = { AP_ATTACK: "Madurai", AP_DEFENSE: "Vazarin", AP_WARD: "Unairu", AP_POWER: "Zenurik", AP_TACTIC: "Naramon" };
  const focusRows = Object.entries(s.focus_xp || {}).sort((a,b)=> (b[1]||0)-(a[1]||0)).map(([k,v]) =>
    `<div class="row"><span class="t">${FOCUS[k] || k}</span><span class="n">${fmt(v)}</span></div>`).join("");
  el.innerHTML = `
  <div class="hero">
    <div class="mr"><div><b>${s.mastery ?? "?"}</b><small>MASTERY</small></div></div>
    <div style="flex:1;min-width:220px"><h1 id="hero-name">Perfil do Tenno</h1>
      <div class="chips" id="hero-chips">
        ${s.created ? `<span class="chip">Conta criada em ${s.created}</span>` : ""}
        ${s.region ? `<span class="chip">Última região: ${esc(s.region)}</span>` : ""}
        ${s.has_guild ? `<span class="chip">Clã vinculada</span>` : ""}
        <span class="chip gold">${fmt(s.maxed)} itens no rank máximo</span>
      </div></div>
  </div>
  <div id="pv-slot"></div>
  ${boostersHtml}
  <div class="sec"><h2>Informações básicas</h2></div>
  <div class="grid g-stats">
    ${stat("Mastery Rank", fmt(s.mastery))}
    ${stat("Conta criada", s.created || "—")}
    ${stat("Última região", esc(s.region || "—"))}
    ${stat("Nós jogados", fmt(s.nodes_played), `${fmt(s.mission_completes)} missões concluídas`)}
    ${stat("Itens no rank 30", fmt(s.maxed))}
    ${stat("Formas aplicadas", fmt(s.forma_total), "", "gold")}
  </div>
  ${focusRows ? `<div class="sec"><h2>Focus</h2></div><div class="panel">${focusRows}</div>` : ""}
  <div class="sec"><h2>Recursos</h2></div>
  <div class="grid g-stats">
    ${stat("Créditos", fmt(s.credits), "", "gold")}${stat("Platina", fmt(s.platinum))}${stat("Endo", fmt(s.endo))}
    ${stat("Formas em uso", fmt(s.forma_total), "aplicadas em equipamentos", "gold")}
    ${s.key_items.map(k => stat(esc(k.name), fmt(k.count), "no inventário")).join("")}
    ${stat("Trocas", s.trades, "restantes hoje")}${stat("Presentes", s.gifts, "restantes hoje")}
  </div>
  <div class="sec"><h2>Coleção</h2></div>
  <div class="grid g-stats">${coll.map(([h, l, n]) => `<a href="#/${h}" style="text-decoration:none;color:inherit">${stat(l, fmt(n), "ver todos →")}</a>`).join("")}</div>
  <div class="sec"><h2>Destaques</h2></div>
  <div class="grid g-stats">
    <a href="#/shards" style="text-decoration:none;color:inherit"><div class="stat"><span class="l">Archon Shards instalados</span><span class="v">${fmt(s.shards)}</span><span class="s">${fmt(s.shards_inv)} no inventário</span></div></a>
    <a href="#/reliquias" style="text-decoration:none;color:inherit">${stat("Relíquias", fmt(s.relic_total), "unidades no inventário")}</a>
  </div>
  <div class="grid g-2" style="margin-top:10px">
    <div class="panel"><h3 style="margin-bottom:8px">Intrínsecos do Railjack</h3>${bars(s.intrinsics)}</div>
    <div class="panel"><h3 style="margin-bottom:8px">Intrínsecos do Drifter</h3>${bars(s.drifter)}</div>
  </div>
`;
  loadPV(el);
};


/* ================================================================ PERFIL PÚBLICO / CONTA (precisa do ID da conta, opcional) */
const PID_KEY = "wf_player_id";
const pidGet = () => { if (ME && ME.auth) return ME.player_id || ""; try { return localStorage.getItem(PID_KEY) || ""; } catch { return ""; } };
const pidSet = async v => { if (ME && ME.auth) { await post("/api/account/player_id", { player_id: v }); ME.player_id = v; return; } try { v ? localStorage.setItem(PID_KEY, v) : localStorage.removeItem(PID_KEY); } catch {} };
const pidForm = (pid, msg = "") => `<div class="panel pvform"><p class="mut" style="margin:0 0 10px;font-size:13px">Cole o ID da sua conta (ou o link do <code>getProfileViewingData</code>). ${ME && ME.auth ? "Ele fica salvo na sua conta" : "Ele fica salvo só neste navegador"} e dá para remover quando quiser.</p>
  <div class="tools" style="margin:0"><input class="inp search" id="pid" placeholder="ID da conta (24 caracteres)" value="${esc(pid)}" autocomplete="off" autocapitalize="off" spellcheck="false"><button class="pill" id="pid-ok">${pid ? "Atualizar" : "Conectar"}</button>${pid ? '<button class="pill" id="pid-x">Remover</button>' : ""}</div>
  ${msg ? `<p style="margin:10px 0 0;font-size:13px;color:var(--bad)">${esc(msg)}</p>` : ""}</div>`;
function pidBind(root, again) {
  const ok = $("#pid-ok", root), x = $("#pid-x", root), inp = $("#pid", root);
  if (ok) ok.onclick = async () => {
    const m = (inp.value || "").toLowerCase().match(/[0-9a-f]{24}/);
    if (!m) { $(".pvform", root).outerHTML = pidForm(pidGet(), "ID inválido: são 24 caracteres (números e letras de a a f)."); pidBind(root, again); return; }
    try { await pidSet(m[0]); } catch (e) { $(".pvform", root).outerHTML = pidForm(pidGet(), e.message); pidBind(root, again); return; }
    again();
  };
  if (x) x.onclick = async () => { await pidSet(""); again(); };
}
const pvLoad = async pid => { const k = "/api/pv?playerId=" + pid; try { const p = await get(k); if (p && p.error) throw new Error(p.error); return p; } catch (e) { delete _c[k]; throw e; } };

/* cartão pequeno na página Perfil */
async function loadPV(el) {
  const slot = $("#pv-slot", el); if (!slot) return;
  const pid = pidGet();
  if (!pid) { slot.innerHTML = `<a class="panel pvmini" href="#/conta"><div class="pvt"><b>Perfil público</b> <span class="mut">— conecte seu ID para ver horas, equipamento, kills e mais</span></div><span class="go">→</span></a>`; return; }
  slot.innerHTML = '<div class="panel pvmini mut">Carregando perfil público…</div>';
  try {
    const p = await pvLoad(pid);
    const h = $("#hero-name", el); if (h && p.name) h.textContent = p.name;
    const hc = $("#hero-chips", el); if (hc && p.guild) { $$(".chip", hc).filter(c => c.textContent.trim() === "Clã vinculada").forEach(c => c.remove()); hc.insertAdjacentHTML("afterbegin", `<span class="chip cyan">Clã ${esc(p.guild.name)}</span>`); }
    slot.innerHTML = `<a class="panel pvmini" href="#/conta"><div class="pvt"><b>${esc(p.name)}</b> <span class="mut">· ${fmt(p.hours)} h · ${fmt(p.kills)} kills · ${fmt(p.missions.done)} missões</span></div><span class="go">Ver perfil completo →</span></a>`;
  } catch (e) { slot.innerHTML = `<a class="panel pvmini" href="#/conta"><div class="pvt"><b>Perfil público</b> <span class="mut">— não consegui carregar (${esc(e.message)})</span></div><span class="go">→</span></a>`; }
}

VIEWS.conta = async el => {
  let tab = "resumo";
  const TABS = [["resumo", "Resumo"], ["equip", "Equipamento"], ["sind", "Sindicatos"], ["miss", "Missões"], ["inim", "Inimigos"]];
  const draw = async () => {
    const pid = pidGet();
    if (!pid) { el.innerHTML = `${head("Conta", "Seu perfil público do Warframe")}${pidForm("")}`; pidBind(el, draw); return; }
    el.innerHTML = `${head("Conta", "Carregando perfil público…")}`;
    let p;
    try { p = await pvLoad(pid); } catch (e) { el.innerHTML = `${head("Conta", "Seu perfil público do Warframe")}${pidForm(pid, e.message)}`; pidBind(el, draw); return; }
    el.innerHTML = `<div class="hero"><div class="mr"><div><b>${p.mr}</b><small>MASTERY</small></div></div>
      <div style="flex:1;min-width:220px"><h1>${esc(p.name)}</h1><div class="chips">
        ${p.created ? `<span class="chip">Conta criada em ${esc(p.created)}</span>` : ""}
        ${p.guild ? `<span class="chip cyan">Clã ${esc(p.guild.name)}${p.guild.tier_name ? " · " + p.guild.tier_name : ""}</span>` : ""}
        <span class="chip gold">${fmt(p.hours)} h jogadas</span></div></div></div>
      <div class="tabs" id="ctabs" style="margin-top:14px">${TABS.map(([k, l]) => `<span class="pill ${k === tab ? "on" : ""}" data-t="${k}">${l}</span>`).join("")}</div><div id="ctab"></div>
      <details class="pvd"><summary>Alterar ou remover ID</summary>${pidForm(pid)}</details>`;
    pidBind(el, draw);
    const box = $("#ctab", el);
    const show = () => { $$("#ctabs .pill", el).forEach(x => x.classList.toggle("on", x.dataset.t === tab)); TAB[tab](box, p, pid); };
    $("#ctabs", el).onclick = e => { const t = e.target.closest("[data-t]"); if (t) { tab = t.dataset.t; show(); } };
    show();
  };
  const st = (l, v, sub = "", cls = "") => `<div class="stat"><span class="l">${l}</span><span class="v ${cls}">${v}</span>${sub ? `<span class="s">${sub}</span>` : ""}</div>`;
  const list = (arr, f) => arr.map(x => `<div class="row">${ico(x.icon, x.name)}<span class="t">${esc(x.name)}<br><small class="mut">${f(x)}</small></span></div>`).join("");
  const bars = o => Object.entries(o || {}).map(([k, v]) => `<div class="hbar"><span class="l">${k}</span><div class="bar ${v >= 10 ? "max" : ""}"><i style="width:${(v || 0) * 10}%"></i></div><span class="v">${v}/10</span></div>`).join("");
  const TAB = {
    resumo: (b, p) => {
      const kd = p.deaths ? p.kills / p.deaths : null, mt = p.missions.done + p.missions.failed + p.missions.quit;
      b.innerHTML = `<div class="grid g-stats">
        ${st("Missões concluídas", fmt(p.missions.done), `${fmt(p.missions.failed)} falhas · ${fmt(p.missions.quit)} abandonadas`)}
        ${st("Kills", fmt(p.kills), `${fmt(p.headshots)} headshots`)}
        ${st("Mortes", fmt(p.deaths), kd ? `${kd.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} kills por morte` : "")}
        ${st("Créditos ganhos", fmt(p.income), "na conta toda", "gold")}
        ${st("Revives", fmt(p.revives), `${fmt(p.heal)} de cura`)}
        ${st("Itens com XP", fmt(p.mastered_items), `${fmt(p.destroyed)} objetos destruídos`)}
        ${st("Ciphers", fmt(p.ciphers), `${fmt(p.ciphers_failed)} falhos`)}
        ${st("Scans", fmt(p.scans), `${fmt(p.fish)} peixes · ${fmt(p.pickups)} pickups`)}</div>
        ${p.loadout.length ? `<div class="sec"><h2>Loadout equipado</h2></div><div class="list">${list(p.loadout, x => x.slot)}</div>` : ""}
        <div class="grid g-2" style="margin-top:10px">
          <div><div class="sec" style="margin-top:6px"><h2>Warframes mais usados</h2></div><div class="list">${list(p.top_frames, x => `${fmt(x.hours)} h · ${fmt(x.kills)} kills`)}</div></div>
          <div><div class="sec" style="margin-top:6px"><h2>Armas com mais kills</h2></div><div class="list">${list(p.top_weapons, x => `${fmt(x.kills)} kills · ${fmt(x.hours)} h`)}</div></div></div>
        <div class="grid g-2" style="margin-top:10px">
          <div class="panel"><h3 style="margin-bottom:8px">Intrínsecos do Railjack</h3>${bars(p.intrinsics)}</div>
          <div class="panel"><h3 style="margin-bottom:8px">Intrínsecos do Drifter</h3>${bars(p.drifter)}</div></div>
        ${(() => { if (!p.daily.length) return ""; const used = p.daily.filter(x => x.left < x.cap), full = p.daily.length - used.length;
          return `<div class="sec"><h2>Standing diário disponível</h2></div>` + (used.length ? `<div class="list">${used.map(x => `<div class="row"><span class="t" style="flex:none;width:min(190px,45%)">${esc(x.name)}</span><div class="bar" style="flex:1"><i style="width:${Math.min(100, x.left / x.cap * 100)}%"></i></div><span class="n" style="width:110px;text-align:right">${fmt(x.left)}<small class="mut"> / ${fmt(x.cap)}</small></span></div>`).join("")}</div>` : "") +
          `<p class="mut" style="margin:6px 2px 0;font-size:12.5px">${full ? `${full} de ${p.daily.length} sindicatos com o standing do dia cheio (${fmt(p.daily[0].cap)} cada).` : "Todo o standing de hoje já foi usado."}</p>`; })()}`;
    },
    equip: (b, p) => {
      const kinds = ["Warframe", "Primária", "Secundária", "Melee", "Companheiro", "Sentinela", "Arma de sentinela", "Archwing", "Necramech", "Railjack", "Amp", "Outro"];
      const has = kinds.filter(k => p.equipment.some(x => x.kind === k));
      let q = "", kind = "", sort = "hours", shown = 60;
      b.innerHTML = `<div class="tools"><input class="inp search" id="eq" placeholder="Buscar…" autocomplete="off"><select class="inp" id="es"><option value="hours">Horas</option><option value="kills">Kills</option><option value="assists">Assists</option><option value="xp">Afinidade</option></select></div>
        <div class="tabs" id="ek">${has.map(k => `<span class="pill" data-k="${k}">${k}</span>`).join("")}</div><div class="count" id="ec"></div><div class="list" id="el"></div><div id="em"></div>`;
      const dr = () => {
        const L = p.equipment.filter(x => (kind ? x.kind === kind : x.kind !== "Outro") && (!q || x.name.toLowerCase().includes(q))).sort((a, c) => (c[sort] - a[sort]) || a.name.localeCompare(c.name));
        $("#ec", b).textContent = `${fmt(L.length)} itens`;
        $("#el", b).innerHTML = L.slice(0, shown).map(x => `<div class="row">${ico(x.icon, x.name)}<span class="t"><span class="nm">${esc(x.name)} <span class="chip">${x.kind}</span></span><small class="mut">${fmt(x.hours)} h · ${fmt(x.kills)} kills${x.hs ? ` · ${fmt(x.hs)} HS` : ""} · ${fmt(x.assists)} assists</small><small class="mut" style="display:block">${fmt(x.xp)} de afinidade</small></span><span class="n">${sort === "hours" ? fmt(x.hours) + '<small class="mut"> h</small>' : fmt(x[sort])}</span></div>`).join("") || '<div class="empty">Nada por aqui.</div>';
        $("#em", b).innerHTML = L.length > shown ? `<button class="more" id="emb">Mostrar mais (${fmt(L.length - shown)})</button>` : "";
        const mb = $("#emb", b); if (mb) mb.onclick = () => { shown += 60; dr(); };
      };
      $("#eq", b).oninput = debounce(e => { q = e.target.value.trim().toLowerCase(); shown = 60; dr(); });
      $("#es", b).onchange = e => { sort = e.target.value; shown = 60; dr(); };
      $("#ek", b).onclick = e => { const t = e.target.closest("[data-k]"); if (!t) return; kind = kind === t.dataset.k ? "" : t.dataset.k; $$("#ek .pill", b).forEach(x => x.classList.toggle("on", x.dataset.k === kind)); shown = 60; dr(); };
      dr();
    },
    sind: (b, p, pid) => VIEWS.sindicatos(b, pid, true),
    miss: (b, p, pid) => VIEWS.missoes(b, pid, true),
    inim: (b, p) => {
      let q = "", shown = 60;
      b.innerHTML = `<div class="tools"><input class="inp search" id="iq" placeholder="Buscar inimigo…" autocomplete="off"></div><div class="count" id="ic"></div><div class="list" id="il"></div><div id="im"></div>`;
      const dr = () => {
        const L = p.enemies.filter(x => !q || x.name.toLowerCase().includes(q));
        $("#ic", b).textContent = `${fmt(L.length)} inimigos · ${fmt(p.kills)} kills no total`;
        $("#il", b).innerHTML = L.slice(0, shown).map((x, i) => `<div class="row"><span class="t"><span class="nm">${esc(x.name)}${x.faction ? ` <span class="chip">${esc(x.faction)}</span>` : ""}</span><small class="mut">${fmt(x.hs)} headshots</small></span><span class="n">${fmt(x.kills)}</span></div>`).join("");
        $("#im", b).innerHTML = L.length > shown ? `<button class="more" id="imb">Mostrar mais (${fmt(L.length - shown)})</button>` : "";
        const mb = $("#imb", b); if (mb) mb.onclick = () => { shown += 60; dr(); };
      };
      $("#iq", b).oninput = debounce(e => { q = e.target.value.trim().toLowerCase(); shown = 60; dr(); });
      dr();
    },
  };
  await draw();
};

/* ================================================================ ITENS (warframes, armas, …) */
function itemsView(title, sub, tabs, opts = {}) {
  return async el => {
    let cat = tabs[0][0], list = [], filtered = [], q = "", sort = "rank", on = new Set(), shown = PAGE;
    el.innerHTML = `${head(title, sub)}
      ${tabs.length > 1 ? `<div class="tabs" id="tabs">${tabs.map(([c, l]) => `<span class="pill" data-c="${c}">${l}</span>`).join("")}</div>` : ""}
      <div class="tools"><input class="inp search" id="q" placeholder="Buscar…" autocomplete="off">
        <select class="inp" id="sort"><option value="rank">Rank</option><option value="forma">Formas</option><option value="xp">Afinidade</option><option value="name">Nome</option></select></div>
      <div class="tabs" id="pills">${[["max", "Rank máx."], ["prime", "Prime"], ["base", "Base"], ["forma", "Com formas"], ...(opts.shards ? [["shards", "Com shards"]] : []), ["reactor", "Com reator"]].map(([k, l]) => `<span class="pill" data-p="${k}">${l}</span>`).join("")}</div>
      <div class="count" id="count"></div><div class="grid g-cards" id="grid"></div><div id="more"></div>`;
    const draw = () => {
      filtered = list.filter(x =>
        (!q || x.name.toLowerCase().includes(q)) && (!on.has("max") || x.rank >= 30) && (!on.has("prime") || x.prime) && (!on.has("base") || !x.prime) &&
        (!on.has("forma") || x.forma > 0) && (!on.has("shards") || (x.shards && x.shards.length)) && (!on.has("reactor") || x.reactor));
      sortBy(filtered, sort, sort === "name" ? 1 : -1);
      const tf = filtered.reduce((a, x) => a + x.forma, 0);
      $("#count").textContent = `${fmt(filtered.length)} de ${fmt(list.length)} · ${fmt(tf)} formas`;
      $("#grid").innerHTML = filtered.slice(0, shown).map((x, i) => {
        const b = [x.forma ? `<span class="b f" title="Formas aplicadas">F${x.forma}</span>` : "", x.reactor ? '<span class="b r" title="Reator/Catalisador">R</span>' : "",
          hasSlots(x) && x.exilus ? '<span class="b e" title="Exilus">E</span>' : "", hasSlots(x) && x.arcane_slot ? '<span class="b a" title="Adaptador de arcano">A</span>' : "",
          (x.shards && x.shards.length) ? `<span class="shard-line" style="font-size:15px">${x.shards.map(s => shard(s.color, s.tau, "", s.icon, s.glow)).join("")}</span>` : ""].join("");
        return `<div class="card ${x.rank >= 30 ? "max" : ""}" data-i="${i}">${ico(x.icon, x.name)}<div class="body">
          <div class="nm" title="${esc(x.name)}">${esc(x.name)}</div><div class="kd">${esc(x.kind)} · R${x.rank}</div>
          <div class="bar ${x.rank >= 30 ? "max" : ""}"><i style="width:${Math.min(100, x.rank / 30 * 100)}%"></i></div><div class="badges">${b}</div></div></div>`;
      }).join("") || '<div class="empty">Nada por aqui.</div>';
      $("#more").innerHTML = filtered.length > shown ? `<button class="more" id="morebtn">Mostrar mais (${fmt(filtered.length - shown)})</button>` : "";
      const mb = $("#morebtn"); if (mb) mb.onclick = () => { shown += PAGE; draw(); };
    };
    const load = async () => {
      list = [].concat(...await Promise.all((Array.isArray(cat) ? cat : [cat]).map(c => get("/api/items?cat=" + c))));
      shown = PAGE; draw();
    };
    $("#grid").onclick = e => { const c = e.target.closest(".card"); if (c) openItem(filtered[+c.dataset.i]); };
    $("#q").oninput = debounce(e => { q = e.target.value.trim().toLowerCase(); shown = PAGE; draw(); });
    $("#sort").onchange = e => { sort = e.target.value; draw(); };
    $("#pills").onclick = e => {
      const p = e.target.closest("[data-p]"); if (!p) return; const k = p.dataset.p;
      if (on.has(k)) on.delete(k); else { on.add(k); const o = { prime: "base", base: "prime" }[k]; if (o) on.delete(o); } // Prime e Base se excluem
      $$("#pills [data-p]").forEach(x => x.classList.toggle("on", on.has(x.dataset.p)));
      shown = PAGE; draw();
    };
    const t = $("#tabs");
    if (t) {
      const mark = () => $$(".pill", t).forEach(p => p.classList.toggle("on", p.dataset.c === String(cat)));
      t.onclick = e => { const p = e.target.closest("[data-c]"); if (!p) return; cat = tabs.find(x => String(x[0]) === p.dataset.c)[0]; mark(); load(); };
      mark();
    }
    await load();
  };
}
VIEWS.warframes = itemsView("Warframes", "Rank, formas, reator e archon shards de cada Warframe", [["warframes", "Warframes"]], { shards: true });
VIEWS.armas = itemsView("Armas", "Primárias, secundárias e corpo a corpo", [["primary", "Primárias"], ["secondary", "Secundárias"], ["melee", "Corpo a corpo"], ["robotic", "Robóticas"], ["amps", "Amps"]]);
VIEWS.companheiros = itemsView("Companheiros", "Sentinelas, bichos e MOAs", [["companions", "Todos"]]);
VIEWS.veiculos = itemsView("Veículos", "Archwings e Necramechs", [["archwing", "Archwing"], ["necramechs", "Necramechs"]]);

/* ================================================================ ARCHON SHARDS */
VIEWS.shards = async el => {
  const a = await get("/api/archon");
  const rows = (arr) => arr.map(r => `<div class="shard-row">${shard(r.color, false, "shard-md", r.icon)}<span class="nm">${r.name}</span>
      <div class="q"><span>${fmt(r.normal)} <small>normal</small></span><span>${shard(r.color, true, "shard-md", r.icon, r.icon_tau)}${fmt(r.tau)} <small>Tau</small></span></div></div>`).join("");
  el.innerHTML = `${head("Archon Shards", `${fmt(a.total_installed)} instalados · ${fmt(a.total_inventory)} no inventário`)}
    <div class="tools"><button class="pill" id="copy">Copiar resumo (estilo Discord)</button></div>
    <div class="grid g-2">
      <div><div class="sec" style="margin-top:0"><h2>Instalados nos Warframes</h2></div><div class="list">${rows(a.installed)}</div></div>
      <div><div class="sec" style="margin-top:0"><h2>No inventário</h2></div><div class="list">${rows(a.inventory)}</div></div>
    </div>
    <div class="sec"><h2>Warframes com shards (${a.frames.length})</h2></div>
    <div class="grid g-cards" id="fr">${a.frames.map((f, i) => `<div class="card" data-i="${i}">${ico(f.icon, f.name)}<div class="body"><div class="nm">${esc(f.name)}</div>
      <div class="shard-line" style="font-size:16px">${f.shards.map(s => shard(s.color, s.tau, "", s.icon, s.glow)).join("")}</div><div class="kd">${f.shards.length} shards</div></div></div>`).join("")}</div>`;
  $("#fr").onclick = e => {
    const c = e.target.closest(".card"); if (!c) return; const f = a.frames[+c.dataset.i];
    openModal(`<div class="m-head">${ico(f.icon, f.name)}<div><h2>${esc(f.name)}</h2><div class="mut">${f.shards.length} archon shards</div></div></div>
      <div class="fx">${f.shards.map(s => `<div>${shard(s.color, s.tau, "shard-big", s.icon, s.glow)}<span><b>${s.name}${s.tau ? " Tau" : ""}</b><br><span class="mut">${esc(s.effect)}</span></span></div>`).join("")}</div>`);
  };
  $("#copy").onclick = async () => {
    const L = ["Archon Shard Analysis", `Total Shards: ${a.total_installed}`];
    a.installed.forEach(r => { L.push(`${r.name} Shards: ${r.normal}`, `${r.name} Shards Tau: ${r.tau}`); });
    L.push("", "Warframes", ...a.frames.map(f => f.name));
    try { await navigator.clipboard.writeText(L.join("\n")); $("#copy").textContent = "Copiado ✓"; } catch { $("#copy").textContent = "Não consegui copiar"; }
  };
};

/* ================================================================ RELÍQUIAS */
VIEWS.reliquias = async el => {
  const all = await get("/api/relics");
  const tiers = ["Lith", "Meso", "Neo", "Axi", "Requiem"];
  let tier = "", q = "", sort = "qty", shown = 80;
  const total = all.reduce((a, r) => a + r.total, 0);
  el.innerHTML = `${head("Relíquias", `${fmt(all.length)} tipos · ${fmt(total)} unidades`)}
    <div class="tabs" id="tabs"><span class="pill on" data-t="">Todas (${all.length})</span>${tiers.map(t => `<span class="pill" data-t="${t}">${t} (${all.filter(r => r.tier === t).length})</span>`).join("")}</div>
    <div class="tools"><input class="inp search" id="q" placeholder="Buscar relíquia ou item de drop…" autocomplete="off">
      <select class="inp" id="sort"><option value="qty">Quantidade</option><option value="name">Nome</option></select></div>
    <div class="count" id="count"></div><div class="grid g-2" id="grid"></div><div id="more"></div>`;
  const draw = () => {
    let L = all.filter(r => (!tier || r.tier === tier) && (!q || r.name.toLowerCase().includes(q) || r.rewards.some(w => w.name.toLowerCase().includes(q))));
    L = sort === "qty" ? L.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name)) : L.sort((a, b) => a.tier_n - b.tier_n || a.name.localeCompare(b.name));
    $("#count").textContent = `${fmt(L.length)} relíquias`;
    $("#grid").innerHTML = L.slice(0, shown).map(r => `<div class="relic tier-${r.tier}"><div class="relic-h"><div class="relic-i">${r.icon ? `<img loading="lazy" src="${r.icon}" onerror="this.outerHTML=window.__rs">` : relicSvg}</div>
      <div style="flex:1;min-width:0"><div class="nm">${esc(r.tier)} ${esc(r.name.replace(new RegExp("^" + r.tier + "\\s*"), ""))}</div>
      <div class="cnt">${Object.entries(r.counts).map(([k, v]) => `<span class="chip">${k} ×${fmt(v)}</span>`).join("")}${r.vault ? '<span class="chip gold">Vault</span>' : ""}</div></div>
      <div class="tot">${fmt(r.total)}</div></div>
      <div class="relic-b">${r.rewards.length ? r.rewards.map(w => `<div class="rw"><span class="rar ${w.rarity}"></span>${ico(w.icon, w.name)}<span style="flex:1">${esc(w.name)}${w.count > 1 ? ` <span class="mut">×${w.count}</span>` : ""}</span><span class="dim" style="font-size:11px;text-transform:uppercase">${w.rarity}</span></div>`).join("") : '<div class="mut" style="padding:8px 0">Drops indisponíveis — rode <code>python3 fetch_data.py</code>.</div>'}</div></div>`).join("") || '<div class="empty">Nenhuma relíquia.</div>';
    $("#more").innerHTML = L.length > shown ? `<button class="more" id="morebtn">Mostrar mais (${fmt(L.length - shown)})</button>` : "";
    const mb = $("#morebtn"); if (mb) mb.onclick = () => { shown += 80; draw(); };
  };
  window.__rs = relicSvg;
  $("#grid").onclick = e => { const h = e.target.closest(".relic-h"); if (h) h.parentElement.classList.toggle("open"); };
  $("#tabs").onclick = e => { const p = e.target.closest("[data-t]"); if (!p) return; tier = p.dataset.t; $$("#tabs .pill").forEach(x => x.classList.toggle("on", x === p)); shown = 80; draw(); };
  $("#q").oninput = debounce(e => { q = e.target.value.trim().toLowerCase(); shown = 80; draw(); });
  $("#sort").onchange = e => { sort = e.target.value; draw(); };
  draw();
};

/* ================================================================ FORMAS */
VIEWS.formas = async el => {
  const f = await get("/api/forma");
  const names = { warframes: "Warframes", primary: "Primárias", secondary: "Secundárias", melee: "Corpo a corpo", companions: "Companheiros", archwing: "Archwing", necramechs: "Necramechs", amps: "Amps", robotic: "Robóticas" };
  const max = Math.max(1, ...Object.values(f.by_cat));
  el.innerHTML = `${head("Formas", "Quantas formas cada equipamento recebeu")}
    <div class="grid g-stats"><div class="stat"><span class="l">Total aplicado</span><span class="v gold">${fmt(f.total)}</span></div></div>
    <div class="sec"><h2>Por categoria</h2></div><div class="panel">${Object.entries(f.by_cat).filter(([, v]) => v).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<div class="hbar"><span class="l">${names[k] || k}</span><div class="bar"><i style="width:${v / max * 100}%"></i></div><span class="v">${fmt(v)}</span></div>`).join("")}</div>
    <div class="sec"><h2>Mais formados</h2></div><div class="list">${f.top.map(x => `<div class="row">${ico(x.icon, x.name)}<span class="t">${esc(x.name)} <span class="dim">· ${esc(x.kind)}</span></span><span class="b f" style="font-size:13px">F${x.forma}</span></div>`).join("")}</div>`;
};

/* ================================================================ INVENTÁRIO (com preços do warframe.market) */
const MK = { cache: {}, err: "", tok: 0, run: 0 };
const mkKey = x => `${x.slug}|${x.pr ?? "any"}|${x.sub || ""}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
/* Pede os preços em lotes. O servidor responde na hora com o cache; o que ainda não existe vem como "pending"
   e é buscado em segundo plano pelo servidor (1 por vez, respeitando o limite do site) — então só repetimos a consulta. */
async function mkSync(list, tok, tick, prio = 0) {
  const seen = new Set(), keys = [];
  for (const x of list) { if (!x.slug) continue; const k = mkKey(x); if (!(k in MK.cache) && !seen.has(k)) { seen.add(k); keys.push(k); } }
  for (let i = 0; i < keys.length && tok === MK.tok; i += 60) {
    let todo = keys.slice(i, i + 60), tries = 0;
    while (todo.length && tok === MK.tok && tries < 400) {
      let r;
      try { r = await (await fetch(`/api/market/prices?p=${prio}&` + todo.map(k => "k=" + encodeURIComponent(k)).join("&"), { cache: "no-store" })).json(); MK.err = ""; }
      catch { MK.err = "sem resposta do servidor"; await sleep(4000); tries += 5; continue; }
      const left = [];
      for (const k of todo) { const v = r[k]; if (!v) continue; if (v.pending) left.push(k); else if (v.error) MK.err = v.error; else MK.cache[k] = v; }
      if (tok === MK.tok) tick();
      todo = left; tries++;
      if (todo.length) await sleep(2500);
    }
  }
}
const plat = n => `${fmt(n)}<span class="plat">p</span>`;
const unitOf = x => { const p = x.slug && MK.cache[mkKey(x)]; return p && !p.none && p.sell != null ? p.sell : null; };
const buyOf = x => { const p = x.slug && MK.cache[mkKey(x)]; return p && !p.none ? p.buy : null; };
const valueOf = x => x.parts ? x.parts.reduce((a, y) => a + (unitOf(y) ?? 0) * y.count, 0) : (unitOf(x) ?? 0) * ((x.vc ?? x.count) || 0);

VIEWS.inventario = async el => {
  const tabs = [["resources", "Recursos"], ["mods", "Mods"], ["arcanes", "Arcanos"], ["archon", "Archon Shards"], ["relics", "Relíquias"], ["primeparts", "Prime parts"], ["primesets", "Prime sets"], ["blueprints", "Blueprints"], ["consumables", "Consumíveis"], ["cosmetics", "Cosméticos"], ["skins", "Skins"]];
  const PRICED = new Set(["mods", "arcanes", "archon", "relics", "primeparts", "primesets"]);
  let cat = "resources", list = [], q = "", sort = "count", shown = 60, filtered = [], only = new Set(), open = new Set(), tok = ++MK.tok;
  el.innerHTML = `${head("Inventário", "Tudo o que está no seu lastData · preços em platina do warframe.market")}
    <div class="grid g-stats" id="sum"></div>
    <div class="tabs" id="tabs">${tabs.map(([c, l]) => `<span class="pill" data-c="${c}">${l}</span>`).join("")}</div>
    <div class="tools"><input class="inp search" id="q" placeholder="Buscar…" autocomplete="off"><select class="inp" id="sort"></select></div>
    <div class="tabs" id="pills"></div>
    <div class="mkbar" id="mkbar"></div>
    <div class="count" id="count"></div><div class="list" id="list"></div><div id="more"></div>`;
  const priced = () => PRICED.has(cat);
  const stateOf = x => !x.slug ? "none" : (mkKey(x) in MK.cache ? (MK.cache[mkKey(x)].none || MK.cache[mkKey(x)].sell == null ? "empty" : "ok") : "wait");
  const priceLine = x => {
    if (!priced()) return "";
    if (x.parts) {
      const su = unitOf(x), ready = x.parts.every(y => stateOf(y) !== "wait"), one = x.parts.reduce((s, y) => s + (unitOf(y) ?? 0), 0), stock = valueOf(x);
      const a1 = x.slug ? (su != null ? `set ${plat(su)}` : stateOf(x) === "wait" ? "set …" : "set sem ordens") : "sem set no mercado";
      const b1 = one ? `1 de cada parte ${plat(one)}${ready ? "" : "+"}` : "";
      const c1 = stock ? `seu estoque ${plat(stock)}${ready ? "" : "+"}` : "";
      const cmp = su != null && ready && one ? (su > one ? '<span class="chip ok">set vale mais que as partes</span>' : '<span class="chip gold">partes valem mais que o set</span>') : "";
      return `<div class="pl">${[a1, b1, c1].filter(Boolean).join(" · ")} ${cmp}</div>`;
    }
    const s = stateOf(x), u = unitOf(x), b = buyOf(x);
    if (s === "none") return `<div class="pl mut">${esc(x.note || "sem mercado")}</div>`;
    if (s === "wait") return `<div class="pl mut">buscando preço…</div>`;
    if (s === "empty") return `<div class="pl mut">sem ordens ativas</div>`;
    return `<div class="pl">${plat(u)} cada${(x.vc ?? x.count) > 1 ? ` · <b>${plat(u * (x.vc ?? x.count))}</b> total` : ""}${b != null ? ` · <span class="mut">compra ${plat(b)}</span>` : ""}</div>`;
  };
  const iconOf = x => x.color ? `<div class="ico">${shard(x.color, x.tau, "", x.icon, x.glow)}</div>` : ico(x.icon, x.name);
  const row = (x, i) => `<div class="row irow ${x.parts ? "set" : ""}" data-i="${i}">${iconOf(x)}${x.rarity ? `<span class="rar ${x.rarity}"></span>` : ""}
      <span class="t"><span class="nm">${esc(x.name)}${x.rank != null ? ` <span class="chip gold">R${x.rank}${x.max ? "/" + x.max : ""}</span>` : ""}${x.ranked ? (x.unranked ? ` <span class="chip">sem rank ×${fmt(x.unranked)}</span>` : "") + x.ranked.slice(0, 3).map(([l, n]) => ` <span class="chip ${x.max && l >= x.max ? "gold" : ""}">R${l}${x.max ? "/" + x.max : ""} ×${fmt(n)}</span>`).join("") : ""}${x.n_parts ? ` <span class="chip">${x.n_parts} partes</span>` : ""}${x.tier && x.counts ? Object.entries(x.counts).map(([k, v]) => ` <span class="chip">${k} ×${fmt(v)}</span>`).join("") : ""}</span>${priceLine(x)}</span>
      <span class="n">${x.parts ? fmt(x.count) + '<small class="mut"> un</small>' : fmt(x.vc ?? x.count)}</span></div>` +
    (x.parts && open.has(x.path) ? `<div class="subrows">${x.parts.map(p => `<div class="row srow">${iconOf(p)}<span class="t"><span class="nm">${esc(p.name)}</span>${priceLine(p)}</span><span class="n">${fmt(p.count)}</span></div>`).join("")}</div>` : "");
  const visibleItems = () => filtered.slice(0, shown).flatMap(x => x.parts ? [x, ...(open.has(x.path) ? x.parts : [])] : [x]);
  const sortOpts = () => `<option value="count">Quantidade</option><option value="name">Nome</option>${priced() ? '<option value="unit">Preço unitário</option><option value="total">Valor total</option>' : ""}`;
  const pillOpts = () => priced() ? [["ok", "Com preço"], ["none", "Sem mercado"],
    ...(cat === "mods" ? [["max", "Rank máximo"], ["rk", "Ranqueados"]] : cat === "arcanes" ? [["max", "Rank máximo"], ["unr", "Sem rank"]] : [])] : [];
  const isMod = x => x.unranked !== undefined;
  const TEST = { ok: x => !!x.slug, none: x => !x.slug,
    max: x => isMod(x) ? x.at_max > 0 : (x.rank != null && x.max != null && x.rank >= x.max),
    rk: x => x.total_ranked > 0, unr: x => x.rank == null };
  /* Mods: por padrão só o estoque sem rank (como antes). "Rank máximo" / "Ranqueados" trocam a visão para os mods ranqueados. */
  const viewCount = x => !isMod(x) ? x.count : only.has("max") ? x.at_max : only.has("rk") ? x.total_ranked : x.unranked;
  const inView = x => !isMod(x) || viewCount(x) > 0;
  let view = [];
  const sumDraw = () => {
    const cnt = view.reduce((a, x) => a + ((x.vc ?? x.count) || 0), 0);
    let s = `<div class="stat"><span class="l">Entradas</span><span class="v">${fmt(view.length)}</span><span class="s">${fmt(cnt)} unidades</span></div>`;
    if (priced()) {
      const rows = view.filter(x => x.slug), ok = rows.filter(x => x.parts ? valueOf(x) > 0 || unitOf(x) != null : unitOf(x) != null);
      const tot = view.reduce((a, x) => a + valueOf(x), 0);
      s += `<div class="stat"><span class="l">${cat === "primesets" ? "Valor das partes" : "Valor estimado"}</span><span class="v gold">${fmt(tot)}<span class="plat">p</span>${ok.length < rows.length ? "+" : ""}</span><span class="s">${fmt(ok.length)} de ${fmt(rows.length)} com preço${ok.length < rows.length ? " · parcial" : ""}</span></div>`;
    }
    $("#sum").innerHTML = s;
  };
  const barDraw = () => {
    const pend = view.flatMap(x => x.parts ? [x, ...x.parts] : [x]).filter(x => x.slug && !(mkKey(x) in MK.cache)).length;
    const noIdx = priced() && view.length && !view.some(x => x.slug);
    $("#mkbar").innerHTML = !priced() ? "" :
      `${MK.err ? `<div class="mkerr">${esc(MK.err)}</div>` : ""}${noIdx ? '<div class="mkerr">Nenhum item deste grupo foi encontrado no warframe.market.</div>' : ""}
       <div class="mkrow"><span class="mut">${pend ? `Buscando ${fmt(pend)} preços em segundo plano…` : "Preços carregados"} · atualizados 1 vez por dia</span></div>`;
  };
  let tickT = 0;
  const tick = () => { clearTimeout(tickT); tickT = setTimeout(draw, 180); };
  const fetchVisible = () => {
    if (!priced()) return;
    const t = tok, all = view.flatMap(x => x.parts ? [x, ...x.parts] : [x]), sig = t + "|" + [...only].sort().join();
    if (MK.run === sig) return; MK.run = sig;           // uma busca automática por aba/visão (o que já está em cache não é pedido de novo)
    mkSync(visibleItems(), t, tick, 0).then(() => mkSync(all, t, tick, 1));
  };
  const keyFns = { count: x => -((x.vc ?? x.count) || 0), unit: x => -(unitOf(x) ?? -1), total: x => -(x.parts ? valueOf(x) : valueOf(x) || -1) };
  function draw() {
    list.forEach(x => { x.vc = viewCount(x); });
    view = list.filter(inView);
    filtered = view.filter(x => (!q || x.name.toLowerCase().includes(q) || (x.parts && x.parts.some(p => p.name.toLowerCase().includes(q)))) &&
      [...only].every(f => TEST[f](x)));
    if (sort === "name") filtered.sort((a, b) => a.name.localeCompare(b.name));
    else filtered.sort((a, b) => (keyFns[sort](a) - keyFns[sort](b)) || a.name.localeCompare(b.name));
    $("#count").textContent = `${fmt(filtered.length)} de ${fmt(view.length)} entradas`;
    $("#list").innerHTML = filtered.slice(0, shown).map(row).join("") || '<div class="empty">Vazio.</div>';
    $("#more").innerHTML = filtered.length > shown ? `<button class="more" id="morebtn">Mostrar mais (${fmt(filtered.length - shown)})</button>` : "";
    const mb = $("#morebtn"); if (mb) mb.onclick = () => { shown += 60; draw(); };
    sumDraw(); barDraw(); fetchVisible();
  }
  const load = async () => {
    tok = ++MK.tok; open.clear();
    $$("#tabs .pill").forEach(p => p.classList.toggle("on", p.dataset.c === cat));
    $("#list").innerHTML = '<div class="empty">Carregando…</div>';
    list = await get("/api/inventory?cat=" + cat);
    shown = 60; sort = "count"; only = new Set();
    $("#sort").innerHTML = sortOpts(); $("#sort").value = sort;
    $("#pills").innerHTML = pillOpts().map(([k, l]) => `<span class="pill" data-p="${k}">${l}</span>`).join("");
    draw();
  };
  $("#tabs").onclick = e => { const p = e.target.closest("[data-c]"); if (p && p.dataset.c !== cat) { cat = p.dataset.c; load(); } };
  $("#q").oninput = debounce(e => { q = e.target.value.trim().toLowerCase(); shown = 60; draw(); });
  $("#sort").onchange = e => { sort = e.target.value; draw(); };
  $("#pills").onclick = e => { const p = e.target.closest("[data-p]"); if (!p) return; const f = p.dataset.p; only.has(f) ? only.delete(f) : only.add(f); $$("#pills .pill").forEach(x => x.classList.toggle("on", only.has(x.dataset.p))); shown = 60; draw(); };
  $("#list").onclick = e => {
    const r = e.target.closest(".irow"); if (!r) return; const x = filtered[+r.dataset.i]; if (!x) return;
    if (x.parts) { open.has(x.path) ? open.delete(x.path) : open.add(x.path); draw(); return; }
    if ((cat === "mods" || cat === "arcanes") && x.path) showFx(x, cat === "arcanes");
  };
  await load();
};

/* ================================================================ SINDICATOS */
VIEWS.sindicatos = async (el, pid = "", embed = false) => {
  const s = await get("/api/syndicates" + (pid ? "?pid=" + pid : ""));
  const row = x => {
    const has = x.cap != null, pct = has ? Math.min(100, x.cur / x.cap * 100) : 0;
    const sub = has ? `Rank ${x.rank}${x.maxed ? " · máximo" : ""} · total ${fmt(x.standing)}` : (x.title != null ? `Rank ${x.title}` : "Total");
    const right = has ? `${x.neg ? "−" : ""}${fmt(x.cur)}<br><small class="mut">/ ${fmt(x.cap)}</small>` : fmt(x.standing);
    return `<div class="row"><span class="t" style="flex:none;width:min(210px,40%)">${esc(x.name)}<br><small class="mut">${esc(sub)}</small></span>
      <div class="bar ${x.neg ? "neg" : x.maxed ? "max" : ""}" style="flex:1"><i style="width:${pct}%"></i></div>
      <span class="n" style="width:104px;text-align:right;line-height:1.2">${right}</span></div>`;
  };
  el.innerHTML = `${embed ? "" : head("Sindicatos", "Reputação dentro do rank atual (o total acumulado aparece embaixo do nome)")}<div class="list">${s.map(row).join("")}</div>`;
};

/* ================================================================ MISSÕES */
VIEWS.missoes = async (el, pid = "", embed = false) => {
  const all = await get("/api/missions" + (pid ? "?pid=" + pid : ""));
  let q = "", mode = "", shown = 150;
  el.innerHTML = `${embed ? "" : head("Missões", `${fmt(all.length)} nós jogados · ${fmt(all.filter(m => m.steel_path).length)} no Steel Path`)}
    <div class="tools"><input class="inp search" id="q" placeholder="Buscar nó, tipo ou facção…" autocomplete="off">
      <span class="pill" data-m="sp">Steel Path</span><span class="pill" data-m="n">Normal</span></div>
    <div class="count" id="count"></div><div class="list mlist" id="tb"></div><div id="more"></div>`;
  const draw = () => {
    const L = all.filter(m => (!q || `${m.name} ${m.type} ${m.enemy}`.toLowerCase().includes(q)) && (!mode || (mode === "sp") === m.steel_path));
    $("#count").textContent = `${fmt(L.length)} resultados`;
    $("#tb").innerHTML = L.slice(0, shown).map(m => `<div class="mrow"><div class="mi"><div class="mn">${esc(m.name)}${m.steel_path ? ' <span class="chip gold">SP</span>' : ""}</div><div class="ms">${esc([m.type, m.enemy].filter(Boolean).join(" · ") || "—")}</div></div><div class="mc"><b>${fmt(m.completes)}</b><small>vezes</small></div></div>`).join("") || '<div class="empty">Nada por aqui.</div>';
    $("#more").innerHTML = L.length > shown ? `<button class="more" id="morebtn">Mostrar mais (${fmt(L.length - shown)})</button>` : "";
    const mb = $("#morebtn"); if (mb) mb.onclick = () => { shown += 150; draw(); };
  };
  $("#q").oninput = debounce(e => { q = e.target.value.trim().toLowerCase(); shown = 150; draw(); });
  $$("[data-m]").forEach(p => p.onclick = () => { const v = p.dataset.m; mode = mode === v ? "" : v; $$("[data-m]").forEach(x => x.classList.toggle("on", x.dataset.m === mode)); shown = 150; draw(); });
  draw();
};

/* ================================================================ LOGIN, UPLOAD DO lastData E BARRA DO USUÁRIO */
let ME = null, LOCKED = false;
const post = async (path, body, raw) => {
  const r = await fetch(path, { method: "POST", headers: raw ? {} : { "Content-Type": "application/json" }, body: raw ?? JSON.stringify(body || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Erro " + r.status);
  return j;
};
const dtFmt = ts => new Date(ts * 1000).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
const ago = ts => { const s = Date.now() / 1000 - ts; if (s < 90) return "agora"; if (s < 3600) return `há ${Math.round(s / 60)} min`; if (s < 86400) return `há ${Math.round(s / 3600)} h`; const d = Math.round(s / 86400); return `há ${d} dia${d > 1 ? "s" : ""}`; };
const left = sec => { const t = Math.max(0, Math.ceil(sec / 60)), h = Math.floor(t / 60), m = t % 60; return h ? `${h}h ${m}min` : `${m}min`; };
const lock = () => { LOCKED = true; document.body.classList.add("locked"); $("#banner").innerHTML = ""; };

function showLogin(tab = "login", msg = "") {
  lock(); $("#userbar").innerHTML = "";
  const T = [["login", "Entrar"], ["register", "Criar conta"], ["visitor", "Visitante"]];
  const inp = (id, label, type = "text", extra = "") => `<label class="fl">${label}<input class="inp" id="${id}" type="${type}" ${extra} autocapitalize="off" spellcheck="false"></label>`;
  const rem = `<label class="chk"><input type="checkbox" id="a-rem" checked> Manter conectado neste aparelho</label>`;
  const code = inp("a-code", "Código de acesso", "password", 'autocomplete="off"');
  const pid = inp("a-pid", "ID da conta Warframe <small class='mut'>(opcional)</small>", "text", 'autocomplete="off" placeholder="24 caracteres"');
  const F = {
    login: inp("a-user", "Usuário", "text", 'autocomplete="username"') + inp("a-pass", "Senha", "password", 'autocomplete="current-password"') + rem,
    register: code + inp("a-user", "Escolha um usuário", "text", 'autocomplete="username"') + inp("a-pass", "Escolha uma senha (mín. 6)", "password", 'autocomplete="new-password"') + pid + rem,
    visitor: code + pid + `<p class="mut" style="margin:2px 0 0;font-size:13px">Sem conta: você envia o seu lastData e vê o seu perfil por <b>${ME.visitor_minutes / 60} horas</b>. Nada é salvo: depois disso os dados são apagados da memória do servidor automaticamente.</p>`,
  };
  const BTN = { login: "Entrar", register: "Criar conta e entrar", visitor: "Entrar como visitante" };
  $("#view").innerHTML = `<div class="auth-card"><div class="auth-brand"><span class="brand-mark">◈</span><span>WARFRAME<small>PROFILE</small></span></div>
    <div class="tabs" id="atabs">${T.map(([k, l]) => `<span class="pill ${k === tab ? "on" : ""}" data-t="${k}">${l}</span>`).join("")}</div>
    <form id="aform" class="aform">${F[tab]}<button class="btn" id="a-go" type="submit">${BTN[tab]}</button><div class="amsg" id="amsg">${esc(msg)}</div></form>
    ${ME.discord ? `<p class="mut adisc">Não tem o código de acesso? Chame no Discord: <button class="linklike" id="a-dc" type="button">${esc(ME.discord)}</button></p>` : ""}</div>`;
  $("#atabs").onclick = e => { const t = e.target.closest("[data-t]"); if (t) showLogin(t.dataset.t); };
  const dc = $("#a-dc"); if (dc) dc.onclick = () => { navigator.clipboard?.writeText(ME.discord); dc.textContent = ME.discord + " ✓ copiado"; };
  const v = id => ($("#" + id)?.value || "").trim();
  $("#aform").onsubmit = async e => {
    e.preventDefault(); const go = $("#a-go"), m = $("#amsg"); go.disabled = true; m.textContent = "";
    const pidv = (v("a-pid").match(/[0-9a-fA-F]{24}/) || [""])[0];
    try {
      if (tab === "login") await post("/api/auth/login", { username: v("a-user"), password: $("#a-pass").value, remember: $("#a-rem").checked });
      else if (tab === "register") await post("/api/auth/register", { code: $("#a-code").value.trim(), username: v("a-user"), password: $("#a-pass").value, player_id: pidv, remember: $("#a-rem").checked });
      else await post("/api/auth/visitor", { code: $("#a-code").value.trim(), player_id: pidv });
      location.reload();
    } catch (err) { m.textContent = err.message; go.disabled = false; }
  };
  ($("#a-user") || $("#a-code")).focus();
}

function showUpload(canCancel = false) {
  lock(); renderUserBar();
  const visitor = ME.kind === "visitor";
  $("#view").innerHTML = `<div class="auth-card"><h1 style="margin:0 0 6px;font-size:22px">${canCancel ? "Atualizar os dados" : "Envie o seu lastData"}</h1>
    <p class="mut" style="margin:0 0 14px;font-size:14px">Escolha o arquivo <b>lastData.dat</b> do AlecaFrame (ou o JSON já descriptografado). Ele é descriptografado ${ME.app ? "aqui no aparelho e fica guardado só nele; substitui a versão anterior" : visitor ? "no servidor e fica só na memória, por tempo limitado" : "no servidor e substitui a versão anterior da sua conta"}.</p>
    <label class="drop" for="f"><span class="drop-ic">⬆</span><span id="fname">Toque para escolher o arquivo</span><input type="file" id="f" accept=".dat,.json,application/json,application/octet-stream" hidden></label>
    ${ME.player_id ? "" : `<label class="fl" style="margin-top:12px">ID da conta Warframe <small class="mut">(opcional, para o perfil público)</small><input class="inp" id="u-pid" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="24 caracteres"></label>`}
    <div style="display:flex;gap:8px;align-items:center;margin-top:14px"><button class="btn" id="u-go" type="button">Enviar</button>${canCancel ? '<button class="pill" id="u-cx" type="button">Cancelar</button>' : ""}</div>
    <div class="amsg" id="umsg"></div></div>`;
  $("#f").onchange = () => { const f = $("#f").files[0]; $("#fname").textContent = f ? `${f.name} · ${(f.size / 1048576).toFixed(1)} MB` : "Toque para escolher o arquivo"; };
  const cx = $("#u-cx"); if (cx) cx.onclick = () => location.reload();
  $("#u-go").onclick = async () => {
    const f = $("#f").files[0], m = $("#umsg"); if (!f) { m.textContent = "Escolha o arquivo primeiro."; return; }
    const go = $("#u-go"); go.disabled = true; m.className = "amsg mut"; m.textContent = "Enviando e descriptografando…";
    const pidv = (($("#u-pid")?.value || "").match(/[0-9a-fA-F]{24}/) || [""])[0];
    try { await post("/api/data/upload" + (pidv ? "?pid=" + pidv : ""), null, f); location.reload(); }
    catch (err) { m.className = "amsg"; m.textContent = err.message; go.disabled = false; }
  };
}

let _ubT = 0;
function renderUserBar() {
  const el = $("#userbar"); clearInterval(_ubT);
  if (!ME || !ME.authenticated || (!ME.auth && ME.kind !== "legacy")) { el.innerHTML = ""; return; }
  const visitor = ME.kind === "visitor", legacy = ME.kind === "legacy", isApp = !!ME.app;
  const fresh = () => { if (!ME.uploaded_at) return ""; const old = Date.now() / 1000 - ME.uploaded_at > 86400;
    return `<span class="chip ${old ? "gold" : "ok"}" title="${dtFmt(ME.uploaded_at)}">Dados de ${dtFmt(ME.uploaded_at)} · ${ago(ME.uploaded_at)}${old ? " · pode estar desatualizado" : ""}</span>`; };
  const paint = () => {
    if (visitor && ME.expires_at - Date.now() / 1000 <= 0) { location.reload(); return; }
    $("#ub-info").innerHTML = ((legacy || isApp) ? "" : `<span class="chip cyan">${visitor ? "Visitante" : "👤 " + esc(ME.user)}</span>`) + fresh() +
      (visitor ? `<span class="chip gold">expira em ${left(ME.expires_at - Date.now() / 1000)} · nada fica salvo</span>` : "");
  };
  el.innerHTML = `<div class="ubar"><div class="chips" id="ub-info" style="margin:0"></div>${legacy ? "" : `<span class="sp"></span>
    <button class="pill" id="ub-up">Atualizar dados</button>${isApp ? "" : '<button class="pill" id="ub-out">Sair</button>'}
    ${visitor ? "" : `<details class="umore"><summary class="pill">⋯</summary><div class="umenu"><button class="linklike" id="ub-del">Apagar meus dados</button>${isApp ? "" : '<button class="linklike danger" id="ub-acc">Excluir minha conta</button>'}</div></details>`}`}</div>`;
  paint(); _ubT = setInterval(paint, 30000);
  if (legacy) return;
  $("#ub-up").onclick = () => showUpload(true);
  const outb = $("#ub-out"); if (outb) outb.onclick = async () => { await post("/api/auth/logout").catch(() => {}); location.reload(); };
  const del = $("#ub-del"); if (del) del.onclick = async () => { if (confirm("Apagar o seu lastData salvo? A conta continua existindo.")) { await post("/api/data/delete"); location.reload(); } };
  const acc = $("#ub-acc"); if (acc) acc.onclick = async () => { const pw = prompt("Para excluir a conta e todos os dados, digite a sua senha:"); if (pw) { try { await post("/api/account/delete", { password: pw }); location.reload(); } catch (e) { alert(e.message); } } };
}

async function boot() {
  try { ME = await (await fetch("/api/auth/me", { cache: "no-store" })).json(); } catch { ME = { authenticated: true, auth: false, kind: "legacy", has_data: true }; }
  if (ME.auth && !ME.authenticated) return showLogin();
  if (ME.auth && !ME.has_data) return showUpload(false);
  LOCKED = false; document.body.classList.remove("locked");
  renderUserBar(); route();
}

boot();


/* ---- versão: mostra qual app.js está rodando e avisa se o servidor está desatualizado */
(async () => {
  const sm = $(".brand-txt small"); if (sm) sm.textContent = "PROFILE · v" + APP_VERSION;
  let msg = "";
  try {
    const v = await (await fetch("/api/version", { cache: "no-store" })).json();
    if (!v || v.version !== APP_VERSION) msg = `servidor desatualizado (${v && v.version ? v.version : "antigo"}) — feche o app e abra de novo.`;
  } catch { msg = "servidor antigo em execução — feche o app e abra de novo."; }
  if (msg) { const d = document.createElement("div"); d.className = "banner"; d.style.cssText = "position:fixed;left:8px;right:8px;bottom:8px;z-index:99"; d.textContent = msg; d.onclick = () => d.remove(); document.body.appendChild(d); }
})();

/* ================================================================ helpers novos */
const jf = async u => { const r = await fetch(u, { cache: "no-store" }); const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.error || "Erro " + r.status); return j; };
const gc = g => String(g).replace("+", "p").replace("-", "m");
const br = t => esc(t).replace(/\n/g, "<br>");

/* ---- efeitos de mods / arcanos (detalhe ao tocar no item do inventário) */
async function showFx(x, arc) {
  openModal(`<div class="m-head">${ico(x.icon, x.name)}<div><h2 style="font-size:21px">${esc(x.name)}</h2><div class="mut" id="fxm"></div></div></div><div id="fxb" class="fx"><div class="empty">Carregando efeitos…</div></div>`);
  for (let i = 0; i < 60; i++) {
    let r; try { r = await jf("/api/effects?p=" + encodeURIComponent(x.path)); } catch (e) { if ($("#fxb")) $("#fxb").innerHTML = `<div class="mkerr">${esc(e.message)}</div>`; return; }
    if (!$("#fxb")) return;
    if (r.status === "building") { $("#fxb").innerHTML = '<div class="empty">Baixando os dados de efeitos (só na primeira vez)…</div>'; await sleep(2000); continue; }
    if (String(r.status).startsWith("error:")) { $("#fxb").innerHTML = `<div class="mkerr">${esc(r.status.slice(6))}</div>`; return; }
    if (!r.e) { $("#fxb").innerHTML = '<div class="empty">Sem dados de efeito para este item.</div>'; return; }
    const e = r.e, S = (e.s || []).filter(Boolean), pol = e.p ? String(e.p).replace("AP_", "").toLowerCase() : "";
    $("#fxm").innerHTML = [e.r, e.t, pol, e.d != null ? "dreno " + e.d : ""].filter(Boolean).map(v => `<span class="chip">${esc(v)}</span>`).join(" ");
    const lv = (t, i) => `<div class="fxr"><b>Rank ${i}</b><div>${br(t)}</div></div>`;
    let h = "";
    if (e.x && e.x.length && !arc) h += `<div class="fxd">${br(e.x.join("\n"))}</div>`;
    if (!S.length) h += e.x && e.x.length ? "" : '<div class="empty">Sem detalhes por rank.</div>';
    else if (arc) h += S.map((t, i) => lv(t, i + 1)).join("");
    else h += `<div class="fxr max"><b>Rank máx (${S.length - 1})</b><div>${br(S[S.length - 1])}</div></div><details class="fxall"><summary>Ver todos os ranks</summary>${S.map((t, i) => lv(t, i)).join("")}</details>`;
    $("#fxb").innerHTML = h; return;
  }
}

/* ================================================================ RIVENS */
VIEWS.rivens = async el => {
  const L = await jf("/api/rivens");
  let q = "", fam = "", sort = "grade", shown = 40;
  const FN = { rifle: "Rifle", pistol: "Pistola", shotgun: "Shotgun", melee: "Melee", arch: "Arch-gun" }, fams = [...new Set(L.map(r => r.fam))];
  el.innerHTML = `${head("Rivens", `${fmt(L.length)} rivens no seu lastData · valores no rank atual e no máximo`)}
    <div class="tabs" id="rf"><span class="pill on" data-f="">Todos</span>${fams.map(f => `<span class="pill" data-f="${f}">${FN[f] || f}</span>`).join("")}</div>
    <div class="tools"><input class="inp search" id="rq" placeholder="Buscar arma ou nome…" autocomplete="off"><select class="inp" id="rs"><option value="grade">Melhor grade</option><option value="rerolls">Mais rerolls</option><option value="mr">Maestria</option><option value="name">Nome</option></select></div>
    <div class="count" id="rc"></div><div class="grid rivs" id="rl"></div><div id="rm"></div>
    <div class="mut" style="font-size:12px;margin-top:12px">Grade calculada como no seu grading.js: base da categoria × disposição 1.2 × multiplicador (2P/3P…) comparado com a rolagem real (S a F). Dano contra facção aparece como multiplicador (x1.47).</div>`;
  const card = r => `<div class="riv"><div class="rv-h"><span class="rv-d">${r.drain}</span><span class="rv-n">${esc(r.name)}</span><b class="gr g-${gc(r.grade)} rv-g" title="Grade geral (${r.gdev}%)">${r.grade}</b></div>
    <div class="rv-s">${r.stats.map(s => `<div class="${s.neg ? "neg" : "pos"}">${esc(s.cur)} ${esc(s.label)}${s.max !== s.cur ? ` <small>(máx ${esc(s.max)})</small>` : ""} ${s.g ? `<b class="gr g-${gc(s.g)}" title="${s.dev}% vs esperado">${s.g}</b>` : ""}</div>`).join("")}</div>
    <div class="rv-f"><span>MR ${r.mr}</span><span>R${r.rank}/8</span><span>↻ ${fmt(r.rerolls)}</span><span class="chip">${esc(r.pol)}</span><span class="chip">${r.cfg}</span></div></div>`;
  const draw = () => {
    let A = L.filter(r => (!fam || r.fam === fam) && (!q || r.name.toLowerCase().includes(q)));
    const K = { grade: (a, b) => b.gdev - a.gdev, rerolls: (a, b) => b.rerolls - a.rerolls, avg: (a, b) => b.avg - a.avg, mr: (a, b) => b.mr - a.mr, name: (a, b) => a.name.localeCompare(b.name) };
    A.sort((a, b) => K[sort](a, b) || a.name.localeCompare(b.name));
    $("#rc").textContent = `${fmt(A.length)} de ${fmt(L.length)} rivens`;
    $("#rl").innerHTML = A.slice(0, shown).map(card).join("") || '<div class="empty">Nenhum Riven.</div>';
    $("#rm").innerHTML = A.length > shown ? `<button class="more" id="rmb">Mostrar mais (${fmt(A.length - shown)})</button>` : "";
    const b = $("#rmb"); if (b) b.onclick = () => { shown += 40; draw(); };
  };
  $("#rf").onclick = e => { const t = e.target.closest(".pill"); if (!t) return; fam = t.dataset.f; $$("#rf .pill").forEach(x => x.classList.toggle("on", x === t)); shown = 40; draw(); };
  $("#rq").oninput = e => { q = e.target.value.trim().toLowerCase(); shown = 40; draw(); };
  $("#rs").onchange = e => { sort = e.target.value; draw(); };
  draw();
};

/* ================================================================ MERCADO (conta do warframe.market) */
window.onWfmToken = async tok => {
  try { await post("/api/wfm/token", { token: tok }); } catch (e) { alert(e.message); }
  if (location.hash === "#/mercado") route(); else location.hash = "#/mercado";
};
VIEWS.mercado = async el => {
  let st; try { st = await jf("/api/wfm/status"); } catch (e) { st = { logged: false, error: e.message }; }
  if (!st.logged) {
    el.innerHTML = `${head("Mercado", "Entre na sua conta do warframe.market para ver, anunciar e remover suas ordens")}
      <div class="mbox">${st.error ? `<div class="mkerr">${esc(st.error)}</div>` : ""}
      ${window.Android ? '<button class="more" id="mweb">Entrar pelo site do warframe.market</button><div class="mut" style="font-size:12px;margin:6px 0 14px">Abre o login oficial do site (funciona com qualquer forma de login). A senha nunca passa pelo app; só a sessão fica guardada neste aparelho.</div>' : ""}
      <details><summary class="pill">Entrar com e-mail e senha</summary><div class="mform"><input class="inp" id="me" type="email" placeholder="E-mail" autocomplete="off"><input class="inp" id="mp" type="password" placeholder="Senha" autocomplete="off"><button class="more" id="mlogin">Entrar</button></div></details>
      <details style="margin-top:8px"><summary class="pill">Colar token (JWT)</summary><div class="mform"><textarea class="inp" id="mt" rows="3" placeholder="Cole aqui o valor do cookie JWT"></textarea><button class="more" id="mtok">Usar token</button></div></details>
      <div class="mkerr" id="merr" hidden></div></div>`;
    const fail = e => { const b = $("#merr"); b.textContent = e.message; b.hidden = false; };
    const go = async (path, body) => { try { await post(path, body); route(); } catch (e) { fail(e); } };
    if ($("#mweb")) $("#mweb").onclick = () => window.Android.loginWfm();
    $("#mlogin").onclick = () => go("/api/wfm/login", { email: $("#me").value, password: $("#mp").value });
    $("#mtok").onclick = () => go("/api/wfm/token", { token: $("#mt").value });
    return;
  }
  const U = st.user, ST = { ingame: "Em jogo", online: "Online", invisible: "Invisível", offline: "Offline" };
  el.innerHTML = `<div class="mprof"><div class="mav">${U.avatar ? `<img src="${esc(U.avatar)}" alt="" onerror="this.remove()">` : ""}<span>${esc((U.name || "?")[0])}</span></div>
      <div class="mpi"><h1>${esc(U.name)}</h1><div class="mut">${esc(ST[U.status] || U.status || "")}${U.platform ? " · " + esc(String(U.platform).toUpperCase()) : ""}${U.locale ? " · " + esc(U.locale) : ""}${U.role ? " · " + esc(U.role) : ""}</div>
      ${U.reputation != null ? `<div class="mrep">+${fmt(U.reputation)} reputação</div>` : ""}</div></div>
    ${U.about ? `<div class="mabout">${br(U.about)}</div>` : ""}
    <div class="mstats" id="mstat"></div>
    <div class="tabs" id="mtabs"><span class="pill on" data-t="o">Ordens</span><span class="pill" data-t="m">Mensagens <b id="mbadge"></b></span></div>
    <div class="tools"><button class="pill" id="mnew">+ Novo anúncio</button><button class="pill" id="mref">Atualizar</button><button class="pill" id="mdiag">Diagnóstico</button><button class="pill" id="mout">Sair</button></div>
    <div id="mform"></div><div class="mkerr" id="merr" hidden></div><div id="mdbg"></div>
    <div class="list" id="mlist"><div class="empty">Carregando…</div></div><div class="list" id="mchats" hidden></div>`;
  const fail = e => { if (e.message.includes("expirada")) return route(); const b = $("#merr"); b.textContent = e.message; b.hidden = false; };
  let O = [];
  const load = async () => {
    try { O = await jf("/api/wfm/orders"); } catch (e) { $("#mlist").innerHTML = ""; return fail(e); }
    $("#merr").hidden = true;
    const row = o => `<div class="row mo ${o.visible ? "" : "hid"}" data-id="${o.id}">${ico(o.icon, o.name)}<span class="t"><span class="nm">${esc(o.name)}${o.rank != null && o.max ? ` <span class="chip gold">R${o.rank}/${o.max}</span>` : ""} <span class="chip ${o.type === "sell" ? "ok" : ""}">${o.type === "sell" ? "vende" : "compra"}</span></span>
      <small class="mut">${fmt(o.platinum)}p × ${o.quantity}${o.visible ? "" : " · oculto"}</small>
      <span class="mact"><input class="inp mp" type="number" min="1" value="${o.platinum}"><button class="pill" data-a="save">Salvar preço</button><button class="pill" data-a="vis">${o.visible ? "Ocultar" : "Mostrar"}</button><button class="pill danger" data-a="del">Remover</button></span></span></div>`;
    const sells = O.filter(o => o.type === "sell"), buys = O.filter(o => o.type !== "sell"), sum = a => a.reduce((t, o) => t + o.platinum * o.quantity, 0);
    $("#mstat").innerHTML = `<div><b>${fmt(O.length)}</b><span>ordens</span></div><div><b>${fmt(sells.length)}</b><span>vendendo · ${fmt(sum(sells))}p</span></div><div><b>${fmt(buys.length)}</b><span>comprando · ${fmt(sum(buys))}p</span></div>`;
    $("#mlist").innerHTML = (O.length ? "" : '<div class="empty">Nenhuma ordem ativa.</div>') +
      (sells.length ? `<div class="sec"><h2>Vendendo (${sells.length})</h2></div>${sells.map(row).join("")}` : "") + (buys.length ? `<div class="sec"><h2>Comprando (${buys.length})</h2></div>${buys.map(row).join("")}` : "");
  };
  $("#mlist").onclick = async e => {
    const b = e.target.closest("button[data-a]"); if (!b) return; const r = b.closest(".mo"), o = O.find(x => x.id === r.dataset.id); if (!o) return;
    try {
      if (b.dataset.a === "save") await post("/api/wfm/order/update", { id: o.id, platinum: +r.querySelector(".mp").value });
      else if (b.dataset.a === "vis") await post("/api/wfm/order/update", { id: o.id, visible: !o.visible });
      else if (b.dataset.a === "del") { if (!confirm(`Remover "${o.name}" do warframe.market?`)) return; await post("/api/wfm/order/delete", { id: o.id }); }
      await load();
    } catch (er) { fail(er); }
  };
  $("#mref").onclick = () => { load(); loadChats(); };
  let showT = "o";
  $("#mtabs").onclick = e => { const t = e.target.closest(".pill"); if (!t) return; showT = t.dataset.t; $$("#mtabs .pill").forEach(x => x.classList.toggle("on", x === t)); $("#mlist").hidden = showT !== "o"; $("#mchats").hidden = showT !== "m"; };
  const loadChats = async () => {
    try {
      const C = await jf("/api/wfm/chats"), un = C.reduce((a, c) => a + (c.unread || 0), 0); $("#mbadge").textContent = un ? "(" + un + ")" : "";
      $("#mchats").innerHTML = C.length ? C.map(c => `<div class="row mchat"><span class="mav sm">${c.avatar ? `<img src="${esc(c.avatar)}" alt="" onerror="this.remove()">` : ""}<span>${esc((c.name || "?")[0])}</span></span><span class="t"><span class="nm">${esc(c.name)}${c.unread ? ` <span class="chip gold">${c.unread}</span>` : ""}</span><small class="mut">${esc(c.text)}</small></span></div>`).join("") : '<div class="empty">Nenhuma conversa.</div>';
    } catch (e) { $("#mchats").innerHTML = `<div class="mkerr">${esc(e.message)}</div>`; }
  };
  $("#mdiag").onclick = async () => {
    $("#mdbg").innerHTML = '<div class="empty">Consultando…</div>';
    try { const r = await jf("/api/wfm/debug"); $("#mdbg").innerHTML = `<div class="mbox"><button class="pill" id="mcp">Copiar</button><pre class="dbg">${esc(r.text)}</pre></div>`; $("#mcp").onclick = () => navigator.clipboard.writeText(r.text).then(() => { $("#mcp").textContent = "Copiado ✓"; }); }
    catch (e) { $("#mdbg").innerHTML = `<div class="mkerr">${esc(e.message)}</div>`; }
  };
  $("#mout").onclick = async () => { await post("/api/wfm/logout").catch(() => {}); route(); };
  $("#mnew").onclick = () => {
    const f = $("#mform"); if (f.innerHTML) { f.innerHTML = ""; return; }
    let pick = null, tmr = 0;
    f.innerHTML = `<div class="mbox"><input class="inp" id="ns" placeholder="Buscar item (ex: Serration)…" autocomplete="off"><div id="nres"></div>
      <div id="nsel" class="mut" style="margin:8px 0"></div>
      <div class="mform nrow"><select class="inp" id="nt"><option value="sell">Vender</option><option value="buy">Comprar</option></select><input class="inp" id="np" type="number" min="1" placeholder="Preço (p)"><input class="inp" id="nq" type="number" min="1" value="1" placeholder="Qtd"><input class="inp" id="nr" type="number" min="0" placeholder="Rank" hidden></div>
      <button class="more" id="nok">Anunciar</button></div>`;
    $("#ns").oninput = ev => {
      clearTimeout(tmr); const v = ev.target.value.trim();
      tmr = setTimeout(async () => {
        if (v.length < 2) { $("#nres").innerHTML = ""; return; }
        try { const R = await jf("/api/wfm/items?q=" + encodeURIComponent(v)); $("#nres").innerHTML = R.map((x, i) => `<div class="row nres" data-i="${i}">${ico(x.icon, x.name)}<span class="t">${esc(x.name)}</span></div>`).join(""); $("#nres").onclick = c => { const r = c.target.closest(".nres"); if (!r) return; pick = R[+r.dataset.i]; $("#nres").innerHTML = ""; $("#nsel").textContent = "Selecionado: " + pick.name + (pick.max ? ` (rank máx ${pick.max})` : ""); $("#nr").hidden = !pick.max; if (pick.max) $("#nr").placeholder = "Rank (0 a " + pick.max + ")"; }; } catch (er) { fail(er); }
      }, 300);
    };
    $("#nok").onclick = async () => {
      if (!pick) return fail(new Error("Escolha um item na busca."));
      try { await post("/api/wfm/order/create", { itemId: pick.id, type: $("#nt").value, platinum: $("#np").value, quantity: $("#nq").value, rank: pick.max ? $("#nr").value : undefined }); f.innerHTML = ""; await load(); } catch (er) { fail(er); }
    };
  };
  load(); loadChats();
};

/* ---- notificação de novas mensagens do warframe.market (enquanto o app está aberto) */
(function () {
  async function tick() {
    if (!(window.Android && window.Android.notify)) return;
    try { const r = await jf("/api/wfm/poll"); if (r.notify) window.Android.notify("warframe.market", (r.unread + " mensagem(ns) não lida(s)") + (r.text ? " · " + r.text : "")); } catch (e) { }
  }
  setTimeout(tick, 10000); setInterval(tick, 60000);
})();
