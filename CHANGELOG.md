# Changelog

## 0.5.2

- Added low-profile upper and lower turret seats to Tithe’s original hull and aligned the native `locator_turret_1a` / `locator_turret_1b` pair with them. Both visual seats serve the existing single turret hardpoint.
- Moved the lower seat onto a clear forward belly panel to avoid the adjacent hull step. Removed unused locator groups inherited from Bestower.
- Preserved the existing hull geometry, UVs, materials, textures, icons, fitting stats, IDs and five native engine exhausts. Rebuilt all seven mesh LODs.

Validated offline with the stock Dual Light Pulse Laser: both mounted weapon meshes clear the hull, locator frames have the correct outward axis, and all 245 exhaust-clearance rays pass. Native BLACK readback confirms that every field outside the turret locator list is unchanged. Live turret tracking and firing still need an in-game check.

## 0.5.1

- Replaced Tithe’s Bestower-based appearance with the approved original Amarr hull, including its ivory armour, unequal stepped gold inlays inspired by Sigil, recessed panels and detailed underside.
- Matched the previous Tithe’s length: approximately 696 client units. The new hull is approximately 204 wide and 168 high; proportions are preserved.
- Rebound native Amarr flight and warp exhausts to five actual nozzle openings. Retained the animated heat-glow shader and native audio/damage controllers, and repositioned turret mounts and navigation lights for the new hull.
- Added seven native mesh LODs and updated all seven Tithe inventory, BPO/BPC and Ship Tree images. Mastery tint and opacity remain controlled by the client.
- Rebuilt Tithe’s cockpit with level glazing, aligned frames and a fitted gold brow. Filled the open space beneath the upper armour with a closed pressure hull joined to the lower body. Kept the accepted icon framing and engine bindings.
- Added restrained panel seams, small service markings and subtle roughness variation only to thirteen large empty underbody faces, retaining the original black gunmetal and existing detailing. Corrected faulty shading normals at the under-armour transition without changing the hull’s shape.
- Preserved all ship IDs, fitting, cargo, skills, blueprints and Mastery profiles, and all other ships’ assets. Includes the three gas transports from 0.5.0.

Validated offline: native GR2/DDS/BLACK readback, seven mesh LODs, five unobstructed exhaust outlets (245 clearance rays), stock booster resources and animation parameters, and package resource hashes. The user confirmed working engine animation in EVE. The latest cockpit, closed-hull, local underbody detailing and shading refinements have been reviewed through native-file studio renders; their in-game visual check remains pending.

## 0.5.0

- Added Anemos (Gallente), Vesper (Amarr) and Sable (Caldari), with the supplied English descriptions.
- Added a 30,000 m³ dedicated Gas Hold, scaling to 45,000 m³ at racial Hauler V, plus 500 m³ regular cargo. Each racial Hauler level grants 5% maximum velocity.
- Included the approved models with stock hull coatings, seven native LODs, original skeletons and animations, BPO/BPC and inventory icons, and neutral Ship Tree sprites. The client applies Mastery tint and opacity.
- Corrected Vesper's forward pipe joint and moved Anemos attachments to match its extended hull.
- Added native Mastery profiles inherited from Epithal, Sigil and Badger, plus T1 blueprints supporting manufacturing, copying and material/time research.
- Extended both market modes to all twelve custom ships. Gas prices follow Epithal on each order side; locations follow their own base hulls. Hardcore mode supports Gallente NPC Epithal blueprint sellers.
- Expanded the catalog and login payload to 24 item types and 185 verified visual resources. Existing ship IDs and visual assets remain unchanged.

Validated offline: 48 native server fitting cases, twelve Solo Progression/Drone Class Balance cases, native Python 2 client lookup/effect/blueprint APIs, signed login composition, all twelve Mastery profiles at I–V, and 29 market tests. Game-native model/DDS readback and all eight retained texture mips passed. The three gas ships still need a live in-game visual and cargo check before being described as in-game verified.

## 0.4.4

- Fixed missing NPC BUY orders in market setup. Normal mode now adds BUY demand at the selected selling locations when the corresponding original hull or BPO has a seeded BUY order there.
- BUY prices follow the Gallente analog's BUY offers separately from SELL prices. If the analog has no BUY offers, the script uses its SELL price and the original item's BUY/SELL price ratio.
- Existing 0.4.3 markets can be repaired by running `Market-Normal.cmd` again after updating. Existing SELL prices and stock are preserved; repeat runs preserve remaining quantities on both sides.
- Blueprint BUY orders are added only when the original BPO has them. Hardcore remains restricted to BPOs and removes the mod's seeded hull SELL and BUY orders; player orders and unrelated NPC orders are preserved.
- Updated the reports, summary caches and English/Russian instructions to cover both order sides.

Validated with 27 market-tool tests and both native login checks. On a temporary copy of the configured market file, the repair added 45 BUY orders at 5,731,458.35 ISK while preserving all 90 existing SELL offers. Repeated application, Jita-only selection, hardcore switching and SQLite integrity checks passed.

## 0.4.3

- Added market setup scripts to the mod installation ZIP. Double-click `Market-Normal.cmd` or `Market-Hardcore.cmd` in the installed mod folder; the database path is resolved from that server's Market configuration.
- Normal mode adds ships and blueprints at the existing selling locations of their original hulls. Jita-only markets stay Jita-only; multiple hubs and galaxy-wide distributions follow the original sellers.
- Hardcore mode adds BPOs only at existing original BPO sellers owned by NPC corporations of the ship's faction. A bundled station ownership reference identifies the eligible factions.
- Prices follow Miasmos, Kryos and Epithal by specialization: local seeded price first, database-wide median next, then the analog's catalog base price with a note if no seeded offers exist.
- Repeat runs preserve purchases, remaining quantities and prices at retained locations. Mode changes update only this mod's seeded sell offers; player orders and other items are preserved. Mod market summaries are refreshed in the same transaction.
- Included step-by-step English and Russian instructions and a detailed guide. Market seeding remains an explicit action after stopping the Market service; installing or enabling the mod does not seed stock automatically.

Requires Python 3.11 or newer for market setup. Validated with 20 market-tool tests, including both Windows launchers, a temporary copy of the configured market file, and a 3,000-station distribution check. The native login compatibility checks from 0.4.2 also pass.

## 0.4.2

- Fixed GamePort login for headless clients, including WC. A missing or unsuccessful client catalog receipt no longer causes the mod to reject native login with `LoginAuthFailed`.
- Kept client catalog reports as diagnostics. The EVE client still receives the ship catalog during login.
- Updated the Launcher manifest and package metadata to 0.4.2.

Validated against EveJS 261028.1's native handshake with empty, unsuccessful and successful catalog responses. The installed 0.4.2 package was also confirmed working in-game by the user.

This release includes all nine ships, blueprints, models, icons and native Mastery profiles. Automatic market stock seeding is not included.
