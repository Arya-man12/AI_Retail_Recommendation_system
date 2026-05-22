from datetime import UTC, datetime

from app.config import settings
from app.services.auth_service import get_mongo_client
from app.services.demo_data import dashboard_payload


DEMO_DASHBOARD_ID = "default-dashboard"


class DashboardDataError(RuntimeError):
    pass


def seed_dashboard_demo_data() -> dict:
    payload = dashboard_payload()
    document = {
        "id": DEMO_DASHBOARD_ID,
        "payload": payload,
        "updated_at": datetime.now(UTC),
    }
    try:
        db = get_mongo_client()[settings.mongodb_database]
        db.demo_dashboard.update_one(
            {"id": DEMO_DASHBOARD_ID},
            {"$set": document},
            upsert=True,
        )
    except Exception as exc:
        return {
            "provider": "mongodb",
            "seeded": False,
            "collection": "demo_dashboard",
            "error": str(exc),
        }

    return {
        "provider": "mongodb",
        "seeded": True,
        "collection": "demo_dashboard",
    }


def get_dashboard_payload() -> dict:
    try:
        db = get_mongo_client()[settings.mongodb_database]
        document = db.demo_dashboard.find_one({"id": DEMO_DASHBOARD_ID}, {"_id": False})
        if document and document.get("payload"):
            return {
                **document["payload"],
                "source": "mongodb",
            }
        raise DashboardDataError("Dashboard data has not been seeded in MongoDB")
    except DashboardDataError:
        raise
    except Exception as exc:
        raise DashboardDataError(f"Unable to load dashboard data from MongoDB: {exc}") from exc
