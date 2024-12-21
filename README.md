# Yad2 Apartment Notifier Bot

This project monitors real estate listings on [Yad2](https://www.yad2.co.il/) and sends notifications via Telegram about new listings that meet specific criteria, such as neighborhood, price, and apartment details.

---

## Features

- Monitors listings for apartments in predefined neighborhoods.
- Sends notifications including address, price, details, and a link to the listing.
- Supports multi-user notifications via Telegram.
- Customizable search parameters via the `neighborhoods.json` file.

---

## Prerequisites

### Software Requirements

- **Python 3.8+**
- Installed dependencies from `requirements.txt`:
  - `aiohttp`
  - `python-telegram-bot`
  - `python-dotenv`
  - `aiogram`
  - `apscheduler`
  - `aiofiles`
  - `aiolimiter`

To install the dependencies, run:

```bash
pip install -r requirements.txt
```

---

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/RoyBidani/Yad2Search.git
cd Yad2Search
```

### 2. Virtual Environment (Optional but Recommended)

Set up a virtual environment to isolate dependencies:

```bash
python -m venv venv
source venv/bin/activate  # For Linux/Mac
venv\Scripts\activate     # For Windows
```

### 3. Configure Environment Variables

Create a `.env` file in the project directory with the following content:

```env
TELEGRAM_BOT_TOKEN=<your-telegram-bot-token>
CHAT_ID_USER=<your-chat-id>  # The admin
CHAT_ID_NAME1=<another-chat-id>
CHAT_ID_NAME2=<another-chat-id>
```

- Replace `<your-telegram-bot-token>` with your bot token.
- Add multiple `CHAT_ID_*` variables for each user who will receive notifications.

### 4. Create the `neighborhoods.json` File

Define the neighborhoods to monitor in a separate `neighborhoods.json` file. An example structure:

```json
[
    {
        "name": "החרוזים רמת גן",
        "topArea": 2,
        "area": 3,
        "city": 8600,
        "rooms": "3-5",
        "price": "4000-7000",
        "balcony": 1,
        "neighborhood": 327,
        "max_pages": 10,
        "forceLdLoad": 1
    }
]
```

- Save the file as `neighborhoods.json` in the same directory as the script.
- Fields such as `rooms`, `price`, and `max_pages` are customizable to your criteria.

### 5. Test the Telegram Bot

Use `test_bot.py` to verify your Telegram integration:

```bash
python test_bot.py
```

This script sends a test message to the specified chat ID to confirm that the bot is working correctly.

---

## How to Create and Connect a Telegram Bot

### Step 1: Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://core.telegram.org/bots#botfather).
2. Start a chat with BotFather and send the command `/newbot`.
3. Follow the instructions to create a bot:
   - Provide a name for your bot.
   - Set a unique username ending with `bot` (e.g., `MyNotifierBot`).
4. Once created, BotFather will provide a **Bot Token**. Save this token securely.

### Step 2: Obtain Chat IDs

1. Start a chat with your bot by searching for its username on Telegram and sending any message.
2. Visit the following URL in your browser, replacing `<your-bot-token>` with your actual bot token:
   ```
   https://api.telegram.org/bot<your-bot-token>/getUpdates
   ```
3. In the JSON response, look for the `"chat"` field under `"message"`. The `"id"` field within `"chat"` is your chat ID.
4. Repeat this process for all users who will interact with the bot.

---

## Running the Application

### Run the Bot

Run the main script to monitor listings and send notifications:

```bash
python main.py --neighborhoods neighborhoods.json
```

If your `neighborhoods.json` file has a custom path or name, provide it with the `--neighborhoods` argument:

```bash
python main.py --neighborhoods /path/to/custom_neighborhoods.json
```

### View Logs

Logs are stored in `bot.log` and can be viewed for troubleshooting or monitoring bot activity.

---

## Troubleshooting

### Common Issues

- **Unauthorized Error**: Ensure that your Telegram Bot Token is correctly set in the `.env` file. This error may also occur if the bot is not properly authorized or if there’s an issue with the chat ID.
- **Connection Timeout**: If you encounter timeouts while sending messages, adjust the connection pool size or increase the timeout values in the bot’s setup.
- **Bot Not Sending Messages**: Check your bot’s permissions and ensure that your chat ID is correct. Review the logs for specific issues with sending messages.

For further assistance, refer to the bot’s logs or check the [Telegram Bot API documentation](https://core.telegram.org/bots/api).


