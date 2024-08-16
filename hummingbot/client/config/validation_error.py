from pydantic import ValidationError


class ConfigValidationError(Exception):
    pass


def retrieve_validation_error_msg(e: ValidationError) -> str:
    return e.errors().pop()["msg"]
