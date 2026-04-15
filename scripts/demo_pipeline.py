from __future__ import annotations

import asyncio

import httpx


BASE_URL = "http://localhost:8079/api/v1"

DEMO_REQUESTS = [
    {
        "raw_input": "Можно ли удержать часть зарплаты сотрудника за ущерб?",
        "priority": "NORMAL",
        "channel": "API",
    },
    {
        "raw_input": "Нужно ли отдельное согласие на обработку ПДн при трудоустройстве?",
        "priority": "NORMAL",
        "channel": "API",
    },
    {
        "raw_input": "Проверь этот пункт договора на одностороннее изменение цены",
        "priority": "HIGH",
        "channel": "API",
    },
    {
        "raw_input": "У нас иск на 15 млн рублей, заседание через 3 дня",
        "priority": "URGENT",
        "channel": "API",
    },
    {
        "raw_input": "Подготовь чек-лист по смене директора ООО",
        "priority": "NORMAL",
        "channel": "API",
    },
]


async def main() -> None:
    """Run demo: login → submit requests → health check → list models."""
    print("🚀 LegalOpsAI-Pipeline Demo\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("1️⃣  Авторизация...")
        resp = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": "admin@legalops.ru", "password": "Admin123!@#"},
        )
        if resp.status_code != 200:
            print(f"   ❌ Login failed: {resp.status_code} {resp.text}")
            return
        tokens = resp.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        print("   ✅ Авторизован\n")

        for i, req in enumerate(DEMO_REQUESTS, 1):
            print(f"2.{i}  Запрос: {req['raw_input'][:60]}...")
            resp = await client.post(
                f"{BASE_URL}/requests/",
                json=req,
                headers=headers,
            )
            if resp.status_code == 201:
                data = resp.json()
                print(f"   ✅ request_id={data['request_id']}")
                print(f"      pipeline_run_id={data['pipeline_run_id']}")
            else:
                print(f"   ❌ {resp.status_code}: {resp.text[:100]}")
            print()

        print("3️⃣  Health check...")
        resp = await client.get(f"{BASE_URL}/health/ready")
        print(f"   Status: {resp.json()}\n")

        print("4️⃣  Модели Ollama...")
        resp = await client.get(f"{BASE_URL}/health/models")
        print(f"   {resp.json()}\n")

    print("✅ Demo завершено!")


if __name__ == "__main__":
    asyncio.run(main())
