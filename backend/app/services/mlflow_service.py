from contextlib import contextmanager

import mlflow

from app.config import settings


def configure_mlflow() -> None:
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
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

