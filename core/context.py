"""Contexto temporário e limitado; memória SQLite fica para a fase sete."""
from brain.provider import Message


class Conversation:
    def __init__(self, max_turns: int, max_chars: int):
        self.max_turns = max_turns
        self.max_chars = max_chars
        self._turns: list[tuple[Message, Message]] = []

    def for_request(self, text: str) -> list[Message]:
        selected = []
        remaining = self.max_chars - len(text)
        for pair in reversed(self._turns):
            size = sum(len(message.content) for message in pair)
            if size > remaining:
                break
            selected.append(pair)
            remaining -= size
        return [message for pair in reversed(selected) for message in pair] + [Message("user", text)]

    def commit(self, user: str, answer: str) -> None:
        self._turns.append((Message("user", user), Message("assistant", answer)))
        self._turns = self._turns[-self.max_turns:]
        while self._turns and sum(len(m.content) for pair in self._turns for m in pair) > self.max_chars:
            self._turns.pop(0)

    def clear(self) -> None:
        self._turns.clear()
