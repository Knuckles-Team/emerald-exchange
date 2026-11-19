"""Emerald Exchange finance ontology contribution (CONCEPT:AU-KG.ontology.package-federation-migration).

Data-only subpackage: it carries the three ``owl:Ontology`` modules this
package owns — ``quant.ttl`` (``https://knuckles-team.github.io/ontology/connector/quant``), ``trading.ttl``
(``https://knuckles-team.github.io/ontology/connector/trading``) and ``banking.ttl``
(``https://knuckles-team.github.io/ontology/connector/banking``) — which graph services federate
in via the ``scion_sdk.ontology_providers`` entry-point. The hub loader
globs every ``*.ttl`` in this directory. It holds no business logic and no heavy
imports so the hub can resolve it cheaply.
"""
