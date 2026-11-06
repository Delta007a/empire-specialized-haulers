"""Build a local Launcher ZIP from the release code and verified local art."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent.parent
PACKAGE_FILES = (
    "README.md",
    "catalog.js",
    "client-bootstrap.py",
    "client-catalog.py",
    "evejs-launcher.mod.json",
    "fleet.json",
    "install.js",
    "loader.js.disabled",
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


def build(source, output):
    manifest = read_json(ROOT / "visual-resources.json")
    local = read_json(source / "visual-resources.json")
    if any(local[key] != manifest[key] for key in ("version", "build", "hulls", "files")):
        raise ValueError("The local resource manifest does not match this release.")

    output.parent.mkdir(parents=True, exist_ok=True)
    stream = output.open("xb")
    try:
        with stream, ZipFile(stream, "w", ZIP_DEFLATED, compresslevel=1) as package:
            for name in PACKAGE_FILES:
                package.write(ROOT / name, name)
            for uri, entry in manifest["files"].items():
                scheme, relative = resource_path(uri)
                destination = PurePosixPath(manifest["roots"][scheme]) / relative
                if destination.is_absolute() or ".." in destination.parts or destination.parts[0] != "art":
                    raise ValueError(f"Invalid package path: {destination}")
                data = (source / local["roots"][scheme] / relative).read_bytes()
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
    version = read_json(ROOT / "evejs-launcher.mod.json")["version"]
    output = args.output or ROOT / "dist" / f"EmpireSpecializedHaulers-{version}-local.zip"
    try:
        build(args.source.resolve(), output.resolve())
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Cannot build local package: {error}\n")


if __name__ == "__main__":
    main()
