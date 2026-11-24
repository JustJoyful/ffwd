"""Load the protocol JSON Schemas (packages/protocol, the single source of truth) and validate."""

import json
from functools import cache
from typing import Literal

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from training import config

Kind = Literal["action", "spec", "probe", "check", "task", "model"]
KINDS: tuple[Kind, ...] = ("action", "spec", "probe", "check", "task", "model")


@cache
def load_schema(kind: Kind) -> dict:
    return json.loads((config.PROTOCOL_DIR / "schemas" / f"{kind}.schema.json").read_text())


@cache
def _validator(kind: Kind) -> Draft202012Validator:
    # Cross-file $refs ("spec#/$defs/id") resolve through a registry keyed by each schema's $id.
    registry = Registry().with_resources(
        (load_schema(k)["$id"], Resource.from_contents(load_schema(k))) for k in KINDS
    )
    return Draft202012Validator(load_schema(kind), registry=registry)


def validate(kind: Kind, obj: object) -> list[str]:
    """Return human-readable schema errors; an empty list means valid."""
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in _validator(kind).iter_errors(obj)
    ]
