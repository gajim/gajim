#!/usr/bin/env python3

import io
import requests
import shutil
import subprocess
import zipfile
from pathlib import Path

from rich.console import Console

console = Console()


PLUGINS = [
    'plugin_installer',
]

PLUGINS_BASE_URL = 'https://ftp.gajim.org'
PLUGINS_FOLDER = Path('./gajim/data/plugins')


def get_plugins_url(plugin: str) -> str:
    return f'{PLUGINS_BASE_URL}/plugins_master_zip/{plugin}.zip'


def extraxt_zip(zip_bytes: bytes, path: Path) -> None:
    console.print('Extract to', path)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_file:
        zip_file.extractall(path)


def download_plugins() -> None:
    PLUGINS_FOLDER.mkdir(parents=True)
    for plugin in PLUGINS:
        url = get_plugins_url(plugin)
        console.print('Download', url)
        req = requests.get(url)
        req.raise_for_status()
        extraxt_zip(req.content, PLUGINS_FOLDER)


def setup() -> None:
    console.print('Setup')
    subprocess.call(['python3', 'setup.py', 'sdist'])


def cleanup() -> None:
    console.print('Cleanup')
    shutil.rmtree(PLUGINS_FOLDER)


if __name__ == '__main__':
    download_plugins()
    setup()
    cleanup()
