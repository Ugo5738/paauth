from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_anon_key: str = Field(..., env="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(..., env="SUPABASE_SERVICE_ROLE_KEY")
    m2m_jwt_secret_key: str = Field(..., env="M2M_JWT_SECRET_KEY")
    auth_service_database_url: str = Field(..., env="AUTH_SERVICE_DATABASE_URL")
    root_path: str = Field("", env="ROOT_PATH")

    # Define the fields from your .env file
    rate_limit_login: str = Field(default="5/minute", env="RATE_LIMIT_LOGIN")
    rate_limit_register: str = Field(default="5/minute", env="RATE_LIMIT_REGISTER")
    rate_limit_token: str = Field(default="10/minute", env="RATE_LIMIT_TOKEN")
    rate_limit_password_reset: str = Field(
        default="3/minute", env="RATE_LIMIT_PASSWORD_RESET"
    )

    initial_admin_email: str = Field(
        default="admin@admin.com", env="INITIAL_ADMIN_EMAIL"
    )
    initial_admin_password: str = Field(default="admin", env="INITIAL_ADMIN_PASSWORD")

    logging_level: str = Field(default="INFO", env="LOGGING_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
