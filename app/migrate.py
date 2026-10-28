from shared.config import Settings
from shared.db import Store


def main():
    settings = Settings()
    if not settings.database_url:
        raise SystemExit("Set AGENT_DATABASE_URL to the intended isolated database")
    Store(settings.database_url.get_secret_value()).migrate()
    print("Agent migrations applied or already current")


if __name__ == "__main__":
    main()
