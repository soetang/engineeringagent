import json
import re
from typing import Any


_JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_structured_json(content: str) -> dict[str, Any]:
    """Parse agent output, tolerating fenced or prose-wrapped JSON objects."""
    clean_content = content.strip()
    fenced_match = _JSON_FENCE_PATTERN.search(clean_content)
    if fenced_match:
        clean_content = fenced_match.group(1).strip()

    try:
        return json.loads(clean_content)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(clean_content):
            if char != "{":
                continue
            try:
                parsed, end = decoder.raw_decode(clean_content[index:])
            except json.JSONDecodeError:
                continue

            trailing = clean_content[index + end :].strip()
            if trailing and trailing != "```":
                continue
            if not isinstance(parsed, dict):
                continue
            return parsed

        raise
