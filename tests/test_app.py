import os
import re
import sys
import pytest
from aiohttp import web
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from main import create_app, Bot

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")

@pytest.mark.asyncio
async def test_startup_cleanup(tmp_path):
    os.environ["DB_PATH"] = str(tmp_path / "db.sqlite")
    import main
    main.DB_PATH = os.environ["DB_PATH"]
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
    assert 'tg://user?id=2' in pending_msg[1]['text']
    assert pending_msg[1]['parse_mode'] == 'Markdown'

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


@pytest.mark.asyncio
async def test_list_users_links(tmp_path):
    bot = Bot("dummy", str(tmp_path / "db.sqlite"))

    calls = []

    async def dummy(method, data=None):
        calls.append((method, data))
        return {"ok": True}

    bot.api_request = dummy  # type: ignore
    await bot.start()

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1, "username": "admin"}}})
    await bot.handle_update({"message": {"text": "/start", "from": {"id": 2, "username": "user"}}})
    bot.approve_user(2)

    await bot.handle_update({"message": {"text": "/list_users", "from": {"id": 1}}})
    msg = calls[-1][1]
    assert msg['parse_mode'] == 'Markdown'
    assert 'tg://user?id=1' in msg['text']
    assert 'tg://user?id=2' in msg['text']

    await bot.close()


@pytest.mark.asyncio
async def test_set_timezone(tmp_path):
    bot = Bot("dummy", str(tmp_path / "db.sqlite"))

    calls = []

    async def dummy(method, data=None):
        calls.append((method, data))
        return {"ok": True}

    bot.api_request = dummy  # type: ignore
    await bot.start()

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})
    await bot.handle_update({"message": {"text": "/tz +03:00", "from": {"id": 1}}})

    cur = bot.db.execute("SELECT tz_offset FROM users WHERE user_id=1")
    row = cur.fetchone()
    assert row["tz_offset"] == "+03:00"

    await bot.close()


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


@pytest.mark.asyncio
async def test_schedule_flow(tmp_path):
    bot = Bot("dummy", str(tmp_path / "db.sqlite"))

    calls = []

    async def dummy(method, data=None):
        calls.append((method, data))
        return {"ok": True}

    bot.api_request = dummy  # type: ignore
    await bot.start()

    # register superadmin
    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})

    # bot added to two channels
    await bot.handle_update({
        "my_chat_member": {
            "chat": {"id": -100, "title": "Chan1"},
            "new_chat_member": {"status": "administrator"}
        }
    })
    await bot.handle_update({
        "my_chat_member": {
            "chat": {"id": -101, "title": "Chan2"},
            "new_chat_member": {"status": "administrator"}
        }
    })

    # forward a message to schedule
    await bot.handle_update({
        "message": {
            "forward_from_chat": {"id": 500},
            "forward_from_message_id": 7,
            "from": {"id": 1}
        }
    })
    keyboard = calls[-1][1]["reply_markup"]["inline_keyboard"]
    assert any(btn["callback_data"] == "svc:tg" for btn in keyboard[0])

    # select service and channel
    await bot.handle_update({"callback_query": {"from": {"id": 1}, "data": "svc:tg", "id": "q"}})
    await bot.handle_update({"callback_query": {"from": {"id": 1}, "data": "tgch:-100", "id": "q"}})

    time_str = (datetime.now() + timedelta(minutes=5)).strftime("%H:%M")
    await bot.handle_update({"message": {"text": time_str, "from": {"id": 1}}})
    assert any(c[0] == "forwardMessage" for c in calls)

    cur = bot.db.execute("SELECT target_chat_id FROM schedule")
    rows = [r["target_chat_id"] for r in cur.fetchall()]
    assert rows == [-100]

    # list schedules
    await bot.handle_update({"message": {"text": "/scheduled", "from": {"id": 1}}})
    forward_calls = [c for c in calls if c[0] == "forwardMessage"]
    assert forward_calls
    last_msg = [c for c in calls if c[0] == "sendMessage" and c[1].get("reply_markup")][-1]
    assert "cancel" in last_msg[1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    assert re.search(r"\d{2}:\d{2} \d{2}\.\d{2}\.\d{4}", last_msg[1]["text"])
    assert "Chan1" in last_msg[1]["text"] or "Chan2" in last_msg[1]["text"]

    # cancel first schedule
    cur = bot.db.execute("SELECT id FROM schedule ORDER BY id")
    sid = cur.fetchone()["id"]
    await bot.handle_update({"callback_query": {"from": {"id": 1}, "data": f"cancel:{sid}", "id": "c"}})
    cur = bot.db.execute("SELECT * FROM schedule WHERE id=?", (sid,))
    assert cur.fetchone() is None

    await bot.close()


@pytest.mark.asyncio
async def test_scheduler_process_due(tmp_path):
    bot = Bot("dummy", str(tmp_path / "db.sqlite"))

    calls = []

    async def dummy(method, data=None):
        calls.append((method, data))
        return {"ok": True}

    bot.api_request = dummy  # type: ignore
    await bot.start()

    # register superadmin
    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})

    due_time = (datetime.utcnow() - timedelta(seconds=1)).isoformat()
    bot.add_schedule('tg', 500, 5, -100, due_time)

    await bot.process_due()

    cur = bot.db.execute("SELECT sent FROM schedule")
    row = cur.fetchone()
    assert row["sent"] == 1
    assert calls[-1][0] == "forwardMessage"

    await bot.close()


@pytest.mark.asyncio
async def test_refresh_vk_groups(tmp_path):
    os.environ["DB_PATH"] = str(tmp_path / "db.sqlite")
    os.environ["VK_TOKEN"] = "token"
    bot = Bot("dummy", os.environ["DB_PATH"])

    async def dummy_api(method, data=None):
        return {"ok": True}

    async def dummy_vk(method, params=None):
        return {"response": {"items": [{"id": 123, "name": "Test Group"}]}}

    bot.api_request = dummy_api  # type: ignore
    bot.vk_request = dummy_vk  # type: ignore
    bot.vk_token = "token"
    await bot.start()

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})

    bot.db.execute("DELETE FROM vk_groups")
    bot.db.commit()

    await bot.handle_update({"message": {"text": "/refresh_vkgroups", "from": {"id": 1}}})
    cur = bot.db.execute("SELECT name FROM vk_groups WHERE group_id=123")
    row = cur.fetchone()
    assert row and row["name"] == "Test Group"

    await bot.close()



@pytest.mark.asyncio
async def test_vk_group_token(tmp_path):
    os.environ["DB_PATH"] = str(tmp_path / "db.sqlite")
    os.environ["VK_TOKEN"] = "token"
    os.environ["VK_GROUP_ID"] = "777"
    bot = Bot("dummy", os.environ["DB_PATH"])

    calls = []

    async def dummy_vk(method, params=None):
        calls.append((method, params))
        if method == "groups.get":
            return {"error": {"error_code": 27}}
        if method == "groups.getById":
            assert params.get("group_id") == "777"
            return {"response": [{"id": 777, "name": "My Group"}]}
        return {}

    async def dummy_api(method, data=None):
        return {"ok": True}

    bot.vk_request = dummy_vk  # type: ignore
    bot.api_request = dummy_api  # type: ignore
    await bot.start()

    await bot.handle_update({"message": {"text": "/refresh_vkgroups", "from": {"id": 1}}})
    cur = bot.db.execute("SELECT name FROM vk_groups WHERE group_id=777")
    row = cur.fetchone()
    assert row and row["name"] == "My Group"
    assert ("groups.getById", {"group_id": "777"}) in calls

    await bot.close()



@pytest.mark.asyncio
async def test_vk_post_uses_caption(tmp_path):
    os.environ["DB_PATH"] = str(tmp_path / "db.sqlite")
    os.environ["VK_TOKEN"] = "token"
    bot = Bot("dummy", os.environ["DB_PATH"])

    calls = []

    async def dummy_vk(method, params=None):
        calls.append((method, params))
        return {"response": {"post_id": 1}}

    async def dummy_api(method, data=None):
        return {"ok": True}

    bot.vk_request = dummy_vk  # type: ignore
    bot.api_request = dummy_api  # type: ignore
    bot.db.execute("INSERT INTO vk_groups (group_id, name) VALUES (111, 'G')")
    bot.db.commit()
    await bot.start()

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})

    await bot.handle_update({
        "message": {
            "forward_from_chat": {"id": 500},
            "forward_from_message_id": 7,
            "caption": "hello",
            "from": {"id": 1}
        }
    })
    await bot.handle_update({"callback_query": {"from": {"id": 1}, "data": "svc:vk", "id": "q"}})
    await bot.handle_update({"callback_query": {"from": {"id": 1}, "data": "vkgrp:111", "id": "q"}})
    await bot.handle_update({"callback_query": {"from": {"id": 1}, "data": "sendnow", "id": "q"}})

    assert any(c[0] == "wall.post" and c[1]["message"] == "hello" for c in calls)

    await bot.close()



@pytest.mark.asyncio
async def test_vk_post_with_photo(tmp_path):
    os.environ["DB_PATH"] = str(tmp_path / "db.sqlite")
    os.environ["VK_TOKEN"] = "token"
    bot = Bot("dummy", os.environ["DB_PATH"])

    calls = []

    async def dummy_vk(method, params=None):
        calls.append((method, params))
        if method == "groups.get":
            return {"response": {"items": []}}
        if method == "photos.getWallUploadServer":
            return {"response": {"upload_url": "http://upload"}}
        if method == "photos.saveWallPhoto":
            return {"response": [{"id": 1, "owner_id": 2}]}
        return {"response": {"post_id": 1}}

    async def dummy_api(method, data=None):
        if method == "getFile":
            return {"ok": True, "result": {"file_path": "path"}}
        return {"ok": True}

    async def dummy_upload(url, data):
        return {"photo": "p", "server": 1, "hash": "h"}

    bot.vk_request = dummy_vk  # type: ignore
    bot.api_request = dummy_api  # type: ignore
    bot.vk_upload = dummy_upload  # type: ignore
    bot.db.execute("INSERT INTO vk_groups (group_id, name) VALUES (111, 'G')")
    bot.db.commit()
    await bot.start()
    real_session = bot.session

    class DummyResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

    class DummyGet(DummyResponse):
        async def read(self):
            return b"data"

    class DummyPost(DummyResponse):
        async def text(self):
            return "{}"

    class DummySession:
        def get(self, url):
            return DummyGet()

        def post(self, url, data=None):
            return DummyPost()

        async def close(self):
            pass

    bot.session = DummySession()
    await real_session.close()

    await bot.handle_update({"message": {"text": "/start", "from": {"id": 1}}})

    await bot.handle_update({
        "message": {
            "forward_from_chat": {"id": 500},
            "forward_from_message_id": 7,
            "caption": "hello",
            "photo": [{"file_id": "abc"}],
            "from": {"id": 1}
        }
    })
    await bot.handle_update({"callback_query": {"from": {"id": 1}, "data": "svc:vk", "id": "q"}})
    await bot.handle_update({"callback_query": {"from": {"id": 1}, "data": "vkgrp:111", "id": "q"}})
    await bot.handle_update({"callback_query": {"from": {"id": 1}, "data": "sendnow", "id": "q"}})

    assert ("photos.getWallUploadServer", {"group_id": 111}) in calls
    assert any(c[0] == "wall.post" and "attachments" in c[1] for c in calls)

    await bot.close()

