from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


def load_template(document_type: str) -> Dict[str, Any]:
    """Load a single disclosure template by document type identifier."""

    template_path = TEMPLATES_DIR / f"{document_type}.yaml"
    if not template_path.exists():
        msg = f"Template not found for document_type={document_type!r}"
        raise FileNotFoundError(msg)

    with template_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def list_templates() -> Dict[str, Dict[str, Any]]:
    """Load every YAML template available under the templates directory."""

    templates: Dict[str, Dict[str, Any]] = {}
    for path in sorted(TEMPLATES_DIR.glob("*.yaml")):
        templates[path.stem] = load_template(path.stem)
    return templates
