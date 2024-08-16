import contextlib
import inspect
import json
from pathlib import PureWindowsPath
from typing import Any, Dict, Generator, List, Optional, Tuple, Type, Union

import yaml
from pydantic import SecretStr, ValidationError, validate_model

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.client.config.config_traversal import ConfigTraversalItem
from hummingbot.client.config.validation_error import ConfigValidationError, retrieve_validation_error_msg


class ClientConfigAdapter:
    def __init__(self, hb_config: BaseClientModel):
        self._hb_config = hb_config

    def __getattr__(self, item):
        value = getattr(self._hb_config, item)
        if isinstance(value, BaseClientModel):
            value = ClientConfigAdapter(value)
        return value

    def __setattr__(self, key, value):
        if key == "_hb_config":
            super().__setattr__(key, value)
        else:
            try:
                self._hb_config.__setattr__(key, value)
            except ValidationError as e:
                raise ConfigValidationError(retrieve_validation_error_msg(e))

    def __repr__(self):
        return f"{self.__class__.__name__}.{self._hb_config.__repr__()}"

    def __eq__(self, other):
        if isinstance(other, ClientConfigAdapter):
            eq = self._hb_config.__eq__(other._hb_config)
        else:
            eq = super().__eq__(other)
        return eq

    @property
    def hb_config(self) -> BaseClientModel:
        return self._hb_config

    @property
    def title(self) -> str:
        return self._hb_config.Config.title

    def is_required(self, attr: str) -> bool:
        return self._hb_config.is_required(attr)

    def keys(self) -> Generator[str, None, None]:
        return self._hb_config.__fields__.keys()

    def config_paths(self) -> Generator[str, None, None]:
        return (traversal_item.config_path for traversal_item in self.traverse())

    def traverse(self, secure: bool = True) -> Generator[ConfigTraversalItem, None, None]:
        """The intended use for this function is to simplify config map traversals in the client code.

        If the field is missing, its value will be set to `None` and its printable value will be set to
        'MISSING_AND_REQUIRED'.
        """
        depth = 0
        for attr, field in self._hb_config.__fields__.items():
            field_info = field.field_info
            type_ = field.type_
            if hasattr(self, attr):
                value = getattr(self, attr)
                printable_value = self._get_printable_value(attr, value, secure)
                client_field_data = field_info.extra.get("client_data")
            else:
                value = None
                printable_value = "&cMISSING_AND_REQUIRED"
                client_field_data = self.get_client_data(attr)
            yield ConfigTraversalItem(
                depth=depth,
                config_path=attr,
                attr=attr,
                value=value,
                printable_value=printable_value,
                client_field_data=client_field_data,
                field_info=field_info,
                type_=type_,
            )
            if isinstance(value, ClientConfigAdapter):
                for traversal_item in value.traverse():
                    traversal_item.depth += 1
                    config_path = f"{attr}.{traversal_item.config_path}"
                    traversal_item.config_path = config_path
                    yield traversal_item

    async def get_client_prompt(self, attr_name: str) -> Optional[str]:
        prompt = None
        client_data = self.get_client_data(attr_name)
        if client_data is not None:
            prompt_fn = client_data.prompt
            if inspect.iscoroutinefunction(prompt_fn):
                prompt = await prompt_fn(self._hb_config)
            else:
                prompt = prompt_fn(self._hb_config)
        return prompt

    def is_secure(self, attr_name: str) -> bool:
        client_data = self.get_client_data(attr_name)
        secure = client_data is not None and client_data.is_secure
        return secure

    def get_client_data(self, attr_name: str) -> Optional[ClientFieldData]:
        return self._hb_config.__fields__[attr_name].field_info.extra.get("client_data")

    def get_description(self, attr_name: str) -> str:
        return self._hb_config.__fields__[attr_name].field_info.description

    def get_default(self, attr_name: str) -> Any:
        default = self._hb_config.__fields__[attr_name].field_info.default
        if isinstance(default, type(Ellipsis)):
            default = None
        return default

    def get_default_str_repr(self, attr_name: str) -> str:
        """Used to generate default strings for config prompts."""
        default = self.get_default(attr_name=attr_name)
        if default is None:
            default_str = ""
        elif isinstance(default, (List, Tuple)):
            default_str = ",".join(default)
        else:
            default_str = str(default)
        return default_str

    def get_type(self, attr_name: str) -> Type:
        return self._hb_config.__fields__[attr_name].type_

    def generate_yml_output_str_with_comments(self) -> str:
        fragments_with_comments = [self._generate_title()]
        self._add_model_fragments(fragments_with_comments)
        yml_str = "".join(fragments_with_comments)
        return yml_str

    def validate_model(self) -> List[str]:
        results = validate_model(type(self._hb_config), json.loads(self._hb_config.json()))
        conf_dict = results[0]
        self._decrypt_secrets(conf_dict)
        for key, value in conf_dict.items():
            self.setattr_no_validation(key, value)
        errors = results[2]
        validation_errors = []
        if errors is not None:
            errors = errors.errors()
            validation_errors = [
                f"{'.'.join(e['loc'])} - {e['msg']}"
                for e in errors
            ]
        return validation_errors

    def setattr_no_validation(self, attr: str, value: Any):
        with self._disable_validation():
            setattr(self, attr, value)

    @contextlib.contextmanager
    def _disable_validation(self):
        self._hb_config.Config.validate_assignment = False
        yield
        self._hb_config.Config.validate_assignment = True

    def _get_printable_value(self, attr: str, value: Any, secure: bool) -> str:
        if isinstance(value, ClientConfigAdapter):
            if self._is_union(self.get_type(attr)):  # it is a union of modes
                printable_value = value.hb_config.Config.title
            else:  # it is a collection of settings stored in a submodule
                printable_value = ""
        elif isinstance(value, SecretStr) and not secure:
            printable_value = value.get_secret_value()
        else:
            printable_value = str(value)
        return printable_value

    @staticmethod
    def _is_union(t: Type) -> bool:
        is_union = hasattr(t, "__origin__") and t.__origin__ == Union
        return is_union

    def _dict_in_conf_order(self) -> Dict[str, Any]:
        d = {}
        for attr in self._hb_config.__fields__.keys():
            value = getattr(self, attr)
            if isinstance(value, ClientConfigAdapter):
                value = value._dict_in_conf_order()
            d[attr] = value
        return d

    def _encrypt_secrets(self, conf_dict: Dict[str, Any]):
        from hummingbot.client.config.security import Security  # avoids circular import
        for attr, value in conf_dict.items():
            attr_type = self._hb_config.__fields__[attr].type_
            if attr_type == SecretStr:
                conf_dict[attr] = Security.secrets_manager.encrypt_secret_value(attr, value.get_secret_value())

    def _decrypt_secrets(self, conf_dict: Dict[str, Any]):
        from hummingbot.client.config.security import Security  # avoids circular import
        for attr, value in conf_dict.items():
            attr_type = self._hb_config.__fields__[attr].type_
            if attr_type == SecretStr:
                decrypted_value = Security.secrets_manager.decrypt_secret_value(attr, value.get_secret_value())
                conf_dict[attr] = SecretStr(decrypted_value)

    def _generate_title(self) -> str:
        title = f"{self._hb_config.Config.title}"
        title = self._adorn_title(title)
        return title

    @staticmethod
    def _adorn_title(title: str) -> str:
        if title:
            title = f"###   {title} config   ###"
            title_len = len(title)
            title = f"{'#' * title_len}\n{title}\n{'#' * title_len}"
        return title

    def _add_model_fragments(
        self,
        fragments_with_comments: List[str],
    ):

        fragments_with_comments.append("\n")
        first_level_conf_items_generator = (item for item in self.traverse() if item.depth == 0)

        for traversal_item in first_level_conf_items_generator:
            fragments_with_comments.append("\n")

            attr_comment = traversal_item.field_info.description
            if attr_comment is not None:
                comment_prefix = f"{' ' * 2 * traversal_item.depth}# "
                attr_comment = "\n".join(f"{comment_prefix}{c}" for c in attr_comment.split("\n"))
                fragments_with_comments.append(attr_comment)
                fragments_with_comments.append("\n")

            attribute = traversal_item.attr
            value = getattr(self, attribute)
            if isinstance(value, ClientConfigAdapter):
                value = value._dict_in_conf_order()
            if isinstance(traversal_item.value, PureWindowsPath):
                conf_as_dictionary = {attribute: traversal_item.printable_value}
            else:
                conf_as_dictionary = {attribute: value}
            self._encrypt_secrets(conf_as_dictionary)

            yaml_config = yaml.safe_dump(conf_as_dictionary, sort_keys=False)
            fragments_with_comments.append(yaml_config)


class ReadOnlyClientConfigAdapter(ClientConfigAdapter):
    def __setattr__(self, key, value):
        if key == "_hb_config":
            super().__setattr__(key, value)
        else:
            raise AttributeError("Cannot set an attribute on a read-only client adapter")

    @classmethod
    def lock_config(cls, config_map: Any):
        return cls(config_map._hb_config)
