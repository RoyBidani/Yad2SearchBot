
# Yad2 Apartment Notifier Bot

This project monitors real estate listings on [Yad2](https://www.yad2.co.il/) and notifies users via Telegram about new listings that meet specified criteria. It allows customization for specific neighborhoods and integrates seamlessly with Telegram for real-time notifications.

---

## Features

- Monitors listings for apartments in predefined neighborhoods.
- Sends detailed notifications, including location, address, and price, directly to Telegram.
- Allows customization of search criteria such as price, rooms, and neighborhoods.

---

## Prerequisites

### Software Requirements

- **Python 3.8+**
- Installed dependencies from `requirements.txt`:
  - `aiohttp`
  - `python-telegram-bot`
  - `python-dotenv`

To install the dependencies, run:
```bash
pip install -r requirements.txt
```

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/Toms422/Yad2Search.git
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
CHAT_ID_USER=<your-chat-id>
```

### 4. Obtain Telegram Bot Token and Chat ID

1. **Telegram Bot Token**:
   - Open Telegram and message [@BotFather](https://core.telegram.org/bots#botfather).
   - Create a new bot using `/newbot`.
   - Follow the instructions to receive a unique bot token.

2. **Chat ID**:
   - Start a chat with your bot and send any message.
   - Visit `https://api.telegram.org/bot<your-bot-token>/getUpdates` to find your chat ID from the JSON response.

Replace `<your-telegram-bot-token>` and `<your-chat-id>` with your actual values.

---

## Usage

### Running the Main Script

Run the bot to monitor listings and send notifications:

```bash
python main.py
```

### Testing the Bot

Use `test_bot.py` to verify your Telegram integration:

```bash
python test_bot.py
```

This script sends a test message to your chat ID to confirm the bot setup.

---

## Customization

### Modifying Search Parameters

You can customize the search parameters for different neighborhoods by editing the `neighborhoods_params` list in `main.py`. Example:

```python
{
    'name': "Example Neighborhood",
    'topArea': 2,
    'area': 3,
    'city': 8600,
    'rooms': '2.5-4',
    'price': '0-7000',
    'balcony': 1,
    'neighborhood': 1647,
    'squaremeter': '65--1',
    'forceLdLoad': True
}
```

- `city`: The city code (e.g., 8600 for Ramat Gan).
- `rooms`: Range of room counts (e.g., '2.5-4').
- `price`: Price range in NIS.
- `neighborhood`: Neighborhood code.

### Logging and Debugging

Logs are saved to `bot.log` for monitoring execution details and debugging.

---

## Data Persistence

- **File**: `unique_date_added.json`
  - Stores the IDs of listings already processed to avoid duplicate notifications.
  - Automatically updated after each successful notification.

---

## Troubleshooting

### Common Errors

1. **Missing Tokens**:
   - Ensure `TELEGRAM_BOT_TOKEN` and `CHAT_ID_USER` are correctly set in the `.env` file.
   
2. **Bot Not Responding**:
   - Check logs in `bot.log` for details.
   - Verify network connectivity and Telegram API status.

3. **Dependencies Issues**:
   - Run `pip install -r requirements.txt` to ensure all dependencies are installed.

---

## Contributing

Feel free to contribute by submitting issues or pull requests.

---

