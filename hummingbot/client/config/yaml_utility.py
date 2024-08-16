import logging
from os import scandir
from os.path import isfile
from pathlib import Path
from typing import Any, Dict, List

import ruamel.yaml
import yaml
from pydantic import SecretStr

from hummingbot.client.settings import CONNECTORS_CONF_DIR_PATH

yaml_parser = ruamel.yaml.YAML()  # legacy


def api_keys_from_connector_config_map(cm: Any) -> Dict[str, str]:
    api_keys = {}
    for c in cm.traverse():
        if c.value is not None and c.client_field_data is not None and c.client_field_data.is_connect_key:
            value = c.value.get_secret_value() if isinstance(c.value, SecretStr) else c.value
            api_keys[c.attr] = value
    return api_keys


def list_connector_configs() -> List[Path]:
    connector_configs = [
        Path(f.path) for f in scandir(str(CONNECTORS_CONF_DIR_PATH))
        if f.is_file() and not f.name.startswith("_") and not f.name.startswith(".")
    ]
    return connector_configs


async def load_yml_into_dict(yml_path: str) -> Dict[str, Any]:
    data = {}
    if isfile(yml_path):
        with open(yml_path, encoding="utf-8") as stream:
            data = yaml_parser.load(stream) or {}

    return dict(data.items())


async def save_yml_from_dict(yml_path: str, conf_dict: Dict[str, Any]):
    try:
        with open(yml_path, "w+", encoding="utf-8") as stream:
            data = yaml_parser.load(stream) or {}
            for key in conf_dict:
                data[key] = conf_dict.get(key)
            with open(yml_path, "w+", encoding="utf-8") as outfile:
                yaml_parser.dump(data, outfile)
    except Exception as e:
        logging.getLogger().error(f"Error writing configs: {str(e)}", exc_info=True)


def save_to_yml(yml_path: Path, cm: Any):
    try:
        cm_yml_str = cm.generate_yml_output_str_with_comments()
        with open(yml_path, "w", encoding="utf-8") as outfile:
            outfile.write(cm_yml_str)
    except Exception as e:
        logging.getLogger().error("Error writing configs: %s" % (str(e),), exc_info=True)


def read_yml_file(yml_path: Path) -> Dict[str, Any]:
    with open(yml_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return dict(data)
