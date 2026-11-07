# Changelog

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
