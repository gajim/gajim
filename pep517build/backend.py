from __future__ import annotations

from typing import Any

import logging
import subprocess
from pathlib import Path

import setuptools.build_meta as _orig

logging.basicConfig(level='INFO', format='%(message)s')

ALLOWED_CONFIG_SETTINGS = {'target'}


def build_translations() -> None:
    # Compile translation files and place them into "gajim/data/locale"

    source_dir = Path.cwd()
    translation_dir = source_dir / 'po'
    locale_dir = source_dir / 'gajim' / 'data' / 'locale'

    langs = sorted([lang.stem for lang in translation_dir.glob('*.po')])

    for lang in langs:
        po_file = source_dir / 'po' / f'{lang}.po'
        mo_file = locale_dir / lang / 'LC_MESSAGES' / 'gajim.mo'
        mo_file.parent.mkdir(parents=True, exist_ok=True)

        logging.info('Compile %s >> %s', po_file, mo_file)

        subprocess.run(['msgfmt',
                        str(po_file),
                        '-o',
                        str(mo_file)],
                       check=True)


def _check_config_settings(config_settings: dict[str, str]) -> None:
    settings = set(config_settings.keys()) - ALLOWED_CONFIG_SETTINGS
    if settings:
        raise ValueError('Unknown config setting %s' % settings)


def get_requires_for_build_sdist(*args: Any, **kwargs: Any) -> list[str]:
    return _orig.get_requires_for_build_sdist(*args, **kwargs)


def build_sdist(*args: Any, **kwargs: Any) -> str:
    return _orig.build_sdist(*args, **kwargs)


def get_requires_for_build_wheel(*args: Any, **kwargs: Any) -> list[str]:
    return _orig.get_requires_for_build_wheel(*args, **kwargs)


def prepare_metadata_for_build_wheel(*args: Any, **kwargs: Any) -> str:
    return _orig.prepare_metadata_for_build_wheel(*args, **kwargs)


def build_wheel(wheel_directory: str,
                config_settings: dict[str, str] | None = None,
                metadata_directory: str | None = None
                ) -> str:

    if config_settings is not None:
        _check_config_settings(config_settings)

    build_translations()

    basename = _orig.build_wheel(
        wheel_directory,
        config_settings=config_settings,
        metadata_directory=metadata_directory,
    )

    return basename


def build_editable(*args: Any, **kwargs: Any) -> str:
    return build_wheel(*args, **kwargs)


def get_requires_for_build_editable(*args: Any, **kwargs: Any) -> list[str]:
    return get_requires_for_build_wheel(*args, **kwargs)


def prepare_metadata_for_build_editable(*args: Any, **kwargs: Any) -> str:
    return prepare_metadata_for_build_wheel(*args, **kwargs)
