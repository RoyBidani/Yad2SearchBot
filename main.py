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
SEMAPHORE_LIMIT = 10  # Increased based on need for concurrency
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

async def handle_new_properties(data, unique_links, neighborhood, bot_token, chat_ids, session, semaphore):
    count = 0
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
                # location_tasks = [
                #     asyncio.create_task(send_location_async(bot_token, chat_id, latitude, longitude, semaphore))
                #     for chat_id in chat_ids
                # ]
                # await asyncio.gather(*location_tasks, return_exceptions=True)

                count += 1  # Increase the count for each new property

        except Exception as e:
            logger.error(f"Error processing feed item: {e}")
    return count

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

async def main_task(params, neighborhood, bot_token, chat_ids, session, headers, semaphore):
    json_file_path = 'unique_links.json'
    page_state_file_path = 'page_state.json'

    # Load unique links from file
    try:
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r', encoding='utf-8') as json_file:
                unique_links = set(json.load(json_file))
        else:
            unique_links = set()
    except Exception as e:
        logger.error(f"Error reading {json_file_path}: {e}")
        unique_links = set()

    # Load page state
    try:
        if os.path.exists(page_state_file_path):
            with open(page_state_file_path, 'r', encoding='utf-8') as state_file:
                page_state = json.load(state_file)
        else:
            page_state = {}
    except Exception as e:
        logger.error(f"Error reading {page_state_file_path}: {e}")
        page_state = {}

    search_key = str(params)
    starting_page = page_state.get(search_key, 1)

    count = 0
    base_url = "https://gw.yad2.co.il/feed-search-legacy/realestate/rent"

    page = starting_page
    max_pages = 10  # Set the maximum pages to fetch

    while page <= max_pages:
        params['page'] = page
        filtered_params = {key: value for key, value in params.items() if key != 'name'}
        encoded_params = urlencode(filtered_params)
        final_url = f"{base_url}?{encoded_params}"

        logger.debug(f"Fetching URL: {final_url}")
        response_json = await fetch_json(session, final_url, headers)

        if response_json and 'feed_items' in response_json.get('data', {}).get('feed', {}):
            # Process the feed items and handle new properties
            new_count = await handle_new_properties(response_json, unique_links, neighborhood, bot_token, chat_ids, session, semaphore)
            count += new_count

            # Stop if no new results are found
            if not response_json['data']['feed']['feed_items']:
                logger.info(f"No more results found on page {page}. Stopping pagination.")
                break

            page += 1  # Go to the next page
        else:
            logger.info(f"No data found or request failed for page {page}. Stopping pagination.")
            break

    # Save the unique links and page state
    try:
        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(list(unique_links), json_file, ensure_ascii=False, indent=4)
            logger.debug(f"Saved unique_links to {json_file_path}")
    except Exception as e:
        logger.error(f"Failed to save unique_links: {e}")

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
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    chat_id_dict = {}
    for key, value in os.environ.items():
        if key.startswith('CHAT_ID_'):
            name = key[len('CHAT_ID_'):]
            try:
                chat_id = int(value)
                chat_id_dict[name] = chat_id
            except ValueError:
                logger.error(f"Invalid CHAT_ID value for {key}: {value}")

    if not chat_id_dict:
        logger.error("No CHAT_ID_* variables found in .env file.")
        return

    recipient_names = ', '.join(chat_id_dict.keys())
    logger.info(f"SEND TO: {recipient_names}")

    chat_ids = list(chat_id_dict.values())

    neighborhoods_params = load_neighborhoods(neighborhoods_file)
    if not neighborhoods_params:
        logger.error("No neighborhoods loaded. Exiting.")
        return

    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Cookie': 'your-cookie-here',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    timeout = aiohttp.ClientTimeout(total=60)
    data_connector = aiohttp.TCPConnector(limit=50)
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
