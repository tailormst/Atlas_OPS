import asyncio
from pathlib import Path

# pyrefly: ignore [missing-import]
from sqlalchemy import text

from app.core.config import get_settings

settings = get_settings()


async def check_postgres():
    try:
        # pyrefly: ignore [missing-import]
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(settings.database_url)

        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        await engine.dispose()

        print("✅ PostgreSQL: Connected successfully.")

    except Exception as e:
        print("❌ PostgreSQL: Connection failed.")
        print(f"Error: {str(e)}")
        print("Ensure PostgreSQL is running and DATABASE_URL in .env is correct.")


async def check_redis():
    try:
        # pyrefly: ignore [missing-import]
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(settings.redis_url)

        await redis_client.ping()
        await redis_client.aclose()

        print("✅ Redis: Connected successfully.")

    except Exception as e:
        print("❌ Redis: Connection failed.")
        print(f"Error: {str(e)}")
        print("Ensure Redis is running on localhost:6379.")


def check_models():
    models = [
        settings.fraud_model_path,
        settings.failure_model_path,
        settings.routing_model_path,
    ]

    for path in models:
        if Path(path).exists():
            print(f"✅ ML Model: Found {path}")
        else:
            print(f"⚠️ ML Model: Missing {path}")
            print("   Fallback models will be used.")


async def main():
    print("\n--- ATLAS-OPS Local Setup Check ---\n")

    await check_postgres()
    await check_redis()

    print()
    check_models()

    print("\n-----------------------------------\n")


if __name__ == "__main__":
    asyncio.run(main())