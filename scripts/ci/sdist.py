#!/usr/bin/env python3

import io
import zipfile
import subprocess
import shutil
from pathlib import Path
import requests

PLUGINS = [
    'plugin_installer',
]

PLUGINS_BASE_URL = 'https://ftp.gajim.org'
PLUGINS_FOLDER = Path('./gajim/data/plugins')


def get_plugins_url(plugin):
    return f'{PLUGINS_BASE_URL}/plugins_master_zip/{plugin}.zip'


def extraxt_zip(zip_bytes, path):
    print('Extract to', path)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_file:
        zip_file.extractall(path)


def download_plugins():
    PLUGINS_FOLDER.mkdir(parents=True)
    for plugin in PLUGINS:
        url = get_plugins_url(plugin)
        print('Download', url)
        req = requests.get(url)
        req.raise_for_status()
        extraxt_zip(req.content, PLUGINS_FOLDER)


def setup():
    print('Setup')
    subprocess.call(['python3', 'setup.py', 'sdist'])


def cleanup():
    print('Cleanup')
    shutil.rmtree(PLUGINS_FOLDER)


download_plugins()
setup()
cleanup()
