from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = Field(..., json_schema_extra={"env": "SUPABASE_URL"})
    supabase_anon_key: str = Field(..., json_schema_extra={"env": "SUPABASE_ANON_KEY"})
    supabase_service_role_key: str = Field(
        ..., json_schema_extra={"env": "SUPABASE_SERVICE_ROLE_KEY"}
    )
    supabase_email_confirmation_required: bool = Field(
        default=True, json_schema_extra={"env": "SUPABASE_EMAIL_CONFIRMATION_REQUIRED"}
    )
    supabase_auto_confirm_new_users: bool = Field(
        default=False, json_schema_extra={"env": "SUPABASE_AUTO_CONFIRM_NEW_USERS"}
    )
    m2m_jwt_secret_key: str = Field(
        ..., json_schema_extra={"env": "M2M_JWT_SECRET_KEY"}
    )
    m2m_jwt_algorithm: str = Field(
        default="HS256", json_schema_extra={"env": "M2M_JWT_ALGORITHM"}
    )
    m2m_jwt_issuer: str = Field(
        default="paauth_auth_service", json_schema_extra={"env": "M2M_JWT_ISSUER"}
    )
    m2m_jwt_audience: str = Field(
        default="paauth_microservices", json_schema_extra={"env": "M2M_JWT_AUDIENCE"}
    )
    m2m_jwt_access_token_expire_minutes: int = Field(
        default=30, json_schema_extra={"env": "M2M_JWT_ACCESS_TOKEN_EXPIRE_MINUTES"}
    )
    auth_service_database_url: str = Field(
        ..., json_schema_extra={"env": "AUTH_SERVICE_DATABASE_URL"}
    )
    root_path: str = Field("", json_schema_extra={"env": "ROOT_PATH"})

    # Define the fields from your .env file
    rate_limit_login: str = Field(
        default="5/minute", json_schema_extra={"env": "RATE_LIMIT_LOGIN"}
    )
    rate_limit_register: str = Field(
        default="5/minute", json_schema_extra={"env": "RATE_LIMIT_REGISTER"}
    )
    rate_limit_token: str = Field(
        default="10/minute", json_schema_extra={"env": "RATE_LIMIT_TOKEN"}
    )
    rate_limit_password_reset: str = Field(
        default="3/minute", json_schema_extra={"env": "RATE_LIMIT_PASSWORD_RESET"}
    )

    initial_admin_email: str = Field(
        default="admin@admin.com", json_schema_extra={"env": "INITIAL_ADMIN_EMAIL"}
    )
    initial_admin_password: str = Field(
        default="admin", json_schema_extra={"env": "INITIAL_ADMIN_PASSWORD"}
    )

    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # OAuth Settings
    OAUTH_REDIRECT_URI: str = (
        "http://localhost:8000/auth/users/login/google/callback"  # Default, adjust per provider if needed
    )
    OAUTH_STATE_COOKIE_NAME: str = "pa_oauth_state"
    OAUTH_STATE_COOKIE_MAX_AGE_SECONDS: int = 300  # 5 minutes

    # Provider-specific OAuth Settings (Example for Google, extend as needed)
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    logging_level: str = Field(
        default="INFO", json_schema_extra={"env": "LOGGING_LEVEL"}
    )
    PASSWORD_RESET_REDIRECT_URL: str = Field(
        default="http://localhost:3000/auth/update-password",
        json_schema_extra={"env": "PASSWORD_RESET_REDIRECT_URL"},
    )

    model_config = ConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


settings = Settings()
