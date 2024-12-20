import aiohttp
import asyncio
import json
import os
import logging
from urllib.parse import urlencode
from dotenv import load_dotenv  # If using python-dotenv
import argparse

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
        logger.debug(f"Sending message to Chat ID {chat_id}")
        logger.debug(f"Command: {debug_url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params) as response:
                    if response.status == 200:
                        logger.info(f"Message sent to {chat_id}: {message_text}")
                    else:
                        logger.error(f"Failed to send message to {chat_id}: {response.status}, {await response.text()}")
        except Exception as e:
            logger.error(f"Error sending message to {chat_id}: {e}")

# async def send_location_async(bot_token, chat_id, latitude, longitude, semaphore):
#     async with semaphore:
#         url = f"https://api.telegram.org/bot{bot_token}/sendLocation"
#         params = {
#             "chat_id": chat_id,
#             "latitude": latitude,
#             "longitude": longitude,
#         }
#         debug_url = f"{url}?chat_id={chat_id}&latitude={latitude}&longitude={longitude}"
#         logger.debug(f"Sending location to Chat ID {chat_id}")
#         logger.debug(f"Command: {debug_url}")

#         try:
#             async with aiohttp.ClientSession() as session:
#                 async with session.post(url, params=params) as response:
#                     if response.status == 200:
#                         logger.info(f"Location sent to {chat_id} (lat: {latitude}, lon: {longitude})")
#                     else:
#                         logger.error(f"Failed to send location to {chat_id}: {response.status}, {await response.text()}")
#         except Exception as e:
#             logger.error(f"Error sending location to {chat_id}: {e}")

async def fetch_json(session, url, headers, retries=3):
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Attempt {attempt}: Received status code {response.status} for URL: {url}")
                    continue
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Attempt {attempt}: Error fetching {url}: {e}")
        await asyncio.sleep(2)  # Wait before retrying
    logger.error(f"Failed to fetch {url} after {retries} attempts")
    return None

async def process_feed_items(data, unique_links, neighborhood, bot_token, chat_ids, session):
    count = 0
    for d in data.get('data', {}).get('feed', {}).get('feed_items', []):
        try:
            item_id = d.get('id')
            if item_id and item_id not in unique_links and d.get('feed_source') == "private":
                count += 1
        except (KeyError, ValueError):
            continue
    return count

async def handle_new_properties(data, unique_links, neighborhood, bot_token, chat_ids, session, semaphore):
    for d in data.get('data', {}).get('feed', {}).get('feed_items', []):
        try:
            neighborhood_name = d.get('neighborhood', 'Unknown Neighborhood')
            if d.get('feed_source') != "private":
                continue

            Address = d.get('title_1', 'No Address')
            price = d.get('price', 'No Price')
            row_3 = d.get('row_3', ['No Detail 1', 'No Detail 2', 'No Detail 3'])
            details = ", ".join(row_3[:3])
            item_id = d.get('id')
            Addid = f"https://www.yad2.co.il/item/{item_id}"

            if item_id and item_id not in unique_links:
                unique_links.add(item_id)
                message = f'*כתובת*: {Address}, *מחיר*: {price}. *פרטים נוספים*: {details}. [קישור למודעה]({Addid})'

                # Create tasks to send message to all chat_ids
                message_tasks = [
                    asyncio.create_task(send_message_async(bot_token, chat_id, message, semaphore))
                    for chat_id in chat_ids
                ]
                await asyncio.gather(*message_tasks, return_exceptions=True)

                latitude = d.get('coordinates', {}).get('latitude', 0)
                longitude = d.get('coordinates', {}).get('longitude', 0)

                # Create tasks to send location to all chat_ids
                location_tasks = [
                    asyncio.create_task(send_location_async(bot_token, chat_id, latitude, longitude, semaphore))
                    for chat_id in chat_ids
                ]
                await asyncio.gather(*location_tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Error processing feed item: {e}")

def load_neighborhoods(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            neighborhoods = json.load(file)
            logger.debug(f"Loaded {len(neighborhoods)} neighborhoods from {file_path}")
            return neighborhoods
    except FileNotFoundError:
        logger.error(f"Neighborhoods file not found: {file_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error loading neighborhoods from {file_path}: {e}")
        return []

import os
import json
from urllib.parse import urlencode

async def main_task(params, neighborhood, bot_token, chat_ids, session, headers, semaphore):
    json_file_path = 'unique_links.json'
    page_state_file_path = 'page_state.json'

    try:
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r', encoding='utf-8') as json_file:
                unique_links = set(json.load(json_file))
        else:
            unique_links = set()
    except Exception as e:
        logger.error(f"Error reading {json_file_path}: {e}")
        unique_links = set()

    # Load or initialize page state
    try:
        if os.path.exists(page_state_file_path):
            with open(page_state_file_path, 'r', encoding='utf-8') as state_file:
                page_state = json.load(state_file)
        else:
            page_state = {}
    except Exception as e:
        logger.error(f"Error reading {page_state_file_path}: {e}")
        page_state = {}

    search_key = str(params)  # Use the params as a key to identify each search
    starting_page = page_state.get(search_key, 1)
    is_first_run = starting_page == 1

    count = 0
    base_url = "https://gw.yad2.co.il/feed-search-legacy/realestate/rent"

    page = starting_page  # Start with the stored page
    max_pages = 10

    while page <= max_pages:
        params['page'] = page
        filtered_params = {key: value for key, value in params.items() if key != 'name'}
        encoded_params = urlencode(filtered_params)
        final_url = f"{base_url}?{encoded_params}"

        logger.debug(f"Fetching URL: {final_url}")
        response_json = await fetch_json(session, final_url, headers)

        if response_json and 'feed_items' in response_json.get('data', {}).get('feed', {}):
            # Process feed items
            new_count = await process_feed_items(response_json, unique_links, neighborhood, bot_token, chat_ids, session)
            count += new_count
            await handle_new_properties(response_json, unique_links, neighborhood, bot_token, chat_ids, session, semaphore)

            # Stop if no new results are found
            if not response_json['data']['feed']['feed_items']:
                logger.info(f"No more results found on page {page}. Stopping pagination.")
                break

            page += 1  # Go to the next page
        else:
            logger.info(f"No data found or request failed for page {page}. Stopping pagination.")
            break

    # Save the updated unique_links to the JSON file
    try:
        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(list(unique_links), json_file, ensure_ascii=False, indent=4)
            logger.debug(f"Saved unique_links to {json_file_path}")
    except Exception as e:
        logger.error(f"Failed to save unique_links: {e}")

    # Update and save the page state
    page_state[search_key] = page
    try:
        with open(page_state_file_path, 'w', encoding='utf-8') as state_file:
            json.dump(page_state, state_file, ensure_ascii=False, indent=4)
            logger.debug(f"Saved page_state to {page_state_file_path}")
    except Exception as e:
        logger.error(f"Failed to save page_state: {e}")
    # if count > 0:
    #     summary_message = f'דירות חדשות בשכונת *{neighborhood}*: {count}'
    #     summary_tasks = [
    #         asyncio.create_task(send_message_async(bot_token, chat_id, summary_message, semaphore))
    #         for chat_id in chat_ids
    #     ]
    #     await asyncio.gather(*summary_tasks, return_exceptions=True)

    # Save the updated unique_links to the JSON file
    return count > 0


async def run_bot(neighborhoods_file):
    # Load sensitive information from environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    # Collect all CHAT_ID_* variables (including CHAT_ID_USER)
    chat_id_dict = {}  # Dictionary to store name: chat_id pairs
    for key, value in os.environ.items():
        if key.startswith('CHAT_ID_'):
            name = key[len('CHAT_ID_'):]  # Extract the name after 'CHAT_ID_'
            try:
                chat_id = int(value)
                chat_id_dict[name] = chat_id
            except ValueError:
                logger.error(f"Invalid CHAT_ID value for {key}: {value}")

    if not chat_id_dict:
        logger.error("No CHAT_ID_* variables found in .env file.")
        return

    # Log the collected chat_ids with their names
    recipient_names = ', '.join(chat_id_dict.keys())
    logger.info(f"SEND TO: {recipient_names}")

    # Extract chat_ids for further processing
    chat_ids = list(chat_id_dict.values())

    # Load neighborhoods from the specified JSON file
    neighborhoods_params = load_neighborhoods(neighborhoods_file)
    if not neighborhoods_params:
        logger.error("No neighborhoods loaded. Exiting.")
        return

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

    timeout = aiohttp.ClientTimeout(total=60)  # 60 seconds timeout
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
                        chat_ids=chat_ids,
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
    parser = argparse.ArgumentParser(description="Yad2 Apartment Notifier Bot")
    parser.add_argument(
        '--neighborhoods',
        type=str,
        default='neighborhoods.json',
        help='Path to the neighborhoods JSON file'
    )
    args = parser.parse_args()
    asyncio.run(run_bot(args.neighborhoods))
