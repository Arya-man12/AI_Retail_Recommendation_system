from functools import lru_cache

from app.config import settings
from app.services.demo_data import dashboard_payload


class GraphServiceError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_neo4j_driver():
    if not settings.neo4j_password:
        raise GraphServiceError("NEO4J_PASSWORD is not configured")

    try:
        from neo4j import GraphDatabase
    except Exception as exc:
        raise GraphServiceError(f"Neo4j driver is not available: {exc}") from exc

    errors = []
    for uri in _neo4j_uri_candidates():
        driver = GraphDatabase.driver(
            uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            connection_timeout=settings.neo4j_connection_timeout_seconds,
            max_connection_lifetime=300,
            max_transaction_retry_time=3,
        )
        try:
            driver.verify_connectivity()
            return driver
        except Exception as exc:
            driver.close()
            errors.append(f"{_uri_scheme(uri)}: {exc}")

    raise GraphServiceError("; ".join(errors) or "Unable to connect to Neo4j")


def graph_status() -> dict:
    try:
        driver = get_neo4j_driver()
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run("RETURN 1 AS ok").single()
    except Exception as exc:
        return {
            "provider": "neo4j",
            "configured": bool(settings.neo4j_password),
            "connected": False,
            "uri": settings.neo4j_uri,
            "database": settings.neo4j_database,
            "error": str(exc),
            "fallback": "demo_customer_360_graph",
        }

    return {
        "provider": "neo4j",
        "configured": True,
        "connected": bool(result and result["ok"] == 1),
        "uri": settings.neo4j_uri,
        "database": settings.neo4j_database,
    }


def seed_demo_graph() -> dict:
    driver = get_neo4j_driver()
    statements = [
        """
        MERGE (c:Customer {id: 'cust-maya-chen'})
        SET c.name = 'Maya Chen', c.segment = 'High-LTV wellness buyer', c.ltv = 18420
        MERGE (p:Product {id: 'sku-hydration'})
        SET p.name = 'Smart Hydration Bundle', p.category = 'wellness'
        MERGE (r:Region {id: 'northeast'})
        SET r.name = 'Northeast'
        MERGE (s:Segment {id: 'high-ltv-wellness'})
        SET s.name = 'High-LTV wellness buyers'
        MERGE (campaign:Campaign {id: 'email-wellness'})
        SET campaign.name = 'Email wellness campaign'
        MERGE (c)-[:VIEWED {weight: 0.88}]->(p)
        MERGE (c)-[:LOCATED_IN]->(r)
        MERGE (c)-[:BELONGS_TO]->(s)
        MERGE (campaign)-[:PROMOTED]->(p)
        MERGE (campaign)-[:TARGETED]->(s)
        """,
        """
        MERGE (c:Customer {id: 'cust-urban-commuter'})
        SET c.name = 'Urban commuter cohort', c.segment = 'loyal_growth', c.ltv = 8600
        MERGE (p:Product {id: 'sku-power'})
        SET p.name = 'Compact Power Kit', p.category = 'commuter'
        MERGE (r:Region {id: 'west'})
        SET r.name = 'West'
        MERGE (c)-[:PURCHASED {weight: 0.74}]->(p)
        MERGE (c)-[:LOCATED_IN]->(r)
        """,
    ]
    with driver.session(database=settings.neo4j_database) as session:
        for statement in statements:
            session.run(statement)
    return {
        "provider": "neo4j",
        "database": settings.neo4j_database,
        "seeded": True,
    }


def seed_demo_graph_if_configured() -> dict:
    if not settings.neo4j_password:
        return {
            "provider": "neo4j",
            "seeded": False,
            "reason": "NEO4J_PASSWORD is not configured",
        }
    try:
        return seed_demo_graph()
    except Exception as exc:
        return {
            "provider": "neo4j",
            "seeded": False,
            "error": str(exc),
        }


def customer_graph(customer_id: str = "cust-maya-chen") -> dict:
    try:
        return _customer_graph_from_neo4j(customer_id)
    except Exception as exc:
        payload = dashboard_payload()
        return {
            "customer_id": customer_id,
            "profile": payload["customers"][0],
            "graph": payload["graph"],
            "relationship_count": len(payload["graph"]["edges"]),
            "source": "demo_customer_360_graph",
            "error": str(exc),
        }


def _customer_graph_from_neo4j(customer_id: str) -> dict:
    driver = get_neo4j_driver()
    query = """
    MATCH (c:Customer {id: $customer_id})-[rel]-(node)
    RETURN c, collect(DISTINCT rel) AS relationships, collect(DISTINCT node) AS neighbors
    """
    with driver.session(database=settings.neo4j_database) as session:
        record = session.run(query, customer_id=customer_id).single()

    if not record:
        raise GraphServiceError(f"No Neo4j customer node found for '{customer_id}'")

    customer = record["c"]
    neighbors = record["neighbors"]
    relationships = record["relationships"]
    nodes = [_node_payload(customer, "customer", 45, 44)]
    node_positions = {customer.get("id"): {"x": 45, "y": 44}}
    positions = [(16, 22), (73, 21), (22, 73), (75, 72), (54, 18)]
    for index, node in enumerate(neighbors):
        x, y = positions[index % len(positions)]
        node_payload = _node_payload(node, _node_kind(node), x, y)
        nodes.append(node_payload)
        node_positions[node_payload["id"]] = {"x": x, "y": y}

    edges = []
    for index, relationship in enumerate(relationships):
        start_id = relationship.start_node.get("id")
        end_id = relationship.end_node.get("id")
        start = node_positions.get(start_id)
        end = node_positions.get(end_id)
        edges.append(
            {
                "id": f"rel-{index}",
                "type": relationship.type,
                "source": start_id,
                "target": end_id,
                "source_position": start,
                "target_position": end,
            }
        )
    return {
        "customer_id": customer_id,
        "profile": {
            "name": customer.get("name") or customer.get("id") or customer_id,
            "segment": customer.get("segment") or "Customer",
            "ltv": _currency(customer.get("ltv")),
            "churnRisk": customer.get("churn_risk") or "Unknown",
            "lastEvent": customer.get("last_event") or "Synced from Neo4j",
            "initials": _initials(customer.get("name") or customer_id),
        },
        "graph": {
            "nodes": nodes,
            "edges": edges,
        },
        "relationship_count": len(edges),
        "source": "neo4j",
    }


def _node_payload(node, kind: str, x: int, y: int) -> dict:
    label = node.get("name") or node.get("id") or kind
    return {
        "id": node.get("id", label),
        "label": str(label).split(" ", 1)[0],
        "kind": kind,
        "x": x,
        "y": y,
    }


def _node_kind(node) -> str:
    labels = set(node.labels)
    if "Product" in labels:
        return "product"
    if "Region" in labels:
        return "region"
    if "Campaign" in labels:
        return "campaign"
    if "Segment" in labels:
        return "segment"
    return "customer"


def _currency(value) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "Unknown"


def _initials(value: str) -> str:
    parts = [part for part in value.replace("-", " ").split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "C"


def _neo4j_uri_candidates() -> list[str]:
    uri = settings.neo4j_uri.strip()
    candidates = [uri]
    if uri.startswith("neo4j+s://"):
        candidates.append(uri.replace("neo4j+s://", "bolt+s://", 1))
    elif uri.startswith("neo4j+ssc://"):
        candidates.append(uri.replace("neo4j+ssc://", "bolt+ssc://", 1))
    return candidates


def _uri_scheme(uri: str) -> str:
    return uri.split("://", 1)[0]
