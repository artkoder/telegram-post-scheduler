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


    calls = []

    async def dummy(method, data=None):
        calls.append((method, data))

        return {"ok": True}

    bot.api_request = dummy  # type: ignore
    await bot.start()

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})
    row = bot.get_user(1)
    assert row and row["is_superadmin"] == 1

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 2}}})
    assert bot.is_pending(2)


    # reject user 2 and ensure they cannot re-register
    bot.reject_user(2)
    await bot.handle_update({"message": {"text": "/start", "from": {"id": 2}}})
    assert bot.is_rejected(2)
    assert not bot.is_pending(2)
    assert calls[-1][0] == 'sendMessage'
    assert calls[-1][1]['text'] == 'Access denied by administrator'


    await bot.close()


@pytest.mark.asyncio
async def test_superadmin_user_management(tmp_path):
    bot = Bot("dummy", str(tmp_path / "db.sqlite"))




@pytest.mark.asyncio
async def test_channel_tracking(tmp_path):
    bot = Bot("dummy", str(tmp_path / "db.sqlite"))

    calls = []

    async def dummy(method, data=None):
        calls.append((method, data))
        return {"ok": True}

    bot.api_request = dummy  # type: ignore
    await bot.start()

    # register superadmin
    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})

    # bot added to channel
    await bot.handle_update({
        "my_chat_member": {
            "chat": {"id": -100, "title": "Chan"},
            "new_chat_member": {"status": "administrator"}
        }
    })
    cur = bot.db.execute('SELECT title FROM channels WHERE chat_id=?', (-100,))
    row = cur.fetchone()
    assert row and row["title"] == "Chan"

    await bot.handle_update({"message": {"text": "/channels", "from": {"id": 1}}})
    assert calls[-1][1]["text"] == "Chan (-100)"

    # non-admin cannot list channels
    await bot.handle_update({"message": {"text": "/start", "from": {"id": 2}}})
    await bot.handle_update({"message": {"text": "/channels", "from": {"id": 2}}})
    assert calls[-1][1]["text"] == "Not authorized"

    # bot removed from channel
    await bot.handle_update({
        "my_chat_member": {
            "chat": {"id": -100, "title": "Chan"},
            "new_chat_member": {"status": "left"}
        }
    })
    cur = bot.db.execute('SELECT * FROM channels WHERE chat_id=?', (-100,))
    assert cur.fetchone() is None

    await bot.close()
    calls = []

    async def dummy(method, data=None):
        calls.append((method, data))

        return {"ok": True}

    bot.api_request = dummy  # type: ignore
    await bot.start()

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})
    await bot.handle_update({"message": {"text": "/start", "from": {"id": 2}}})
    await bot.handle_update({"message": {"text": "/pending", "from": {"id": 1}}})
    assert bot.is_pending(2)

    pending_msg = calls[-1]
    assert pending_msg[0] == 'sendMessage'
    assert pending_msg[1]['reply_markup']['inline_keyboard'][0][0]['callback_data'] == 'approve:2'


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
