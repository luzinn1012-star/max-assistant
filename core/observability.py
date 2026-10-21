"""Per-request correlation, isolated across threads and concurrent contexts."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

_request_id: ContextVar[str] = ContextVar("max_request_id", default="-")


def current_request_id() -> str:
    return _request_id.get()


@contextmanager
def request_scope() -> Iterator[str]:
    request_id = uuid4().hex
    token = _request_id.set(request_id)
    try:
        yield request_id
    finally:
        _request_id.reset(token)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id()
        return True
