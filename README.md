# Empire Specialized Haulers

Twelve T1 specialized haulers across **Amarr, Caldari, Gallente and Minmatar**, with dedicated holds for ore, minerals and ice, planetary cargo, or harvested gases. Each custom ship has its own model, inventory and Ship Tree icons, T1 blueprint, and native Mastery profile inherited from its base hull.

**Version 0.5.2** · [Changelog](CHANGELOG.md) · [Releases](https://github.com/Delta007a/empire-specialized-haulers/releases)

**New in 0.5.2:** Tithe now has dedicated upper and lower mounting seats for its single turret hardpoint, with native locators aligned to the seats. A stock Dual Light Pulse Laser was used to verify the fit. Both seats belong to one fitted weapon. Existing hull detailing, textures, icons, stats and engine effects are preserved.

**Hull introduced in 0.5.1:** Tithe has a new original Amarr hull with ivory armour and stepped gold inlays inspired by Sigil, five repositioned native engine exhausts, and refreshed inventory, blueprint and Ship Tree icons. Its cockpit has aligned glazing and a fitted brow, and a closed pressure hull fills the space beneath its upper armour. Local panel details enrich the large empty underbody surfaces while retaining the original black gunmetal; corrected shading normals smooth the transition beneath the armour. Its length remains approximately 696 client units, matching the previous Tithe. Ship stats and IDs are unchanged.

**Also new since 0.4.4:** three gas transport ships — **Anemos** (Gallente), **Vesper** (Amarr), and **Sable** (Caldari). Their dedicated Gas Hold carries **30,000 m³**, increasing to **45,000 m³** at racial Hauler V. They have 500 m³ of regular cargo and a 5% maximum-velocity bonus per racial Hauler level. Their stock hull coatings are retained and the new equipment uses matching materials.

| Empire | Ore | Minerals and ice | Planetary | Gas |
| --- | --- | --- | --- | --- |
| Amarr | Tithe | Reliquary | Steward | Vesper |
| Caldari | Wolverine | Marten | Stoat | Sable |
| Gallente | — | — | — | Anemos |
| Minmatar | Bison | Muskox | Caravan | Hoarder (stock) |

Hoarder is the existing Minmatar gas hauler and is not modified or counted among the twelve custom ships. The three new gas ships retain their base hull's tank, movement and fitting resources, with the established faction slot layout used by this mod.

## Compatibility

**EveJS 261028.1**, the Launcher's **Native** backend, and **EVE client build 3396210**.

Includes the headless GamePort login fix from 0.4.2, including WC support. The EVE client receives the custom ship catalog during login. **Python 3.11 or newer** is required to run the optional market setup scripts.

## Installation

1. Download [EveJS-EmpireSpecializedHaulers-0.5.2.zip](https://github.com/Delta007a/empire-specialized-haulers/releases/download/v0.5.2/EveJS-EmpireSpecializedHaulers-0.5.2.zip).
2. Open **Launcher → Mods → Add ZIP** and select the downloaded file.
3. Enable **Empire Specialized Haulers**.
4. Restart the **Game server** and start a fresh EVE client.

For manual installation, extract the installation ZIP into `mods/empire-specialized-haulers`, with `evejs-launcher.mod.json` at the top of that folder. Enable the mod in the Launcher, restart the Game server and start a fresh EVE client. The installation ZIP includes all models and icons and starts with `loader.js.disabled`.

## Update

**Launcher → Mods → Check mod updates → Update Empire Specialized Haulers → Restart Game server → start a fresh EVE client.**

The Launcher update feed uses the ZIP and `.update.json` file attached to the [latest release](https://github.com/Delta007a/empire-specialized-haulers/releases/latest).

## Add market stock

The new ships and blueprints appear in the market catalog when the mod is enabled. To add NPC sell offers to an existing market database:

1. **Stop the Market service.**
2. Open **`mods/empire-specialized-haulers`**.
3. Double-click **one** setup file:

   | File | Market supply |
   | --- | --- |
   | `Market-Normal.cmd` | Ships and blueprints at the selling locations of their original faction hulls, including BUY orders where the corresponding original has them. Jita-only markets stay Jita-only; other hubs and galaxy-wide distributions follow the existing sellers. |
   | `Market-Hardcore.cmd` | Blueprints only, where the original hull's BPO is already sold at an NPC station of the ship's faction. |

4. Wait for **`Finished successfully`**, then **start Market again**.

The scripts are included in the installation ZIP. No database path entry is needed: they read this server's Market configuration. They work directly with a ready SQLite market file, independently of its generator. SELL and BUY prices follow Miasmos, Kryos and Epithal by specialization, using the corresponding order side. The gas ships use Epithal prices, while placement follows Epithal, Sigil or Badger respectively. In hardcore mode, Anemos BPOs follow existing Epithal BPO sellers at Gallente NPC stations. Repeat runs preserve existing prices and purchased stock; player orders and other items are preserved.

Market setup requires **Python 3.11 or newer**. Installing or enabling the mod does not seed stock automatically. After regenerating your market file, run the chosen setup file again.

[Step-by-step English instructions](MARKET-SETUP.md) · [Инструкция на русском](MARKET-SETUP-RU.txt) · [Detailed guide](tools/MARKET-SEED.md)

## Repository contents

The `main` branch contains the runtime code and all **185 visual resources** used by the mod:

- `art/native/` — all twelve ship models and textures, including Wolverine under `ci2_w2/`.
- `art/icons/` — inventory, blueprint and Ship Tree icons.
- `fleet.json`, `catalog.js` and the client and login files — ship definitions and catalog integration.
- `evejs-launcher.mod.json` — Launcher metadata and update feed.
- `Market-Normal.cmd` and `Market-Hardcore.cmd` — market setup launchers.
- `MARKET-SETUP.md` and `MARKET-SETUP-RU.txt` — English and Russian quick-start instructions.
- `tools/` and `test/` — market utility, NPC station reference, package builder and validation checks.

The installation ZIP includes all runtime files, visual resources, market tools and guides. In the repository and an enabled installation the loader is named `loader.js`; the installation ZIP uses `loader.js.disabled` so it can be enabled through the Launcher.

For Launcher installation, use the named **EveJS-EmpireSpecializedHaulers-0.5.2.zip** release asset. GitHub's automatic **Source code (zip)** and **Source code (tar.gz)** downloads are repository snapshots that also include development files.

## Build the installation ZIP

With Python 3, run from a checkout of `main`:

```powershell
python tools/build-local-package.py .
```

All required visual resources are included in the repository. The builder verifies their sizes and SHA-256 hashes against `visual-resources.json` and writes `dist/EveJS-EmpireSpecializedHaulers-0.5.2.zip` with the market scripts, guides and changelog.

## Validation

The original nine ships, icons and native Mastery profiles have been checked in EVE. Tithe’s replacement hull in 0.5.1 has passed native GR2/DDS/BLACK readback, seven-LOD checks, and clearance checks for all five exhaust outlets. It retains the native animated heat shader and stock Amarr flight/warp booster definitions. The user confirmed working engine animation in EVE. The latest cockpit, closed-hull, local underbody detailing and shading refinements have been reviewed through native-file studio renders and still need an in-game visual check. The three gas ships have passed native-format readback, client API and server integration checks; live in-game visual and cargo testing remains to be completed. The installed 0.4.2 package was confirmed working in-game by the user. The headless login fix passed checks against the supported native handshake with empty, unsuccessful and successful catalog responses.

Tithe’s turret seats in 0.5.2 passed native-locator readback and stock-weapon geometry clearance checks. Live firing and tracking animation still need an in-game check.

The market utility passed 29 offline tests, including both Windows launchers in a relocated server folder, Jita-only placement, both order sides, Epithal gas pricing, and actual Gallente NPC ownership for hardcore blueprint placement. The utility does not start or stop running services.

The server log records `[EmpireHaulers] LOGIN_READY build=3396210 types=24` when the login hook loads. After EVE client login, `[EmpireHaulers] MASTERIES_READY ships=12 levels=5 source=native-stock` confirms Mastery loading. Catalog receipts are diagnostic and do not block native login.
