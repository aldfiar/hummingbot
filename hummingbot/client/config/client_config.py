from typing import Any

from hummingbot.client.config.validate import _load_yml_data_into_map
from hummingbot.client.config.validation_error import ConfigValidationError
from hummingbot.client.config.yaml_utility import read_yml_file, save_to_yml
from hummingbot.client.settings import CLIENT_CONFIG_PATH


def load_client_config_map_from_file() -> Any:
    from hummingbot.client.config.client_config_map import ClientConfigMap
    yml_path = CLIENT_CONFIG_PATH
    if yml_path.exists():
        config_data = read_yml_file(yml_path)
    else:
        config_data = {}
    client_config = ClientConfigMap()
    from hummingbot.client.config.client_config_adapter import ClientConfigAdapter
    config_map = ClientConfigAdapter(client_config)
    config_validation_errors = _load_yml_data_into_map(config_data, config_map)

    if len(config_validation_errors) > 0:
        all_errors = "\n".join(config_validation_errors)
        raise ConfigValidationError(f"There are errors in the client global configuration (\n{all_errors})")
    save_to_yml(yml_path, config_map)

    return config_map
