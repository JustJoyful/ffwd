"""Model and data card builders (RULES §7.2-7.3). A card with a missing required section is refused, not shipped."""

MODEL_SECTIONS = (
    "Base model",
    "Training data",
    "Teacher",
    "Training recipe",
    "Evaluation",
    "Limitations",
    "Licence",
    "Intended use",
)
DATA_SECTIONS = (
    "Generator",
    "Splits",
    "Teacher usage and cost",
    "Family distribution",
    "Known issues",
    "Licence",
)


class MissingSection(ValueError):
    pass


def _render(title: str, required: tuple[str, ...], sections: dict[str, str]) -> str:
    missing = [s for s in required if not (sections.get(s) or "").strip()]
    if missing:
        raise MissingSection(f"card sections missing or empty: {', '.join(missing)}")
    body = "\n\n".join(f"## {name}\n\n{sections[name].strip()}" for name in required)
    extra = "\n\n".join(f"## {n}\n\n{t.strip()}" for n, t in sections.items() if n not in required)
    return f"# {title}\n\n{body}\n" + (f"\n{extra}\n" if extra else "")


def model_card(name: str, sections: dict[str, str]) -> str:
    if "| " not in sections.get("Evaluation", ""):
        raise MissingSection(
            "the Evaluation section must contain the results table with confidence intervals"
        )
    return _render(name, MODEL_SECTIONS, sections)


def data_card(name: str, sections: dict[str, str]) -> str:
    return _render(name, DATA_SECTIONS, sections)
