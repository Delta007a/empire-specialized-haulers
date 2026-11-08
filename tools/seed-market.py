"""Add Empire Specialized Haulers to an existing EveJS SQLite market file.

Python 3.11+, standard library only. Preview by default; --apply writes one
transaction. The market generator, its configuration and its manifest are not
used. Stop the market service before applying so its in-memory caches reload.
"""

import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import sqlite3
from statistics import median
import tomllib


ROOT = Path(__file__).resolve().parent.parent
NATIVE_BLUEPRINTS = {648: 983, 649: 984, 651: 986, 652: 987, 653: 988,
                     1944: 1945, 19744: 19745, 655: 990}
FACTIONS = {"caldari": 500001, "minmatar": 500002, "amarr": 500003, "gallente": 500004}
TYPE_FIELDS = {"type_id", "group_id", "category_id", "market_group_id", "name",
               "group_name", "base_price", "volume", "portion_size", "published"}
STOCK_FIELDS = {"station_id", "solar_system_id", "constellation_id", "region_id",
                "type_id", "price", "quantity", "initial_quantity", "updated_at"}
SUMMARY_FIELDS = {"type_id", "best_ask_price", "total_ask_quantity", "best_ask_station_id",
                  "best_bid_price", "total_bid_quantity", "best_bid_station_id", "updated_at"}


def installed_database(mod_root):
    """Resolve this installation's configured file, without scanning other installs."""
    mod_root = Path(mod_root).resolve()
    market = mod_root.parent.parent / "externalservices/market-server"
    if mod_root.parent.name.lower() != "mods" or not market.is_dir():
        raise ValueError("Put this mod folder in <EveJS>/mods/empire-specialized-haulers, "
                         "then run Market-Normal.cmd or Market-Hardcore.cmd again. "
                         "An explicit database path is also accepted by the Python script.")
    config_path = market / "config/market-server.local.toml"
    configured = "data/generated/market.sqlite"
    if config_path.is_file():
        config = tomllib.loads(config_path.read_text(encoding="utf-8-sig"))
        storage = config.get("storage", {})
        if not isinstance(storage, dict):
            raise ValueError(f"Invalid [storage] section in {config_path}")
        configured = storage.get("database_path", configured)
    if not isinstance(configured, str) or not configured.strip():
        raise ValueError(f"Invalid storage.database_path in {config_path}")
    database = Path(configured)
    if not database.is_absolute():
        database = market / database
    database = database.resolve()
    if not database.is_file():
        raise ValueError(f"Market database not found: {database}. "
                         "Generate the market database first, then run this script again.")
    return database


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def columns(conn, table):
    return {row[1] for row in conn.execute("PRAGMA table_info(" + quoted(table) + ")")}


def require_fields(conn, table, required):
    found = columns(conn, table)
    if not required <= found:
        raise ValueError(f"Unsupported market schema: {table} missing {sorted(required - found)}")
    return found


def check_schema(conn):
    require_fields(conn, "market_types", TYPE_FIELDS)
    require_fields(conn, "seed_stock", STOCK_FIELDS)
    require_fields(conn, "stations", {"station_id", "station_name"})
    for table, scope in (("region_summaries", "region_id"),
                         ("system_seed_summaries", "solar_system_id")):
        if columns(conn, table):
            require_fields(conn, table, SUMMARY_FIELDS | {scope})
    if columns(conn, "market_orders"):
        require_fields(conn, "market_orders", {"type_id", "region_id", "station_id", "price",
                       "vol_remaining", "bid", "state", "source"})
    if columns(conn, "seed_buy_orders"):
        require_fields(conn, "seed_buy_orders", STOCK_FIELDS)


def positive_price(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result > 0 else None
    except ArithmeticError:
        return None


def price_references(stock, types, role_ids, catalog_fallback=True):
    references = {}
    for type_id in role_ids:
        if type_id not in types:
            raise ValueError(f"Missing Gallente market template {type_id}")
        local = {r["station_id"]: positive_price(r["price"]) for r in stock[type_id]
                 if positive_price(r["price"]) is not None}
        fallback = median(list(local.values())) if local else (
            positive_price(types[type_id]["base_price"]) if catalog_fallback else None)
        references[type_id] = (local, fallback, "median Gallente seed price across this database"
                               if local else "Gallente base_price (no seed offers)")
    return references


def reference_price(type_id, station_id, references):
    local, fallback, source = references[type_id]
    price = local.get(station_id, fallback)
    if station_id in local:
        source = "local Gallente seed offer"
    if price is None:
        raise ValueError(f"No usable Gallente price for type {type_id}")
    return float(price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)), source


def buy_price(role_id, original_id, station_id, original_buy, buy_references,
              sell_references, original_sell_references):
    if buy_references[role_id][1] is not None:
        price, source = reference_price(role_id, station_id, buy_references)
        return price, source.replace("seed", "BUY seed")
    # Preserve the file's original bid/ask spread when its Gallente analog has no bids.
    gallente_sell, _ = reference_price(role_id, station_id, sell_references)
    original_sell, _ = reference_price(original_id, station_id, original_sell_references)
    bid = positive_price(original_buy["price"])
    if bid is None:
        raise ValueError(f"No usable original BUY price for type {original_id}")
    price = (Decimal(str(gallente_sell)) * bid / Decimal(str(original_sell))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    if price <= 0:
        raise ValueError(f"Calculated BUY price for type {role_id} is not positive")
    return float(price), "Gallente SELL price x original BUY/SELL ratio (no Gallente BUY offers)"


def make_plan(conn, fleet, npc_owners, mode="normal", station_ids=()):
    check_schema(conn)
    owned = {i for ship in fleet["ships"] for i in (ship["typeID"], ship["blueprintTypeID"])}
    needed = owned | set(NATIVE_BLUEPRINTS) | set(NATIVE_BLUEPRINTS.values())
    needed |= {i for role in fleet["roles"].values() for i in role[:2]} | {i for pair in fleet.get("marketPriceReferences", {}).values() for i in pair}
    placeholders = ",".join("?" for _ in needed)
    types = {r["type_id"]: dict(r) for r in conn.execute(
        f"SELECT * FROM market_types WHERE type_id IN ({placeholders})", tuple(needed))}
    stock = defaultdict(list)
    for row in conn.execute(f"SELECT * FROM seed_stock WHERE initial_quantity > 0 AND type_id IN ({placeholders})", tuple(needed)):
        stock[row["type_id"]].append(dict(row))
    stock_at = {type_id: {r["station_id"]: r for r in rows} for type_id, rows in stock.items()}
    references = price_references(stock, types, {i for role in fleet["roles"].values() for i in role[:2]} | {i for pair in fleet.get("marketPriceReferences", {}).values() for i in pair})
    buy_stock = defaultdict(list)
    has_buys = bool(columns(conn, "seed_buy_orders"))
    if has_buys:
        for row in conn.execute(f"SELECT * FROM seed_buy_orders WHERE initial_quantity > 0 AND type_id IN ({placeholders})", tuple(needed)):
            buy_stock[row["type_id"]].append(dict(row))
    buy_at = {type_id: {r["station_id"]: r for r in rows} for type_id, rows in buy_stock.items()}
    buy_references = price_references(buy_stock, types,
        {i for role in fleet["roles"].values() for i in role[:2]} | {i for pair in fleet.get("marketPriceReferences", {}).values() for i in pair}, catalog_fallback=False)
    original_sell_references = price_references(stock, types, set(NATIVE_BLUEPRINTS) | set(NATIVE_BLUEPRINTS.values()))
    stations = {r["station_id"]: r["station_name"] for r in
                conn.execute("SELECT station_id, station_name FROM stations")}
    if set(station_ids) - stations.keys():
        raise ValueError("Requested station is absent from the market database")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    catalog, offers, buy_offers, warnings = [], [], [], []
    current = {(r["station_id"], r["type_id"]): dict(r) for r in conn.execute(
        "SELECT * FROM seed_stock WHERE type_id IN (" + ",".join("?" for _ in owned) + ")", tuple(owned))}
    current_buys = {(r["station_id"], r["type_id"]): dict(r) for r in conn.execute(
        "SELECT * FROM seed_buy_orders WHERE type_id IN (" + ",".join("?" for _ in owned) + ")", tuple(owned))} if has_buys else {}
    for ship in fleet["ships"]:
        role_ship, role_bp = fleet.get("marketPriceReferences", {}).get(ship["role"], fleet["roles"][ship["role"]][:2])
        base_ship, base_bp = ship["stockTypeID"], NATIVE_BLUEPRINTS[ship["stockTypeID"]]
        for type_id, category in ((base_ship, 6), (role_ship, 6), (base_bp, 9), (role_bp, 9)):
            if type_id not in types or types[type_id]["category_id"] != category:
                raise ValueError(f"Missing or incompatible original market type {type_id}")
        for is_bp, original in ((False, base_ship), (True, role_bp)):
            row = dict(types[original])
            row.update(type_id=ship["blueprintTypeID"] if is_bp else ship["typeID"],
                       name=ship["name"] + (" Blueprint" if is_bp else ""), published=1,
                       base_price=types[role_bp if is_bp else role_ship]["base_price"],
                       market_group_id=fleet["races"][ship["empire"]][6 if is_bp else 5])
            if "graphic_id" in row:
                row["graphic_id"] = ship["graphicID"]
            if "race_id" in row:
                row["race_id"] = fleet["races"][ship["empire"]][0]
            existing = types.get(row["type_id"])
            if existing and any(existing[k] != row[k] for k in ("name", "category_id", "group_id")):
                raise ValueError(f"Type ID collision: {row['type_id']} is already {existing['name']!r}")
            catalog.append({"row": row, "new": existing is None})

        anchor_id = base_ship if mode == "normal" else base_bp
        anchors = sorted(stock[anchor_id], key=lambda r: r["station_id"])
        if mode == "normal" and station_ids:
            anchors = [r for r in anchors if r["station_id"] in station_ids]
        if mode == "hardcore":
            anchors = [r for r in anchors if npc_owners.get(str(r["station_id"]), [None, None])[1]
                       == FACTIONS[ship["empire"]]]
        if not anchors:
            warnings.append(f"{ship['name']}: no matching {'hull sellers' if mode == 'normal' else 'own-faction NPC BPO sellers'}; no offers added")
        for anchor in anchors:
            station_id = anchor["station_id"]
            for is_bp in ([False, True] if mode == "normal" else [True]):
                target_id = ship["blueprintTypeID"] if is_bp else ship["typeID"]
                price_id = role_bp if is_bp else role_ship
                price, source = reference_price(price_id, station_id, references)
                quantity_source = stock_at.get(base_bp, {}).get(station_id, anchor) if is_bp else anchor
                row = dict(quantity_source)
                # Placement follows the hull in normal mode and the BPO in hardcore mode.
                for key in ("station_id", "solar_system_id", "constellation_id", "region_id"):
                    row[key] = anchor[key]
                row.update(type_id=target_id, price=price, quantity=quantity_source["initial_quantity"], updated_at=stamp)
                existing = current.get((station_id, target_id))
                if existing:
                    row, source = existing, "existing mod offer preserved"
                offers.append({"row": row, "new": existing is None, "name": ship["name"] + (" Blueprint" if is_bp else ""),
                               "stationName": stations.get(station_id, str(station_id)), "anchorTypeID": anchor_id,
                               "priceTypeID": price_id, "priceSource": source, "orderSide": "SELL"})
                original_id = base_bp if is_bp else base_ship
                original_buy = buy_at.get(original_id, {}).get(station_id)
                if original_buy is not None:
                    existing_buy = current_buys.get((station_id, target_id))
                    if existing_buy:
                        buy_row, buy_source = existing_buy, "existing mod BUY offer preserved"
                    else:
                        price, buy_source = buy_price(price_id, original_id, station_id, original_buy,
                                                     buy_references, references, original_sell_references)
                        buy_row = dict(original_buy)
                        buy_row.update(type_id=target_id, price=price, quantity=original_buy["initial_quantity"], updated_at=stamp)
                    buy_offers.append({"row": buy_row, "new": existing_buy is None, "name": ship["name"] + (" Blueprint" if is_bp else ""),
                                       "stationName": stations.get(station_id, str(station_id)), "anchorTypeID": original_id,
                                       "priceTypeID": price_id, "priceSource": buy_source, "orderSide": "BUY"})
    if not offers:
        raise ValueError("No matching base hauler sellers found for this mode/station selection; nothing changed")
    wanted = {(r["row"]["station_id"], r["row"]["type_id"]) for r in offers}
    wanted_buys = {(r["row"]["station_id"], r["row"]["type_id"]) for r in buy_offers}
    return {"mode": mode, "catalog": catalog, "offers": offers, "buyOffers": buy_offers,
            "remove": [r for key, r in current.items() if key not in wanted], "warnings": warnings,
            "removeBuys": [r for key, r in current_buys.items() if key not in wanted_buys],
            "ownedTypeIDs": sorted(owned)}


def insert_row(conn, table, row):
    names = list(row)
    conn.execute("INSERT INTO " + quoted(table) + " (" + ",".join(map(quoted, names))
                 + ") VALUES (" + ",".join("?" for _ in names) + ")", [row[n] for n in names])


def refresh_summaries(conn, owned):
    """Refresh only mod types; region caches include player orders, system caches seed only."""
    placeholders = ",".join("?" for _ in owned)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    for table, scope in (("region_summaries", "region_id"),
                         ("system_seed_summaries", "solar_system_id")):
        if not columns(conn, table):
            continue
        books = defaultdict(lambda: [[], []])
        sources = [("seed_stock", "quantity", 0), ("seed_buy_orders", "quantity", 1)]
        for source, quantity, bid in sources:
            if columns(conn, source):
                for r in conn.execute(f"SELECT {scope},type_id,price,{quantity},station_id FROM {source} "
                                      f"WHERE type_id IN ({placeholders}) AND {quantity}>0", owned):
                    books[(r[0], r[1])][bid].append((r[2], r[3], r[4]))
        if scope == "region_id" and columns(conn, "market_orders"):
            for r in conn.execute(f"SELECT region_id,type_id,price,vol_remaining,station_id,bid FROM market_orders "
                                  f"WHERE type_id IN ({placeholders}) AND state='open' AND vol_remaining>0 "
                                  "AND (bid=0 OR (bid=1 AND source='player'))", owned):
                books[(r[0], r[1])][r[5]].append((r[2], r[3], r[4]))
        conn.execute(f"DELETE FROM {table} WHERE type_id IN ({placeholders})", owned)
        for (location, type_id), (sells, buys) in books.items():
            row = {scope: location, "type_id": type_id, "updated_at": stamp}
            for side, entries, choose in (("ask", sells, min), ("bid", buys, max)):
                price = choose(e[0] for e in entries) if entries else None
                row.update({f"best_{side}_price": price, f"total_{side}_quantity": sum(e[1] for e in entries),
                            f"best_{side}_station_id": min(e[2] for e in entries if e[0] == price) if entries else None})
            insert_row(conn, table, row)


def apply_plan(conn, plan):
    for entry in plan["catalog"]:
        if entry["new"]:
            insert_row(conn, "market_types", entry["row"])
    for table, removal_key, offers_key in (("seed_stock", "remove", "offers"),
                                           ("seed_buy_orders", "removeBuys", "buyOffers")):
        for row in plan[removal_key]:
            conn.execute(f"DELETE FROM {table} WHERE station_id=? AND type_id=?", (row["station_id"], row["type_id"]))
        for entry in plan[offers_key]:
            if entry["new"]:
                insert_row(conn, table, entry["row"])
    refresh_summaries(conn, plan["ownedTypeIDs"])


def run(database, mode="normal", apply=False, station_ids=()):
    database = Path(database).resolve(strict=True)
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8-sig"))
    npc = json.loads((ROOT / "tools/market-npc-stations.json").read_text(encoding="utf-8-sig"))
    if npc["clientBuild"] != fleet["clientBuild"]:
        raise ValueError("NPC station reference and fleet target different client builds")
    with closing(sqlite3.connect(database.as_uri() + ("?mode=rw" if apply else "?mode=ro"), uri=True, timeout=5)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        if not apply:
            conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        try:
            plan = make_plan(conn, fleet, npc["stations"], mode, station_ids)
            if apply:
                apply_plan(conn, plan)
                conn.commit()
            else:
                conn.rollback()
        except BaseException:
            conn.rollback()
            raise
    plan.update(database=str(database), applied=apply)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, nargs="?", help="Existing market SQLite file; defaults to this EveJS installation's market configuration")
    parser.add_argument("--mode", choices=("normal", "hardcore"), default="normal")
    parser.add_argument("--station", type=int, action="append", default=[], help="Limit normal mode to this station ID; repeat for multiple stations")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the file; default is read-only preview")
    parser.add_argument("--report", type=Path, help="Optional detailed JSON report")
    args = parser.parse_args()
    if args.mode == "hardcore" and args.station:
        parser.error("--station applies to normal mode; hardcore follows own-faction NPC BPO sellers")
    if any(s <= 0 for s in args.station):
        parser.error("station IDs must be positive")
    try:
        database = args.database.resolve() if args.database else installed_database(ROOT)
        if args.report and args.report.resolve() in {
                database, Path(str(database) + "-wal"), Path(str(database) + "-shm")}:
            parser.error("report path must differ from the database and its WAL/SHM files")
        print("Market database:", database)
        plan = run(database, args.mode, args.apply, args.station)
    except (OSError, ValueError, sqlite3.Error, KeyError) as error:
        parser.exit(1, f"Cannot seed market: {error}\n")
    new_types = sum(e["new"] for e in plan["catalog"])
    new_offers = sum(e["new"] for e in plan["offers"])
    new_buys = sum(e["new"] for e in plan["buyOffers"])
    print(f"{'APPLIED' if args.apply else 'PREVIEW'} {args.mode}: {new_types} new types, {new_offers} new SELL offers, "
          f"{new_buys} new BUY offers, {len(plan['offers']) + len(plan['buyOffers']) - new_offers - new_buys} preserved, "
          f"{len(plan['remove']) + len(plan['removeBuys'])} obsolete mod seed offers removed")
    groups = defaultdict(list)
    for entry in plan["offers"] + plan["buyOffers"]:
        groups[(entry["name"], entry["orderSide"])].append(entry)
    for (name, side), entries in groups.items():
        prices = [e["row"]["price"] for e in entries]
        print(f"  {name} {side}: {len(entries)} station(s), {min(prices):,.2f}..{max(prices):,.2f} ISK")
    for warning in plan["warnings"]:
        print("NOTE:", warning)
    if any("base_price" in e["priceSource"] for e in plan["offers"]):
        print("NOTE: Some Gallente analogs have no seed offers; their catalog base_price was used.")
    if any("no Gallente BUY" in e["priceSource"] for e in plan["buyOffers"]):
        print("NOTE: Some Gallente analogs have no BUY offers; their SELL prices and the original BUY/SELL ratio were used.")
    if args.report:
        try:
            args.report.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            parser.exit(1, f"Database operation {'committed' if args.apply else 'previewed'}, but report could not be written: {error}\n")
    if not args.apply:
        print("Read-only preview. Add --apply to write these changes with the market service stopped.")


if __name__ == "__main__":
    main()
