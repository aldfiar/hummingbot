from pathlib import Path
from typing import Dict, Union

from hummingbot.client.config.client_config_adapter import ClientConfigAdapter
from hummingbot.client.config.config_helpers import (
    get_strategy_config_map,
    get_strategy_pydantic_config_cls,
    get_strategy_template_path,
    load_yml_into_cm_legacy,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.utility_methods import strategy_name_from_file
from hummingbot.client.config.validate import _load_yml_data_into_map
from hummingbot.client.config.yaml_utility import read_yml_file


async def load_strategy_config_map_from_file(yml_path: Path) -> Union[ClientConfigAdapter, Dict[str, ConfigVar]]:
    strategy_name = strategy_name_from_file(yml_path)
    config_cls = get_strategy_pydantic_config_cls(strategy_name)
    if config_cls is None:  # legacy
        config_map = get_strategy_config_map(strategy_name)
        template_path = get_strategy_template_path(strategy_name)
        await load_yml_into_cm_legacy(str(yml_path), str(template_path), config_map)
    else:
        config_data = read_yml_file(yml_path)
        hb_config = config_cls.construct()
        config_map = ClientConfigAdapter(hb_config)
        _load_yml_data_into_map(config_data, config_map)
    return config_map
