"""Test package import and version dynamics. CONCEPT:AU-AHE.assimilation.autonomous-trading-ecosystem"""

import importlib


def test_import_package():
    """Package must be importable."""
    mod = importlib.import_module("emerald_exchange")
    assert mod is not None


def test_version_defined():
    """Package must expose __version__."""
    import emerald_exchange

    assert hasattr(emerald_exchange, "__version__")
    assert isinstance(emerald_exchange.__version__, str)
    assert len(emerald_exchange.__version__) > 0


def test_backends_importable():
    """Core backends module must be importable."""
    from emerald_exchange.backends import (
        ExchangeBackend,
        PaperBackend,
        BACKEND_REGISTRY,
        create_backend,
    )

    assert PaperBackend is not None
    assert "paper" in BACKEND_REGISTRY


def test_risk_guards_importable():
    """Risk guards module must be importable."""
    from emerald_exchange.risk_guards import RiskGuard, RiskLimits

    assert RiskGuard is not None
    assert RiskLimits is not None
