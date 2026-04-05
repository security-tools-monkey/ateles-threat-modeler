from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from jsonschema import Draft202012Validator

from .schema_loader import load_nsm_schema


def _type_name(value: Any) -> str:
    """Return a JSON-friendly type name for error messages."""
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
    """Merge multiple template dicts into one, preferring non-empty examples."""
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
    """Pick a representative list item template for array validation."""
    if not template_list:
        return None
    if all(isinstance(item, dict) for item in template_list):
        return _merge_dict_templates([item for item in template_list if isinstance(item, dict)])
    return template_list[0]


def _validate_value(value: Any, template: Any, path: str, errors: List[str]) -> None:
    """Validate a value against a template or JSON Schema-like fragment."""
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
    """Validate payload against the canonical NSM schema.

    Uses JSON Schema validation when the schema file is a JSON Schema,
    otherwise falls back to template-based validation.
    """
    schema_template = load_nsm_schema()
    if _is_json_schema(schema_template):
        validator = Draft202012Validator(schema_template)
        errors: List[str] = []
        for error in sorted(validator.iter_errors(payload), key=_error_sort_key):
            path = _format_error_path(error.path)
            if path:
                errors.append(f"{path} {error.message}")
            else:
                errors.append(error.message)
        return errors
    errors: List[str] = []
    _validate_value(payload, schema_template, "", errors)
    return errors


def _is_json_schema(schema: Dict[str, Any]) -> bool:
    """Detect whether a schema file is a JSON Schema (vs example template)."""
    if "$schema" in schema or "$defs" in schema:
        return True
    if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
        return True
    return False


def _error_sort_key(error) -> tuple:
    """Sort JSON Schema errors deterministically by path."""
    return tuple(str(item) for item in error.path)


def _format_error_path(path: Iterable[Any]) -> str:
    """Convert a JSON Schema error path into dotted/indexed form."""
    parts: List[str] = []
    for item in path:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            if parts:
                parts.append(f".{item}")
            else:
                parts.append(str(item))
    return "".join(parts)
