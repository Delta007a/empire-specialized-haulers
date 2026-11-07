# Add the ships to your market

Requires **Python 3.11 or newer** and an existing market database.

1. **Stop the Market service.** If it runs in a separate console, press **Ctrl+C** in that console.
2. Open your EveJS server folder, then **mods → empire-specialized-haulers**.
3. Double-click **one** file:

   | File | Result |
   | --- | --- |
   | `Market-Normal.cmd` | Ships and blueprints at the existing selling locations of their original hulls. A Jita-only market stays Jita-only. |
   | `Market-Hardcore.cmd` | Blueprints only, at existing original BPO sellers owned by NPC corporations of the ship's faction. |

4. Wait for **`APPLIED normal`** or **`APPLIED hardcore`**, followed by **`Finished successfully`**. Press any key to close the window.
5. **Start the Market service again**, then open the market in EVE.

**You do not need to enter a database path or type commands.** Run one mode; running the other changes the mod's seeded supply to that mode.

The script reads `storage.database_path` from this server's `externalservices/market-server/config/market-server.local.toml`. Without that config, it uses `externalservices/market-server/data/generated/market.sqlite`. The mod and its `tools` folder must remain under this server's `mods/empire-specialized-haulers` folder; a shortcut to a `.cmd` file is fine.

If Python is missing, install Python 3.11 or newer from python.org, enable **Add python.exe to PATH** if offered, and run the `.cmd` file again. If the database is missing, generate your market file first. If the database is locked, stop Market before retrying. The console stays open so you can read any error.

Repeat runs preserve purchases, remaining quantities, existing prices and player orders. After regenerating the market database, run the desired mode again.

See [the detailed guide](tools/MARKET-SEED.md) for pricing, station mapping and optional command-line controls, or [the Russian step-by-step instructions](MARKET-SETUP-RU.txt).
