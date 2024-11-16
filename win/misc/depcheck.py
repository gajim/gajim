# Copyright 2016 Christoph Reiter
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Deletes unneeded DLLs and checks DLL dependencies.

import logging
import os
import subprocess
import sys

import gi

gi.require_version("GIRepository", "2.0")
from gi.repository import GIRepository  # noqa: E402

logging.basicConfig(level="INFO", format="%(levelname)s: %(message)s")
log = logging.getLogger()

IGNORED_LIBS = [("Soup", "2.4"), ("Gtk", "4.0")]


def get_required_by_typelibs() -> set[str]:
    deps: set[str] = set()
    repo = GIRepository.Repository()
    for tl in os.listdir(repo.get_search_path()[0]):
        namespace, version = os.path.splitext(tl)[0].split("-", 1)
        if (namespace, version) in IGNORED_LIBS:
            continue
        try:
            repo.require(namespace, version, 0)  # pyright: ignore
        except Exception as error:
            log.warning("Unable to load %s %s: %s", namespace, version, error)
            continue
        lib = repo.get_shared_library(namespace)
        if lib:
            deps.update(lib.split(","))
    return deps


EXTENSIONS = [".exe", ".pyd", ".dll"]
SYSTEM_LIBS = [
    "advapi32.dll",
    "cabinet.dll",
    "comctl32.dll",
    "comdlg32.dll",
    "crypt32.dll",
    "d3d9.dll",
    "dnsapi.dll",
    "dsound.dll",
    "dwmapi.dll",
    "gdi32.dll",
    "imm32.dll",
    "iphlpapi.dll",
    "kernel32.dll",
    "ksuser.dll",
    "msi.dll",
    "msimg32.dll",
    "msvcr71.dll",
    "msvcr80.dll",
    "msvcrt.dll",
    "ole32.dll",
    "oleaut32.dll",
    "opengl32.dll",
    "rpcrt4.dll",
    "setupapi.dll",
    "shell32.dll",
    "user32.dll",
    "usp10.dll",
    "winmm.dll",
    "winspool.drv",
    "wldap32.dll",
    "ws2_32.dll",
    "wsock32.dll",
    "shlwapi.dll",
]


def get_dependencies(filename: str) -> list[str]:
    deps: list[str] = []
    try:
        data = subprocess.getoutput("objdump -p %s" % filename)
    except Exception as error:
        log.error(error)
        return deps

    for line in data.splitlines():
        line = line.strip()
        if line.startswith("DLL Name:"):
            deps.append(line.split(":", 1)[-1].strip().lower())
    return deps


def find_lib(root: str, name: str) -> str | None:
    search_path = os.path.join(root, "bin")
    if os.path.exists(os.path.join(search_path, name)):
        return os.path.join(search_path, name)
    elif name in SYSTEM_LIBS:
        return name


def get_things_to_delete(root: str) -> list[str]:
    all_libs: set[str] = set()
    needed: set[str] = set()
    for base, _, files in os.walk(root):
        for f in files:
            path = os.path.join(base, f)
            if os.path.splitext(path)[-1].lower() in EXTENSIONS:
                all_libs.add(f.lower())
                for lib in get_dependencies(path):
                    all_libs.add(lib)
                    needed.add(lib)
                    if find_lib(root, lib) is None:
                        log.info("MISSING: %s %s", path, lib)

    for lib in get_required_by_typelibs():
        needed.add(lib)
        if find_lib(root, lib) is None:
            log.info("MISSING: %s", lib)

    result: list[str] = []
    libs = all_libs - needed
    for lib in libs:
        _, ext = os.path.splitext(lib)
        if ext == ".exe":
            continue

        name = find_lib(root, lib)
        if name is None:
            continue

        result.append(name)

    return result


def main() -> None:
    libs = get_things_to_delete(sys.prefix)
    while libs:
        for lib in libs:
            log.info("DELETE: %s", lib)
            os.unlink(lib)
        libs = get_things_to_delete(sys.prefix)


if __name__ == "__main__":
    main()
