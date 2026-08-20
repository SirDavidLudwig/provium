"""Tests for artifact resource sessions."""

from dataclasses import dataclass

import pytest

from provium import current_session, session
from provium.context import activate_context, current_context


@dataclass
class Resource:
    name: str
    closed: list[str]
    error: BaseException | None = None

    def close(self) -> None:
        self.closed.append(self.name)
        if self.error is not None:
            raise self.error


def test_sessions_activate_nest_and_restore_the_current_context() -> None:
    parent = session()
    child = session()

    assert current_session() is None
    assert not parent._owns_active_context()
    with parent:
        assert current_session() is parent
        assert parent.active
        with child:
            assert child.parent is parent
            assert current_session() is child
            assert parent._owns_active_context()
        assert current_session() is parent
        assert not child.active
    assert current_context() is None
    assert not parent.active


def test_session_is_single_use() -> None:
    active = session()

    with active:
        pass

    with pytest.raises(RuntimeError, match="already been entered"):
        active.__enter__()


def test_session_rejects_a_non_session_parent_context() -> None:
    with activate_context(object()), pytest.raises(RuntimeError, match="not a session"):
        session().__enter__()


def test_session_exit_requires_its_matching_active_context() -> None:
    inactive = session()
    with pytest.raises(RuntimeError, match="not active"):
        inactive.__exit__(None, None, None)

    active = session()
    active.__enter__()
    with activate_context(session()), pytest.raises(RuntimeError, match="not active"):
        active.__exit__(None, None, None)
    active.__exit__(None, None, None)


def test_session_closes_managed_resources_in_reverse_order() -> None:
    closed: list[str] = []

    with session() as active:
        active._manage(Resource("first", closed))
        active._manage(Resource("second", closed))

    assert closed == ["second", "first"]


def test_session_reports_first_cleanup_error_after_attempting_every_close() -> None:
    closed: list[str] = []

    with pytest.raises(RuntimeError, match="second failed"):
        with session() as active:
            active._manage(Resource("first", closed, ValueError("first failed")))
            active._manage(Resource("second", closed, RuntimeError("second failed")))

    assert closed == ["second", "first"]
    assert current_session() is None


def test_session_preserves_body_error_over_cleanup_error() -> None:
    closed: list[str] = []

    with pytest.raises(LookupError, match="body failed"):
        with session() as active:
            active._manage(Resource("resource", closed, RuntimeError("close failed")))
            raise LookupError("body failed")

    assert closed == ["resource"]


def test_session_restores_context_when_cleanup_raises_a_base_exception() -> None:
    closed: list[str] = []

    with pytest.raises(KeyboardInterrupt, match="interrupted"):
        with session() as active:
            active._manage(
                Resource("resource", closed, KeyboardInterrupt("interrupted"))
            )

    assert closed == ["resource"]
    assert current_session() is None


def test_manage_requires_the_active_owning_session() -> None:
    active = session()
    with pytest.raises(RuntimeError, match="active session"):
        active._manage(Resource("resource", []))

    with active:
        with session(), pytest.raises(RuntimeError, match="active session"):
            active._manage(Resource("resource", []))


def test_manage_rejects_a_resource_without_a_close_operation() -> None:
    with session() as active:
        with pytest.raises(TypeError, match="close"):
            active._manage(object())  # type: ignore[arg-type]
