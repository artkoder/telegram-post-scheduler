# Telegram Scheduler Bot

This bot allows authorized users to schedule posts to their Telegram channels.

## Features
- User authorization with superadmin.
- Channel tracking where bot is admin.
- Schedule message forwarding to channels.
- View posting history.

## Deployment
The bot is designed for Fly.io using a webhook on `/webhook` and listens on port `8080`.

### Environment Variables
- `TELEGRAM_BOT_TOKEN` – Telegram bot API token.
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
```

4. Переменная окружения FLY_API_TOKEN должна быть добавлена в Github репозиторий для работы CI/CD.


4. Переменная окружения FLY_API_TOKEN должна быть добавлена в Github репозиторий для работы CI/CD.


## CI/CD
Каждый push в main запускает GitHub Actions → flyctl deploy → Fly.io.

