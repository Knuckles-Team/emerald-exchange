"""Emerald Exchange finance ontology contribution (CONCEPT:KG-2.325).

Data-only subpackage: it carries the three ``owl:Ontology`` modules this
package owns — ``quant.ttl`` (``http://knuckles.team/kg/quant``), ``trading.ttl``
(``http://knuckles.team/kg/trading``) and ``banking.ttl``
(``http://knuckles.team/kg/banking``) — which the agent-utilities hub federates
in via the ``agent_utilities.ontology_providers`` entry-point. The hub loader
globs every ``*.ttl`` in this directory. It holds no business logic and no heavy
imports so the hub can resolve it cheaply.
"""
