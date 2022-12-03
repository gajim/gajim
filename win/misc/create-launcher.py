#!/usr/bin/env python

# Copyright 2016 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# Creates simple Python .exe launchers for gui and cli apps
#
# ./create-launcher.py "1.4.0" <target-dir>


import os
import sys
import subprocess
import shlex
import tempfile
import shutil
import struct


def build_resource(rc_path: str, out_path: str) -> None:
    '''Raises subprocess.CalledProcessError'''

    def is_64bit():
        return struct.calcsize('P') == 8

    subprocess.check_call(
        ['windres', '-O', 'coff', '-F',
         'pe-x86-64' if is_64bit() else 'pe-i386', rc_path,
         '-o', out_path])


def get_build_args() -> list[str]:
    python_name = os.path.splitext(os.path.basename(sys.executable))[0]
    python_config = os.path.join(
        os.path.dirname(sys.executable), python_name + '-config')

    cflags = subprocess.check_output(
        ['sh', python_config, '--cflags']).strip()
    libs = subprocess.check_output(
        ['sh', python_config, '--libs']).strip()

    cflags = os.fsdecode(cflags)
    libs = os.fsdecode(libs)
    return shlex.split(cflags) + shlex.split(libs)


def build_exe(source_path: str,
              resource_path: str,
              out_path: str,
              *,
              is_gui: bool) -> None:

    args = ['gcc', '-s']
    if is_gui:
        args.append('-mwindows')
    args.extend(['-o', out_path, source_path, resource_path])
    args.extend(get_build_args())
    subprocess.check_call(args)


def get_launcher_code(*, debug: bool) -> str:
    template = '''\
#include "Python.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>


int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                   LPSTR lpCmdLine, int nCmdShow)
{
    int result;
    LPWSTR *szArglist;
    int nArgs;

    szArglist = CommandLineToArgvW(GetCommandLineW(), &nArgs);
    if( NULL == szArglist )
    {
      printf("CommandLineToArgvW failed");
      return 0;
    }

    Py_NoUserSiteDirectory = 1;
    Py_IgnoreEnvironmentFlag = 1;
    Py_DontWriteBytecodeFlag = 1;
    Py_FrozenFlag = 1;
    Py_Initialize();
    PySys_SetArgvEx(__argc, szArglist, 0);
    result = PyRun_SimpleString(
        "import sys; import os;"
        "os.environ['GAJIM_DEBUG'] = '%s';"
        "sys.frozen=True;"
        "from pathlib import Path;"
        "root_path = Path(sys.executable).parents[1];"
        "from ctypes import windll;"
        "windll.kernel32.SetDllDirectoryW(str(root_path / 'bin'));"
        "from gajim import gajim;"
        "gajim.main();");
    Py_Finalize();
    return result;
}
    ''' % int(debug)

    return template


def get_resouce_code(filename: str,
                     file_version: str,
                     file_desc: str,
                     icon_path: str,
                     product_name: str,
                     product_version: str,
                     company_name: str) -> str:

    template = '''\
1 ICON "%(icon_path)s"
1 VERSIONINFO
FILEVERSION     %(file_version_list)s
PRODUCTVERSION  %(product_version_list)s
FILEOS 0x4
FILETYPE 0x1
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904E4"
        BEGIN
            VALUE "CompanyName",      "%(company_name)s"
            VALUE "FileDescription",  "%(file_desc)s"
            VALUE "FileVersion",      "%(file_version)s"
            VALUE "InternalName",     "%(internal_name)s"
            VALUE "OriginalFilename", "%(filename)s"
            VALUE "ProductName",      "%(product_name)s"
            VALUE "ProductVersion",   "%(product_version)s"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x409, 1252
    END
END
'''

    def to_ver_list(v: str) -> str:
        v = v.split('-')[0]
        return ','.join(map(str, (list(map(int, v.split('.'))) + [0] * 4)[:4]))

    file_version_list = to_ver_list(file_version)
    product_version_list = to_ver_list(product_version)

    return template % {
        'icon_path': icon_path, 'file_version_list': file_version_list,
        'product_version_list': product_version_list,
        'file_version': file_version, 'product_version': product_version,
        'company_name': company_name, 'filename': filename,
        'internal_name': os.path.splitext(filename)[0],
        'product_name': product_name, 'file_desc': file_desc,
    }


def build_launcher(out_path: str,
                   icon_path: str,
                   file_desc: str,
                   product_name: str,
                   product_version: str,
                   company_name: str,
                   *,
                   is_gui: bool,
                   debug: bool) -> None:

    src_ico = os.path.abspath(icon_path)
    target = os.path.abspath(out_path)

    file_version = product_version

    dir_ = os.getcwd()
    temp = tempfile.mkdtemp()
    try:
        os.chdir(temp)
        with open('launcher.c', 'w') as h:
            h.write(get_launcher_code(debug=debug))
        shutil.copyfile(src_ico, 'launcher.ico')
        with open('launcher.rc', 'w') as h:
            h.write(get_resouce_code(
                os.path.basename(target), file_version, file_desc,
                'launcher.ico', product_name, product_version, company_name))

        build_resource('launcher.rc', 'launcher.res')
        build_exe('launcher.c', 'launcher.res', target, is_gui=is_gui)
    finally:
        os.chdir(dir_)
        shutil.rmtree(temp)


def main() -> None:
    argv = sys.argv

    version = argv[1]
    target = argv[2]

    company_name = 'Gajim'
    misc = os.path.dirname(os.path.realpath(__file__))

    build_launcher(
        os.path.join(target, 'Gajim.exe'),
        os.path.join(misc, 'gajim.ico'), 'Gajim', 'Gajim',
        version, company_name, is_gui=True, debug=False)

    build_launcher(
        os.path.join(target, 'Gajim-Debug.exe'),
        os.path.join(misc, 'gajim.ico'), 'Gajim', 'Gajim',
        version, company_name, is_gui=False, debug=True)

    # build_launcher(
    #     os.path.join(target, "history_manager.exe"),
    #     os.path.join(misc, "gajim.ico"), "History Manager", "History Manager",
    #     version, company_name, 'history_manager.py', True)


if __name__ == '__main__':
    main()
