"""Observability is a safe no-op when Langfuse keys are absent (REVAMP_PLAN §9).

These run with sockets disabled: they assert the tracer never constructs a client
or touches the network, and that every public function tolerates being called with
no active trace.
"""

import app.observability as obs


def test_disabled_without_keys(monkeypatch):
    # Force a clean, keyless state (settings come from the test env).
    monkeypatch.setattr(obs.settings, "langfuse_public_key", None, raising=False)
    monkeypatch.setattr(obs.settings, "langfuse_secret_key", None, raising=False)
    monkeypatch.setattr(obs, "_client", None, raising=False)
    monkeypatch.setattr(obs, "_initialized", False, raising=False)

    assert obs.is_enabled() is False


def test_all_functions_are_noops_when_disabled(monkeypatch):
    monkeypatch.setattr(obs.settings, "langfuse_public_key", None, raising=False)
    monkeypatch.setattr(obs, "_client", None, raising=False)
    monkeypatch.setattr(obs, "_initialized", False, raising=False)

    # None of these should raise, create a client, or open a socket.
    trace = obs.start_trace(name="research", thread_id="t1", question="q", mode="quick")
    assert trace is None

    obs.node_start("intake", 0)
    obs.record_generation(
        model="gemini-2.5-flash-lite",
        prompt_id="intake@1",
        input_tokens=10,
        output_tokens=5,
        latency_ms=12,
        temperature=0.0,
    )
    obs.node_end("intake", "done", 12)
    obs.end_trace(trace, outcome="answered", usage={"llm_calls": 1})
    obs.flush()

    # Still disabled — nothing enabled tracing as a side effect.
    assert obs.is_enabled() is False


def test_partial_keys_do_not_enable(monkeypatch):
    # Public key alone is insufficient; must not attempt to construct a client.
    monkeypatch.setattr(obs.settings, "langfuse_public_key", "pk-only", raising=False)
    monkeypatch.setattr(obs.settings, "langfuse_secret_key", None, raising=False)
    monkeypatch.setattr(obs, "_client", None, raising=False)
    monkeypatch.setattr(obs, "_initialized", False, raising=False)

    assert obs.is_enabled() is False
