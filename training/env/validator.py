"""Allowlist validator for model `run` actions (RULES §1.2, ARCH §3.5).

Anything not explicitly allowed is rejected. The model never writes paths: files appear only as
{in:<id>} right after -i and {out:<id>} as positionals; the executor maps IDs to real paths.
The same rules are ported to TypeScript and kept in sync by conformance/validator.jsonl.
"""

import json
import re
from dataclasses import dataclass
from functools import cache

from training import config


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str | None = None


class _Reject(Exception):
    pass


_IN = re.compile(r"^\{in:([a-z][a-z0-9_]{0,15})\}$")
_OUT = re.compile(r"^\{out:([a-z][a-z0-9_]{0,15})\}$")
_OPT = re.compile(r"^(-[a-z_]+)((?::[a-z0-9]+)*)$")  # base name + optional :stream-spec
_KIND_RE = {
    "time": r"-?\d+(\.\d+)?|-?\d{1,2}:\d{2}(:\d{2})?(\.\d+)?",
    "number": r"-?\d+(\.\d+)?(/\d+)?",
    "int": r"-?\d+",
    "bitrate": r"\d+(\.\d+)?[kKmM]?",
    "map": r"-?\[?[A-Za-z0-9_:]+\]?\??",
    "metadata": r"[a-z_]+=[A-Za-z0-9 _.:-]{0,64}",
}
_LABEL = re.compile(r"^[A-Za-z0-9_:]+$")
_FILTER_NAME = re.compile(r"^[a-z0-9_]+$")
_PROTOCOL_OR_PATH = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:/|\.\.")
_CODEC_OPTS = {"-c", "-codec", "-vcodec", "-acodec"}
_FILTER_OPTS = {"-vf", "-af", "-filter", "-filter_complex"}


@cache
def allowlist() -> dict:
    return json.loads((config.PROTOCOL_DIR / "allowlist.json").read_text())


def _split_graph(graph: str) -> list[str]:
    """Split a filtergraph on , and ; outside [labels], '...' quotes and backslash escapes
    (the same tokenisation FFmpeg applies)."""
    parts, buf, i, quoted, bracket = [], [], 0, False, False
    while i < len(graph):
        ch = graph[i]
        if ch == "\\" and i + 1 < len(graph):
            buf.append(graph[i : i + 2])
            i += 2
            continue
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch == "[":
            bracket = True
        elif not quoted and ch == "]":
            bracket = False
        elif not quoted and not bracket and ch in ",;":
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if quoted or bracket:
        raise _Reject("unbalanced quote or bracket in filtergraph")
    parts.append("".join(buf))
    return parts


def _check_filtergraph(graph: str) -> None:
    allowed = set(allowlist()["filters"])
    for part in _split_graph(graph):
        # Strip leading/trailing [label] pads around the filter.
        m = re.fullmatch(r"((?:\[[^\]]*\])*)([^\[\]]*)((?:\[[^\]]*\])*)", part.strip())
        if not m:
            raise _Reject(f"bad filter syntax: {part!r}")
        for label in re.findall(r"\[([^\]]*)\]", m.group(1) + m.group(3)):
            if not _LABEL.match(label):
                raise _Reject(f"bad filter label: {label!r}")
        name, _, fargs = m.group(2).partition("=")
        if not _FILTER_NAME.match(name):
            raise _Reject(f"bad filter syntax: {part!r}")
        if name not in allowed:
            raise _Reject(f"filter not allowed: {name}")
        if _PROTOCOL_OR_PATH.search(fargs):
            raise _Reject(f"bad filter arguments for {name}")


def _check_value(opt: str, kind: str, value: str) -> None:
    al = allowlist()
    if kind == "codec":
        if value != "copy" and value not in al["encoders"]:
            raise _Reject(f"codec not allowed: {value}")
    elif kind == "filtergraph":
        _check_filtergraph(value)
    elif kind == "pix_fmt":
        if value not in al["pix_fmts"]:
            raise _Reject(f"bad value for {opt}: {value!r}")
    elif kind == "muxer":
        if value not in al["muxers"]:
            raise _Reject(f"muxer not allowed: {value}")
    elif kind.startswith("enum:"):
        if value not in kind[5:].split(","):
            raise _Reject(f"bad value for {opt}: {value!r}")
    elif not re.fullmatch(_KIND_RE[kind], value):
        raise _Reject(f"bad value for {opt}: {value!r}")


def _walk(args: list[str]) -> tuple[list[str], list[str]]:
    """Validate every token; return the input and output IDs in order of appearance."""
    options = allowlist()["options"]
    used_in, used_out, i = [], [], 0
    while i < len(args):
        tok = args[i]
        if tok == "-i":
            if i + 1 >= len(args) or not (m := _IN.match(args[i + 1])):
                raise _Reject("input must be {in:<id>}")
            used_in.append(m.group(1))
            i += 2
        elif tok.startswith("-"):
            m = _OPT.match(tok)
            if not m or m.group(1) not in options:
                raise _Reject(f"option not allowed: {tok}")
            kind = options[m.group(1)]
            if kind == "flag":
                i += 1
                continue
            if i + 1 >= len(args):
                raise _Reject(f"missing value for {tok}")
            _check_value(tok, kind, args[i + 1])
            i += 2
        elif m := _OUT.match(tok):
            used_out.append(m.group(1))
            i += 1
        else:
            raise _Reject(f"unexpected positional argument: {tok!r}")
    return used_in, used_out


def _check_ids(used: list[str], declared: list[str], known: set[str]) -> None:
    for x in used:
        if x not in known or x not in declared:
            raise _Reject(f"unknown id: {x}")
    for x in sorted({x for x in used if used.count(x) > 1}):
        raise _Reject(f"used more than once: {x}")
    for x in declared:
        if x not in used:
            raise _Reject(f"declared but not used: {x}")


def validate_run(
    args: list[str],
    inputs: list[str],
    outputs: list[str],
    *,
    known_inputs: set[str],
    known_outputs: set[str],
) -> ValidationResult:
    try:
        used_in, used_out = _walk(args)
        _check_ids(used_in, inputs, known_inputs)
        _check_ids(used_out, outputs, known_outputs)
    except _Reject as e:
        return ValidationResult(False, str(e))
    return ValidationResult(True)


def uses_stream_copy_only(args: list[str]) -> bool:
    """True when every codec option is `copy` and no filter is applied (no re-encode)."""
    codecs, filtered = [], False
    for opt, value in zip(args, args[1:] + [""], strict=True):
        base = opt.split(":")[0]
        if base in _CODEC_OPTS:
            codecs.append(value)
        elif base in _FILTER_OPTS:
            filtered = True
    return bool(codecs) and all(c == "copy" for c in codecs) and not filtered
