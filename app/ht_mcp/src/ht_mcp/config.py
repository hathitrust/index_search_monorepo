from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Base URL of the catalog API (the MCP server calls this)
    catalog_url: str = "http://apache:8080"
    # Host/port the MCP server itself listens on (AI clients connect here)
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    log_level: str = "INFO"
    http_timeout_seconds: int = 10


settings = Settings()
