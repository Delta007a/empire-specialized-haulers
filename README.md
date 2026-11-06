# Empire Specialized Haulers

Version **0.4.0** adds nine T1 haulers for Amarr, Caldari and Minmatar to EveJS. The ships cover ore, mineral and planetary cargo. They have individual models, inventory and Ship Tree icons, native Mastery profiles inherited from their base hulls, and T1 blueprint definitions.

| Empire | Ore | Mineral | Planetary |
| --- | --- | --- | --- |
| Amarr | Tithe | Reliquary | Steward |
| Caldari | Wolverine | Marten | Stoat |
| Minmatar | Bison | Muskox | Caravan |

## Install locally

The package targets **EveJS 261028.1**, the Launcher's **Native** backend, and **EVE client build 3396210**. The visual assets are required at runtime. This repository carries the loader, client code, catalog, and resource checksums. Build the installable ZIP with a local copy of the verified visual assets for this revision. The script reads the source mod's `visual-resources.json`, which can reference separate local resource directories. The stock EVE installation alone cannot supply the custom models.

From the repository root, run Python 3 with the directory of the existing local mod package:

```powershell
python tools/build-local-package.py '<EveJS directory>/mods/empire-specialized-haulers'
```

The builder checks all 137 resources against the committed manifest and writes `dist/EmpireSpecializedHaulers-0.4.0-local.zip`. The ZIP bundles the verified local assets under relative paths and starts with the loader disabled. Keep this ZIP local because its art includes EVE-derived resources.

Import the ZIP in EveJS Launcher and enable **Empire Specialized Haulers** on the selected Native installation. If replacing an installation with the same mod ID, follow the Launcher's replacement flow with the server stopped. Disable Tayra Client Canary before enabling this package. Start the game server and log in with a fresh client process.

## Check the client

The server log records `[EmpireHaulers] LOGIN_READY build=3396210 types=18` when the login hook loads. After login, the client log records `[EmpireHaulers] MASTERIES_READY ships=9 levels=5 source=native-stock`. The current test runtime has rendered the ships in EVE. The Minmatar Ship Tree was also checked in the live client with Mastery V.
