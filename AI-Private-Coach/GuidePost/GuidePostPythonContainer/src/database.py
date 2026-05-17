import os
import json
import logging
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger("guidepost.db")

def _build_database_url() -> str:
    """Resolve a SQLAlchemy database URL.

    Priority:
    1) Explicit DATABASE_URL env var (recommended when using a dedicated secret containing the full URL)
    2) Build from RDS Secrets Manager ARN + host (recommended for ECS/Fargate)
    3) Local dev default
    """
    explicit = (os.getenv("DATABASE_URL") or "").strip()
    if explicit:
        return explicit

    # ECS-friendly: build from RDS Secrets Manager secret (JSON with username/password)
    secret_arn = (os.getenv("RDS_MASTER_SECRET_ARN") or os.getenv("DB_SECRET_ARN") or "").strip()
    host = (os.getenv("RDS_HOST") or os.getenv("DB_HOST") or "").strip()
    port = int((os.getenv("RDS_PORT") or os.getenv("DB_PORT") or "5432").strip() or "5432")
    dbname = (os.getenv("DB_NAME") or "postgres").strip() or "postgres"

    if (secret_arn or host) and not (secret_arn and host):
        raise RuntimeError(
            "Incomplete RDS configuration. Provide BOTH RDS_HOST and RDS_MASTER_SECRET_ARN "
            "(or set DATABASE_URL explicitly)."
        )

    if secret_arn and host:
        try:
            import boto3  # type: ignore

            sm = boto3.client("secretsmanager")
            res = sm.get_secret_value(SecretId=secret_arn)
            secret_str = res.get("SecretString") or ""
            payload = json.loads(secret_str) if isinstance(secret_str, str) and secret_str else {}
            if not isinstance(payload, dict):
                payload = {}

            user = str(payload.get("username") or payload.get("user") or "postgres")
            password = str(payload.get("password") or "")
            if not password:
                raise RuntimeError("Missing password in Secrets Manager secret payload.")

            sslmode = (os.getenv("DB_SSLMODE") or "require").strip() or "require"
            sslrootcert = (os.getenv("DB_SSLROOTCERT_PATH") or os.getenv("PGSSLROOTCERT") or "").strip()

            qs = f"sslmode={quote_plus(sslmode)}"
            if sslrootcert and sslmode in {"verify-full", "verify-ca"}:
                qs += f"&sslrootcert={quote_plus(sslrootcert)}"

            logger.info("Using RDS Secrets Manager DB config (host=%s port=%s db=%s sslmode=%s)", host, port, dbname, sslmode)
            return (
                f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(dbname)}?{qs}"
            )
        except Exception as e:
            raise RuntimeError(
                "Failed to build DATABASE_URL from RDS secret. "
                "Set DATABASE_URL explicitly or provide RDS_MASTER_SECRET_ARN + RDS_HOST."
            ) from e

    # Local dev default (docker compose / local postgres)
    logger.warning("Falling back to local DATABASE_URL (localhost). Set DATABASE_URL or RDS_HOST/RDS_MASTER_SECRET_ARN for ECS.")
    return "postgresql://coach:coachpass@localhost:5432/ai_coach"


DATABASE_URL = _build_database_url()

_connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "10"))
_statement_timeout_ms = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "30000"))

# Make startup failures fail fast (important for ECS/Fargate deploys).
# psycopg2 uses connect_timeout in seconds; statement_timeout is in ms.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": _connect_timeout,
        "options": f"-c statement_timeout={_statement_timeout_ms}",
    },
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()