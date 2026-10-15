"""Build complete, link-free producer payloads. This never touches a project."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat


class MaterializeError(ValueError):
    pass


def relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise MaterializeError("expected a nonempty relative path without control characters")
    parts = value.split("/")
    if value.startswith("/") or any(part in ("", ".", "..") for part in parts):
        raise MaterializeError(f"unsafe relative path: {value!r}")
    return PurePosixPath(value)


def copy_entry(source: Path, destination: Path, boundary: Path, ancestors: frozenset[Path]) -> None:
    try:
        resolved = source.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise MaterializeError(f"dangling or cyclic source link: {source}") from error
    if not resolved.is_relative_to(boundary):
        raise MaterializeError(f"source link escapes declared tree: {source}")
    mode = resolved.stat().st_mode
    if stat.S_ISREG(mode):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(resolved, destination)
        destination.chmod(stat.S_IMODE(mode) & 0o777)
    elif stat.S_ISDIR(mode):
        if resolved in ancestors:
            raise MaterializeError(f"cyclic source directory: {source}")
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(resolved.iterdir()):
            copy_entry(child, destination / child.name, boundary, ancestors | {resolved})
        destination.chmod((stat.S_IMODE(mode) & 0o777) | 0o700)
    else:
        raise MaterializeError(f"special source file is unsupported: {source}")


def materialize(files: dict[str, str], skills: dict[str, str], output: Path) -> None:
    if not isinstance(files, dict) or not isinstance(skills, dict):
        raise MaterializeError("files and skills must be objects")
    destinations = {key: relative_path(key) for key in files}
    for first in destinations:
        for second in destinations:
            if first != second and second.startswith(first + "/"):
                raise MaterializeError(f"overlapping destinations: {first}, {second}")
    if output.is_symlink() or (output.exists() and any(output.iterdir())):
        raise MaterializeError("output must be an empty, real directory")
    output.mkdir(parents=True, exist_ok=True)
    for name, relative in sorted(destinations.items()):
        source = Path(files[name])
        if not source.is_absolute() or source.is_symlink():
            raise MaterializeError(f"source must be an absolute non-symlink root: {source}")
        try:
            boundary = source.resolve(strict=True)
        except OSError as error:
            raise MaterializeError(f"source does not exist: {source}") from error
        copy_entry(source, output / relative, boundary, frozenset())
    for name, path in skills.items():
        root = output / relative_path(path)
        if not root.is_dir() or not (root / "SKILL.md").is_file():
            raise MaterializeError(f"skill {name} is missing its directory or SKILL.md: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", required=True, type=Path)
    parser.add_argument("--skills", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        materialize(json.loads(args.files.read_text()), json.loads(args.skills.read_text()), args.output)
    except (MaterializeError, OSError, ValueError) as error:
        parser.exit(1, f"agent-env-nix: {error}\n")


if __name__ == "__main__":
    main()
