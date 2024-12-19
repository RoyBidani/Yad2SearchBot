import os
import asyncio
from telegram import Bot
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed logs
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("test_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def send_test_message():
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('CHAT_ID_USER')

    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set.")
        return
    if not chat_id:
        logger.error("CHAT_ID_USER is not set.")
        return

    try:
        chat_id = int(chat_id)
    except ValueError:
        logger.error("CHAT_ID_USER must be an integer.")
        return

    # Initialize the Bot with HTTPXRequest with increased connection pool size and proper timeouts
    request = HTTPXRequest(
        connection_pool_size=20,
        connect_timeout=60,  # Connection timeout in seconds
        read_timeout=60      # Read timeout in seconds
    )
    bot = Bot(token=bot_token, request=request)

    try:
        await bot.send_message(chat_id=chat_id, text="Hello from your bot!", parse_mode='Markdown')
        logger.info("Test message sent successfully!")
    except Exception as e:
        logger.error(f"Failed to send test message: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(send_test_message())
