from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "customer-intelligence-api"
    frontend_origin: str = "http://localhost:5173"
    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str | None = None
    langsmith_project: str = "customer-intelligence-copilot"
    openrouter_api_key: str | None = None
    openrouter_model: str = "nvidia/nemotron-3-super-120b-a12b"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_name: str = "customer-intelligence-copilot"
    openrouter_site_url: str = "http://localhost:5173"
    openrouter_timeout_seconds: int = 60
    openrouter_max_tokens: int = 700
    openrouter_temperature: float = 0.2
    mlflow_tracking_uri: str = "./mlruns"
    mlflow_experiment_name: str = "customer-intelligence-baselines"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "customer_product_embeddings"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    redis_url: str = "redis://localhost:6379/0"
    redis_feature_prefix: str = "ci:features"
    redis_socket_timeout_seconds: float = 2.0
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "customer_intelligence"
    auth_required: bool = True
    auth_jwt_secret: str = "change-me-in-production"
    auth_jwt_issuer: str = "customer-intelligence-api"
    auth_token_ttl_minutes: int = 480
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "ChangeMe123!"
    bootstrap_admin_role: str = "admin"
    seed_dashboard_email: str = "analyst@example.com"
    seed_dashboard_password: str = "Analyst123!"
    seed_dashboard_role: str = "marketing_analyst"
    seed_shop_email: str = "shopper@example.com"
    seed_shop_password: str = "Shopper123!"
    seed_shop_role: str = "customer"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None
    neo4j_database: str = "neo4j"
    neo4j_connection_timeout_seconds: float = 5.0
    ml_recommender_model: str = "content_affinity"
    ml_segmentation_model: str = "kmeans"
    ml_forecast_model: str = "moving_average"
    ml_kmeans_clusters: int = 4
    policy_block_pii: bool = True
    policy_require_tool_rbac: bool = True
    spark_app_name: str = "customer-intelligence-processing"
    spark_master: str = "local[*]"
    emqx_host: str = "localhost"
    emqx_port: int = 1883
    emqx_username: str | None = None
    emqx_password: str | None = None
    emqx_tls_enabled: bool = False
    emqx_client_id: str = "customer-intelligence-api"
    emqx_keepalive_seconds: int = 60
    emqx_qos: int = 1
    emqx_ecommerce_topic: str = "customer-intelligence/ecommerce/events"
    emqx_purchase_topic: str = "customer-intelligence/purchase/events"
    enable_emqx_subscriber: bool = False
    enable_local_event_mirror: bool = True
    emqx_connect_timeout_seconds: float = 5.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
