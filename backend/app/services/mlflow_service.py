from contextlib import contextmanager
from pathlib import Path

import mlflow

from app.config import settings


def _tracking_uri() -> str:
    uri = settings.mlflow_tracking_uri
    if "://" in uri:
        return uri

    path = Path(uri)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    path.mkdir(parents=True, exist_ok=True)
    return path.as_uri()


def configure_mlflow() -> None:
    mlflow.set_tracking_uri(_tracking_uri())
    mlflow.set_experiment(settings.mlflow_experiment_name)


@contextmanager
def tracked_run(run_name: str, tags: dict | None = None):
    configure_mlflow()
    with mlflow.start_run(run_name=run_name) as run:
        if tags:
            mlflow.set_tags(tags)
        yield run


def registry_status() -> dict:
    configure_mlflow()
    return {
        "tracking_uri": mlflow.get_tracking_uri(),
        "experiment_name": settings.mlflow_experiment_name,
        "status": "configured",
    }
