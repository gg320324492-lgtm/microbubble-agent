"""W68 D6 Phase 1 in-process runner smoke tests.

Five scenarios that gate ``inprocess_runner.run_inprocess`` behaviour:

1. Empty question list -> empty results list (no LLM call).
2. Single question -> one verdict; answer is either text or ``"empty"``.
3. Per-question failure isolation: one failing question does not poison the
   rest of the run.
4. ``CancelledError`` short-circuiting the runner mid-loop.  We use a stub
   ``engine_factory`` that emits ``asyncio.CancelledError`` on the second
   question; the runner must re-raise after marking the partial result.
5. Verdict collection: the returned objects always expose the dataclass
   contract used by the dry-run report generator.

The tests live under ``tests/qa-bench/`` and must NOT touch production code
(W68 zero production-change rule).  They use lightweight stubs and the
``engine_factory`` seam added to ``run_inprocess`` so the suite runs on any
Python 3.11 host without spinning up PostgreSQL / Redis / the full agent.

The root ``tests/conftest.py`` boots PostgreSQL when ``SKIP_DB_SETUP`` is
unset.  These tests don't need DB -- pytest.ini already sets
``env = SKIP_DB_SETUP=1`` for this directory via the auto-load (the root
conftest also re-checks ``SKIP_DB_SETUP``).  Run with::

    python -m pytest tests/qa-bench/test_inprocess_runner_smoke.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import pytest

_QA_BENCH_DIR = Path(__file__).resolve().parent
if str(_QA_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_BENCH_DIR))

# The root ``tests/conftest.py`` boots PostgreSQL when ``SKIP_DB_SETUP`` is
# unset.  These tests deliberately avoid DB.  Run with::
#
#     SKIP_DB_SETUP=1 python -m pytest tests/qa-bench/test_inprocess_runner_smoke.py -v
#
# Without the env the suite is auto-skipped -- the in-process runner design
# depends on the *production* app being available, which is out of scope here.
if not os.environ.get("SKIP_DB_SETUP"):
    pytest.skip(
        "in-process runner smoke tests require SKIP_DB_SETUP=1",
        allow_module_level=True,
    )

from inprocess_runner import VerdictResult, run_inprocess  # noqa: E402


# --- Stub ChatEngine replacement --------------------------------------------


class _StubEngine:
    """Drop-in replacement for ``ChatEngine`` used by the smoke tests.

    Each entry in ``self.responses`` corresponds to one call to
    ``synthesize_stream``.  Tests can pre-load answers / exceptions to
    simulate real LLM behaviour without booting the full stack.
    """

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def synthesize_stream(self, *, messages, system, user_id, db, session_id, **kwargs):  # noqa: D401
        self.calls.append(
            {
                "messages": list(messages),
                "system": system,
                "user_id": user_id,
                "session_id": session_id,
            }
        )
        if not self.responses:
            raise IndexError("no more stub responses queued")
        item = self.responses.pop(0)

        # Special handling: a class object means "raise this exception class
        # before yielding anything".  We wrap it in an async generator so the
        # runner's ``async for`` loop triggers the raise immediately.
        if isinstance(item, type) and issubclass(item, BaseException):
            async def _raise_then_done():
                raise item("stub-raise")
                yield {"type": "done", "content": ""}  # pragma: no cover - unreachable
            return _raise_then_done()

        if isinstance(item, BaseException):
            exc = item

            async def _raise_exc():
                raise exc
                yield {"type": "done", "content": ""}  # pragma: no cover - unreachable
            return _raise_exc()

        # Normal path: yield a couple of ``text_delta`` events plus ``done``.
        async def _gen():
            if isinstance(item, str):
                # split into two halves to exercise the increment collection
                mid = max(len(item) // 2, 1)
                yield {"type": "text_delta", "text": item[:mid]}
                yield {"type": "text_delta", "text": item[mid:]}
            yield {"type": "done", "content": item if isinstance(item, str) else ""}

        return _gen()


@pytest.fixture
def stub_engine_factory():
    """Return a factory that yields a fresh ``_StubEngine`` per call.

    Tests can inspect ``captured["engines"]`` to assert call counts and
    payload after the run completes.
    """

    captured: dict[str, Any] = {"engines": []}

    def _factory(responses: list[Any]) -> _StubEngine:
        engine = _StubEngine(responses)
        captured["engines"].append(engine)
        return engine

    return captured, _factory


# --- 1. Empty input ---------------------------------------------------------


def test_empty_question_list_returns_empty(stub_engine_factory):
    captured, factory = stub_engine_factory

    async def _go():
        return await run_inprocess(
            [],
            db_url="postgresql+asyncpg://localhost/test",
            engine_factory=lambda: factory([]),
        )

    result = asyncio.run(_go())
    assert result == []
    # No engine instantiated because the loop short-circuits before the
    # factory is invoked.
    assert captured["engines"] == []


# --- 2. Single question ------------------------------------------------------


def test_single_question_emits_one_verdict(stub_engine_factory):
    captured, factory = stub_engine_factory

    async def _go():
        return await run_inprocess(
            [{"id": "P-L3-0001", "question": "什么是 zeta 电位？"}],
            db_url="postgresql+asyncpg://localhost/test",
            engine_factory=lambda: factory(["zeta 电位是表征纳米气泡表面电荷的关键参数。"]),
        )

    results = asyncio.run(_go())
    assert len(results) == 1
    only = results[0]
    assert isinstance(only, VerdictResult)
    assert only.question_id == "P-L3-0001"
    assert "zeta" in only.answer
    assert only.verdict == "pass"
    assert only.error is None
    # The stub recorded exactly one call to ``synthesize_stream``.
    engine = captured["engines"][-1]
    assert len(engine.calls) == 1
    call = engine.calls[0]
    assert call["messages"][0]["content"] == "什么是 zeta 电位？"
    assert call["session_id"] == "qa-bench-P-L3-0001"


# --- 3. Per-question failure isolation --------------------------------------


def test_one_failing_question_does_not_block_the_rest(stub_engine_factory):
    captured, factory = stub_engine_factory

    questions = [
        {"id": "Q-A", "question": "什么是 zeta 电位？"},
        {"id": "Q-B", "question": "DLVO 是什么？"},
        {"id": "Q-C", "question": "王天志是谁？"},
    ]

    async def _go():
        return await run_inprocess(
            questions,
            db_url="postgresql+asyncpg://localhost/test",
            engine_factory=lambda: factory(
                [
                    RuntimeError("LLM timed out"),
                    "DLVO 理论描述胶体稳定性。",
                    "成员王天志负责项目 A。",
                ]
            ),
        )

    results = asyncio.run(_go())
    assert [r.question_id for r in results] == ["Q-A", "Q-B", "Q-C"]
    assert results[0].verdict == "error"
    assert results[0].error and "RuntimeError" in results[0].error
    assert results[1].verdict == "pass"
    assert results[2].verdict == "pass"
    # All three questions were attempted despite the first failure.
    engine = captured["engines"][-1]
    assert len(engine.calls) == 3


# --- 4. CancelledError short-circuit ----------------------------------------


def test_cancelled_error_propagates_and_records_partial(stub_engine_factory):
    captured, factory = stub_engine_factory

    questions = [
        {"id": "Q-A", "question": "Q1"},
        {"id": "Q-B", "question": "Q2"},
        {"id": "Q-C", "question": "Q3"},  # never reached
    ]

    async def _go():
        return await run_inprocess(
            questions,
            db_url="postgresql+asyncpg://localhost/test",
            engine_factory=lambda: factory(
                [
                    "first answer OK",
                    asyncio.CancelledError,
                    "third answer OK",
                ]
            ),
        )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_go())

    # The engine saw two calls (Q-A succeeded, Q-B raised, loop aborted).
    engine = captured["engines"][-1]
    assert len(engine.calls) == 2
    assert engine.calls[0]["session_id"] == "qa-bench-Q-A"
    assert engine.calls[1]["session_id"] == "qa-bench-Q-B"


# --- 5. Verdict dataclass contract ------------------------------------------


def test_verdict_dataclass_contract_round_trip(stub_engine_factory):
    captured, factory = stub_engine_factory

    questions = [
        {"id": "V-1", "question": "q1", "expect": {"intent": "EXPLAIN_CONCEPT"}},
        {"id": "V-2", "question": "q2", "expect": {"intent": "DATA"}},
        {"id": "V-3", "question": "q3", "expect": {"intent": "CASUAL"}},
    ]

    async def _go():
        return await run_inprocess(
            questions,
            db_url="postgresql+asyncpg://localhost/test",
            engine_factory=lambda: factory(
                [
                    "zeta",  # pass
                    "DLVO",  # pass
                    "",     # empty -> verdict "empty"
                ]
            ),
        )

    results = asyncio.run(_go())
    assert len(results) == 3
    for r, q in zip(results, questions):
        assert r.question_id == q["id"]
        assert r.question == q["question"]
        # ``metadata`` is a copy of the original question dict (so callers can
        # group by category without reaching back into the input).
        assert r.metadata["expect"]["intent"] == q["expect"]["intent"]
    # Empty-answer case is recorded as ``"empty"`` so the dry-run report
    # can still count it.
    assert results[2].answer == ""
    assert results[2].verdict == "empty"


if __name__ == "__main__":  # pragma: no cover - allows `python ...`
    sys.exit(pytest.main([__file__, "-v"]))