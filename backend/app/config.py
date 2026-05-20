from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "customer-intelligence-api"
    frontend_origin: str = "http://localhost:5173"
    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str | None = None
    langsmith_project: str = "customer-intelligence-copilot"
    mlflow_tracking_uri: str = "./mlruns"
    mlflow_experiment_name: str = "customer-intelligence-baselines"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "customer_product_embeddings"
    policy_block_pii: bool = True
    policy_require_tool_rbac: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
