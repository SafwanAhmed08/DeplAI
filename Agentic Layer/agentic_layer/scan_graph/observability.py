from __future__ import annotations

import os
from pathlib import Path
from typing import Callable
from typing import TypeVar

from dotenv import load_dotenv

T = TypeVar("T", bound=Callable)


def configure_langsmith() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=env_path, override=False)

    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        return

    endpoint = os.getenv("LANGSMITH_ENDPOINT") or os.getenv("LANGCHAIN_ENDPOINT")
    project = os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT") or "deplai-agentic-layer"

    os.environ.setdefault("LANGSMITH_API_KEY", api_key)
    os.environ.setdefault("LANGCHAIN_API_KEY", api_key)
    if endpoint:
        os.environ.setdefault("LANGSMITH_ENDPOINT", endpoint)
        os.environ.setdefault("LANGCHAIN_ENDPOINT", endpoint)
    os.environ.setdefault("LANGSMITH_PROJECT", project)
    os.environ.setdefault("LANGCHAIN_PROJECT", project)

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")


def traceable_if_available(name: str, run_type: str = "chain") -> Callable[[T], T]:
    try:
        from langsmith import traceable  # type: ignore

        def _decorator(func: T) -> T:
            return traceable(name=name, run_type=run_type)(func)  # type: ignore[return-value]

        return _decorator
    except Exception:
        def _noop(func: T) -> T:
            return func

        return _noop
