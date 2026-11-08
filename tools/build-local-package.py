"""Build a local Launcher ZIP from the release code and verified local art."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent.parent
WOLVERINE_BLACK = "eh40:/ci2_w2/ci2_w2.black"
WOLVERINE_GEOMETRY = "eh40:/ci2_w2/ci2_w2.gr2"
LEGACY_WOLVERINE = {
    WOLVERINE_BLACK: "wolfrt2:/ci2_w2.black",
    WOLVERINE_GEOMETRY: "wolfrt2:/dx9/model/ship/caldari/hauler/ci2/ci2_w2.gr2",
}
LEGACY_BLACK_SHA256 = "d9f4ec4297be2205c902b3de9776e6f98f9734fe4323596b723a623752a18f3e"
PACKAGE_FILES = (
    "README.md",
    "CHANGELOG.md",
    "MARKET-SETUP.md",
    "MARKET-SETUP-RU.txt",
    "Market-Normal.cmd",
    "Market-Hardcore.cmd",
    "tools/seed-market.py",
    "tools/run-market.cmd",
    "tools/market-npc-stations.json",
    "tools/MARKET-SEED.md",
    "catalog.js",
    "client-bootstrap.py",
    "client-catalog.py",
    "evejs-launcher.mod.json",
    "fleet.json",
    "install.js",
    "loader.js",
    "login-contract.json",
    "login-envelope.js",
    "visual-resources.json",
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resource_path(uri):
    match = re.fullmatch(r"([a-z0-9]+):/([a-zA-Z0-9_./-]+)", uri)
    if not match:
        raise ValueError(f"Invalid resource URI: {uri}")
    scheme, relative = match.groups()
    if any(part in ("", ".", "..") for part in relative.split("/")):
        raise ValueError(f"Invalid resource path: {uri}")
    return scheme, relative


def relocate_wolverine_black(data):
    if hashlib.sha256(data).hexdigest() != LEGACY_BLACK_SHA256:
        raise ValueError("Unknown source for Wolverine's legacy BLACK resource.")
    magic, version, table_length, count = struct.unpack_from("<IIIH", data)
    end = 12 + table_length
    strings = data[14:end].split(b"\0")
    legacy_path = LEGACY_WOLVERINE[WOLVERINE_GEOMETRY].encode("ascii")
    if (magic, version) != (0xB1ACF11E, 1) or not 14 < end < len(data):
        raise ValueError("Invalid BLACK header.")
    if strings[0] != b"EveSOFDataHull" or len(strings) != count + 1 or strings[-1] != b"":
        raise ValueError("Invalid BLACK string table.")
    if strings.count(legacy_path) != 1:
        raise ValueError("Wolverine's original geometry reference is ambiguous.")
    strings[strings.index(legacy_path)] = WOLVERINE_GEOMETRY.encode("ascii")
    table = b"\0".join(strings)
    # String indices and the serialized object stream remain identical.
    return data[:8] + struct.pack("<IH", len(table) + 2, count) + table + data[end:]


def read_asset(source, manifest, uri):
    source_uri = uri
    if uri not in manifest["files"]:
        source_uri = LEGACY_WOLVERINE.get(uri, uri)
        if source_uri not in manifest["files"]:
            raise ValueError(f"Local resource is missing: {uri}")
    scheme, relative = resource_path(source_uri)
    data = (source / manifest["roots"][scheme] / relative).read_bytes()
    if uri == WOLVERINE_BLACK and source_uri != uri:
        return relocate_wolverine_black(data)
    return data


def build(source, output):
    manifest = read_json(ROOT / "visual-resources.json")
    fleet = read_json(ROOT / "fleet.json")
    metadata = read_json(ROOT / "evejs-launcher.mod.json")
    versions = {
        "evejs-launcher.mod.json": metadata["version"],
        "fleet.json": fleet["version"],
        "visual-resources.json": manifest["version"],
    }
    if len(set(versions.values())) != 1:
        details = ", ".join(f"{name}={version}" for name, version in versions.items())
        raise ValueError(f"Release version mismatch: {details}")
    if fleet["clientBuild"] != manifest["build"]:
        raise ValueError("Fleet and visual resources target different EVE client builds.")
    local = read_json(source / "visual-resources.json")
    if local["build"] != manifest["build"]:
        raise ValueError("The local resource manifest targets a different client build.")

    output.parent.mkdir(parents=True, exist_ok=True)
    stream = output.open("xb")
    try:
        with stream, ZipFile(stream, "w", ZIP_DEFLATED, compresslevel=1) as package:
            for name in PACKAGE_FILES:
                target = "loader.js.disabled" if name == "loader.js" else name
                package.write(ROOT / name, target)
            for uri, entry in manifest["files"].items():
                scheme, relative = resource_path(uri)
                destination = PurePosixPath(manifest["roots"][scheme]) / relative
                if destination.is_absolute() or ".." in destination.parts or destination.parts[0] != "art":
                    raise ValueError(f"Invalid package path: {destination}")
                data = read_asset(source, local, uri)
                if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                    raise ValueError(f"Local resource size or SHA-256 differs: {uri}")
                package.writestr(destination.as_posix(), data)
    except BaseException:
        output.unlink()
        raise
    print(f"Built {output} with {len(manifest['files'])} verified resources.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Local mod folder with the matching visual manifest")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = read_json(ROOT / "evejs-launcher.mod.json")
    filename = manifest["updates"]["asset"].replace("{version}", manifest["version"])
    output = args.output or ROOT / "dist" / filename
    try:
        build(args.source.resolve(), output.resolve())
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Cannot build local package: {error}\n")


if __name__ == "__main__":
    main()
