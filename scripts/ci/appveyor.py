#!/usr/bin/env python3

import os
import requests

webhook_key = os.environ['APPVEYOR_WEBHOOK_KEY']
branch = os.environ['CI_COMMIT_BRANCH']

url = f'https://ci.appveyor.com/api/git/webhook?id={webhook_key}'
ref = f'refs/heads/{branch}'

with open('appveyor.yml', 'r') as file:
    yaml = file.read()

payload = {
    'ref': ref,
    'repository': {'name': 'Gajim'},
    'config': yaml
}

req = requests.post(url, json=payload)
req.raise_for_status()
