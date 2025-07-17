# Telegram Scheduler Bot

This bot allows authorized users to schedule posts to their Telegram channels or VK communities.

## Features
- User authorization with superadmin.
- Channel tracking where bot is admin.
- Schedule message forwarding to Telegram channels or posting to VK groups. The bot forwards the original post so views and custom emoji are preserved in Telegram, while the post caption is sent as text to VK.
- If forwarding fails (e.g., bot not in source), the message is copied instead.
- View posting history.
- User lists show clickable usernames for easy profile access.
- Local timezone support for scheduling.
- Configurable scheduler interval.


## Commands
- /start - register or access bot
- /pending - list pending users (admin)
- /approve <id> - approve user
- /reject <id> - reject user
- /list_users - list approved users
- /remove_user <id> - remove user
- /channels - list Telegram channels (admin)
- /vkgroups - list connected VK groups (admin)
- /refresh_vkgroups - reload VK groups using current token (admin)
- /scheduled - show scheduled posts with target channel names
- /history - recent posts
- /tz <offset> - set timezone offset (e.g., +02:00)
- Forward a post to the bot, choose Telegram or VK, then select a channel/group and time or "Now" to publish. VK posts use the caption of the forwarded message as their text.

## User Stories

### Done
- **US-1**: Registration of the first superadmin.
- **US-2**: User registration queue with limits and admin approval flow.
- **US-3**: Superadmin manages pending and approved users. Rejected users cannot
  register again. Pending and approved lists display clickable usernames with
  inline approval buttons.
- **US-4**: Channel listener events and `/channels` command.
- **US-5**: Post scheduling interface with channel selection, cancellation and rescheduling. Scheduled list shows the post preview or link along with the target channel name and time in HH:MM DD.MM.YYYY format.
 - **US-6**: Scheduler forwards queued posts at the correct local time. If forwarding fails because the bot is not a member, it falls back to copying. Interval is configurable and all actions are logged.

### In Progress
- **US-7**: Logging of all operations.

### Planned
- none

## Deployment
The bot is designed for Fly.io using a webhook on `/webhook` and listens on port `8080`.
For Telegram to reach the webhook over HTTPS, the Fly.io service must expose port `443` with TLS termination enabled. This is configured in `fly.toml`.

### Environment Variables
- `TELEGRAM_BOT_TOKEN` – Telegram bot API token.

- `WEBHOOK_URL` – external HTTPS URL of the deployed application. Used to register the Telegram webhook.

- `DB_PATH` – path to the SQLite database (default `/data/bot.db`).
- `VK_TOKEN` – user or community access token for posting to VK. When using a community token, set `VK_GROUP_ID` to the numeric group id. User tokens require `wall` and `groups` permissions, and the user must be an admin of the communities. The bot loads accessible groups at startup or via `/refresh_vkgroups`.
- `VK_GROUP_ID` – id of the VK community if using a group access token.
- `FLY_API_TOKEN` – token for automated Fly deployments.
- `TZ_OFFSET` – default timezone offset like `+02:00`.
- `SCHED_INTERVAL_SEC` – scheduler check interval in seconds (default `30`).

### Запуск локально
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Запустите бота:
   ```bash
   python main.py
   ```

> Fly.io secrets `TELEGRAM_BOT_TOKEN`, `FLY_API_TOKEN` и при необходимости `VK_TOKEN` должны быть заданы перед запуском.


### Деплой на Fly.io

1. Запустить приложение в первый раз (из CLI, однократно):

```bash
fly launch
fly volumes create sched_db --size 1

The volume is mounted to `/data`, so set `DB_PATH=/data/bot.db` to keep data between deployments.


```

2. После этого любой push в ветку `main` будет автоматически триггерить деплой.

3. Все секреты устанавливаются через Fly.io UI или CLI:

```bash
fly secrets set TELEGRAM_BOT_TOKEN=xxx
fly secrets set WEBHOOK_URL=https://<app-name>.fly.dev/
fly secrets set VK_TOKEN=<vk_user_token>
fly secrets set VK_GROUP_ID=<vk_group_id>  # if using a community token
```

The `fly.toml` file should expose port `443` so that Telegram can connect over HTTPS.

## CI/CD
Каждый push в main запускает GitHub Actions → flyctl deploy → Fly.io.

