"""Markdown-file prompt registry.

Each ``*.md`` in this package has YAML frontmatter (``id``, ``version``,
``model_role``, ``temperature``) followed by the template body. ``render(id,
**vars)`` substitutes ``{var}`` placeholders via ``str.format`` (a missing var
raises ``KeyError`` — a unit test renders every prompt with dummy vars to catch
that at test time). Every LLM call logs ``prompt_id@version`` into the trace.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

_PROMPT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    model_role: str
    temperature: float
    body: str

    @property
    def tag(self) -> str:
        return f"{self.id}@{self.version}"

    def render(self, **variables: object) -> str:
        return self.body.format(**variables)


def _parse(path: Path) -> Prompt:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"Prompt {path.name} missing YAML frontmatter.")
    _, front, body = raw.split("---", 2)
    meta = yaml.safe_load(front) or {}
    return Prompt(
        id=str(meta["id"]),
        version=int(meta.get("version", 1)),
        model_role=str(meta.get("model_role", "control")),
        temperature=float(meta.get("temperature", 0.0)),
        body=body.lstrip("\n"),
    )


def _load_all() -> dict[str, Prompt]:
    prompts: dict[str, Prompt] = {}
    for path in sorted(_PROMPT_DIR.glob("*.md")):
        prompt = _parse(path)
        prompts[prompt.id] = prompt
    return prompts


_REGISTRY: dict[str, Prompt] = _load_all()


def get(prompt_id: str) -> Prompt:
    if prompt_id not in _REGISTRY:
        raise KeyError(f"Unknown prompt id: {prompt_id}")
    return _REGISTRY[prompt_id]


def all_prompts() -> list[Prompt]:
    return list(_REGISTRY.values())


def render(prompt_id: str, **variables: object) -> str:
    return get(prompt_id).render(**variables)
