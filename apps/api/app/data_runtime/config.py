from apps.api.app.core.config import settings


def get_data_database_url() -> str:
    """
    Isolated data/analytics database.

    IMPORTANT:
    - must never reuse runtime authority DB intentionally
    - must never be used for trading authority
    - append-only observational workloads only
    """

    url = getattr(settings, "DATA_DATABASE_URL", "")

    if not url:
        raise RuntimeError(
            "DATA_DATABASE_URL is required for data runtime isolation"
        )

    return str(url)
