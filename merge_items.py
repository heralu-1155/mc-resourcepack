"""Injects real held/3D vanilla item models (from mc-model-kit's own
java-vanilla-resourcepack output) into BetterModel's generated build.zip,
via a custom_model_data override on minecraft:paper, so these items show
their actual shape in hand/third-person/GUI/ground -- not just a flat icon.

Also injects FLAT_ICONS: a plain "item/generated" 2D icon (front-render
snapshot) for models that can't get the full 3D treatment (e.g.
concrete_cutter, whose spinning blade is a rotated bone, so mc-model-kit
never emits a java-vanilla-resourcepack for it at all).

Run this AFTER the server has (re)built plugins/BetterModel/build.zip
(i.e. after a server start or /bm reload), and BEFORE update_pack.ps1
uploads it to GitHub. Safe to re-run any time.

The custom_model_data numbers assigned here MUST match ModelHub's
config.yml ("custom-model-data:" per model) -- see MODEL_DATA/FLAT_ICONS.
"""
import json
import shutil
import zipfile
from pathlib import Path

KIT_ITEMS = Path(r"C:\Users\PC_User\Downloads\mc-model-kit-v3.0\items")
BUILD_ZIP = Path(r"C:\Users\PC_User\AppData\Roaming\FastServer\servers\93f24aeb\plugins\BetterModel\build.zip")
REPO_DIR = Path(__file__).resolve().parent

# Custom sound events injected into the pack (ModelHub's 携帯電話ゲーム).
# event id (code side: "modelhub.phone_ring") -> local .ogg under REPO_DIR/sounds/
# + its sounds.json entry.  The ogg lands at
# assets/minecraft/sounds/modelhub/<file>.ogg and is referenced as "modelhub/<file>".
SOUNDS = {
    "modelhub.phone_ring": {
        "file": "phone_ring.ogg",
        "json": {"category": "players",
                 "sounds": [{"name": "modelhub/phone_ring", "volume": 1.0,
                             "attenuation_distance": 20}]},
    },
    "modelhub.phone_scream": {
        "file": "phone_scream.ogg",
        "json": {"category": "master",
                 "sounds": [{"name": "modelhub/phone_scream", "volume": 1.0,
                             "attenuation_distance": 32}]},
    },
}

# model name -> custom_model_data value used on minecraft:paper, for
# models with a full 3D java-vanilla-resourcepack export.
# Keep in sync with modelhub-plugin/src/main/resources/config.yml.
MODEL_DATA = {
    "key_brass_house": 1,
    "key_rusty_basement": 2,
    "key_silver_room": 3,
    "key_black_prison": 4,
    "key_bronze_mansion": 5,
    "key_copper_maintenance": 6,
    "key_steel_master": 7,
    "key_gold_ceremonial": 8,
    "key_gray_industrial": 9,
    "key_brass_attic": 10,
    "concrete_cutter": 11,
    "concrete_cutter_on": 12,
    "battery": 13,
    "teddy_bear": 14,
    "telephone": 15,
}

# model name -> custom_model_data value, for models given a flat 2D icon
# instead (item/generated + one texture layer) because they can't export a
# real 3D vanilla model. Currently unused -- every model has a real 3D
# vanilla export -- kept in case a future model needs the fallback.
FLAT_ICONS = {}


def build_paper_override():
    entries = []
    for name, cmd in sorted(MODEL_DATA.items(), key=lambda kv: kv[1]):
        entries.append({
            "threshold": cmd,
            "model": {"type": "model", "model": f"{name}:item/{name}"},
        })
    for name, cmd in sorted(FLAT_ICONS.items(), key=lambda kv: kv[1]):
        entries.append({
            "threshold": cmd,
            "model": {"type": "model", "model": f"{name}:item/{name}_icon"},
        })
    entries.sort(key=lambda e: e["threshold"])
    return {
        "model": {
            "type": "range_dispatch",
            "property": "custom_model_data",
            "fallback": {"type": "model", "model": "minecraft:item/paper"},
            "entries": entries,
        }
    }


def our_files():
    """Every path this script owns, so a rebuild can drop stale copies of
    them (e.g. an old paper.json) before writing fresh ones -- zipfile
    can't overwrite an entry in place, only append, so a real update needs
    a full rewrite rather than an append-only merge."""
    paths = {"assets/minecraft/items/paper.json", "assets/minecraft/sounds.json"}
    for meta in SOUNDS.values():
        paths.add(f"assets/minecraft/sounds/modelhub/{meta['file']}")
    for name in MODEL_DATA:
        paths.add(f"assets/{name}/models/item/{name}.json")
        paths.add(f"assets/{name}/textures/item/{name}.png")
    for name in FLAT_ICONS:
        paths.add(f"assets/{name}/models/item/{name}_icon.json")
        paths.add(f"assets/{name}/textures/item/{name}_icon.png")
    return paths


def main():
    if not BUILD_ZIP.exists():
        raise SystemExit(f"build.zip not found at {BUILD_ZIP} -- start the server (or /bm reload) first.")

    ours = our_files()
    tmp = BUILD_ZIP.with_suffix(".merging.zip")

    for meta in SOUNDS.values():
        ogg = REPO_DIR / "sounds" / meta["file"]
        if not ogg.exists():
            raise SystemExit(f"sound file missing: {ogg}")

    with zipfile.ZipFile(BUILD_ZIP, "r") as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        existing_sounds = {}
        for item in src.infolist():
            if item.filename == "assets/minecraft/sounds.json":
                try:
                    existing_sounds = json.loads(src.read(item.filename).decode("utf-8"))
                except Exception:
                    existing_sounds = {}
            if item.filename in ours:
                continue  # drop any stale copy; rewritten fresh below
            out.writestr(item, src.read(item.filename))

        added = []
        payload = json.dumps(build_paper_override(), ensure_ascii=False, indent=2)
        out.writestr("assets/minecraft/items/paper.json", payload)
        added.append("assets/minecraft/items/paper.json")

        # custom sounds: merge our events into whatever sounds.json was there
        merged = dict(existing_sounds)
        for event, meta in SOUNDS.items():
            merged[event] = meta["json"]
            out.write(REPO_DIR / "sounds" / meta["file"],
                      f"assets/minecraft/sounds/modelhub/{meta['file']}")
        out.writestr("assets/minecraft/sounds.json",
                     json.dumps(merged, ensure_ascii=False, indent=2))
        added.append(f"{len(SOUNDS)} sound(s)")

        for name in MODEL_DATA:
            src_root = KIT_ITEMS / name / "out" / "java-vanilla-resourcepack" / "assets" / name
            model_src = src_root / "models" / "item" / f"{name}.json"
            tex_src = src_root / "textures" / "item" / f"{name}.png"
            if not model_src.exists() or not tex_src.exists():
                print(f"[skip] {name}: vanilla-resourcepack output not found, run its build first")
                continue
            out.write(model_src, f"assets/{name}/models/item/{name}.json")
            out.write(tex_src, f"assets/{name}/textures/item/{name}.png")
            added.append(name)

        for name in FLAT_ICONS:
            flat_root = KIT_ITEMS / name / "out" / "flat_icon" / "assets" / name
            model_src = flat_root / "models" / "item" / f"{name}_icon.json"
            tex_src = flat_root / "textures" / "item" / f"{name}_icon.png"
            if not model_src.exists() or not tex_src.exists():
                print(f"[skip] {name}: flat_icon output not found (out/flat_icon/... missing)")
                continue
            out.write(model_src, f"assets/{name}/models/item/{name}_icon.json")
            out.write(tex_src, f"assets/{name}/textures/item/{name}_icon.png")
            added.append(name)

    tmp.replace(BUILD_ZIP)
    print(f"Rebuilt {BUILD_ZIP} with {len(added)} merged item(s): {', '.join(added)}")


if __name__ == "__main__":
    main()
