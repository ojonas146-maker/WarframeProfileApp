"""Rivens do lastData: decodifica o UpgradeFingerprint (stats, rolagem, rank, rerolls) e calcula os valores.
Fórmula (conferida com prints de Amprex/Acceltra/Afentis):  valor = base × disposição × mult(buffs/curses) × (0.9 + 0.2·f) × (rank+1)/9
onde f = Value / 2^30. Tabelas de armas que não são rifle são aproximadas."""
import json, os, re, threading, time, urllib.request
from pathlib import Path

BASE = Path(os.environ.get("WF_HOME") or Path(__file__).parent)
DISP_F = BASE / "data" / "riven_disp.json"
DEFAULT_DISP = 1.2

# tag: (rótulo, unidade, {família: base}, inverte_sinal)
def _b(rifle=None, pistol=None, shotgun=None, melee=None, arch=None):
    d = {"rifle": rifle, "pistol": pistol, "shotgun": shotgun, "melee": melee, "arch": arch if arch is not None else rifle}
    return {k: v for k, v in d.items() if v is not None}

_ELEM = _b(90, 90, 90, 90, 90)
_IPS = _b(119.7, 119.7, 119.7, 119.7, 119.7)
_FAC = _b(55, 55, 55, 55, 55)
TAGS = {
    "WeaponDamageAmountMod": ("Damage", "%", _b(165, 220, 90, None, 99)),
    "WeaponMeleeDamageMod": ("Melee Damage", "%", _b(melee=164.7)),
    "WeaponFireIterationsMod": ("Multishot", "%", _b(90, 120, 119, None, 90)),
    "WeaponCritChanceMod": ("Critical Chance", "%", _b(150, 150, 90, 150, 150)),
    "WeaponCritDamageMod": ("Critical Damage", "%", _b(120, 90, 90, 90, 120)),
    "WeaponStunChanceMod": ("Status Chance", "%", _b(90, 90, 90, 90, 90)),
    "WeaponProcTimeMod": ("Status Duration", "%", _b(99, 99, 99, 99, 99)),
    "WeaponFireRateMod": ("Fire Rate", "%", _b(60, 60, 90, 55, 60)),
    "WeaponReloadSpeedMod": ("Reload Speed", "%", _b(50, 50, 50, None, 50)),
    "WeaponClipMaxMod": ("Magazine Capacity", "%", _b(50, 60, 90, None, 50)),
    "WeaponAmmoMaxMod": ("Ammo Maximum", "%", _b(49.5, 90, 90, None, 49.5)),
    "WeaponRecoilReductionMod": ("Weapon Recoil", "%", _b(90, 90, 90, None, 90), True),
    "WeaponZoomFovMod": ("Zoom", "%", _b(80, 80, 80, None, 80)),
    "WeaponProjectileSpeedMod": ("Projectile Speed", "%", _b(90, 90, 90, None, 90)),
    "WeaponPunctureDepthMod": ("Punch Through", "", _b(2.7, 2.7, 2.7, None, 2.7)),
    "WeaponFreezeDamageMod": ("Cold", "%", _ELEM), "WeaponFireDamageMod": ("Heat", "%", _ELEM),
    "WeaponElectricityDamageMod": ("Electricity", "%", _ELEM), "WeaponToxinDamageMod": ("Toxin", "%", _ELEM),
    "WeaponImpactDamageMod": ("Impact", "%", _IPS), "WeaponArmorPiercingDamageMod": ("Puncture", "%", _IPS),
    "WeaponSlashDamageMod": ("Slash", "%", _IPS),
    "WeaponFactionDamageCorpus": ("Damage to Corpus", "%", _FAC), "WeaponFactionDamageGrineer": ("Damage to Grineer", "%", _FAC),
    "WeaponFactionDamageInfested": ("Damage to Infested", "%", _FAC),
    "WeaponMeleeFactionDamageCorpus": ("Damage to Corpus", "%", _FAC), "WeaponMeleeFactionDamageGrineer": ("Damage to Grineer", "%", _FAC),
    "WeaponMeleeFactionDamageInfested": ("Damage to Infested", "%", _FAC),
    "ComboDurationMod": ("Combo Duration", " s", _b(melee=8.1)),
    "WeaponMeleeComboInitialBonusMod": ("Initial Combo", "", _b(melee=24.5)),
    "WeaponMeleeComboPointsOnHitMod": ("Additional Combo Count Chance", "%", _b(melee=58.8)),
    "WeaponMeleeComboEfficiencyMod": ("Heavy Attack Efficiency", "%", _b(melee=73.5)),
    "WeaponMeleeFinisherDamageMod": ("Finisher Damage", "%", _b(melee=119.7)),
    "WeaponMeleeRangeIncMod": ("Range", " m", _b(melee=1.94)),
    "SlideAttackCritChanceMod": ("Critical Chance on Slide Attack", "%", _b(melee=120)),
}
# prefixo / sufixo do nome do Riven (ordem do nome = rolagens em ordem decrescente)
NAMES = {
    "WeaponDamageAmountMod": ("Visi", "ata"), "WeaponMeleeDamageMod": ("Visi", "ata"), "WeaponFireIterationsMod": ("Sati", "can"),
    "WeaponCritChanceMod": ("Crita", "cron"), "WeaponCritDamageMod": ("Acri", "tis"), "WeaponStunChanceMod": ("Hexa", "dex"),
    "WeaponProcTimeMod": ("Deci", "des"), "WeaponFireRateMod": ("Croni", "dra"), "WeaponReloadSpeedMod": ("Feva", "tak"),
    "WeaponClipMaxMod": ("Arma", "tin"), "WeaponAmmoMaxMod": ("Ampi", "bin"), "WeaponRecoilReductionMod": ("Zeti", "mag"),
    "WeaponZoomFovMod": ("Hera", "lis"), "WeaponProjectileSpeedMod": ("Conci", "nak"), "WeaponPunctureDepthMod": ("Lexi", "nok"),
    "WeaponFreezeDamageMod": ("Geli", "do"), "WeaponFireDamageMod": ("Igni", "pha"), "WeaponElectricityDamageMod": ("Vexi", "tio"),
    "WeaponToxinDamageMod": ("Toxi", "tox"), "WeaponImpactDamageMod": ("Magna", "ton"), "WeaponArmorPiercingDamageMod": ("Insi", "cak"),
    "WeaponSlashDamageMod": ("Sci", "sus"), "WeaponFactionDamageCorpus": ("Manti", "tron"), "WeaponFactionDamageGrineer": ("Argi", "con"),
    "WeaponFactionDamageInfested": ("Pura", "ada"), "WeaponMeleeFactionDamageCorpus": ("Manti", "tron"),
    "WeaponMeleeFactionDamageGrineer": ("Argi", "con"), "WeaponMeleeFactionDamageInfested": ("Pura", "ada"),
    "ComboDurationMod": ("Tempi", "nem"), "WeaponMeleeComboInitialBonusMod": ("Laci", "nus"),
    "WeaponMeleeComboPointsOnHitMod": ("Macto", "tia"), "WeaponMeleeComboEfficiencyMod": ("Para", "um"),
    "WeaponMeleeFinisherDamageMod": ("Exi", "cta"), "WeaponMeleeRangeIncMod": ("Locti", "tor"), "SlideAttackCritChanceMod": ("Pleci", "nent"),
}
MULT = {(2, 0): (0.99, 0), (2, 1): (1.2375, 0.495), (3, 0): (0.75, 0), (3, 1): (0.9375, 0.75)}
FAMILY = (("LotusRifle", "rifle"), ("LotusPistol", "pistol"), ("LotusShotgun", "shotgun"), ("PlayerMeleeWeapon", "melee"),
          ("LotusArchgun", "arch"), ("LotusModularMelee", "melee"), ("LotusModularPistol", "pistol"))
FAM_LABEL = {"rifle": "Rifle", "pistol": "Pistola", "shotgun": "Shotgun", "melee": "Melee", "arch": "Arch-gun"}
POL = {"AP_ATTACK": "madurai", "AP_DEFENSE": "vazarin", "AP_TACTIC": "naramon", "AP_POWER": "zenurik", "AP_WARD": "unairu",
       "AP_UNIVERSAL": "universal"}

_disp = {"data": None, "ts": 0, "busy": False}


def _load_disp():
    if _disp["data"] is None:
        try:
            _disp["data"] = json.loads(DISP_F.read_text(encoding="utf-8"))
        except Exception:
            _disp["data"] = {}
    return _disp["data"]


def refresh_disp():
    """Baixa as disposições dos Rivens do warframe.market (público, sem login). Roda em segundo plano, 1x por semana."""
    d = _load_disp()
    if _disp["busy"] or (d and time.time() - d.get("_ts", 0) < 7 * 86400):
        return
    _disp["busy"] = True

    def run():
        try:
            req = urllib.request.Request("https://api.warframe.market/v2/riven/weapons",
                                         headers={"User-Agent": "Mozilla/5.0 WarframeProfileApp", "Accept": "application/json", "Platform": "pc"})
            j = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
            out = {"_ts": time.time()}
            for w in j.get("data", []):
                if w.get("gameRef") and w.get("disposition") is not None:
                    out[w["gameRef"]] = w["disposition"]
            if len(out) > 5:
                DISP_F.parent.mkdir(parents=True, exist_ok=True)
                DISP_F.write_text(json.dumps(out), encoding="utf-8")
                _disp["data"] = out
        except Exception as e:
            print("riven disposições:", e)
        finally:
            _disp["busy"] = False
    threading.Thread(target=run, daemon=True).start()


def _disp_of(compat):
    v = _load_disp().get(compat)
    if v is None:
        return DEFAULT_DISP, False
    v = float(v)
    if v >= 2:  # veio como nº de pontinhos (1..5)
        v = {1: 0.5, 2: 0.8, 3: 1.0, 4: 1.2, 5: 1.4}.get(int(v), DEFAULT_DISP)
    return v, True


def _fmt(v, unit):
    s = ("%.1f" % abs(v)).rstrip("0").rstrip(".") if abs(v) < 10 else ("%.1f" % abs(v))
    if s.endswith(".0"):
        s = s[:-2]
    return s + unit


def name_of(buffs):
    order = sorted(buffs, key=lambda b: -b["Value"])
    p = [NAMES.get(b["Tag"], (b["Tag"][:4], b["Tag"][-3:])) for b in order]
    if len(p) == 2:
        return (p[0][0] + p[1][1]).capitalize()
    if len(p) >= 3:
        return p[0][0].capitalize() + "-" + p[1][0].lower() + p[2][1]
    return ""


def decode(data, cat_items, icon_of):
    refresh_disp()
    out = []
    for u in data.get("Upgrades", []):
        it = u.get("ItemType", "")
        if "/Randomized/" not in it:
            continue
        fp = u.get("UpgradeFingerprint")
        try:
            fp = json.loads(fp) if isinstance(fp, str) else fp
        except Exception:
            continue
        if not fp or "buffs" not in fp:
            continue
        fam = next((f for k, f in FAMILY if k in it), "rifle")
        compat = fp.get("compat", "")
        wname = (cat_items.get(compat) or {}).get("n") or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", compat.rsplit("/", 1)[-1]).replace("Player Wep", "").strip()
        buffs, curses = fp.get("buffs", []), fp.get("curses", [])
        mult = MULT.get((len(buffs), len(curses)), (1.0, 1.0))
        disp, real = _disp_of(compat)
        lvl = int(fp.get("lvl") or 0)
        rk = (lvl + 1) / 9.0
        stats = []
        for neg, arr in ((False, buffs), (True, curses)):
            for b in arr:
                info = TAGS.get(b["Tag"])
                f = max(0.0, min(1.0, b["Value"] / 2 ** 30))
                if not info:
                    stats.append({"label": b["Tag"], "cur": "?", "max": "?", "neg": neg, "q": round(f * 100)})
                    continue
                label, unit, bases = info[0], info[1], info[2]
                inv = len(info) > 3 and info[3]
                base = bases.get(fam) or bases.get("rifle") or next(iter(bases.values()))
                full = base * disp * (mult[1] if neg else mult[0]) * (0.9 + 0.2 * f)
                sign = -1 if (neg != inv) else 1
                if fam == "melee" and b["Tag"] == "WeaponFireRateMod":
                    label = "Attack Speed"
                stats.append({"label": label, "cur": ("+" if sign > 0 else "-") + _fmt(full * rk, unit),
                              "max": ("+" if sign > 0 else "-") + _fmt(full, unit), "neg": neg, "q": round(f * 100)})
        qs = [s["q"] for s in stats if not s["neg"]]
        out.append({
            "id": (u.get("ItemId") or {}).get("$oid", ""), "weapon": wname, "name": (wname + " " + name_of(buffs)).strip(),
            "fam": fam, "famlabel": FAM_LABEL.get(fam, fam), "rank": lvl, "mr": fp.get("lvlReq", 8), "rerolls": fp.get("rerolls", 0) or 0,
            "drain": 10 + lvl, "pol": POL.get(fp.get("pol"), fp.get("pol") or ""), "stats": stats, "disp": disp, "disp_real": real,
            "approx": fam != "rifle", "avg": round(sum(qs) / len(qs)) if qs else 0, "icon": icon_of(it),
        })
    out.sort(key=lambda r: (-r["rerolls"], r["name"]))
    return out
