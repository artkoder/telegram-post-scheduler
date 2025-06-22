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

### Development
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run locally:
   ```bash
   python main.py
   ```

### Fly.io
Deploy with:
```bash
fly launch
fly deploy
```

## CI/CD
Каждый push в main запускает GitHub Actions → flyctl deploy → Fly.io.
