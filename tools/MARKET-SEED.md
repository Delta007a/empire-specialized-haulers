# Market file seeding

`seed-market.py` adds sell offers for Empire Specialized Haulers to an **existing EveJS SQLite market file**. It uses the contents of that file, independently of the tool or settings used to generate it. No Market Workbench, running server API, third-party Python package or network access is required.

Requires **Python 3.11 or newer**. Keep `fleet.json` at the mod root and both `seed-market.py` and `market-npc-stations.json` in `tools/`.

## Start here: no commands or paths

Install the files into **`<EveJS>/mods/empire-specialized-haulers`**, stop Market, then double-click **`Market-Normal.cmd`** or **`Market-Hardcore.cmd`** in that mod folder. When the window says **Finished successfully**, close it and start Market again.

The script reads the database path from this server's `externalservices/market-server/config/market-server.local.toml`. If that config is absent, it uses the standard `externalservices/market-server/data/generated/market.sqlite` file. It does not scan other EveJS installations.

See [the simple English instructions](../MARKET-SETUP.md) or [the Russian instructions](../MARKET-SETUP-RU.txt). The commands below are optional advanced controls.

## Normal mode: ships and blueprints

Run from the installed mod folder:

```powershell
python tools/seed-market.py
```

This previews the changes without writing to the database. To apply them, stop the market service, run:

```powershell
python tools/seed-market.py --apply
```

Then start the market service again so it loads the updated file and summary caches.

The script follows **existing seeded sell offers for each original hull**:

| Original hull | New ships placed at the same stations |
| --- | --- |
| Tayra | Wolverine, Marten |
| Badger | Stoat |
| Bestower | Tithe, Reliquary |
| Sigil | Steward |
| Mammoth | Bison |
| Hoarder | Muskox |
| Wreathe | Caravan |

Both a ship and its blueprint are added at these stations. If the original ships are sold only in Jita, the new offers appear only in Jita, even if original blueprints are available elsewhere. Several selected hubs produce offers at those hubs. A galaxy-wide database retains the original hulls' individual station distribution.

**Both SELL and BUY are supported.** At each selected station, the new hull or BPO also receives a seeded BUY order when the corresponding original hull or BPO has one there. BUY orders do not expand the chosen supply locations. If an original BPO has no BUY order, none is invented for its new blueprint.

To explicitly restrict normal mode to Jita 4-4:

```powershell
python tools/seed-market.py --station 60003760 --apply
```

`--station` can be repeated for several stations. Each selected station must already sell the relevant original hull; selecting a station does not create original sellers.

## Hardcore mode: blueprints at own-faction NPC sellers

```powershell
python tools/seed-market.py --mode hardcore
python tools/seed-market.py --mode hardcore --apply
```

Only blueprints receive seeded sell offers. Each one follows an existing offer for its original hull's blueprint: Tayra Blueprint for Wolverine and Marten, Badger Blueprint for Stoat, and so on.

The station must belong to an NPC corporation of the ship's faction. The bundled reference identifies **3,180 Caldari, Amarr and Minmatar NPC stations** using station ownership and corporation faction membership for client build 3396210. Region names, station names and station model races are not used to guess ownership. The reference supplies ownership only; it does not create sellers or supply offers absent from the user's file.

If the file has no suitable seller for a particular ship, the script reports that ship and skips its offers. For example, a Jita-only database cannot supply Amarr or Minmatar own-faction sellers unless those stations and original BPO offers are also present. If no ship has suitable sellers, the operation stops without changes.

## Prices and quantities

Prices follow the corresponding Gallente specialization, separately for hulls and blueprints:

| Role | Price reference |
| --- | --- |
| Ore | Miasmos / Miasmos Blueprint |
| Minerals and ice | Kryos / Kryos Blueprint |
| Planetary | Epithal / Epithal Blueprint |

The price comes from the Gallente analog's seeded offer at the destination station. If there is no local offer, the script uses the median seeded price for that same analog across the file. If the analog has no seeded offers anywhere, it uses its `market_types.base_price` and prints a note. There is no added price multiplier. Prices are rounded to two decimal places.

BUY prices use the analog's **BUY** offers, separately from SELL prices: local bid first, then the database-wide median bid. If the analog has no bids anywhere, the fallback is its SELL price multiplied by the original item's BUY/SELL price ratio, with a note in the report. The SELL price is never copied directly into a BUY order. New BUY capacity copies the original BUY order's initial quantity and other stored order fields.

New hull stock copies the original hull's initial quantity. New BPO stock copies the original hull's BPO initial quantity at the destination, when present; otherwise normal mode uses the hull's initial quantity. The script does not copy player orders to establish locations or prices.

## Repeat runs and mode changes

- Existing mod SELL and BUY offers at retained locations keep their price, initial quantity and remaining quantity. A repeat run does not replenish purchased stock or duplicate offers.
- Changing mode or station selection removes this mod's seeded offers outside the new selection. Switching to hardcore removes seeded SELL and BUY orders for the nine hulls and keeps BPO offers only at the eligible NPC sellers.
- Player orders, purchases, inventory, unrelated seeded buy orders, other item types and generator metadata are preserved.
- All 18 ship/BPO market catalog entries are available in either mode. Hardcore restricts NPC supply; player manufacturing and sales remain possible.
- Existing regional and system summary tables are refreshed only for this mod's 18 types. Regional summaries include existing player orders; system seed summaries include seeded stock and seeded buy orders.
- Applying runs inside one SQLite transaction. A failed write rolls back the catalog, sell offers and summary updates together.

## Detailed report

```powershell
python tools/seed-market.py --mode hardcore --report hardcore-preview.json
```

The JSON report lists each proposed station, original placement type, Gallente price reference, stock quantity, preserved offer and removal. Add `--apply` to the same command to write the changes and report the applied plan.

The console and JSON report distinguish SELL offers from BUY offers and list removals on each side. To repair a market seeded with 0.4.3, update to 0.5.1 and run normal mode again; existing SELL offers are preserved while missing BUY orders are added.

An explicit file is still accepted when using a checkout outside a server installation: `python tools/seed-market.py "D:/your/actual/market.sqlite"`. That path is an example to replace with your file; the double-click launchers do not require it.

## Supported database layout

The file must contain EveJS `market_types`, `seed_stock` and `stations` tables. The script checks columns instead of generator names, configuration files or manifest flags. Optional summary, player-order and seeded-buy tables are supported when present. Unknown or incomplete layouts produce an explanation before changes are written.

After regenerating a market file, run the script again on the new file. The mod itself does not automatically seed or restore market stock.

The **mod installation ZIP 0.5.1** includes the scripts, station reference and both quick-start guides in the mod folder. Users of 0.4.2 or 0.4.3 can update through the Launcher before running market setup.


Gas ships: Anemos follows Epithal, Vesper follows Sigil, and Sable follows Badger. Normal mode mirrors both original SELL and BUY availability; prices follow the corresponding Epithal order side. Hardcore mode adds only BPOs at the matching original BPO sellers owned by NPC corporations of the ship's faction.
