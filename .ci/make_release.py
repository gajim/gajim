#!/usr/bin/env python

from __future__ import annotations

import argparse
import logging

from gitlab import Gitlab
from gitlab.v4.objects import Project

logging.basicConfig(level='INFO', format='%(levelname)s: %(message)s')
log = logging.getLogger()


GITLAB_INSTANCE_URL = 'https://dev.gajim.org'
PROJECT_ID = 31


def adjust_milestones(project: Project, version: str) -> None:
    log.info('Rename Milestone: Next Release -> %s', version)
    milestones = project.milestones.list(title='Next Release', get_all=True)
    assert isinstance(milestones, list)
    milestone = milestones[0]
    milestone.title = version
    milestone.save()

    log.info('Create Milestone: Next Release')
    project.milestones.create({'title': 'Next Release'})


def create_release(project: Project, version: str) -> None:
    log.info('Create Release: %s', version)
    project.releases.create({
        'name': version,
        'tag_name': version,
        'milestones': [version],
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Make Gitlab Release')
    parser.add_argument('version', type=str, help='The new version string')
    parser.add_argument('token', type=str, help='The API token')
    args = parser.parse_args()

    api = Gitlab(GITLAB_INSTANCE_URL, private_token=args.token)
    api.auth()
    project = api.projects.get(PROJECT_ID)

    adjust_milestones(project, args.version)
    create_release(project, args.version)
