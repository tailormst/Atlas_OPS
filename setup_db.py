"""
Database setup script for local PostgreSQL.
Creates the 'atlas_ops' database if it doesn't exist.

Usage:
    python setup_db.py

Requires:
    pip install psycopg2-binary python-dotenv
"""

import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv


def setup_database():
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        print("ERROR: psycopg2 not installed.")
        print("Run: pip install psycopg2-binary")
        sys.exit(1)

    # Load .env file
    load_dotenv()

    # Read DATABASE_URL from .env
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ DATABASE_URL not found in .env")
        sys.exit(1)

    # Parse DATABASE_URL
    # Example:
    # postgresql+asyncpg://postgres:password@localhost:5432/atlas_ops

    parsed = urlparse(
        database_url.replace("postgresql+asyncpg", "postgresql")
    )

    DB_HOST = parsed.hostname or "localhost"
    DB_PORT = parsed.port or 5432
    DB_USER = parsed.username
    DB_PASSWORD = parsed.password
    DB_NAME = parsed.path.lstrip("/")

    print(f"Connecting to PostgreSQL at {DB_HOST}:{DB_PORT} as '{DB_USER}'...")

    try:
        # Connect to default postgres DB first
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database="postgres",
        )

        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if DB already exists
        cursor.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (DB_NAME,),
        )

        exists = cursor.fetchone()

        if exists:
            print(f"✅ Database '{DB_NAME}' already exists.")
        else:
            cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"✅ Database '{DB_NAME}' created successfully!")

        cursor.close()
        conn.close()

        # Verify connection to created DB
        conn2 = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
        )

        conn2.close()

        print(f"✅ Successfully connected to '{DB_NAME}'.")

    except psycopg2.OperationalError as e:
        print("\n❌ Could not connect to PostgreSQL!")
        print(f"Error: {e}")

        print("\nCheck the following:")
        print("- PostgreSQL service is running")
        print("- Username/password in .env are correct")
        print("- Port is correct")
        print("- pgAdmin/PostgreSQL is installed properly")

        sys.exit(1)


if __name__ == "__main__":
    setup_database()