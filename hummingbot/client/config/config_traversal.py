from dataclasses import dataclass
from typing import Any, Optional, Type

from pydantic.fields import FieldInfo

from hummingbot.client.config.config_data_types import ClientFieldData


@dataclass()
class ConfigTraversalItem:
    depth: int
    config_path: str
    attr: str
    value: Any
    printable_value: str
    client_field_data: Optional[ClientFieldData]
    field_info: FieldInfo
    type_: Type
