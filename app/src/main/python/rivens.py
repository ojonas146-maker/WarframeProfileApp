"""Rivens do lastData: decodifica o UpgradeFingerprint e calcula valores e GRADE.
Mesma lógica do grading.js do seu outro projeto: esperado = base(categoria) × disposição(1.2 única) × mult(2P/2P1N/3P/3P1N) × (rank+1)/9;
a rolagem real varia 0.9x–1.1x, então desvio% = (0.9+0.2·f - 1)·100 (curses invertidas) e a letra vem de letterGrade()."""
import json, os, re
from pathlib import Path

BASE = Path(os.environ.get("WF_HOME") or Path(__file__).parent)
BV_F = BASE / "data" / "riven_base_values.json"
DISP = 1.2   # disposição única (igual ao baseData.js)
_bv = {}

# tag do jogo -> (nome em base_values.json, rótulo exibido)
T = {
    "WeaponDamageAmountMod": ("Damage", "Damage"), "WeaponMeleeDamageMod": ("Damage", "Melee Damage"),
    "WeaponFireIterationsMod": ("Multishot", "Multishot"), "WeaponCritChanceMod": ("Critical Chance", "Critical Chance"),
    "WeaponCritDamageMod": ("Critical Damage", "Critical Damage"), "WeaponStunChanceMod": ("Status Chance", "Status Chance"),
    "WeaponProcTimeMod": ("Status Duration", "Status Duration"), "WeaponFireRateMod": ("Fire Rate / Attack Speed", "Fire Rate"),
    "WeaponReloadSpeedMod": ("Reload Speed", "Reload Speed"), "WeaponClipMaxMod": ("Magazine Capacity", "Magazine Capacity"),
    "WeaponAmmoMaxMod": ("Ammo Maximum", "Ammo Maximum"), "WeaponRecoilReductionMod": ("Weapon Recoil", "Weapon Recoil"),
    "WeaponZoomFovMod": ("Zoom", "Zoom"), "WeaponProjectileSpeedMod": ("Projectile Speed", "Projectile Speed"),
    "WeaponPunctureDepthMod": ("Punch Through", "Punch Through"), "WeaponFreezeDamageMod": ("Cold Damage", "Cold"),
    "WeaponFireDamageMod": ("Heat Damage", "Heat"), "WeaponElectricityDamageMod": ("Electricity Damage", "Electricity"),
    "WeaponToxinDamageMod": ("Toxin Damage", "Toxin"), "WeaponImpactDamageMod": ("Impact Damage", "Impact"),
    "WeaponArmorPiercingDamageMod": ("Puncture Damage", "Puncture"), "WeaponSlashDamageMod": ("Slash Damage", "Slash"),
    "WeaponFactionDamageCorpus": ("Damage vs. Corpus", "Damage to Corpus"), "WeaponFactionDamageGrineer": ("Damage vs. Grineer", "Damage to Grineer"),
    "WeaponFactionDamageInfested": ("Damage vs. Infested", "Damage to Infested"),
    "WeaponMeleeFactionDamageCorpus": ("Damage vs. Corpus", "Damage to Corpus"), "WeaponMeleeFactionDamageGrineer": ("Damage vs. Grineer", "Damage to Grineer"),
    "WeaponMeleeFactionDamageInfested": ("Damage vs. Infested", "Damage to Infested"),
    "ComboDurationMod": ("Combo Duration", "Combo Duration"), "WeaponMeleeComboInitialBonusMod": ("Initial Combo", "Initial Combo"),
    "WeaponMeleeComboPointsOnHitMod": ("Additional Combo Count Chance", "Additional Combo Count Chance"),
    "WeaponMeleeComboEfficiencyMod": ("Heavy Attack Efficiency", "Heavy Attack Efficiency"),
    "WeaponMeleeFinisherDamageMod": ("Finisher Damage", "Finisher Damage"), "WeaponMeleeRangeIncMod": ("Range", "Range"),
    "SlideAttackCritChanceMod": ("Critical Chance for Slide Attack", "Critical Chance on Slide Attack"),
}
CATS = {"rifle": "Rifle", "pistol": "Pistol", "shotgun": "Shotgun", "melee": "Melee", "arch": "Archgun"}

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

FAMILY = (("LotusRifle", "rifle"), ("LotusPistol", "pistol"), ("LotusShotgun", "shotgun"), ("PlayerMeleeWeapon", "melee"),
          ("LotusArchgun", "arch"), ("LotusModularMelee", "melee"), ("LotusModularPistol", "pistol"))
FAM_LABEL = {"rifle": "Rifle", "pistol": "Pistola", "shotgun": "Shotgun", "melee": "Melee", "arch": "Arch-gun"}
POL = {"AP_ATTACK": "madurai", "AP_DEFENSE": "vazarin", "AP_TACTIC": "naramon", "AP_POWER": "zenurik", "AP_WARD": "unairu",
       "AP_UNIVERSAL": "universal"}


def name_of(buffs):
    order = sorted(buffs, key=lambda b: -b["Value"])
    p = [NAMES.get(b["Tag"], (b["Tag"][:4], b["Tag"][-3:])) for b in order]
    if len(p) == 2:
        return (p[0][0] + p[1][1]).capitalize()
    if len(p) >= 3:
        return p[0][0].capitalize() + "-" + p[1][0].lower() + p[2][1]
    return ""




def _load_bv():
    if not _bv:
        try:
            _bv.update(json.loads(BV_F.read_text(encoding="utf-8")))
        except Exception as e:
            print("riven_base_values:", e)
    return _bv


def letter(dev):
    for lim, g in ((9.5, "S"), (7.5, "+A"), (5.5, "A"), (3.5, "-A"), (1.5, "+B"), (-1.5, "B"), (-3.5, "-B"), (-5.5, "+C"), (-7.5, "C"), (-9.5, "-C")):
        if dev >= lim:
            return g
    return "F"


def _num(v, d=1):
    t = ("%.*f" % (d, round(abs(v) + 1e-9, d))).rstrip("0").rstrip(".")
    return t or "0"


def _show(v, unit, label, neg, inv):
    """formata o valor como no jogo: +99%, x1.47 (facções), +0.3 m ..."""
    if unit == "x":
        return "x" + _num(1 - v if neg else 1 + v, 2)
    sign = "-" if (neg != inv) else "+"
    suf = {"%": "%", "s": " s", "m": "" if "Punch" in label else " m", "flat": ""}.get(unit, "")
    return sign + _num(v) + suf


def decode(data, cat_items, icon_of):
    bv = _load_bv()
    S = bv.get("stats", {})
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
        cat = CATS.get(fam, "Rifle")
        compat = fp.get("compat", "")
        wname = (cat_items.get(compat) or {}).get("n") or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", compat.rsplit("/", 1)[-1]).replace("Player Wep", "").strip()
        buffs, curses = fp.get("buffs", []), fp.get("curses", [])
        nb, nc = len(buffs), len(curses)
        cfg = {(2, 0): "2P", (2, 1): "2P1N", (3, 0): "3P", (3, 1): "3P1N"}.get((nb, nc), "3P1N" if nb >= 3 else "2P")
        mults = bv.get("count_multipliers", {}).get(cfg, {"positive": 1, "negative": 0.75})
        lvl = int(fp.get("lvl") or 0)
        rk = (lvl + 1) / 9.0
        stats, devs = [], []
        for neg, arr in ((False, buffs), (True, curses)):
            for b in arr:
                f = max(0.0, min(1.0, b["Value"] / 2 ** 30))
                bname, label = T.get(b["Tag"], (None, b["Tag"]))
                ent = S.get(bname) if bname else None
                base = ent.get(cat) if ent else None
                if base is None:
                    stats.append({"label": label, "cur": "?", "max": "?", "neg": neg, "q": round(f * 100), "g": "", "dev": 0})
                    continue
                mult = abs((mults.get("negative") if neg else mults.get("positive")) or 0.75)
                full = base * DISP * mult * (0.9 + 0.2 * f)
                unit, inv = ent.get("unit", "%"), bname == "Weapon Recoil"
                if fam == "melee" and bname == "Fire Rate / Attack Speed":
                    label = "Attack Speed"
                dev = (0.2 * f - 0.1) * 100
                if neg and bname != "Weapon Recoil":
                    dev = -dev
                devs.append(dev)
                stats.append({"label": label, "cur": _show(full * rk, unit, label, neg, inv), "max": _show(full, unit, label, neg, inv),
                              "neg": neg, "q": round(f * 100), "g": letter(dev), "dev": round(dev, 1)})
        avg = sum(devs) / len(devs) if devs else 0
        qs = [s["q"] for s in stats if not s["neg"]]
        out.append({
            "id": (u.get("ItemId") or {}).get("$oid", ""), "weapon": wname, "name": (wname + " " + name_of(buffs)).strip(),
            "fam": fam, "famlabel": CATS.get(fam, fam), "rank": lvl, "mr": fp.get("lvlReq", 8), "rerolls": fp.get("rerolls", 0) or 0,
            "drain": 10 + lvl, "pol": POL.get(fp.get("pol"), fp.get("pol") or ""), "stats": stats, "grade": letter(avg), "gdev": round(avg, 1),
            "avg": round(sum(qs) / len(qs)) if qs else 0, "icon": icon_of(it), "cfg": cfg,
        })
    out.sort(key=lambda r: (-r["gdev"], r["name"]))
    return out
