# Copyright 2016 Christoph Reiter
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Deletes unneeded DLLs and checks DLL dependencies.

from typing import cast

import logging
import os
import subprocess
import sys
from functools import cache
from multiprocessing import Process
from multiprocessing import Queue

import gi

gi.require_version("GIRepository", "3.0")
from gi.repository import GIRepository  # noqa: E402
from gi.repository import GLib  # noqa: E402

logging.basicConfig(level="INFO", format="%(levelname)s: %(message)s")
log = logging.getLogger()

IGNORED_LIBS = [("Soup", "2.4"), ("Gtk", "3.0")]

LibrariesDataT = tuple[list[str] | None, Exception | None]


def _get_shared_libraries(
    q: "Queue[LibrariesDataT]", namespace: str, version: str
) -> None:
    try:
        repo = GIRepository.Repository()
        repo.require(namespace, version, 0)  # type: ignore
        libs = cast(list[str], repo.get_shared_libraries(namespace))  # type: ignore
    except Exception as e:
        q.put((None, e))
    else:
        q.put((libs, None))


@cache
def get_shared_libraries(namespace: str, version: str) -> list[str] | None:
    # we have to start a new process because multiple versions can't be loaded
    # in the same process
    q: "Queue[LibrariesDataT]" = Queue()
    p = Process(target=_get_shared_libraries, args=(q, namespace, version))
    p.start()
    libs, error = q.get()
    p.join()
    if error is not None:
        raise error
    return libs


def get_required_by_typelibs() -> set[tuple[str, str, str]]:
    deps: set[tuple[str, str, str]] = set()
    repo = GIRepository.Repository()
    for tl in os.listdir(repo.get_search_path()[0]):
        namespace, version = os.path.splitext(tl)[0].split("-", 1)
        if (namespace, version) in IGNORED_LIBS:
            continue

        try:
            libs = get_shared_libraries(namespace, version)
        except GLib.Error as e:
            # g-i fails to load itself with a different version
            if "GIRepository" in e.message and "2.0" in e.message:
                continue
            else:
                raise

        if libs is None:
            continue

        for lib in libs:
            deps.add((namespace, version, lib))
    return deps


@cache
def get_dependencies(filename: str) -> list[str]:
    deps: list[str] = []
    try:
        data = subprocess.check_output(
            ["objdump", "-p", filename], stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError:
        # can happen with wrong arch binaries
        return []
    data = data.decode("utf-8")
    for line in data.splitlines():
        line = line.strip()
        if line.startswith("DLL Name:"):
            deps.append(line.split(":", 1)[-1].strip().lower())
    return deps


def find_lib(root: str, name: str) -> bool:
    system_search_path = os.path.join("C:", os.sep, "Windows", "System32")
    if get_lib_path(root, name):
        return True
    elif os.path.exists(os.path.join(system_search_path, name)):
        return True
    elif name in ["gdiplus.dll"]:
        return True
    elif name.startswith("msvcr"):
        return True
    elif name.startswith("api-ms-win-"):
        return True
    return False


def get_lib_path(root: str, name: str) -> str | None:
    search_path = os.path.join(root, "bin")
    if os.path.exists(os.path.join(search_path, name)):
        return os.path.join(search_path, name)


def get_things_to_delete(root: str) -> list[str]:
    extensions = [".exe", ".pyd", ".dll"]

    all_libs: set[str] = set()
    needed: set[str] = set()
    for base, _, files in os.walk(root):
        for f in files:
            lib = f.lower()
            path = os.path.join(base, f)
            ext_lower = os.path.splitext(f)[-1].lower()
            if ext_lower in extensions:
                if ext_lower == ".exe":
                    # we use .exe as dependency root
                    needed.add(lib)
                all_libs.add(f.lower())
                for lib in get_dependencies(path):
                    all_libs.add(lib)
                    needed.add(lib)
                    if not find_lib(root, lib):
                        print("MISSING:", path, lib)

    for namespace, version, lib in get_required_by_typelibs():
        all_libs.add(lib)
        needed.add(lib)
        if not find_lib(root, lib):
            print("MISSING:", namespace, version, lib)

    to_delete: list[str] = []
    for not_depended_on in all_libs - needed:
        path = get_lib_path(root, not_depended_on)
        if path:
            to_delete.append(path)

    return to_delete


def main() -> None:
    libs = get_things_to_delete(sys.prefix)
    while libs:
        for lib in libs:
            log.info("DELETE: %s", lib)
            os.unlink(lib)
        libs = get_things_to_delete(sys.prefix)


if __name__ == "__main__":
    main()
