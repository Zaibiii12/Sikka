from sqlalchemy import text

from app.db.session import engine


class DatabaseService:
    def status(self) -> dict:
        with engine.connect() as connection:
            database_name = connection.execute(
                text(
                    "SELECT current_database()"
                )
            ).scalar_one()

            database_user = connection.execute(
                text(
                    "SELECT current_user"
                )
            ).scalar_one()

            version = connection.execute(
                text(
                    "SHOW server_version"
                )
            ).scalar_one()

        return {
            "connected": True,
            "database": database_name,
            "user": database_user,
            "server_version": version,
        }
