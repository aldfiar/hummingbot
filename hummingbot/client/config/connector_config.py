from pathlib import Path

from hummingbot.client.config.client_config_adapter import ClientConfigAdapter
from hummingbot.client.config.utility_methods import connector_name_from_file, get_connector_hb_config
from hummingbot.client.config.validate import _load_yml_data_into_map
from hummingbot.client.config.yaml_utility import read_yml_file


def load_connector_config_map_from_file(yml_path: Path) -> ClientConfigAdapter:
    config_data = read_yml_file(yml_path)
    connector_name = connector_name_from_file(yml_path)
    hb_config = get_connector_hb_config(connector_name)
    config_map = ClientConfigAdapter(hb_config)
    _load_yml_data_into_map(config_data, config_map)
    return config_map
