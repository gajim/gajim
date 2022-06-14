# Copyright 2016 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

"""
Deletes unneeded DLLs and checks DLL dependencies.
"""

import subprocess
import os
import sys
from typing import Optional

import gi
gi.require_version("GIRepository", "2.0")
from gi.repository import GIRepository  # noqa: E402


def get_required_by_typelibs() -> set[str]:
    deps: set[str] = set()
    repo = GIRepository.Repository()
    for tl in os.listdir(repo.get_search_path()[0]):
        namespace, version = os.path.splitext(tl)[0].split("-", 1)
        repo.require(namespace, version, 0)
        lib = repo.get_shared_library(namespace)
        if lib:
            deps.update(lib.split(","))
    return deps


EXTENSIONS = [".exe", ".pyd", ".dll"]
SYSTEM_LIBS = [
    "advapi32.dll",
    "cabinet.dll", "comctl32.dll", "comdlg32.dll", "crypt32.dll", "d3d9.dll",
    "dnsapi.dll", "dsound.dll", "dwmapi.dll", "gdi32.dll", "imm32.dll",
    "iphlpapi.dll", "kernel32.dll", "ksuser.dll", "msi.dll", "msimg32.dll",
    "msvcr71.dll", "msvcr80.dll", "msvcrt.dll", "ole32.dll", "oleaut32.dll",
    "opengl32.dll", "rpcrt4.dll", "setupapi.dll", "shell32.dll", "user32.dll",
    "usp10.dll", "winmm.dll", "winspool.drv", "wldap32.dll", "ws2_32.dll",
    "wsock32.dll", "shlwapi.dll"
]


def get_dependencies(filename: str) -> list[str]:
    deps: list[str] = []
    try:
        data = subprocess.getoutput("objdump -p %s" % filename)
    except Exception as error:
        print(error)
        return deps

    for line in data.splitlines():
        line = line.strip()
        if line.startswith("DLL Name:"):
            deps.append(line.split(":", 1)[-1].strip().lower())
    return deps


def find_lib(root: str, name: str) -> Optional[str]:
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
                        print("MISSING:", path, lib)

    for lib in get_required_by_typelibs():
        needed.add(lib)
        if find_lib(root, lib) is None:
            print("MISSING:", lib)

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
            print("DELETE:", lib)
            os.unlink(lib)
        libs = get_things_to_delete(sys.prefix)


if __name__ == "__main__":
    main()
