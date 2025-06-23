import os
import sys
import pytest
from aiohttp import web

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from main import create_app, Bot

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")

@pytest.mark.asyncio
async def test_startup_cleanup():
    app = create_app()

    async def dummy(method, data=None):
        return {"ok": True}

    app['bot'].api_request = dummy  # type: ignore

    runner = web.AppRunner(app)
    await runner.setup()
    await runner.cleanup()

@pytest.mark.asyncio
async def test_registration_queue(tmp_path):
    bot = Bot("dummy", str(tmp_path / "db.sqlite"))

    async def dummy(method, data=None):
        return {"ok": True}

    bot.api_request = dummy  # type: ignore
    await bot.start()

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})
    row = bot.get_user(1)
    assert row and row["is_superadmin"] == 1

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 2}}})
    assert bot.is_pending(2)

    await bot.close()


@pytest.mark.asyncio
async def test_superadmin_user_management(tmp_path):
    bot = Bot("dummy", str(tmp_path / "db.sqlite"))

    async def dummy(method, data=None):
        return {"ok": True}

    bot.api_request = dummy  # type: ignore
    await bot.start()

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})
    await bot.handle_update({"message": {"text": "/start", "from": {"id": 2}}})
    await bot.handle_update({"message": {"text": "/pending", "from": {"id": 1}}})
    assert bot.is_pending(2)

    await bot.handle_update({"message": {"text": "/approve 2", "from": {"id": 1}}})
    assert bot.get_user(2)
    assert not bot.is_pending(2)

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 3}}})
    await bot.handle_update({"message": {"text": "/reject 3", "from": {"id": 1}}})
    assert not bot.is_pending(3)
    assert not bot.get_user(3)

    await bot.handle_update({"message": {"text": "/remove_user 2", "from": {"id": 1}}})
    assert not bot.get_user(2)

    await bot.close()

