from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./candidates.db"

    # 104 企業帳號
    account_104_username: str = ""
    account_104_password: str = ""

    # LinkedIn (預留)
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""

    # Scorecard 預設門檻
    scorecard_threshold: float = 70.0

    # Telegram 通知設定
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Cookie 儲存路徑
    cookie_storage_path: str = "/tmp/104_session"

    model_config = {"env_file": ".env"}


settings = Settings()
