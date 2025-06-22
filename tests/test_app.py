import os
import sys
import pytest
from aiohttp import web

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from main import create_app

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")

@pytest.mark.asyncio
async def test_startup_cleanup():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    await runner.cleanup()
