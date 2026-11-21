"""CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R003: the packaged ontology extends only the medulla core ontology."""

import re
from pathlib import Path

import pytest

ONTOLOGY = Path(__file__).resolve().parents[1] / "emerald_exchange" / "ontology"
CONNECTOR_NAMESPACES = (
    "https://knuckles-team.github.io/ontology/connector/emerald#",
    "https://knuckles-team.github.io/ontology/connector/emerald/finance#",
)
CORE_TERMS = (
    "Account",
    "Action",
    "Agent",
    "ApplicationComponent",
    "ApplicationLayer",
    "ArchiMateElement",
    "ArchitectureDecisionRecord",
    "Assessment",
    "BacktestResult",
    "BacktestRun",
    "Belief",
    "Budget",
    "BusinessLayer",
    "BusinessProcess",
    "Commit",
    "Concept",
    "CreativeWork",
    "DataClassification",
    "DataPipeline",
    "Dataset",
    "Decision",
    "EcosystemPackage",
    "Episode",
    "Event",
    "Evidence",
    "Experiment",
    "ExternalGraphReference",
    "Fact",
    "File",
    "FinanceAlgorithm",
    "FinancialInstrument",
    "GeopoliticalRisk",
    "Goal",
    "Hypothesis",
    "Incident",
    "Issue",
    "Memory",
    "MergeRequest",
    "Metric",
    "MotivationLayer",
    "Observation",
    "Order",
    "Organization",
    "OutcomeEvaluation",
    "Person",
    "Phase",
    "Pipeline",
    "Policy",
    "Position",
    "Principle",
    "Procedure",
    "Prompt",
    "PullRequest",
    "Region",
    "Repository",
    "ResourceGroup",
    "Role",
    "SecurityClearance",
    "Server",
    "Skill",
    "StateMachine",
    "StrategyLayer",
    "Symbol",
    "System",
    "Task",
    "Team",
    "TechnologyLayer",
    "Tool",
    "TradingDebate",
    "TradingSignal",
    "TradingStrategy",
    "alternativesTo",
    "citesSource",
    "confidence",
    "contains",
    "decidedBy",
    "dependsOn",
    "derivedFrom",
    "filledQty",
    "hasRole",
    "impactsConcept",
    "mitigatedBy",
    "mitigatesRisk",
    "occurredDuring",
    "orderStatus",
    "ownedBy",
    "partOf",
    "platform",
    "providedBy",
    "provides",
    "severity",
    "signalType",
    "similarTo",
    "state",
    "subject",
    "supersedes",
    "title",
    "tradingMode",
    "verifiedBy",
)
OLD_BASE = re.compile(r"knuckles\.team/kg|http://knuckles\.team")


def _files() -> list[Path]:
    return sorted(ONTOLOGY.glob("**/*.ttl"))


def _subjects(text: str) -> set[str]:
    """Full IRIs of every statement subject written under a connector namespace."""
    found = set()
    for namespace in CONNECTOR_NAMESPACES:
        prefixes = re.findall(
            r"@prefix\s+(\w*):\s*<" + re.escape(namespace) + ">", text
        )
        for prefix in prefixes:
            for match in re.finditer(
                r"^" + re.escape(prefix) + r":([\w-]+)\s", text, re.M
            ):
                found.add(namespace + match.group(1))
        for match in re.finditer(
            r"^<" + re.escape(namespace) + r"([\w-]+)>", text, re.M
        ):
            found.add(namespace + match.group(1))
    return found


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R003")
def test_pack_declares_no_core_term():
    """No core class or property is redeclared under a connector namespace."""
    subjects = set().union(*(_subjects(p.read_text()) for p in _files()))
    redeclared = sorted(
        namespace + term
        for namespace in CONNECTOR_NAMESPACES
        for term in CORE_TERMS
        if namespace + term in subjects
    )
    assert redeclared == []


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R003")
def test_pack_uses_the_one_iri_base():
    """No packaged ontology file carries the retired IRI base."""
    stale = [p.name for p in _files() if OLD_BASE.search(p.read_text())]
    assert stale == []
