import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime, date
import contextlib

from aiohttp import web, ClientSession

logging.basicConfig(level=logging.INFO)

DB_PATH = os.getenv("DB_PATH", "bot.db")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://telegram-post-scheduler.fly.dev")

CREATE_TABLES = [
    """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_superadmin INTEGER DEFAULT 0
        )""",
    """CREATE TABLE IF NOT EXISTS channels (
            chat_id INTEGER PRIMARY KEY,
            title TEXT
        )""",
    """CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_chat_id INTEGER,
            message_id INTEGER,
            target_chat_id INTEGER,
            publish_time TEXT,
            sent INTEGER DEFAULT 0,
            sent_at TEXT
        )""",
]


class Bot:
    def __init__(self, token: str, db_path: str):
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        for stmt in CREATE_TABLES:
            self.db.execute(stmt)
        self.db.commit()
        self.pending = {}
        self.session: ClientSession | None = None
        self.running = False

    async def start(self):
        self.session = ClientSession()
        self.running = True

    async def close(self):
        self.running = False
        if self.session:
            await self.session.close()

        self.db.close()

    async def api_request(self, method: str, data: dict = None):
        async with self.session.post(f"{self.api_url}/{method}", json=data) as resp:
            if resp.status != 200:
                logging.error("API error: %s", await resp.text())
            return await resp.json()

    async def handle_update(self, update):
        if 'message' in update:
            await self.handle_message(update['message'])
        elif 'callback_query' in update:
            await self.handle_callback(update['callback_query'])
        elif 'my_chat_member' in update:
            await self.handle_my_chat_member(update['my_chat_member'])

    async def handle_my_chat_member(self, chat_update):
        chat = chat_update['chat']
        status = chat_update['new_chat_member']['status']
        if status in {'administrator', 'creator'}:
            self.db.execute(
                'INSERT OR REPLACE INTO channels (chat_id, title) VALUES (?, ?)',
                (chat['id'], chat.get('title', chat.get('username', '')))
            )
            self.db.commit()
            logging.info("Added channel %s", chat['id'])

    def get_user(self, user_id):
        cur = self.db.execute('SELECT * FROM users WHERE user_id=?', (user_id,))
        return cur.fetchone()

    def is_authorized(self, user_id):
        return self.get_user(user_id) is not None

    def is_superadmin(self, user_id):
        row = self.get_user(user_id)
        return row and row['is_superadmin']

    async def handle_message(self, message):
        text = message.get('text', '')
        user_id = message['from']['id']

        # first /start registers superadmin
        if text.startswith('/start'):
            # Previous registration logic preserved for future use:
            # if not self.get_user(user_id):
            #     self.db.execute(
            #         'INSERT INTO users (user_id, is_superadmin) VALUES (?, 1)',
            #         (user_id,)
            #     )
            #     self.db.commit()
            #     await self.api_request('sendMessage', {
            #         'chat_id': user_id,
            #         'text': 'You are superadmin'
            #     })
            # else:
            #     await self.api_request('sendMessage', {
            #         'chat_id': user_id,
            #         'text': 'Bot is running'
            #     })
            await self.api_request('sendMessage', {
                'chat_id': user_id,
                'text': 'Bot is working'
            })
            return

        if text.startswith('/add_user') and self.is_superadmin(user_id):
            parts = text.split()
            if len(parts) == 2:
                uid = int(parts[1])
                if not self.get_user(uid):
                    self.db.execute('INSERT INTO users (user_id) VALUES (?)', (uid,))
                    self.db.commit()
                await self.api_request('sendMessage', {
                    'chat_id': user_id,
                    'text': f'User {uid} added'
                })
            return

        if text.startswith('/remove_user') and self.is_superadmin(user_id):
            parts = text.split()
            if len(parts) == 2:
                uid = int(parts[1])
                self.db.execute('DELETE FROM users WHERE user_id=?', (uid,))
                self.db.commit()
                await self.api_request('sendMessage', {
                    'chat_id': user_id,
                    'text': f'User {uid} removed'
                })
            return

        if text.startswith('/list_users') and self.is_superadmin(user_id):
            cur = self.db.execute('SELECT user_id, is_superadmin FROM users')
            rows = cur.fetchall()
            msg = '\n'.join(f"{r['user_id']} {'(admin)' if r['is_superadmin'] else ''}" for r in rows)
            await self.api_request('sendMessage', {'chat_id': user_id, 'text': msg or 'No users'})
            return

        if text.startswith('/channels'):
            cur = self.db.execute('SELECT chat_id, title FROM channels')
            rows = cur.fetchall()
            msg = '\n'.join(f"{r['title']} ({r['chat_id']})" for r in rows)
            await self.api_request('sendMessage', {'chat_id': user_id, 'text': msg or 'No channels'})
            return

        if text.startswith('/history'):
            cur = self.db.execute(
                'SELECT target_chat_id, sent_at FROM schedule WHERE sent=1 ORDER BY sent_at DESC LIMIT 10'
            )
            rows = cur.fetchall()
            msg = '\n'.join(f"{r['target_chat_id']} at {r['sent_at']}" for r in rows)
            await self.api_request('sendMessage', {'chat_id': user_id, 'text': msg or 'No history'})
            return

        # handle time input for scheduling
        if user_id in self.pending and 'await_time' in self.pending[user_id]:
            time_str = text.strip()
            try:
                if len(time_str.split()) == 1:
                    # HH:MM today
                    dt = datetime.strptime(time_str, '%H:%M')
                    pub_time = datetime.combine(date.today(), dt.time())
                else:
                    pub_time = datetime.strptime(time_str, '%d.%m.%Y %H:%M')
            except ValueError:
                await self.api_request('sendMessage', {
                    'chat_id': user_id,
                    'text': 'Invalid time format'
                })
                return
            if pub_time <= datetime.now():
                await self.api_request('sendMessage', {
                    'chat_id': user_id,
                    'text': 'Time must be in future'
                })
                return
            data = self.pending.pop(user_id)
            self.db.execute(
                'INSERT INTO schedule (from_chat_id, message_id, target_chat_id, publish_time) VALUES (?, ?, ?, ?)',
                (data['from_chat_id'], data['message_id'], data['target_chat_id'], pub_time.isoformat())
            )
            self.db.commit()
            await self.api_request('sendMessage', {
                'chat_id': user_id,
                'text': f'Scheduled for {pub_time}'
            })
            return

        # start scheduling on forwarded message
        if 'forward_from_chat' in message and self.is_authorized(user_id):
            from_chat = message['forward_from_chat']['id']
            msg_id = message['forward_from_message_id']
            cur = self.db.execute('SELECT chat_id, title FROM channels')
            rows = cur.fetchall()
            if not rows:
                await self.api_request('sendMessage', {
                    'chat_id': user_id,
                    'text': 'No channels available'
                })
                return
            keyboard = {
                'inline_keyboard': [[{'text': r['title'], 'callback_data': f"channel:{r['chat_id']}"}] for r in rows]
            }
            self.pending[user_id] = {
                'from_chat_id': from_chat,
                'message_id': msg_id
            }
            await self.api_request('sendMessage', {
                'chat_id': user_id,
                'text': 'Choose channel',
                'reply_markup': keyboard
            })
            return
        else:
            if not self.is_authorized(user_id):
                await self.api_request('sendMessage', {
                    'chat_id': user_id,
                    'text': 'Not authorized'
                })

    async def handle_callback(self, query):
        user_id = query['from']['id']
        data = query['data']
        if data.startswith('channel:') and user_id in self.pending:
            chat_id = int(data.split(':')[1])
            self.pending[user_id]['target_chat_id'] = chat_id
            self.pending[user_id]['await_time'] = True
            await self.api_request('sendMessage', {
                'chat_id': user_id,
                'text': 'Enter time (HH:MM or DD.MM.YYYY HH:MM)'
            })
        await self.api_request('answerCallbackQuery', {'callback_query_id': query['id']})


    async def schedule_loop(self):
        """Background scheduler placeholder."""
        # TODO: implement scheduler

        try:
            while self.running:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass


async def ensure_webhook(bot: Bot, base_url: str):
    expected = base_url.rstrip('/') + '/webhook'
    info = await bot.api_request('getWebhookInfo')
    current = info.get('result', {}).get('url')
    if current != expected:
        logging.info('Registering webhook %s', expected)
        resp = await bot.api_request('setWebhook', {'url': expected})
        if not resp.get('ok'):
            logging.error('Failed to register webhook: %s', resp)
            raise RuntimeError(f"Webhook registration failed: {resp}")
        logging.info('Webhook registered successfully')
    else:
        logging.info('Webhook already registered at %s', current)

async def handle_webhook(request):
    bot: Bot = request.app['bot']
    data = await request.json()
    await bot.handle_update(data)
    return web.Response(text='ok')

def create_app():
    app = web.Application()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not found in environment variables")

    bot = Bot(token, DB_PATH)
    app['bot'] = bot

    app.router.add_post('/webhook', handle_webhook)

    webhook_base = WEBHOOK_URL

    async def start_background(app: web.Application):
        logging.info("Application startup")
        try:
            await bot.start()
            await ensure_webhook(bot, webhook_base)
        except Exception:
            logging.exception("Error during startup")
            raise
        app['schedule_task'] = asyncio.create_task(bot.schedule_loop())

    async def cleanup_background(app: web.Application):
        await bot.close()
        app['schedule_task'].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app['schedule_task']


    app.on_startup.append(start_background)
    app.on_cleanup.append(cleanup_background)

    return app


if __name__ == '__main__':

    web.run_app(create_app(), port=int(os.getenv("PORT", 8080)))


