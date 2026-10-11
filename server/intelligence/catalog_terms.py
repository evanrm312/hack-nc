"""Small, explicit catalog vocabulary; never derive facts from listing prose."""
from __future__ import annotations

import re

ITEM_CATEGORIES = (
    'formalwear', 'clothing', 'electronics', 'academic supplies',
    'dorm essentials', 'mobility', 'outdoor gear', 'tools', 'event equipment',
)
CALCULATOR_TYPES = ('calculator', 'graphing calculator', 'scientific calculator')


def calculator_type(value):
    if not isinstance(value, str):
        return None
    term = ' '.join(value.strip().casefold().split())
    if term.endswith('s'):
        term = term[:-1]
    return term if term in CALCULATOR_TYPES else None


def catalog_request(category, required):
    """Map a calculator category to its catalog parent, retaining item kind."""
    required = dict(required or {})
    if isinstance(category, str):
        category = category.strip().casefold()
    kind = calculator_type(category)
    if kind:
        category = 'academic supplies'
        required.setdefault('type', kind)
    return category, required


def model_key(value):
    # Formatting aliases only; Plus, CE, and other suffixes stay significant.
    if not isinstance(value, str):
        return None
    value = value.strip().casefold()
    if re.fullmatch(r'ti[ -]*\d+[a-z0-9 -]*', value):
        return re.sub(r'[ -]+', '', value)
    return value


def specification_same(name, expected, actual):
    """True/False for known agreement/conflict; None for a broader item kind."""
    if name == 'model' and isinstance(expected, str) and isinstance(actual, str):
        return model_key(expected) == model_key(actual)
    if name == 'type':
        wanted, offered = calculator_type(expected), calculator_type(actual)
        if wanted and offered:
            if wanted == 'calculator' or wanted == offered:
                return True
            if offered == 'calculator':
                return None
            return False
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().casefold() == actual.strip().casefold()
    return type(expected) is type(actual) and expected == actual
