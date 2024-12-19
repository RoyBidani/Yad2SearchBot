import aiohttp
import asyncio
import json
import os
import logging
from urllib.parse import urlencode
from io import BytesIO
from aiohttp import ClientError, ClientTimeout
from dotenv import load_dotenv  # If using python-dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed logs
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define a global semaphore to limit concurrent send operations
SEMAPHORE_LIMIT = 5  # Adjust based on testing
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)  # Global semaphore

async def send_message_async(bot_token, chat_id, message_text, semaphore):
    async with semaphore:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "Markdown",
        }
        debug_url = f"{url}?chat_id={chat_id}&text={message_text}"
        logger.debug(f"Token: {bot_token}")
        logger.debug(f"Chat ID: {chat_id}")
        logger.debug(f"Command: {debug_url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params) as response:
                    if response.status == 200:
                        logger.info(f"Message sent to {chat_id}: {message_text}")
                    else:
                        logger.error(f"Failed to send message: {response.status}, {await response.text()}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")

async def send_location_async(bot_token, chat_id, latitude, longitude, semaphore):
    async with semaphore:
        url = f"https://api.telegram.org/bot{bot_token}/sendLocation"
        params = {
            "chat_id": chat_id,
            "latitude": latitude,
            "longitude": longitude,
        }
        debug_url = f"{url}?chat_id={chat_id}&latitude={latitude}&longitude={longitude}"
        logger.debug(f"Token: {bot_token}")
        logger.debug(f"Chat ID: {chat_id}")
        logger.debug(f"Command: {debug_url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params) as response:
                    if response.status == 200:
                        logger.info(f"Location sent to {chat_id} (lat: {latitude}, lon: {longitude})")
                    else:
                        logger.error(f"Failed to send location: {response.status}, {await response.text()}")
        except Exception as e:
            logger.error(f"Error sending location: {e}")

async def fetch_json(session, url, headers, retries=3):
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Attempt {attempt}: Received status code {response.status} for URL: {url}")
                    continue
                return await response.json()
        except (ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Attempt {attempt}: Error fetching {url}: {e}")
        await asyncio.sleep(2)  # Wait before retrying
    logger.error(f"Failed to fetch {url} after {retries} attempts")
    return None

async def process_feed_items(data, unique_date_added, neighborhood, bot_token, chat_id_User, session):
    count = 0
    for d in data.get('data', {}).get('feed', {}).get('feed_items', []):
        try:
            date_added = d['date_added']
            if date_added not in unique_date_added and d.get('feed_source') == "private":
                count += 1
        except (KeyError, ValueError):
            continue
    return count

async def handle_new_properties(data, unique_date_added, neighborhood, bot_token, chat_id_User, session, semaphore):
    for d in data.get('data', {}).get('feed', {}).get('feed_items', []):
        try:
            neighborhood_name = d.get('neighborhood', 'Unknown Neighborhood')
            if d.get('feed_source') != "private":
                continue

            Address = d.get('title_1', 'No Address')
            price = d.get('price', 'No Price')
            row_3 = d.get('row_3', ['No Detail 1', 'No Detail 2', 'No Detail 3'])
            details = ", ".join(row_3[:3])
            date_added = d.get('date_added')
            Addid = f"https://www.yad2.co.il/item/{d.get('id', '')}"

            if date_added and date_added not in unique_date_added:
                unique_date_added.add(date_added)
                message = f'*כתובת*: {Address}, *מחיר*: {price}. *פרטים נוספים*: {details}. [קישור למודעה]({Addid})'
                await send_message_async(bot_token, chat_id_User, message, semaphore)

                latitude = d.get('coordinates', {}).get('latitude', 0)
                longitude = d.get('coordinates', {}).get('longitude', 0)
                await send_location_async(bot_token, chat_id_User, latitude, longitude, semaphore)

        except Exception as e:
            logger.error(f"Error processing feed item: {e}")

async def main_task(params, neighborhood, bot_token, chat_id_User, session, headers, semaphore):
    TotalCheck = False
    json_file_path = 'unique_date_added.json'
    try:
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r', encoding='utf-8') as json_file:
                unique_date_added = set(json.load(json_file))
        else:
            unique_date_added = set()
    except Exception as e:
        logger.error(f"Error reading {json_file_path}: {e}")
        unique_date_added = set()

    count = 0
    base_url = "https://gw.yad2.co.il/feed-search-legacy/realestate/rent"

    for i in range(1):  # Adjust the range as needed for pagination
        params['page'] = i
        filtered_params = {key: value for key, value in params.items() if key != 'name'}
        encoded_params = urlencode(filtered_params)
        final_url = f"{base_url}?{encoded_params}"

        await asyncio.sleep(1)  # Non-blocking sleep
        logger.debug(f"Fetching URL: {final_url}")
        response_json = await fetch_json(session, final_url, headers)

        if response_json:
            # First pass: Count new apartments
            new_count = await process_feed_items(response_json, unique_date_added, neighborhood, bot_token, chat_id_User, session)
            count += new_count
            if new_count > 0:
                TotalCheck = True
                logger.info(f"Found {new_count} new apartments in {neighborhood}")

            # Second pass: Handle new properties
            await handle_new_properties(response_json, unique_date_added, neighborhood, bot_token, chat_id_User, session, semaphore)
        else:
            logger.error(f"Request failed for neighborhood {neighborhood} with URL: {final_url}")

    if count > 0:
        message = f'דירות חדשות בשכונת *{neighborhood}*: {count}'
        await send_message_async(bot_token, chat_id_User, message, semaphore)

    # Save the updated unique_date_added to the JSON file
    try:
        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(list(unique_date_added), json_file, ensure_ascii=False, indent=4)
            logger.debug(f"Saved unique_date_added to {json_file_path}")
    except Exception as e:
        logger.error(f"Failed to save unique_date_added: {e}")

    return TotalCheck

async def run_bot():
    # Load sensitive information from environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    try:
        chat_id_User = int(os.getenv('CHAT_ID_USER'))
    except (TypeError, ValueError):
        logger.error("CHAT_ID_USER must be set as an environment variable and must be an integer.")
        return

    # Debug print for bot token and chat ID
    logger.debug(f"Loaded bot token: {bot_token}")
    logger.debug(f"Loaded chat ID: {chat_id_User}")


    # Define property search parameters for different neighborhoods
    neighborhoods_params = [
        {'name': "הראשונים-רג", 'topArea': 2, 'area': 3, 'city': 8600, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'neighborhood': 1647, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "החשמונאים-רג", 'topArea': 2, 'area': 3, 'city': 8600, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'neighborhood': 1477, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "החרוזים-רג", 'topArea': 2, 'area': 3, 'city': 8600, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'neighborhood': 327, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "בורכוב-גבעתיים", 'topArea': 2, 'area': 3, 'city': 6300, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'neighborhood': 355, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "הלה-גבעתיים", 'topArea': 2, 'area': 3, 'city': 6300, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'neighborhood': 991510, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "ארלוזורוב-גבעתיים", 'topArea': 2, 'area': 3, 'city': 6300, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'neighborhood': 1642, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "גבעת רמבם-גבעתיים", 'topArea': 2, 'area': 3, 'city': 6300, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'neighborhood': 1643, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "קריית יוסף-גבעתיים", 'topArea': 2, 'area': 3, 'city': 6300, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'neighborhood': 1644, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "נחלת יצחק-תל אביב", 'topArea': 2, 'area': 1, 'city': 5000, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'neighborhood': 317, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "מונטיפיורי-תל אביב", 'topArea': 2, 'area': 1, 'city': 5000, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'neighborhood': 485, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "צפון ישן-תל אביב", 'topArea': 2, 'area': 1, 'city': 5000, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'parking': 1, 'neighborhood': 204, 'squaremeter': '65--1', 'forceLdLoad': True},
        {'name': "בבלי-תל אביב", 'topArea': 2, 'area': 1, 'city': 5000, 'rooms': '2.5-4',
         'price': '0-7000', 'balcony': 1, 'parking': 1, 'neighborhood': 1518, 'squaremeter': '65--1', 'forceLdLoad': True},
    ]

    # Define headers (replace with your actual headers)
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Cookie': '__ssds=3; __ssuzjsr3=a9be0cd8e; __uzmaj3=2482bab2-e643-4981-b19f-ca5d3afc7132; __uzmbj3=1687852959; __uzmlj3=PyqZE7dcY4wB1d0cwdis7E=; y2018-2-cohort=87; leadSaleRentFree=82; __uzmb=1687852961; __uzma=1489c434-41b7-4cb2-ba68-54014c40ede2; __uzme=7900; guest_token=eyJhbGciOiJIUz3ZS04ZWQ0LTQ4NDItOTE3YS0zjoxNjg3ODUyOTYxLCJleHAiOjE3MjEwNzY4MTQ4MDN9.15-hRYa5G_B7ASy6lrVllacDfAG8zz08c_riM57i1vs; abTestKey=79; use_elastic_search=1; canary=never; __uzmcj3=105419468535; __uzmdj3=1690528114; __uzmfj3=7; server_env=production; y2_cohort_2020=8; favorites_userid=edd1063272547; __uzmd=; __uzmc=763',
        'Origin': 'https://www.yad2.co.il',
        'Pragma': 'no-cache',
        'Referer': 'https://www.yad2.co.il/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'mainsite_version_commit': '7c9a9c5c1fe45ec28c16bc473d25aad7141f53bd',
        'mobile-app': 'false',
        'sec-ch-ua': 'Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': 'Windows',
    }

    timeout = ClientTimeout(total=60)  # 60 seconds timeout
    data_connector = aiohttp.TCPConnector(limit=50)  # Adjust as needed
    async with aiohttp.ClientSession(connector=data_connector, timeout=timeout) as data_session:
        try:
            tasks = []
            for params in neighborhoods_params:
                task = asyncio.create_task(
                    main_task(
                        params=params,
                        neighborhood=params['name'],
                        bot_token=bot_token,
                        chat_id_User=chat_id_User,
                        session=data_session,
                        headers=headers,
                        semaphore=semaphore
                    )
                )
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(run_bot())