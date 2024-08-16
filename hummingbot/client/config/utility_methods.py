from pathlib import Path
from typing import Any

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.config.yaml_utility import read_yml_file
from hummingbot.client.settings import CONNECTORS_CONF_DIR_PATH, AllConnectorSettings


def strategy_name_from_file(file_path: Path) -> str:
    data = read_yml_file(file_path)
    strategy = data.get("strategy")
    return strategy


def connector_name_from_file(file_path: Path) -> str:
    data = read_yml_file(file_path)
    connector = data["connector"]
    return connector


def get_connector_config_yml_path(connector_name: str) -> Path:
    connector_path = Path(CONNECTORS_CONF_DIR_PATH) / f"{connector_name}.yml"
    return connector_path


def get_connector_hb_config(connector_name: str) -> BaseClientModel:
    hb_config = AllConnectorSettings.get_connector_config_keys(connector_name)
    return hb_config


def reset_connector_hb_config(connector_name: str):
    AllConnectorSettings.reset_connector_config_keys(connector_name)


def update_connector_hb_config(connector_config: Any):
    AllConnectorSettings.update_connector_config_keys(connector_config.hb_config)
