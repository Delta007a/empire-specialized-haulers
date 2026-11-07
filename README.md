# Empire Specialized Haulers

Nine T1 haulers for **Amarr, Caldari and Minmatar**, with dedicated holds for ore, minerals and ice, or planetary cargo. Each ship has its own model, inventory and Ship Tree icons, T1 blueprint, and native Mastery profile inherited from its base hull.

**Current release: 0.4.2** · [Download installation ZIP](https://github.com/Delta007a/empire-specialized-haulers/releases/download/v0.4.2/EveJS-EmpireSpecializedHaulers-0.4.2.zip) · [Release notes](https://github.com/Delta007a/empire-specialized-haulers/releases/tag/v0.4.2) · [Changelog](CHANGELOG.md)

| Empire | Ore | Minerals and ice | Planetary |
| --- | --- | --- | --- |
| Amarr | Tithe | Reliquary | Steward |
| Caldari | Wolverine | Marten | Stoat |
| Minmatar | Bison | Muskox | Caravan |

## Compatibility

**EveJS 261028.1**, the Launcher's **Native** backend, and **EVE client build 3396210**.

Version 0.4.2 fixes headless GamePort login, including WC: a missing client catalog receipt no longer causes `LoginAuthFailed`. The EVE client still receives the custom ship catalog during login.

## Installation

1. Download [EveJS-EmpireSpecializedHaulers-0.4.2.zip](https://github.com/Delta007a/empire-specialized-haulers/releases/download/v0.4.2/EveJS-EmpireSpecializedHaulers-0.4.2.zip).
2. Open **Launcher → Mods → Add ZIP** and select the downloaded file.
3. Enable **Empire Specialized Haulers**.
4. Restart the **Game server** and start a fresh EVE client.

For manual installation, extract the installation ZIP into `mods/empire-specialized-haulers`, with `evejs-launcher.mod.json` at the top of that folder. Enable the mod in the Launcher, restart the Game server and start a fresh EVE client. The installation ZIP includes all models and icons and starts with `loader.js.disabled`.

## Update

**Launcher → Mods → Check mod updates → Update Empire Specialized Haulers → Restart Game server → start a fresh EVE client.**

The Launcher update feed uses the ZIP and `.update.json` file attached to the [latest release](https://github.com/Delta007a/empire-specialized-haulers/releases/latest).

## Market availability

The new ships and blueprints appear in the market catalog. **Automatic NPC sell orders and market stock seeding are not included in 0.4.2.** Availability for purchase depends on the server's market setup.

## Repository contents

The `main` branch contains the runtime code and all **137 visual resources** used by the mod:

- `art/native/` — all nine ship models and textures, including Wolverine under `ci2_w2/`.
- `art/icons/` — inventory, blueprint and Ship Tree icons.
- `fleet.json`, `catalog.js` and the client and login files — ship definitions and catalog integration.
- `evejs-launcher.mod.json` — Launcher metadata and update feed.
- `tools/` and `test/` — package builder and login checks.

The 0.4.2 installation ZIP was checked against the installed working mod: all runtime files and visual resources match. In the repository and an enabled installation the loader is named `loader.js`; the installation ZIP uses `loader.js.disabled` so it can be enabled through the Launcher.

For installation, use the named **EveJS-EmpireSpecializedHaulers-0.4.2.zip** release asset. GitHub's automatic **Source code (zip)** and **Source code (tar.gz)** downloads are repository snapshots; older tags do not include the visual resources.

## Build the installation ZIP

With Python 3, run from a checkout of `main`:

```powershell
python tools/build-local-package.py .
```

All required visual resources are included in the repository. The builder verifies their sizes and SHA-256 hashes against `visual-resources.json` and writes `dist/EveJS-EmpireSpecializedHaulers-0.4.2.zip`.

## Validation

The nine ships, icons and native Mastery profiles have been checked in EVE. The installed 0.4.2 package was confirmed working in-game by the user. The headless login fix passed checks against the supported native handshake with empty, unsuccessful and successful catalog responses.

The server log records `[EmpireHaulers] LOGIN_READY build=3396210 types=18` when the login hook loads. After EVE client login, `[EmpireHaulers] MASTERIES_READY ships=9 levels=5 source=native-stock` confirms Mastery loading. Catalog receipts are diagnostic and do not block native login.
