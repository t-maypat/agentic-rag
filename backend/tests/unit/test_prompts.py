"""Every prompt must render with dummy vars (missing placeholder -> KeyError)."""

import string

from app.prompts import registry

# Union of placeholders any prompt might reference.
_DUMMY = {
    "question": "Q",
    "history": "H",
    "blocks": "B",
    "evidence_block": "E",
}


def _placeholders(body: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(body) if name}


def test_all_prompts_render():
    for prompt in registry.all_prompts():
        needed = _placeholders(prompt.body)
        missing = needed - _DUMMY.keys()
        assert not missing, f"{prompt.id} references unknown vars {missing}"
        rendered = prompt.render(**{k: _DUMMY[k] for k in needed})
        assert rendered


def test_prompt_tags_are_versioned():
    for prompt in registry.all_prompts():
        assert "@" in prompt.tag
        assert prompt.model_role in {"control", "synth"}
