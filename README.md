# Empire Specialized Haulers

Empire Specialized Haulers adds nine T1 haulers for Amarr, Caldari and Minmatar to EveJS. Each ship has its own model, inventory and Ship Tree icons, T1 blueprint, and native Mastery profile inherited from its base hull.

| Empire | Ore | Mineral | Planetary |
| --- | --- | --- | --- |
| Amarr | Tithe | Reliquary | Steward |
| Caldari | Wolverine | Marten | Stoat |
| Minmatar | Bison | Muskox | Caravan |

## Install and update

The package targets **EveJS 261028.1**, the Launcher's **Native** backend, and **EVE client build 3396210**.

Use the `EveJS-EmpireSpecializedHaulers-0.4.1.zip` installation package. Import it through **Launcher → Mods → Add ZIP**, or extract its contents into `mods/empire-specialized-haulers` with `evejs-launcher.mod.json` at the top of that folder. Enable the mod, restart the Game server and start a fresh EVE client. The ZIP starts with `loader.js.disabled`.

The installation package includes all nine ship models under `art/native` and the inventory and Ship Tree icons under `art/icons`. Published install packages and update metadata are listed on [Releases](https://github.com/Delta007a/empire-specialized-haulers/releases). The Launcher update feed needs access to the release and its assets.

## Build the ZIP locally

Use Python 3 and an existing local copy of the mod's matching visual resources. Run from the repository root:

```powershell
python tools/build-local-package.py '<EveJS directory>/mods/empire-specialized-haulers'
```

The builder checks all 137 resources against the committed manifest and writes `dist/EveJS-EmpireSpecializedHaulers-0.4.1.zip`. It accepts the verified 0.4.0 visual resources and relocates Wolverine into `art/native/ci2_w2` during packaging.

## Check the client

The server log records `[EmpireHaulers] LOGIN_READY build=3396210 types=18` when the login hook loads. After login, the client log records `[EmpireHaulers] MASTERIES_READY ships=9 levels=5 source=native-stock`. The current test runtime has rendered the ships in EVE. The Minmatar Ship Tree was also checked in the live client with Mastery V.
