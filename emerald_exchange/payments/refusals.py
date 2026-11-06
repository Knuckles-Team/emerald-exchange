"""The one refusal type of the payments package (CONN-EMERALD-EXCHANGE-X402-R010.1)."""

from __future__ import annotations

from typing import Any


class PaymentRefused(Exception):
    """A payment or wallet operation was refused before or by the runtime.

    ``code`` is a stable refusal code; ``detail`` holds only safe, non-secret
    fields (never a secret value or a secret reference).
    """

    def __init__(self, code: str, **detail: Any) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail

    def as_result(self) -> dict[str, Any]:
        """The tool-result form of this refusal."""
        return {"error": self.code, "approved": False, **self.detail}
