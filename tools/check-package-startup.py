"""Initialize a packaged mod in an isolated Node process without booting the server."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

PROBE = r'''
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const runtime = path.resolve(process.argv[1]);
const mod = path.resolve(process.argv[2]);
process.chdir(path.join(runtime, "server"));
const state = require(path.join(mod, "install.js")).install(runtime, mod);
assert.equal(state.active, true);
assert.equal(state.handshakeReady, false);
const fleet = require(path.join(mod, "fleet.json"));
const visuals = require(path.join(mod, "visual-resources.json"));
console.log(JSON.stringify({version: fleet.version, ships: fleet.ships.length,
  visualResources: Object.keys(visuals.files).length,
  nativeModInitialization: "PASS", serverStarted: false}));
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--runtime", type=Path, required=True, help="Compatible EveJS runtime folder, read only")
    args = parser.parse_args()
    with zipfile.ZipFile(args.package) as archive:
        headers = {name: json.loads(archive.read(name)) for name in
                   ("evejs-launcher.mod.json", "fleet.json", "visual-resources.json")}
        versions = {name: data["version"] for name, data in headers.items()}
        if len(set(versions.values())) != 1:
            parser.exit(1, "Package version mismatch: " + json.dumps(versions) + "\n")
        if archive.testzip() is not None:
            parser.exit(1, "ZIP integrity check failed\n")
        with tempfile.TemporaryDirectory(prefix="hauler-startup-check-") as directory:
            target = Path(directory).resolve()
            assert target.parent == Path(tempfile.gettempdir()).resolve()
            for entry in archive.infolist():
                destination = (target / entry.filename).resolve()
                if not destination.is_relative_to(target):
                    parser.exit(1, "Package entry escapes extraction folder\n")
            archive.extractall(target)
            assert (target / "loader.js.disabled").is_file()
            subprocess.run(["node", "-e", PROBE, str(args.runtime.resolve()), str(target)], check=True)


if __name__ == "__main__":
    main()
