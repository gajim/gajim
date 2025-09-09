#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
ICONS_DIR = REPO_DIR / "gajim" / "data" / "icons" / "hicolor" / "scalable" / "devices"


def convert_svg(input_path: Path, temp_path: Path) -> None:
    # https://wiki.inkscape.org/wiki/Action
    try:
        subprocess.check_output(
            [
                "inkscape",
                input_path,
                "--actions",
                "select-all;object-stroke-to-path",
                "--export-type=svg",
                "--export-plain-svg",
                f"--export-filename={temp_path}",
            ],
        )
    except Exception as e:
        print("Error:", e)
        sys.exit(1)


def clean_svg(temp_path: Path, output_path: Path) -> None:
    try:
        subprocess.check_output(
            [
                "scour",
                temp_path,
                output_path,
                "--strip-xml-prolog",
                "--no-line-breaks",
                "--enable-id-stripping",
            ],
        )
    except Exception as e:
        print("Error:", e)
        sys.exit(1)


def process_file(file_name: str) -> None:
    print("Processing", file_name)
    input_path = ICONS_DIR / file_name
    temp_path = ICONS_DIR / f"{file_name}-temp.svg"
    output_path = ICONS_DIR / f"lucide-{Path(file_name).stem}-symbolic.svg"

    convert_svg(input_path, temp_path)
    clean_svg(temp_path, output_path)

    # Remove temp file and original file
    temp_path.unlink()
    input_path.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    file_ = subparsers.add_parser("file", help="Process single file")
    file_.add_argument("file_name")

    all_files = subparsers.add_parser("all_files")
    args = parser.parse_args()

    if args.command == "all_files":
        for _root, _dirs, files in os.walk(ICONS_DIR):
            for file in sorted(files):
                file_path = Path(file)

                if not file_path.suffix == ".svg":
                    continue

                if file_path.stem.startswith("lucide") or file_path.stem.endswith(
                    "symbolic"
                ):
                    continue

                process_file(file)

    elif args.command == "file":
        process_file(args.file_name)
