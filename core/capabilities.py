"""Deny-by-default capabilities; risk confirmation remains a separate gate."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from core.errors import PermissionDenied


class Capability(StrEnum):
    APP_LAUNCH = "app.launch"
    APP_CLOSE = "app.close"
    PROCESS_INSPECT = "process.inspect"
    PROCESS_TERMINATE = "process.terminate"
    AUDIO_READ = "audio.read"
    AUDIO_WRITE = "audio.write"
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    SYSTEM_POWER = "system.power"
    NETWORK_REQUEST = "network.request"


DEFAULT_ALLOWED = frozenset(
    {
        Capability.APP_LAUNCH,
        Capability.APP_CLOSE,
        Capability.PROCESS_INSPECT,
        Capability.AUDIO_READ,
        Capability.AUDIO_WRITE,
        Capability.FILESYSTEM_READ,
        Capability.NETWORK_REQUEST,
    }
)


@dataclass
class CapabilityPolicy:
    allowed: frozenset[Capability] = field(default_factory=lambda: DEFAULT_ALLOWED)

    def require(self, capabilities: Iterable[Capability]) -> None:
        requested = frozenset(Capability(value) for value in capabilities)
        if not requested.issubset(self.allowed):
            raise PermissionDenied(
                "capability_denied", "Esta operação não tem permissão nesta sessão."
            )
