import json
from typing import Any


PREPARE_RESULT_FIELDS = (
    "reference_codebases",
    "reference_paths",
    "reference_papers",
)


def parse_prepare_result(output_text: str) -> dict[str, list[str]]:
    """Parse and validate the structured output returned by the Prepare Agent."""
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError("Prepare Agent returned an empty response.")

    decoder = json.JSONDecoder()
    parsed: Any = None
    for index, character in enumerate(output_text):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(output_text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            parsed = candidate
            break

    if parsed is None:
        raise ValueError("Prepare Agent response does not contain a valid JSON object.")

    validated: dict[str, list[str]] = {}
    for field in PREPARE_RESULT_FIELDS:
        value = parsed.get(field)
        if not isinstance(value, list) or not value:
            raise ValueError(
                f"Prepare Agent response field '{field}' must be a non-empty list."
            )
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError(
                f"Prepare Agent response field '{field}' must contain non-empty strings."
            )
        validated[field] = value

    return validated
