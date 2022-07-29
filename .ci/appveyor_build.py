#!/usr/bin/env python3

from typing import Any

import json
import os
import requests
import time
from pathlib import Path

from rich.console import Console


ACCOUNT = 'lovetox'
PROJECT_SLUG = 'gajim'
BRANCH = 'master'
BASE_URL = 'https://ci.appveyor.com/api'
API_KEY = os.environ['APPVEYOR_API_KEY']
HEADERS = {'Authorization': f'Bearer {API_KEY}'}
RETRY_TIMEOUT = 2 * 60
INITIAL_START_DELAY = 20 * 60

SETTINGS_API_URL = f'{BASE_URL}/projects/{ACCOUNT}/{PROJECT_SLUG}/settings/yaml'
BUILDS_API_URL = f'{BASE_URL}/builds'
PROJECT_API_URL = f'{BASE_URL}/projects/{ACCOUNT}/{PROJECT_SLUG}'


console = Console()


def get_gajim_version() -> str:
    if os.environ.get('GAJIM_NIGHTLY_BUILD') is not None:
        return 'Nightly'

    tag = os.environ.get('CI_COMMIT_TAG')
    if tag is None:
        exit('No tag found')
    return tag


def push_yaml_to_project() -> None:
    console.print('Push settings ...')
    with open('.ci/appveyor.yml', 'r') as file:
        yaml = file.read()

    req = requests.put(SETTINGS_API_URL, data=yaml, headers=HEADERS)
    req.raise_for_status()


def start_build() -> str:
    console.print('Start build ...')
    payload = {
        'accountName': ACCOUNT,
        'projectSlug': PROJECT_SLUG,
        'branch': BRANCH,
        'commitId': os.environ['CI_COMMIT_SHA'],
        'environmentVariables': {
            'GAJIM_VERSION': get_gajim_version(),
        }
    }
    req = requests.post(BUILDS_API_URL, headers=HEADERS, json=payload)
    req.raise_for_status()
    response = req.json()
    return response['buildId']


def is_build_finished(build: dict[str, str]) -> bool:
    if build['status'] in ('failed', 'cancelled'):
        exit('Found failed job')

    return build['status'] == 'success'


def check_for_response(build_id: str) -> None:
    time.sleep(INITIAL_START_DELAY)
    while True:
        time.sleep(RETRY_TIMEOUT)

        console.print('Check build status ...')
        req = requests.get(PROJECT_API_URL, headers=HEADERS)
        req.raise_for_status()
        response = req.json()
        build = response['build']
        if build_id != build['buildId']:
            exit('Unable to find buildid: %s' % build_id)

        if is_build_finished(build):
            break

        console.print('Build status:', build['status'])

    build_folder = Path.cwd() / 'build'
    build_folder.mkdir()

    for job in build['jobs']:
        response = get_job_response(job['jobId'])
        result = build_folder / f'{job["jobId"]}.json'
        result.write_text(json.dumps(response))
        console.print('Write job response:', result)


def get_job_response(job_id: str) -> list[dict[str, Any]]:
    artifacts_api_url = f'{BASE_URL}/buildjobs/{job_id}/artifacts'
    req = requests.get(artifacts_api_url, headers=HEADERS)
    req.raise_for_status()
    response = req.json()

    for artifact in response:
        file_url = f'{artifacts_api_url}/{artifact["fileName"]}'
        artifact['fileUrl'] = file_url

    return response


if __name__ == '__main__':
    push_yaml_to_project()
    build_id = start_build()
    check_for_response(build_id)
