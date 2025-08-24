#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
ICONS_DIR = REPO_DIR / "gajim" / "data" / "icons" / "hicolor" / "scalable" / "devices"


def convert_svg(input_path: Path, temp_path: Path) -> None:
    try:
        subprocess.check_output(
            [
                "inkscape",
                input_path,
                "--actions",
                "select-all;object-to-path",
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file_name")
    args = parser.parse_args()

    input_path = ICONS_DIR / args.file_name
    temp_path = ICONS_DIR / f"{args.file_name}-temp.svg"
    output_path = ICONS_DIR / f"lucide-{Path(args.file_name).stem}-symbolic.svg"

    convert_svg(input_path, temp_path)
    clean_svg(temp_path, output_path)

    # Remove temp file and original file
    temp_path.unlink()
    input_path.unlink()
