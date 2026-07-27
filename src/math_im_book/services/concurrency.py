from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Protocol, TypeVar


T = TypeVar("T")
R = TypeVar("R")


class OrderedConcurrentRunner(Protocol):
    def run_ordered(self, items: list[T], worker: Callable[[T], R]) -> list[R]:
        """Run worker for each item concurrently and return results in input order."""


class ThreadPoolOrderedConcurrentRunner:
    def __init__(self, max_workers: int | None = None) -> None:
        self.max_workers = max_workers

    def run_ordered(self, items: list[T], worker: Callable[[T], R]) -> list[R]:
        if len(items) <= 1:
            return [worker(item) for item in items]
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(worker, item) for item in items]
            return [future.result() for future in futures]
