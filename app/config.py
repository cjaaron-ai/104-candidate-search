from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./candidates.db"

    # 104 企業帳號
    account_104_username: str = ""
    account_104_password: str = ""

    # LinkedIn (預留)
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""

    # 排程設定（分鐘）
    search_interval_minutes: int = 1440  # 預設每日

    # Scorecard 預設門檻
    scorecard_threshold: float = 70.0

    model_config = {"env_file": ".env"}


settings = Settings()
