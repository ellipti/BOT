from typing import Any

TRADE_DECISION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AIVO_Vision_Decision",
    "type": "object",
    "required": ["overlays", "decision", "reason", "confidence", "risk", "guards_ok"],
    "properties": {
        "overlays": {
            "type": "object",
            "required": ["trendlines", "channels", "zones", "fibonacci", "patterns"],
            "properties": {
                "trendlines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "anchor_a", "anchor_b"],
                        "properties": {
                            "id": {"type": "string"},
                            "anchor_a": {
                                "type": "object",
                                "required": ["time", "price"],
                                "properties": {
                                    "time": {"type": "string", "format": "date-time"},
                                    "price": {"type": "number"},
                                },
                            },
                            "anchor_b": {
                                "type": "object",
                                "required": ["time", "price"],
                                "properties": {
                                    "time": {"type": "string", "format": "date-time"},
                                    "price": {"type": "number"},
                                },
                            },
                        },
                    },
                },
                "channels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "base", "offset_price"],
                        "properties": {
                            "id": {"type": "string"},
                            "base": {"type": "string"},
                            "offset_price": {"type": "number"},
                        },
                    },
                },
                "zones": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "type", "price_min", "price_max"],
                        "properties": {
                            "id": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["supply", "demand", "sr"],
                            },
                            "price_min": {"type": "number"},
                            "price_max": {"type": "number"},
                        },
                    },
                },
                "fibonacci": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "swing_high", "swing_low", "levels"],
                        "properties": {
                            "id": {"type": "string"},
                            "swing_high": {
                                "type": "object",
                                "required": ["time", "price"],
                                "properties": {
                                    "time": {"type": "string", "format": "date-time"},
                                    "price": {"type": "number"},
                                },
                            },
                            "swing_low": {
                                "type": "object",
                                "required": ["time", "price"],
                                "properties": {
                                    "time": {"type": "string", "format": "date-time"},
                                    "price": {"type": "number"},
                                },
                            },
                            "levels": {"type": "array", "items": {"type": "number"}},
                        },
                    },
                },
                "patterns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "name", "at"],
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "at": {"type": "string", "format": "date-time"},
                        },
                    },
                },
            },
        },
        "decision": {"type": "string", "enum": ["BUY", "SELL", "WAIT"]},
        "reason": {"type": "string"},
        "entry": {"type": ["number", "null"]},
        "sl": {"type": ["number", "null"]},
        "tp": {"type": ["number", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "risk": {
            "type": "object",
            "required": ["r_multiple", "atr", "sl_distance"],
            "properties": {
                "r_multiple": {"type": "number"},
                "atr": {"type": "number"},
                "sl_distance": {"type": "number"},
            },
        },
        "guards_ok": {
            "type": "object",
            "required": ["spread_ok", "news_ok", "cooldown_ok"],
            "properties": {
                "spread_ok": {"type": "boolean"},
                "news_ok": {"type": "boolean"},
                "cooldown_ok": {"type": "boolean"},
            },
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
}


def validate_trade_decision(decision: dict[str, Any]) -> str | None:
    """
    Validate a trade decision against the schema

    Args:
        decision: Trade decision dictionary

    Returns:
        None if valid, error message if invalid
    """
    try:
        # Basic structure validation
        required_fields = TRADE_DECISION_SCHEMA["required"]
        for field in required_fields:
            if field not in decision:
                return f"Missing required field: {field}"

        # Decision validation
        if decision["decision"] not in ["BUY", "SELL", "WAIT"]:
            return "Invalid decision value"

        # Confidence validation
        if not isinstance(decision["confidence"], (int, float)):
            return "Confidence must be a number"
        if not 0 <= decision["confidence"] <= 1:
            return "Confidence must be between 0 and 1"

        # Reason validation
        if not isinstance(decision["reason"], str):
            return "Reason must be a string"
        if len(decision["reason"]) > 200:
            return "Reason too long (max 200 chars)"

        # Overlays validation
        overlays = decision.get("overlays", {})
        if not isinstance(overlays, dict):
            return "Overlays must be an object"

        for key in ["levels", "lines", "annotations"]:
            if key not in overlays:
                return f"Missing required overlay type: {key}"

        # Validate individual overlays
        if error := _validate_levels(overlays.get("levels", [])):
            return error

        if error := _validate_lines(overlays.get("lines", [])):
            return error

        if error := _validate_annotations(overlays.get("annotations", [])):
            return error

        return None

    except Exception as e:
        return f"Validation error: {str(e)}"


def _validate_levels(levels):
    """Validate price levels"""
    if not isinstance(levels, list):
        return "Levels must be an array"

    for level in levels:
        if not isinstance(level, dict):
            return "Each level must be an object"

        if "price" not in level or not isinstance(level["price"], (int, float)):
            return "Each level must have a numeric price"

        if "type" not in level or level["type"] not in [
            "entry",
            "stop",
            "target",
            "support",
            "resistance",
        ]:
            return "Invalid level type"

        if "color" not in level or not isinstance(level["color"], str):
            return "Each level must have a color"

    return None


def _validate_lines(lines):
    """Validate trendlines"""
    if not isinstance(lines, list):
        return "Lines must be an array"

    for line in lines:
        if not isinstance(line, dict):
            return "Each line must be an object"

        if "points" not in line or not isinstance(line["points"], list):
            return "Each line must have points array"

        for point in line["points"]:
            if not isinstance(point, dict):
                return "Each point must be an object"

            if "time" not in point or not isinstance(point["time"], str):
                return "Each point must have a time string"

            if "price" not in point or not isinstance(point["price"], (int, float)):
                return "Each point must have a numeric price"

        if "type" not in line or line["type"] not in ["trend", "channel", "fibonacci"]:
            return "Invalid line type"

        if "color" not in line or not isinstance(line["color"], str):
            return "Each line must have a color"

    return None


def _validate_annotations(annotations):
    """Validate text annotations"""
    if not isinstance(annotations, list):
        return "Annotations must be an array"

    for ann in annotations:
        if not isinstance(ann, dict):
            return "Each annotation must be an object"

        if "text" not in ann or not isinstance(ann["text"], str):
            return "Each annotation must have text"

        if "position" not in ann or not isinstance(ann["position"], dict):
            return "Each annotation must have a position"

        pos = ann["position"]
        if "time" not in pos or not isinstance(pos["time"], str):
            return "Position must have a time string"

        if "price" not in pos or not isinstance(pos["price"], (int, float)):
            return "Position must have a numeric price"

    return None
