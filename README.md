# Empire Specialized Haulers

Nine T1 haulers for **Amarr, Caldari and Minmatar**, with dedicated holds for ore, minerals and ice, or planetary cargo. Each ship has its own model, inventory and Ship Tree icons, T1 blueprint, and native Mastery profile inherited from its base hull.

**Current release: 0.4.4** · [Download installation ZIP](https://github.com/Delta007a/empire-specialized-haulers/releases/download/v0.4.4/EveJS-EmpireSpecializedHaulers-0.4.4.zip) · [Release notes](https://github.com/Delta007a/empire-specialized-haulers/releases/tag/v0.4.4) · [Changelog](CHANGELOG.md)

**New in 0.4.4:** market setup now mirrors both **SELL and BUY** orders when the corresponding original has them. If you used the 0.4.3 scripts, update and run `Market-Normal.cmd` again to add the missing BUY orders while preserving existing SELL stock. Both launchers and English/Russian instructions are included.

| Empire | Ore | Minerals and ice | Planetary |
| --- | --- | --- | --- |
| Amarr | Tithe | Reliquary | Steward |
| Caldari | Wolverine | Marten | Stoat |
| Minmatar | Bison | Muskox | Caravan |

## Compatibility

**EveJS 261028.1**, the Launcher's **Native** backend, and **EVE client build 3396210**.

Includes the headless GamePort login fix from 0.4.2, including WC support. The EVE client receives the custom ship catalog during login. **Python 3.11 or newer** is required to run the optional market setup scripts.

## Installation

1. Download [EveJS-EmpireSpecializedHaulers-0.4.4.zip](https://github.com/Delta007a/empire-specialized-haulers/releases/download/v0.4.4/EveJS-EmpireSpecializedHaulers-0.4.4.zip).
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

The scripts are included in **0.4.4**. No database path entry is needed: they read this server's Market configuration. They work directly with a ready SQLite market file, independently of its generator. SELL and BUY prices follow Miasmos, Kryos and Epithal by specialization, using the corresponding order side. Repeat runs preserve existing prices and purchased stock; player orders and other items are preserved.

Market setup requires **Python 3.11 or newer**. Installing or enabling the mod does not seed stock automatically. After regenerating your market file, run the chosen setup file again.

[Step-by-step English instructions](MARKET-SETUP.md) · [Инструкция на русском](MARKET-SETUP-RU.txt) · [Detailed guide](tools/MARKET-SEED.md)

## Repository contents

The `main` branch contains the runtime code and all **137 visual resources** used by the mod:

- `art/native/` — all nine ship models and textures, including Wolverine under `ci2_w2/`.
- `art/icons/` — inventory, blueprint and Ship Tree icons.
- `fleet.json`, `catalog.js` and the client and login files — ship definitions and catalog integration.
- `evejs-launcher.mod.json` — Launcher metadata and update feed.
- `Market-Normal.cmd` and `Market-Hardcore.cmd` — market setup launchers.
- `MARKET-SETUP.md` and `MARKET-SETUP-RU.txt` — English and Russian quick-start instructions.
- `tools/` and `test/` — market utility, NPC station reference, package builder and validation checks.

The installation ZIP includes all runtime files, visual resources, market tools and guides. In the repository and an enabled installation the loader is named `loader.js`; the installation ZIP uses `loader.js.disabled` so it can be enabled through the Launcher.

For Launcher installation, use the named **EveJS-EmpireSpecializedHaulers-0.4.4.zip** release asset. GitHub's automatic **Source code (zip)** and **Source code (tar.gz)** downloads are repository snapshots that also include development files.

## Build the installation ZIP

With Python 3, run from a checkout of `main`:

```powershell
python tools/build-local-package.py .
```

All required visual resources are included in the repository. The builder verifies their sizes and SHA-256 hashes against `visual-resources.json` and writes `dist/EveJS-EmpireSpecializedHaulers-0.4.4.zip` with the market scripts, guides and changelog.

## Validation

The nine ships, icons and native Mastery profiles have been checked in EVE. The installed 0.4.2 package was confirmed working in-game by the user. The headless login fix passed checks against the supported native handshake with empty, unsuccessful and successful catalog responses.

The market utility passed 27 tests, including both Windows launchers in a relocated server folder, and application to a temporary copy of the configured market file. A separate 3,000-station check produced the expected 54,000 SELL and 27,000 BUY proposals. These were offline checks; the utility does not start or stop running services.

The server log records `[EmpireHaulers] LOGIN_READY build=3396210 types=18` when the login hook loads. After EVE client login, `[EmpireHaulers] MASTERIES_READY ships=9 levels=5 source=native-stock` confirms Mastery loading. Catalog receipts are diagnostic and do not block native login.
