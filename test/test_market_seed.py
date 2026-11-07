"""Offline market files only; no running server or installed database is modified."""

import importlib.util
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("market_seed", ROOT / "tools/seed-market.py")
seed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seed)
FLEET = json.loads((ROOT / "fleet.json").read_text())
OWNED = {i for s in FLEET["ships"] for i in (s["typeID"], s["blueprintTypeID"])}
JITA, AMARR, RENS, SECOND_CALDARI, FOREIGN = 60003760, 60008494, 60004588, 60000004, 70000000
LOCATIONS = {JITA: (30000142, 20000020, 10000002), AMARR: (30002187, 20000322, 10000043),
             RENS: (30002510, 20000367, 10000030), SECOND_CALDARI: (30002780, 20000407, 10000033),
             FOREIGN: (30000142, 20000020, 10000002)}


class MarketSeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hauler-market-test-")
        self.db = Path(self.tmp.name) / "market.sqlite"
        self.conn = sqlite3.connect(self.db)
        self.conn.executescript("""
            CREATE TABLE market_types(type_id INTEGER PRIMARY KEY,group_id INTEGER,category_id INTEGER,
                market_group_id INTEGER,name TEXT,group_name TEXT,base_price REAL,volume REAL,portion_size INTEGER,published INTEGER);
            CREATE TABLE seed_stock(station_id INTEGER,solar_system_id INTEGER,constellation_id INTEGER,region_id INTEGER,
                type_id INTEGER,price REAL,quantity INTEGER,initial_quantity INTEGER,price_version INTEGER DEFAULT 1,
                updated_at TEXT,PRIMARY KEY(station_id,type_id));
            CREATE TABLE stations(station_id INTEGER PRIMARY KEY,solar_system_id INTEGER,constellation_id INTEGER,
                region_id INTEGER,station_name TEXT,security REAL);
            CREATE TABLE manifest(key TEXT PRIMARY KEY,value TEXT);
            INSERT INTO manifest VALUES('arbitrary_generator','neither inspected nor changed');
            CREATE TABLE market_orders(order_id INTEGER PRIMARY KEY,owner_id INTEGER,region_id INTEGER,station_id INTEGER,
                type_id INTEGER,price REAL,vol_remaining INTEGER,bid INTEGER,state TEXT,source TEXT);
            CREATE TABLE seed_buy_orders AS SELECT * FROM seed_stock WHERE 0;
            CREATE TABLE region_summaries(region_id INTEGER,type_id INTEGER,best_ask_price REAL,total_ask_quantity INTEGER,
                best_ask_station_id INTEGER,best_bid_price REAL,total_bid_quantity INTEGER,best_bid_station_id INTEGER,
                updated_at TEXT,PRIMARY KEY(region_id,type_id));
            CREATE TABLE system_seed_summaries(solar_system_id INTEGER,type_id INTEGER,best_ask_price REAL,total_ask_quantity INTEGER,
                best_ask_station_id INTEGER,best_bid_price REAL,total_bid_quantity INTEGER,best_bid_station_id INTEGER,
                updated_at TEXT,PRIMARY KEY(solar_system_id,type_id));
        """)
        for station, (system, constellation, region) in LOCATIONS.items():
            self.conn.execute("INSERT INTO stations VALUES(?,?,?,?,?,0.9)",
                              (station, system, constellation, region, f"Station {station}"))
        bases = {s["stockTypeID"]: s["stock"] for s in FLEET["ships"]}
        for type_id, name in bases.items():
            self.add_type(type_id, name, 6, 1400000, 123000)
            self.add_type(seed.NATIVE_BLUEPRINTS[type_id], name + " Blueprint", 9, 3000000, 0.01)
        for role, name in (("ore", "Miasmos"), ("mineral", "Kryos"), ("planetary", "Epithal")):
            hull, bp, price = FLEET["roles"][role][:3]
            self.add_type(hull, name, 6, 1400000, 250000)
            self.add_type(bp, name + " Blueprint", 9, price, 0.01)
        self.add_type(34, "Tritanium", 4, 5, 0.01)
        self.add_seed(34, JITA, 7, 123)
        self.conn.execute("INSERT INTO region_summaries VALUES(10000002,34,7,123,?,NULL,0,NULL,'untouched')", (JITA,))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def add_type(self, type_id, name, category, price, volume):
        self.conn.execute("INSERT INTO market_types VALUES(?,?,?,?,?,?,?,?,1,1)",
                          (type_id, 108 if category == 9 else 28, category, 283 if category == 9 else 83,
                           name, "Hauler Blueprint" if category == 9 else "Hauler", price, volume))

    def add_seed(self, type_id, station, price=123456, quantity=100):
        system, constellation, region = LOCATIONS[station]
        self.conn.execute("INSERT INTO seed_stock VALUES(?,?,?,?,?,?,?,?,1,'original')",
                          (station, system, constellation, region, type_id, price, quantity, quantity))

    def add_buy(self, type_id, station, price=10000, quantity=40):
        system, constellation, region = LOCATIONS[station]
        self.conn.execute("INSERT INTO seed_buy_orders VALUES(?,?,?,?,?,?,?,?,1,'original buy')",
                          (station, system, constellation, region, type_id, price, quantity, quantity))

    def hull_buys(self, *stations):
        for station in stations:
            for type_id in seed.NATIVE_BLUEPRINTS:
                self.add_buy(type_id, station, 50000)
            for i, role in enumerate(("ore", "mineral", "planetary")):
                self.add_buy(FLEET["roles"][role][0], station, 1000000 + i * 100000)
        self.conn.commit()

    def native_hulls(self, *stations):
        for station in stations:
            for type_id in seed.NATIVE_BLUEPRINTS:
                self.add_seed(type_id, station)
        self.conn.commit()

    def native_bpos(self, *stations):
        for station in stations:
            for type_id in seed.NATIVE_BLUEPRINTS.values():
                self.add_seed(type_id, station, quantity=2147483647)
        self.conn.commit()

    def gallente(self, *stations):
        for station in stations:
            for i, role in enumerate(("ore", "mineral", "planetary")):
                hull, bp = FLEET["roles"][role][:2]
                self.add_seed(hull, station, 7000000 + i * 1000000)
                self.add_seed(bp, station, 2000000 + i * 1000000, 2147483647)
        self.conn.commit()

    def rows(self, table):
        return self.conn.execute(f'SELECT * FROM "{table}" ORDER BY 1,2').fetchall()

    def mod_stock(self):
        return [r for r in self.rows("seed_stock") if r[4] in OWNED]

    def installation(self, config_text=None):
        server = Path(self.tmp.name) / "EveJS server with spaces !"
        mod = server / "mods/empire-specialized-haulers"
        market = server / "externalservices/market-server"
        (market / "config").mkdir(parents=True)
        (market / "data/generated").mkdir(parents=True)
        mod.mkdir(parents=True)
        for name in ("fleet.json", "Market-Normal.cmd", "Market-Hardcore.cmd",
                     "tools/run-market.cmd", "tools/seed-market.py", "tools/market-npc-stations.json"):
            destination = mod / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        target = market / "data/generated/market.sqlite"
        with closing(sqlite3.connect(target)) as c:
            self.conn.backup(c)
        if config_text is not None:
            (market / "config/market-server.local.toml").write_text(config_text, encoding="utf-8")
        return mod, target

    def test_jita_only_hulls_keep_both_products_in_jita_even_with_bpos_elsewhere(self):
        self.native_hulls(JITA)
        self.native_bpos(JITA, AMARR, RENS)
        self.gallente(JITA)
        before = self.rows("seed_stock")
        preview = seed.run(self.db)
        self.assertEqual(self.rows("seed_stock"), before)
        self.assertEqual({e["row"]["station_id"] for e in preview["offers"]}, {JITA})
        self.assertEqual(len(preview["offers"]), 18)
        seed.run(self.db, apply=True)
        self.assertEqual(len(self.mod_stock()), 18)
        self.assertEqual(self.conn.execute('SELECT volume FROM market_types WHERE type_id=2000000001').fetchone()[0], 123000)

    def test_multiple_hubs_mirror_all_existing_hub_locations(self):
        self.native_hulls(JITA, AMARR, RENS, SECOND_CALDARI, FOREIGN)
        plan = seed.run(self.db, apply=True)
        self.assertEqual(len(plan["offers"]), 90)
        self.assertEqual(len(self.mod_stock()), 90)

    def test_galaxy_distribution_uses_each_exact_original_hull(self):
        for i, type_id in enumerate(seed.NATIVE_BLUEPRINTS):
            self.add_seed(type_id, list(LOCATIONS)[i % len(LOCATIONS)])
        self.conn.commit()
        plan = seed.run(self.db)
        for entry in plan["offers"]:
            ship = next(s for s in FLEET["ships"] if entry["row"]["type_id"] in (s["typeID"], s["blueprintTypeID"]))
            expected = {r[0] for r in self.conn.execute("SELECT station_id FROM seed_stock WHERE type_id=?", (ship["stockTypeID"],))}
            self.assertIn(entry["row"]["station_id"], expected)
            self.assertEqual(entry["anchorTypeID"], ship["stockTypeID"])

    def test_hardcore_matches_owning_npc_faction_and_actual_native_bpo_seller(self):
        self.native_bpos(JITA, AMARR, RENS, SECOND_CALDARI, FOREIGN)
        self.gallente(JITA)
        plan = seed.run(self.db, "hardcore", apply=True)
        bp_ids = {s["blueprintTypeID"] for s in FLEET["ships"]}
        self.assertEqual({r[4] for r in self.mod_stock()}, bp_ids)
        for s in FLEET["ships"]:
            places = {r[0] for r in self.mod_stock() if r[4] == s["blueprintTypeID"]}
            self.assertEqual(places, {"caldari": {JITA, SECOND_CALDARI}, "amarr": {AMARR}, "minmatar": {RENS}}[s["empire"]])
        self.assertNotIn(FOREIGN, {r[0] for r in self.mod_stock()})
        self.assertFalse(plan["warnings"])

    def test_hardcore_does_not_invent_missing_sellers(self):
        self.native_bpos(JITA)
        plan = seed.run(self.db, "hardcore")
        self.assertEqual(len(plan["offers"]), 3)
        self.assertEqual(len(plan["warnings"]), 6)

    def test_prices_prefer_local_gallente_specialization(self):
        self.native_hulls(JITA, AMARR)
        self.gallente(JITA, AMARR)
        self.conn.execute('UPDATE seed_stock SET price=price+0.17 WHERE station_id=? AND type_id IN (656,991)', (AMARR,))
        self.conn.commit()
        plan = seed.run(self.db)
        for entry in plan["offers"]:
            expected = self.conn.execute('SELECT price FROM seed_stock WHERE station_id=? AND type_id=?',
                                         (entry["row"]["station_id"], entry["priceTypeID"])).fetchone()[0]
            self.assertEqual(entry["row"]["price"], expected)
            self.assertEqual(entry["priceSource"], "local Gallente seed offer")

    def test_missing_local_price_uses_database_median_then_catalog_base(self):
        self.native_hulls(AMARR)
        self.gallente(JITA, RENS)
        self.conn.execute('UPDATE seed_stock SET price=9000000 WHERE station_id=? AND type_id=656', (RENS,))
        self.conn.execute('DELETE FROM seed_stock WHERE type_id=989')
        self.conn.commit()
        plan = seed.run(self.db)
        ore = next(e for e in plan["offers"] if e["name"] == "Wolverine")
        mineral_bp = next(e for e in plan["offers"] if e["name"] == "Marten Blueprint")
        self.assertEqual(ore["row"]["price"], 8000000)
        self.assertIn("median", ore["priceSource"])
        self.assertEqual(mineral_bp["row"]["price"], FLEET["roles"]["mineral"][2])
        self.assertIn("base_price", mineral_bp["priceSource"])

    def test_repeat_preserves_purchases_prices_and_unrelated_data(self):
        self.native_hulls(JITA)
        self.gallente(JITA)
        unrelated = self.conn.execute('SELECT * FROM region_summaries WHERE type_id=34').fetchall()
        seed.run(self.db, apply=True)
        self.conn.execute('UPDATE seed_stock SET quantity=0,price=777 WHERE type_id=2000000001')
        self.conn.commit()
        before_stock, before_types, before_manifest = self.rows("seed_stock"), self.rows("market_types"), self.rows("manifest")
        plan = seed.run(self.db, apply=True)
        self.assertEqual(sum(e["new"] for e in plan["offers"]), 0)
        self.assertEqual(self.rows("seed_stock"), before_stock)
        self.assertEqual(self.rows("market_types"), before_types)
        self.assertEqual(self.rows("manifest"), before_manifest)
        self.assertEqual(self.conn.execute('SELECT * FROM region_summaries WHERE type_id=34').fetchall(), unrelated)

    def test_switch_to_hardcore_removes_mod_hull_bids_preserves_player_and_unrelated_orders(self):
        self.native_hulls(JITA, AMARR, RENS)
        self.native_bpos(JITA, AMARR, RENS)
        seed.run(self.db, apply=True)
        self.conn.execute("INSERT INTO market_orders VALUES(1,42,10000002,?,2000000001,900,3,0,'open','player')", (JITA,))
        self.conn.execute("INSERT INTO market_orders VALUES(2,42,10000002,?,2000000001,700,2,1,'open','player')", (JITA,))
        self.conn.execute("INSERT INTO seed_buy_orders VALUES(?,30000142,20000020,10000002,2000000001,800,4,4,1,'keep')", (JITA,))
        self.add_buy(34, JITA, 3, 100)
        self.conn.commit()
        orders = self.rows("market_orders")
        unrelated_buys = [r for r in self.rows("seed_buy_orders") if r[4] not in OWNED]
        seed.run(self.db, "hardcore", apply=True)
        self.assertEqual(len(self.mod_stock()), 9)
        self.assertEqual(self.rows("market_orders"), orders)
        self.assertEqual(self.rows("seed_buy_orders"), unrelated_buys)
        region = self.conn.execute('SELECT best_ask_price,total_ask_quantity,best_bid_price,total_bid_quantity FROM region_summaries WHERE region_id=10000002 AND type_id=2000000001').fetchone()
        self.assertEqual(region, (900, 3, 700, 2))
        system = self.conn.execute('SELECT best_ask_price,total_ask_quantity,best_bid_price,total_bid_quantity FROM system_seed_summaries WHERE solar_system_id=30000142 AND type_id=2000000001').fetchone()
        self.assertIsNone(system)

    def test_station_override_removes_only_outside_mod_seed_offers(self):
        self.native_hulls(JITA, AMARR)
        seed.run(self.db, apply=True)
        seed.run(self.db, apply=True, station_ids=[JITA])
        self.assertEqual(len(self.mod_stock()), 18)
        self.assertEqual({r[0] for r in self.mod_stock()}, {JITA})
        self.assertTrue(self.conn.execute('SELECT 1 FROM seed_stock WHERE station_id=? AND type_id=648', (AMARR,)).fetchone())

    def test_id_collision_aborts_without_changing_any_table(self):
        self.native_hulls(JITA)
        self.add_type(2000000208, "Another mod's item", 9, 99, 0.01)
        self.conn.commit()
        before = list(self.conn.iterdump())
        with self.assertRaisesRegex(ValueError, "Type ID collision"):
            seed.run(self.db, apply=True)
        self.assertEqual(list(self.conn.iterdump()), before)

    def test_failed_insert_rolls_back_catalog_offers_and_caches(self):
        self.native_hulls(JITA)
        self.conn.execute("CREATE TRIGGER reject_new_seed BEFORE INSERT ON seed_stock WHEN NEW.type_id=2000000208 BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        self.conn.commit()
        before = list(self.conn.iterdump())
        with self.assertRaisesRegex(sqlite3.IntegrityError, "fixture failure"):
            seed.run(self.db, apply=True)
        self.assertEqual(list(self.conn.iterdump()), before)

    def test_no_anchors_does_not_delete_existing_mod_stock(self):
        self.add_seed(2000000001, JITA)
        self.conn.commit()
        before = self.rows("seed_stock")
        with self.assertRaisesRegex(ValueError, "No matching base"):
            seed.run(self.db, apply=True)
        self.assertEqual(self.rows("seed_stock"), before)

    def test_optional_price_version_and_caches_are_not_required(self):
        self.native_hulls(JITA)
        for table in ("region_summaries", "system_seed_summaries", "seed_buy_orders", "market_orders"):
            self.conn.execute('DROP TABLE ' + table)
        self.conn.execute('ALTER TABLE seed_stock DROP COLUMN price_version')
        self.conn.commit()
        seed.run(self.db, apply=True)
        self.assertEqual(len(self.mod_stock()), 18)

    def test_preview_reads_uncheckpointed_wal(self):
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA wal_autocheckpoint=0')
        self.native_hulls(JITA)
        self.assertGreater(Path(str(self.db) + '-wal').stat().st_size, 0)
        self.assertEqual(len(seed.run(self.db)["offers"]), 18)

    def test_cli_preview_report_and_bad_schema(self):
        self.native_hulls(JITA)
        report = Path(self.tmp.name) / 'preview.json'
        result = subprocess.run([sys.executable, str(ROOT/'tools/seed-market.py'), str(self.db), '--report', str(report)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PREVIEW normal', result.stdout)
        self.assertFalse(json.loads(report.read_text())["applied"])
        self.assertFalse(self.mod_stock())
        self.conn.execute('DROP TABLE market_types')
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'Unsupported market schema'):
            seed.run(self.db, apply=True)

    def test_installed_default_uses_own_server_and_needs_no_database_argument(self):
        self.native_hulls(JITA)
        mod, target = self.installation()
        self.assertEqual(seed.installed_database(mod), target.resolve())
        result = subprocess.run([sys.executable, str(mod/'tools/seed-market.py')],
                                cwd=self.tmp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PREVIEW normal: 18 new types, 18 new SELL offers', result.stdout)
        with closing(sqlite3.connect(target)) as c:
            self.assertIsNone(c.execute('SELECT 1 FROM seed_stock WHERE type_id=2000000001').fetchone())

    def test_installed_relative_configuration_takes_precedence_over_default_file(self):
        mod, target = self.installation('[storage]\ndatabase_path = "data/custom-market.sqlite"\n')
        configured = target.parent.parent / 'custom-market.sqlite'
        configured.write_bytes(b'configuration selected this existing file')
        self.assertEqual(seed.installed_database(mod), configured.resolve())
        configured.unlink()
        with self.assertRaisesRegex(ValueError, 'Market database not found'):
            seed.installed_database(mod)

    def test_installed_absolute_configuration_and_wrong_folder(self):
        config = '[storage]\ndatabase_path = ' + json.dumps(str(self.db)) + '\n'
        mod, _ = self.installation(config)
        self.assertEqual(seed.installed_database(mod), self.db.resolve())
        with self.assertRaisesRegex(ValueError, 'Put this mod folder'):
            seed.installed_database(Path(self.tmp.name) / 'downloaded-tools')

    @unittest.skipUnless(os.name == 'nt', 'Windows double-click launchers')
    def test_both_windows_launchers_apply_to_their_own_relocated_server(self):
        self.native_hulls(JITA, AMARR, RENS)
        self.native_bpos(JITA, AMARR, RENS)
        self.gallente(JITA)
        self.hull_buys(JITA, AMARR, RENS)
        mod, target = self.installation('[storage]\ndatabase_path = "data/generated/market.sqlite"\n')
        for name, mode, expected in (("Market-Normal.cmd", "normal", 54), ("Market-Hardcore.cmd", "hardcore", 9)):
            result = subprocess.run(['cmd.exe', '/d', '/c', str(mod/name)], input='\n',
                                    cwd=self.tmp.name, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('APPLIED ' + mode, result.stdout)
            self.assertIn('Finished successfully', result.stdout)
            with closing(sqlite3.connect(target)) as c:
                count = c.execute('SELECT count(*) FROM seed_stock WHERE type_id IN (' +
                                  ','.join('?' for _ in OWNED) + ')', tuple(OWNED)).fetchone()[0]
                self.assertEqual(count, expected)
                buy_count = c.execute('SELECT count(*) FROM seed_buy_orders WHERE type_id IN (' +
                                      ','.join('?' for _ in OWNED) + ')', tuple(OWNED)).fetchone()[0]
                self.assertEqual(buy_count, 27 if mode == 'normal' else 0)
        self.assertFalse(self.mod_stock())

    def test_normal_copies_buy_side_with_gallente_bid_price_and_original_demand(self):
        self.native_hulls(JITA)
        self.gallente(JITA)
        self.hull_buys(JITA)
        plan = seed.run(self.db, apply=True)
        self.assertEqual(len(plan['offers']), 18)
        self.assertEqual(len(plan['buyOffers']), 9)
        for entry in plan['buyOffers']:
            self.assertEqual(entry['orderSide'], 'BUY')
            price = self.conn.execute('SELECT price FROM seed_buy_orders WHERE type_id=? AND station_id=?',
                                      (entry['priceTypeID'], JITA)).fetchone()[0]
            self.assertEqual(entry['row']['price'], price)
            self.assertEqual(entry['row']['quantity'], 40)
            self.assertIn('BUY seed', entry['priceSource'])
        summary = self.conn.execute('SELECT best_ask_price,best_bid_price,total_bid_quantity FROM region_summaries '
                                    'WHERE type_id=2000000001 AND region_id=10000002').fetchone()
        self.assertEqual(summary, (7000000, 1000000, 40))

    def test_buy_prices_use_remote_gallente_median_or_original_spread(self):
        self.native_hulls(JITA)
        self.gallente(JITA)
        self.conn.execute('UPDATE seed_stock SET price=4000000 WHERE type_id=649')
        self.add_buy(649, JITA, 1000000)
        self.add_buy(656, AMARR, 2000000)
        self.add_buy(656, RENS, 4000000)
        self.conn.commit()
        plan = seed.run(self.db)
        ore = next(e for e in plan['buyOffers'] if e['name'] == 'Wolverine')
        mineral = next(e for e in plan['buyOffers'] if e['name'] == 'Marten')
        self.assertEqual(ore['row']['price'], 3000000)
        self.assertIn('median', ore['priceSource'])
        self.assertEqual(mineral['row']['price'], 2000000)
        self.assertIn('original BUY/SELL ratio', mineral['priceSource'])

    def test_upgrade_from_sell_only_adds_missing_bids_preserves_both_sides_after_trades(self):
        self.native_hulls(JITA)
        self.gallente(JITA)
        seed.run(self.db, apply=True)
        self.conn.execute('UPDATE seed_stock SET quantity=0,price=123 WHERE type_id=2000000001')
        self.conn.commit()
        previous_sells = self.rows('seed_stock')
        self.hull_buys(JITA)
        upgrade = seed.run(self.db, apply=True)
        self.assertFalse(any(e['new'] for e in upgrade['offers']))
        self.assertEqual(sum(e['new'] for e in upgrade['buyOffers']), 9)
        self.assertEqual(self.rows('seed_stock'), previous_sells)
        self.conn.execute('UPDATE seed_buy_orders SET quantity=0,price=456 WHERE type_id=2000000001')
        self.conn.commit()
        previous_buys = self.rows('seed_buy_orders')
        repeat = seed.run(self.db, apply=True)
        self.assertFalse(any(e['new'] for e in repeat['buyOffers']))
        self.assertEqual(self.rows('seed_buy_orders'), previous_buys)

    def test_buy_side_does_not_expand_outside_selected_hub_or_invent_original_bids(self):
        self.native_hulls(JITA, AMARR)
        self.gallente(JITA)
        self.hull_buys(AMARR)
        for role in FLEET['roles'].values():
            self.add_buy(role[0], JITA)
        self.conn.commit()
        plan = seed.run(self.db, station_ids=[JITA])
        self.assertEqual(len(plan['offers']), 18)
        self.assertFalse(plan['buyOffers'])

    def test_bpo_buy_orders_follow_original_bpos_in_normal_and_hardcore(self):
        self.native_hulls(JITA, AMARR, RENS)
        self.native_bpos(JITA, AMARR, RENS)
        self.gallente(JITA)
        self.hull_buys(JITA, AMARR, RENS)
        self.add_buy(984, JITA, 10000)
        self.add_buy(1945, AMARR, 10000)
        self.add_buy(991, JITA, 200000)
        self.add_buy(989, JITA, 300000)
        self.conn.commit()
        normal = seed.run(self.db, apply=True)
        self.assertEqual(len(normal['buyOffers']), 31)
        hardcore = seed.run(self.db, 'hardcore', apply=True)
        self.assertEqual(len(hardcore['buyOffers']), 4)
        self.assertTrue(all(e['name'].endswith(' Blueprint') for e in hardcore['buyOffers']))
        self.assertEqual(len(hardcore['removeBuys']), 27)

    def test_failed_buy_insert_rolls_back_catalog_sells_and_buys(self):
        self.native_hulls(JITA)
        self.gallente(JITA)
        self.hull_buys(JITA)
        self.conn.execute("CREATE TRIGGER reject_new_bid BEFORE INSERT ON seed_buy_orders "
                          "WHEN NEW.type_id=2000000108 BEGIN SELECT RAISE(ABORT,'bid fixture failure'); END")
        self.conn.commit()
        before = list(self.conn.iterdump())
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'bid fixture failure'):
            seed.run(self.db, apply=True)
        self.assertEqual(list(self.conn.iterdump()), before)

    def test_incomplete_buy_schema_is_rejected_before_writes(self):
        self.native_hulls(JITA)
        self.conn.execute('ALTER TABLE seed_buy_orders DROP COLUMN initial_quantity')
        self.conn.commit()
        before = self.rows('seed_stock')
        with self.assertRaisesRegex(ValueError, 'seed_buy_orders missing'):
            seed.run(self.db, apply=True)
        self.assertEqual(self.rows('seed_stock'), before)


if __name__ == '__main__':
    unittest.main()
