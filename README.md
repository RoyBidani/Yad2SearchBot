
# Yad2 Apartment Notifier Bot

This project monitors real estate listings on [Yad2](https://www.yad2.co.il/) and notifies users via Telegram about new listings that meet specified criteria. It supports multi-user notifications, dynamic configuration, and integrates seamlessly with Telegram for real-time notifications.

---

## Features

- Monitors listings for apartments in predefined neighborhoods.
- Sends detailed notifications, including location, address, and price, directly to Telegram.
- Supports multi-user notifications by dynamically scanning `.env` variables for multiple chat IDs.
- Customizable search parameters via an external `neighborhoods.json` file.
- Persists processed listing data to avoid duplicate notifications using `unique_date_added.json`.

---

## Prerequisites

### Software Requirements

- **Python 3.8+**
- Installed dependencies from `requirements.txt`:
  - `aiohttp`
  - `python-dotenv`

To install the dependencies, run:
```bash
pip install -r requirements.txt
```

---

## Setup Instructions

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

---

### 4. Create the `neighborhoods.json` File

Define the neighborhoods to monitor in a separate `neighborhoods.json` file. An example structure:

```json
[
    {
        "name": "Example Neighborhood",
        "topArea": 2,
        "area": 3,
        "city": 8600,
        "rooms": "2.5-4",
        "price": "0-7000",
        "balcony": 1,
        "neighborhood": 1647,
        "squaremeter": "65--1",
        "forceLdLoad": true
    }
]
```

- Save the file as `neighborhoods.json` in the same directory as the script.
- Fields such as `rooms`, `price`, and `squaremeter` are customizable to your criteria.

---

## How to Create a Telegram Bot and Obtain Token/Chat IDs

### 1. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://core.telegram.org/bots#botfather).
2. Start a chat with BotFather and send the command `/newbot`.
3. Follow the instructions to create a bot:
   - Provide a name for your bot.
   - Set a unique username ending with `bot` (e.g., `MyNotifierBot`).
4. Once created, BotFather will provide a **Bot Token**. Save this token securely.

### 2. Obtain Chat IDs

1. Start a chat with your bot by searching for its username on Telegram and sending any message.
2. Visit the following URL in your browser, replacing `<your-bot-token>` with your actual bot token:
   ```
   https://api.telegram.org/bot<your-bot-token>/getUpdates
   ```
3. In the JSON response, look for the `"chat"` field under `"message"`. The `"id"` field within `"chat"` is your chat ID.
4. Repeat this process for all users who will interact with the bot.

---

## Usage

### Running the Main Script

Run the bot to monitor listings and send notifications:

```bash
python main.py --neighborhoods neighborhoods.json
```

If your `neighborhoods.json` file has a custom path or name, provide it with the `--neighborhoods` argument.

### Testing the Bot

Use `test_bot.py` to verify your Telegram integration:

```bash
python test_bot.py
```

This script sends a test message to all specified chat IDs to confirm the bot setup.

---

## Data Persistence

### `unique_date_added.json`

- This file stores the IDs of listings already processed to avoid duplicate notifications.
- It is automatically updated after each successful notification.
- If the file is deleted or its contents are cleared, all listings will be reprocessed as if they were new.

---

## Multi-User Notifications

- The script dynamically scans the `.env` file for all `CHAT_ID_*` variables.
- Each variable corresponds to a recipient who will receive notifications.
- Logs the list of recipients (usernames) at the start of execution for transparency.

---

## Customization

### Modifying Search Parameters

You can customize the search parameters for different neighborhoods by editing the `neighborhoods.json` file. Example:

```json
{
    "name": "New Neighborhood",
    "topArea": 2,
    "area": 3,
    "city": 8600,
    "rooms": "3-5",
    "price": "0-7000",
    "balcony": 1,
    "neighborhood": 327,
    "squaremeter": "120--1",
    "forceLdLoad": true
}
```

- `city`: The city code (e.g., 8600 for Ramat Gan).
- `rooms`: Range of room counts (e.g., `"3-5"`).
- `price`: Price range in NIS.
- `squaremeter`: Size range in square meters.

---

## Troubleshooting

### Common Errors

1. **Missing Tokens**:
   - Ensure `TELEGRAM_BOT_TOKEN` and `CHAT_ID_*` variables are correctly set in the `.env` file.

2. **Bot Not Responding**:
   - Check logs in `bot.log` for details.
   - Verify network connectivity and Telegram API status.

3. **Dependencies Issues**:
   - Run `pip install -r requirements.txt` to ensure all dependencies are installed.

---

## Security Considerations

- **Environment Variables**: Protect the `.env` file as it contains sensitive information like bot tokens and chat IDs.
- **Rate Limiting**: Avoid exceeding Telegram API rate limits by testing with a small number of recipients first.

---

## Contributing

Feel free to contribute by submitting issues or pull requests.

---

## Final Notes

- Regularly back up the `unique_date_added.json` file to prevent data loss.
- Ensure all `.env` variables and `neighborhoods.json` are correctly configured before execution.
- Logs (`bot.log`) provide detailed execution flow and can assist with debugging.
