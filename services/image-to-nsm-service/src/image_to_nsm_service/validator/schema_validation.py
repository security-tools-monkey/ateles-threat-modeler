from __future__ import annotations

from typing import Any, Dict, List, Optional

from .schema_loader import load_nsm_schema


def _type_name(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    return "unknown"


def _merge_dict_templates(templates: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for template in templates:
        for key, value in template.items():
            if key not in merged:
                merged[key] = value
                continue
            existing = merged[key]
            if isinstance(existing, list) and isinstance(value, list):
                if not existing and value:
                    merged[key] = value
            elif isinstance(existing, dict) and isinstance(value, dict):
                if not existing and value:
                    merged[key] = value
    return merged


def _select_list_item_template(template_list: List[Any]) -> Optional[Any]:
    if not template_list:
        return None
    if all(isinstance(item, dict) for item in template_list):
        return _merge_dict_templates([item for item in template_list if isinstance(item, dict)])
    return template_list[0]


def _validate_value(value: Any, template: Any, path: str, errors: List[str]) -> None:
    if isinstance(template, dict):
        if not isinstance(value, dict):
            errors.append(f"{path} must be object")
            return
        for key, template_value in template.items():
            next_path = f"{path}.{key}" if path else key
            if key not in value:
                errors.append(f"{next_path} is required")
                continue
            if key == "properties":
                if not isinstance(value[key], dict):
                    errors.append(f"{next_path} must be object")
                continue
            _validate_value(value[key], template_value, next_path, errors)
        return

    if isinstance(template, list):
        if not isinstance(value, list):
            errors.append(f"{path} must be array")
            return
        item_template = _select_list_item_template(template)
        if item_template is None:
            return
        for index, item in enumerate(value):
            _validate_value(item, item_template, f"{path}[{index}]", errors)
        return

    if isinstance(template, bool):
        if not isinstance(value, bool):
            errors.append(f"{path} must be boolean")
        return

    if isinstance(template, (int, float)) and not isinstance(template, bool):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{path} must be number")
        return

    if isinstance(template, str):
        if not isinstance(value, str):
            errors.append(f"{path} must be string")
            return
        if path == "schema_version" and value != template:
            errors.append(f"{path} must be '{template}'")
        return


def validate_schema(payload: Dict[str, Any]) -> List[str]:
    schema_template = load_nsm_schema()
    errors: List[str] = []
    _validate_value(payload, schema_template, "", errors)
    return errors
