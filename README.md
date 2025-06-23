# Telegram Scheduler Bot

This bot allows authorized users to schedule posts to their Telegram channels.

## Features
- User authorization with superadmin.
- Channel tracking where bot is admin.
- Schedule message forwarding to channels.
- View posting history.

## User Stories

### Done
- **US-1**: Registration of the first superadmin.
- **US-2**: User registration queue with limits and admin approval flow.
- **US-3**: Superadmin manages pending and approved users. Rejected users cannot
  register again and pending users are shown with inline approval buttons.

### In Progress
- **US-4**: Channel listener events and `/channels` command.

### Planned
- **US-5**: Post scheduling interface.
- **US-6**: Background scheduler to publish messages.
- **US-7**: Logging of all operations.

## Deployment
The bot is designed for Fly.io using a webhook on `/webhook` and listens on port `8080`.
For Telegram to reach the webhook over HTTPS, the Fly.io service must expose port `443` with TLS termination enabled. This is configured in `fly.toml`.

### Environment Variables
- `TELEGRAM_BOT_TOKEN` – Telegram bot API token.

- `WEBHOOK_URL` – external HTTPS URL of the deployed application. Used to register the Telegram webhook.

- `DB_PATH` – path to the SQLite database (default `bot.db`).
- `FLY_API_TOKEN` – token for automated Fly deployments.

### Запуск локально
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Запустите бота:
   ```bash
   python main.py
   ```

> Fly.io secrets `TELEGRAM_BOT_TOKEN` и `FLY_API_TOKEN` должны быть заданы перед запуском.


### Деплой на Fly.io

1. Запустить приложение в первый раз (из CLI, однократно):

```bash
fly launch
fly volumes create sched_db --size 1


```

2. После этого любой push в ветку `main` будет автоматически триггерить деплой.

3. Все секреты устанавливаются через Fly.io UI или CLI:

```bash
fly secrets set TELEGRAM_BOT_TOKEN=xxx
fly secrets set WEBHOOK_URL=https://<app-name>.fly.dev/
```

The `fly.toml` file should expose port `443` so that Telegram can connect over HTTPS.

## CI/CD
Каждый push в main запускает GitHub Actions → flyctl deploy → Fly.io.

