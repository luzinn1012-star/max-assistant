"""Typed failures carrying only safe codes and user-facing messages."""


class MaxError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SkillExecutionError(MaxError):
    pass


class InvalidParameter(SkillExecutionError, ValueError):
    pass


class AppNotFound(SkillExecutionError):
    pass


class PermissionDenied(SkillExecutionError):
    pass


class ConfirmationRequired(SkillExecutionError):
    pass


class ProviderError(MaxError):
    def __init__(self, provider: str, code: str, message: str) -> None:
        super().__init__(code, message)
        self.provider = provider


class ProviderUnavailable(ProviderError):
    pass
