from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BlockSikka API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"

    rpc_url: str = "http://127.0.0.1:8545"
    chain_id: int = 1337

    indexer_start_block: int = 0
    indexer_batch_size: int = 500
    indexer_confirmations: int = 0
    indexer_poll_seconds: float = 2.0

    database_url: str = (
        "postgresql+psycopg://"
        "blocksikka:blocksikka_local_dev_password"
        "@127.0.0.1:5432/blocksikka"
    )

    access_manager_address: str = ""
    private_usd_address: str = ""
    bank_registry_address: str = ""
    payment_processor_address: str = ""
    settlement_engine_address: str = ""
    governance_address: str = ""

    bank_admin_private_key: str = ""
    minter_private_key: str = ""
    burner_private_key: str = ""
    freezer_private_key: str = ""
    pauser_private_key: str = ""
    settlement_private_key: str = ""
    relayer_private_key: str = ""

    cors_origins: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
