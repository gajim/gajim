#!/usr/bin/env python3

from typing import Optional

import json
import logging
import sys
from urllib.request import urlopen

import ruamel.yaml

PYPI_INDEX = 'https://pypi.org/pypi'

YAML = ruamel.yaml.YAML()
YAML.indent(mapping=2, sequence=4, offset=2)
YAML.preserve_quotes = True

logging.basicConfig(level='INFO', format='%(levelname)s: %(message)s')

def get_package_type(module: ruamel.yaml.comments.CommentedMap) -> str:
    url = module['sources'][0]['url']
    if '.whl' in url:
        return 'bdist_wheel'
    return 'sdist'

def get_current_version(module: ruamel.yaml.comments.CommentedMap
                        ) -> Optional[str]:
    name = module['name'].replace('python3-','')
    url = module['sources'][0]['url']
    if url.endswith('.git'):
        return None
    file_name = url.split('/')[-1]
    file_name = file_name.replace(name, '')
    return file_name.split('-')[1].replace('.tar.gz', '')

def get_latest_version(package_name: str,
                       package_type: str
                       ) -> tuple[str, Optional[str]]:
    with urlopen(f'{PYPI_INDEX}/{package_name}/json') as f:
        data = f.read()
        d = json.loads(data)
        version = d['info']['version']
        sha = None
        for entry in d['releases'][version]:
            if entry['packagetype'] == package_type:
                if sha is not None:
                    return version, None
                sha = entry['digests']['sha256']
        return version, sha

def update_module(module: ruamel.yaml.comments.CommentedMap) -> None:
    if not module['name'].startswith('python3-'):
        logging.warning('Check %s manually', module['name'])
        return

    package_type = get_package_type(module)
    current_version = get_current_version(module)
    if current_version is None:
        return

    name = module['name'].replace('python3-','')
    latest_version, sha = get_latest_version(name, package_type)

    if current_version == latest_version:
        return

    if 'only-arches' in module:
        logging.warning('Update %s manually', module['name'])
        return

    if sha is None:
        logging.warning('Could not get a unique SHA sum for %s', module['name'])
        return

    module['build-commands'][0] = module['build-commands'][0].replace(
        current_version, latest_version)
    module['sources'][0]['url'] = module['sources'][0]['url'].replace(
        current_version, latest_version)
    module['sources'][0]['sha256'] = sha

def update_modules(data) -> None:
    for module in data['modules']:
        if isinstance(module, ruamel.yaml.comments.CommentedMap):
            update_module(module)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Input yaml file is missing')

    try:
        with open(sys.argv[1]) as f:
            data = YAML.load(f)
    except (FileNotFoundError,
            ruamel.yaml.parser.ParserError,
            ruamel.yaml.scanner.ScannerError
            ) as error:
        sys.exit(error)

    update_modules(data)

    with open(sys.argv[1], 'w') as f:
        YAML.dump(data, f)
