from typing import Any, Dict, List


def _load_yml_data_into_map(yml_data: Dict[str, Any], cm: Any) -> List[str]:
    for key in cm.keys():
        if key in yml_data:
            cm.setattr_no_validation(key, yml_data[key])

    config_validation_errors = cm.validate_model()  # try coercing values to appropriate type
    return config_validation_errors
