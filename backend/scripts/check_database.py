from sqlalchemy import inspect, text

from app.db.session import engine


def main() -> None:
    with engine.connect() as connection:
        database = connection.execute(
            text(
                "SELECT current_database()"
            )
        ).scalar_one()

        user = connection.execute(
            text(
                "SELECT current_user"
            )
        ).scalar_one()

        version = connection.execute(
            text(
                "SHOW server_version"
            )
        ).scalar_one()

    inspector = inspect(engine)

    tables = sorted(
        inspector.get_table_names()
    )

    print(f"Database: {database}")
    print(f"User: {user}")
    print(f"PostgreSQL: {version}")

    print()
    print("Tables:")

    for table in tables:
        print(f"  - {table}")


if __name__ == "__main__":
    main()
