import json
import logging
import shutil
from collections import OrderedDict, defaultdict
from datetime import date, datetime, time
from decimal import Decimal
from os import listdir, unlink
from os.path import isfile, join
from pathlib import Path, PosixPath
from typing import Any, Callable, Dict, List, Optional, Union

import yaml
from pydantic.main import ModelMetaclass
from yaml import SafeDumper

from hummingbot import get_strategy_list, root_path
from hummingbot.client.config.client_config_adapter import ClientConfigAdapter
from hummingbot.client.config.client_config_map import CommandShortcutModel
from hummingbot.client.config.config_data_types import ClientConfigEnum
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map, init_fee_overrides_config
from hummingbot.client.config.utility_methods import strategy_name_from_file
from hummingbot.client.config.yaml_utility import save_to_yml, yaml_parser
from hummingbot.client.settings import (
    CLIENT_CONFIG_PATH,
    CONF_DIR_PATH,
    CONF_POSTFIX,
    CONF_PREFIX,
    STRATEGIES_CONF_DIR_PATH,
    TEMPLATE_PATH,
    TRADE_FEES_CONFIG_PATH,
    AllConnectorSettings,
)

# Use ruamel.yaml to preserve order and comments in .yml file


def decimal_representer(dumper: SafeDumper, data: Decimal):
    return dumper.represent_float(float(data))


def enum_representer(dumper: SafeDumper, data: ClientConfigEnum):
    return dumper.represent_str(str(data))


def date_representer(dumper: SafeDumper, data: date):
    return dumper.represent_date(data)


def time_representer(dumper: SafeDumper, data: time):
    return dumper.represent_str(data.strftime("%H:%M:%S"))


def datetime_representer(dumper: SafeDumper, data: datetime):
    return dumper.represent_datetime(data)


def path_representer(dumper: SafeDumper, data: Path):
    return dumper.represent_str(str(data))


def command_shortcut_representer(dumper: SafeDumper, data: CommandShortcutModel):
    return dumper.represent_dict(data.__dict__)


yaml.add_representer(
    data_type=Decimal, representer=decimal_representer, Dumper=SafeDumper
)
yaml.add_multi_representer(
    data_type=ClientConfigEnum, multi_representer=enum_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=date, representer=date_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=time, representer=time_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=datetime, representer=datetime_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=Path, representer=path_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=PosixPath, representer=path_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=CommandShortcutModel, representer=command_shortcut_representer, Dumper=SafeDumper
)


def parse_cvar_value(cvar: ConfigVar, value: Any) -> Any:
    """
    Based on the target type specified in `ConfigVar.type_str`, parses a string value into the target type.
    :param cvar: ConfigVar object
    :param value: User input from running session or from saved `yml` files. Type is usually string.
    :return: value in the correct type
    """
    if value is None:
        return None
    elif cvar.type == 'str':
        return str(value)
    elif cvar.type == 'list':
        if isinstance(value, str):
            if len(value) == 0:
                return []
            filtered: filter = filter(lambda x: x not in ['[', ']', '"', "'"], list(value))
            value = "".join(filtered).split(",")  # create csv and generate list
            return [s.strip() for s in value]  # remove leading and trailing whitespaces
        else:
            return value
    elif cvar.type == 'json':
        if isinstance(value, str):
            value_json = value.replace("'", '"')  # replace single quotes with double quotes for valid JSON
            cvar_value = json.loads(value_json)
        else:
            cvar_value = value
        return cvar_json_migration(cvar, cvar_value)
    elif cvar.type == 'float':
        try:
            return float(value)
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not valid float.", exc_info=True)
            return value
    elif cvar.type == 'decimal':
        try:
            return Decimal(str(value))
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not valid decimal.", exc_info=True)
            return value
    elif cvar.type == 'int':
        try:
            return int(value)
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not an integer.", exc_info=True)
            return value
    elif cvar.type == 'bool':
        if isinstance(value, str) and value.lower() in ["true", "yes", "y"]:
            return True
        elif isinstance(value, str) and value.lower() in ["false", "no", "n"]:
            return False
        else:
            return value
    else:
        raise TypeError


def cvar_json_migration(cvar: ConfigVar, cvar_value: Any) -> Any:
    """
    A special function to migrate json config variable when its json type changes, for paper_trade_account_balance
    and min_quote_order_amount (deprecated), they were List but change to Dict.
    """
    if cvar.key in ("paper_trade_account_balance", "min_quote_order_amount") and isinstance(cvar_value, List):
        results = {}
        for item in cvar_value:
            results[item[0]] = item[1]
        return results
    return cvar_value


def parse_cvar_default_value_prompt(cvar: ConfigVar) -> str:
    """
    :param cvar: ConfigVar object
    :return: text for default value prompt
    """
    if cvar.default is None:
        default = ""
    elif callable(cvar.default):
        default = cvar.default()
    elif cvar.type == 'bool' and isinstance(cvar.prompt, str) and "Yes/No" in cvar.prompt:
        default = "Yes" if cvar.default else "No"
    else:
        default = str(cvar.default)
    if isinstance(default, Decimal):
        default = "{0:.4f}".format(default)
    return default


async def copy_strategy_template(strategy: str) -> str:
    """
    Look up template `.yml` file for a particular strategy in `hummingbot/templates` and copy it to the `conf` folder.
    The file name is `conf_{STRATEGY}_strategy_{INDEX}.yml`
    :return: The newly created file name
    """
    old_path = get_strategy_template_path(strategy)
    i = 0
    new_fname = f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml"
    new_path = STRATEGIES_CONF_DIR_PATH / new_fname
    while isfile(new_path):
        new_fname = f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml"
        new_path = STRATEGIES_CONF_DIR_PATH / new_fname
        i += 1
    shutil.copy(old_path, new_path)
    return new_fname


def get_strategy_template_path(strategy: str) -> Path:
    """
    Given the strategy name, return its template config `yml` file name.
    """
    return TEMPLATE_PATH / f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_TEMPLATE.yml"


def _merge_dicts(*args: Dict[str, ConfigVar]) -> OrderedDict:
    """
    Helper function to merge a few dictionaries into an ordered dictionary.
    """
    result: OrderedDict[any] = OrderedDict()
    for d in args:
        result.update(d)
    return result


def get_connector_class(connector_name: str) -> Callable:
    conn_setting = AllConnectorSettings.get_connector_settings()[connector_name]
    mod = __import__(conn_setting.module_path(),
                     fromlist=[conn_setting.class_name()])
    return getattr(mod, conn_setting.class_name())


def get_strategy_config_map(
    strategy: str
) -> Optional[Union[ClientConfigAdapter, Dict[str, ConfigVar]]]:
    """
    Given the name of a strategy, find and load strategy-specific config map.
    """
    try:
        config_cls = get_strategy_pydantic_config_cls(strategy)
        if config_cls is None:  # legacy
            cm_key = f"{strategy}_config_map"
            strategy_module = __import__(f"hummingbot.strategy.{strategy}.{cm_key}",
                                         fromlist=[f"hummingbot.strategy.{strategy}"])
            config_map = getattr(strategy_module, cm_key)
        else:
            hb_config = config_cls.construct()
            config_map = ClientConfigAdapter(hb_config)
    except Exception:
        config_map = defaultdict()
    return config_map


def get_strategy_starter_file(strategy: str) -> Callable:
    """
    Given the name of a strategy, find and load the `start` function in
    `hummingbot/strategy/{STRATEGY_NAME}/start.py` file.
    """
    if strategy is None:
        return lambda: None
    try:
        strategy_module = __import__(f"hummingbot.strategy.{strategy}.start",
                                     fromlist=[f"hummingbot.strategy.{strategy}"])
        return getattr(strategy_module, "start")
    except Exception as e:
        logging.getLogger().error(e, exc_info=True)


def validate_strategy_file(file_path: Path) -> Optional[str]:
    if not isfile(file_path):
        return f"{file_path} file does not exist."
    strategy = strategy_name_from_file(file_path)
    if strategy is None:
        return "Invalid configuration file or 'strategy' field is missing."
    if strategy not in get_strategy_list():
        return "Invalid strategy specified in the file."
    return None


def get_strategy_pydantic_config_cls(strategy_name: str) -> Optional[ModelMetaclass]:
    pydantic_cm_class = None
    try:
        pydantic_cm_pkg = f"{strategy_name}_config_map_pydantic"
        pydantic_cm_path = root_path() / "hummingbot" / "strategy" / strategy_name / f"{pydantic_cm_pkg}.py"
        if pydantic_cm_path.exists():
            pydantic_cm_class_name = f"{''.join([s.capitalize() for s in strategy_name.split('_')])}ConfigMap"
            pydantic_cm_mod = __import__(f"hummingbot.strategy.{strategy_name}.{pydantic_cm_pkg}",
                                         fromlist=[f"{pydantic_cm_class_name}"])
            pydantic_cm_class = getattr(pydantic_cm_mod, pydantic_cm_class_name)
    except ImportError:
        logging.getLogger().exception(f"Could not import Pydantic configs for {strategy_name}.")
    return pydantic_cm_class


async def load_yml_into_cm_legacy(yml_path: str, template_file_path: str, cm: Dict[str, ConfigVar]):
    try:
        data = {}
        conf_version = -1
        if isfile(yml_path):
            with open(yml_path, encoding="utf-8") as stream:
                data = yaml_parser.load(stream) or {}
                conf_version = data.get("template_version", 0)

        with open(template_file_path, "r", encoding="utf-8") as template_fd:
            template_data = yaml_parser.load(template_fd)
            template_version = template_data.get("template_version", 0)

        for key in template_data:
            if key in {"template_version"}:
                continue

            cvar = cm.get(key)
            if cvar is None:
                logging.getLogger().error(f"Cannot find corresponding config to key {key} in template.")
                continue

            if cvar.is_secure:
                raise DeprecationWarning("Secure values are no longer supported in legacy configs.")

            val_in_file = data.get(key, None)
            if (val_in_file is None or val_in_file == "") and cvar.default is not None:
                cvar.value = cvar.default
                continue

            # Todo: the proper process should be first validate the value then assign it
            cvar.value = parse_cvar_value(cvar, val_in_file)
            if cvar.value is not None:
                err_msg = await cvar.validate(str(cvar.value))
                if err_msg is not None:
                    # Instead of raising an exception, simply skip over this variable and wait till the user is prompted
                    logging.getLogger().error(
                        "Invalid value %s for config variable %s: %s" % (val_in_file, cvar.key, err_msg)
                    )
                    cvar.value = None

        if conf_version < template_version:
            # delete old config file
            if isfile(yml_path):
                unlink(yml_path)
            # copy the new file template
            shutil.copy(template_file_path, yml_path)
            # save the old variables into the new config file
            save_to_yml_legacy(yml_path, cm)
    except Exception as e:
        logging.getLogger().error("Error loading configs. Your config file may be corrupt. %s" % (e,),
                                  exc_info=True)


async def read_system_configs_from_yml():
    """
    Read global config and selected strategy yml files and save the values to corresponding config map
    If a yml file is outdated, it gets reformatted with the new template
    """
    await load_yml_into_cm_legacy(
        str(TRADE_FEES_CONFIG_PATH), str(TEMPLATE_PATH / "conf_fee_overrides_TEMPLATE.yml"), fee_overrides_config_map
    )
    # In case config maps get updated (due to default values)
    save_system_configs_to_yml()


def save_system_configs_to_yml():
    save_to_yml_legacy(str(TRADE_FEES_CONFIG_PATH), fee_overrides_config_map)


async def refresh_trade_fees_config(client_config_map: Any):
    """
    Refresh the trade fees config, after new connectors have been added (e.g. gateway connectors).
    """
    init_fee_overrides_config()
    save_to_yml(CLIENT_CONFIG_PATH, client_config_map)
    save_to_yml_legacy(str(TRADE_FEES_CONFIG_PATH), fee_overrides_config_map)


def save_to_yml_legacy(yml_path: str, cm: Dict[str, ConfigVar]):
    """
    Write current config saved a single config map into each a single yml file
    """
    try:
        with open(yml_path, encoding="utf-8") as stream:
            data = yaml_parser.load(stream) or {}
            for key in cm:
                cvar = cm.get(key)
                if type(cvar.value) == Decimal:
                    data[key] = float(cvar.value)
                else:
                    data[key] = cvar.value
            with open(yml_path, "w+", encoding="utf-8") as outfile:
                yaml_parser.dump(data, outfile)
    except Exception as e:
        logging.getLogger().error("Error writing configs: %s" % (str(e),), exc_info=True)


def write_config_to_yml(
    strategy_config_map: Union[Any, Dict],
    strategy_file_name: str,
    client_config_map: Any,
):
    strategy_file_path = Path(STRATEGIES_CONF_DIR_PATH) / strategy_file_name
    save_to_yml(strategy_file_path, strategy_config_map)
    save_to_yml(CLIENT_CONFIG_PATH, client_config_map)


async def create_yml_files_legacy():
    """
    Copy `hummingbot_logs.yml` and `conf_global.yml` templates to the `conf` directory on start up
    """
    for fname in listdir(TEMPLATE_PATH):
        if "_TEMPLATE" in fname and CONF_POSTFIX not in fname:
            stripped_fname = fname.replace("_TEMPLATE", "")
            template_path = str(TEMPLATE_PATH / fname)
            conf_path = join(CONF_DIR_PATH, stripped_fname)
            if not isfile(conf_path):
                shutil.copy(template_path, conf_path)

            # Only overwrite log config. Updating `conf_global.yml` is handled by `read_configs_from_yml`
            if conf_path.endswith("hummingbot_logs.yml"):
                with open(template_path, "r", encoding="utf-8") as template_fd:
                    template_data = yaml_parser.load(template_fd)
                    template_version = template_data.get("template_version", 0)
                with open(conf_path, "r", encoding="utf-8") as conf_fd:
                    conf_version = 0
                    try:
                        conf_data = yaml_parser.load(conf_fd)
                        conf_version = conf_data.get("template_version", 0)
                    except Exception:
                        pass
                if conf_version < template_version:
                    shutil.copy(template_path, conf_path)


def default_strategy_file_path(strategy: str) -> str:
    """
    Find the next available file name.
    :return: a default file name - `conf_{short_strategy}_{INDEX}.yml` e.g. 'conf_pure_mm_1.yml'
    """
    i = 1
    new_fname = f"{CONF_PREFIX}{short_strategy_name(strategy)}_{i}.yml"
    new_path = STRATEGIES_CONF_DIR_PATH / new_fname
    while new_path.is_file():
        new_fname = f"{CONF_PREFIX}{short_strategy_name(strategy)}_{i}.yml"
        new_path = STRATEGIES_CONF_DIR_PATH / new_fname
        i += 1
    return new_fname


def short_strategy_name(strategy: str) -> str:
    if strategy == "pure_market_making":
        return "pure_mm"
    elif strategy == "cross_exchange_market_making":
        return "xemm"
    elif strategy == "arbitrage":
        return "arb"
    else:
        return strategy


def all_configs_complete(strategy_config: Union[Any, Dict], client_config_map: Any):
    strategy_valid = (
        config_map_complete_legacy(strategy_config)
        if isinstance(strategy_config, Dict)
        else len(strategy_config.validate_model()) == 0
    )
    client_config_valid = len(client_config_map.validate_model()) == 0
    return client_config_valid and strategy_valid


def config_map_complete_legacy(config_map):
    return not any(c.required and c.value is None for c in config_map.values())


def missing_required_configs_legacy(config_map):
    return [c for c in config_map.values() if c.required and c.value is None and not c.is_connect_key]


def format_config_file_name(file_name):
    if "." not in file_name:
        return file_name + ".yml"
    return file_name


def parse_config_default_to_text(config: ConfigVar) -> str:
    """
    :param config: ConfigVar object
    :return: text for default value prompt
    """
    if config.default is None:
        default = ""
    elif callable(config.default):
        default = config.default()
    elif config.type == 'bool' and isinstance(config.prompt, str) and "Yes/No" in config.prompt:
        default = "Yes" if config.default else "No"
    else:
        default = str(config.default)
    if isinstance(default, Decimal):
        default = "{0:.4f}".format(default)
    return default


def save_previous_strategy_value(file_name: str, client_config_map: Any):
    client_config_map.previous_strategy = file_name
    save_to_yml(CLIENT_CONFIG_PATH, client_config_map)
