import aiohttp
import asyncio
import json
import os
import logging
from urllib.parse import urlencode
from dotenv import load_dotenv
import argparse
import re  # For price sanitization
from pathlib import Path
import sys
import aiofiles
from aiolimiter import AsyncLimiter  # For rate limiting

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more detailed logs
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Define a global semaphore to limit concurrent send operations
SEMAPHORE_LIMIT = 3  # Adjust based on Telegram's rate limits
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

# Define a rate limiter (e.g., 30 messages per second)
rate_limiter = AsyncLimiter(max_rate=30, time_period=1)

# Path to store sent post IDs
SENT_POSTS_FILE = Path("sent_posts.json")

def load_sent_posts():
    """Load the set of sent post IDs from a JSON file."""
    if SENT_POSTS_FILE.exists():
        try:
            with SENT_POSTS_FILE.open("r", encoding="utf-8") as f:
                return set(json.load(f))
        except json.JSONDecodeError:
            logger.error("sent_posts.json is corrupted. Starting with an empty set.")
            return set()
    return set()

def save_sent_posts(sent_posts):
    """Save the set of sent post IDs to a JSON file."""
    try:
        with SENT_POSTS_FILE.open("w", encoding="utf-8") as f:
            json.dump(list(sent_posts), f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Failed to save sent posts: {e}")

# Telegram Bot Setup
async def send_message_async(session, bot_token, chat_id, message_text, semaphore, retries=3):
    """Send a message to a Telegram chat asynchronously with retries and rate limiting."""
    async with rate_limiter:
        async with semaphore:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            params = {
                "chat_id": chat_id,
                "text": message_text,
                "parse_mode": "HTML",  # Use HTML for formatting
            }

            for attempt in range(1, retries + 1):
                try:
                    async with session.post(url, params=params) as response:
                        if response.status == 200:
                            logger.info(f"Message sent to {chat_id}")
                            return True
                        elif response.status in [429, 503]:
                            # Handle rate limiting and service unavailable
                            retry_after = int(response.headers.get("Retry-After", 1))
                            logger.warning(f"Attempt {attempt}: Rate limited or service unavailable. Retrying after {retry_after} seconds.")
                            await asyncio.sleep(retry_after)
                        else:
                            response_text = await response.text()
                            logger.error(f"Failed to send message to {chat_id}: {response.status}, {response_text}")
                            return False
                except Exception as e:
                    logger.error(f"Attempt {attempt}: Error sending message to {chat_id}: {e}")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

            logger.error(f"Failed to send message to {chat_id} after {retries} attempts.")
            return False

# Fetch JSON data for search parameters and perform the search with exponential backoff
async def fetch_json(session, url, retries=3):
    """Fetch JSON data from a URL with retries and exponential backoff."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Yad2Bot/1.0)"
    }
    delay = 2  # Initial delay for retries
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    json_data = await response.json()
                    logger.debug(f"Fetched data for URL {url}: {json_data}")
                    return json_data
                elif response.status in [429, 503]:  # Rate limit or service unavailable
                    logger.warning(f"Attempt {attempt}: Received status code {response.status} for URL: {url}. Retrying after {delay} seconds.")
                else:
                    logger.warning(f"Attempt {attempt}: Received status code {response.status} for URL: {url}. Retrying after {delay} seconds.")
        except aiohttp.ClientError as e:
            logger.warning(f"Attempt {attempt}: Network error fetching {url}: {e}. Retrying after {delay} seconds.")
        except asyncio.TimeoutError:
            logger.warning(f"Attempt {attempt}: Timeout fetching {url}. Retrying after {delay} seconds.")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Unexpected error fetching {url}: {e}. Retrying after {delay} seconds.")
        await asyncio.sleep(delay)
        delay *= 2  # Exponential backoff
    logger.error(f"Failed to fetch {url} after {retries} attempts")
    return None

# Process feed items and send Telegram messages
async def process_feed_items(data, bot_token, chat_ids, neighborhood_name, session, sent_posts):
    """Process feed items and send new posts as Telegram messages."""
    count = 0

    # Process all items found in the neighborhood's feed
    feed_items = data.get('data', {}).get('feed', {}).get('feed_items', [])
    if not feed_items:
        logger.warning(f"No feed items found for neighborhood '{neighborhood_name}'")
        return count

    for d in feed_items:
        # Skip non-item entries without 'id'
        if 'id' not in d:
            logger.debug(f"Skipping post without 'id': {d}")
            continue

        try:
            # Extract 'id'
            item_id = d.get('id') or d.get('item_id') or d.get('itemId')
            if not item_id:
                logger.debug(f"Skipping post without 'id': {d}")
                continue  # Skip this post as we cannot create a valid link

            if item_id in sent_posts:
                logger.debug(f"Post ID {item_id} already sent. Skipping.")
                continue  # Skip already sent posts

            # Extract 'title' with multiple fallbacks
            title = d.get('title') or d.get('title_1') or d.get('street') or 'No title available'

            # Extract 'price' with multiple fallbacks
            price = d.get('price') or d.get('price_value') or d.get('priceText') or 'No price available'

            # Sanitize and format the price
            if isinstance(price, (int, float)):
                price = f"{price:,} ₪"
            elif isinstance(price, str):
                # Extract digits and format
                price_digits = re.findall(r'\d+', price)
                if price_digits:
                    price_number = int(''.join(price_digits))
                    price = f"{price_number:,} ₪"
                else:
                    price = 'No price available'
            else:
                price = 'No price available'

            # Construct the post link
            link = f"https://www.yad2.co.il/item/{item_id}"

            # Escape HTML special characters to prevent formatting issues
            escaped_title = re.sub(r'([&<>])', lambda match: {'&': '&amp;', '<': '&lt;', '>': '&gt;'}[match.group()], title)
            escaped_neighborhood = re.sub(r'([&<>])', lambda match: {'&': '&amp;', '<': '&lt;', '>': '&gt;'}[match.group()], neighborhood_name)

            # Construct the message using HTML formatting
            message = f"""<b>נמצאה דירה חדשה המתאימה לך!</b>

<b>רחוב:</b> {escaped_title}
<b>מחיר:</b> {price}
<b>שכונת:</b> {escaped_neighborhood}

<a href="{link}">קישור לפוסט</a>"""

            # Send message to all chat_ids and collect success flags
            send_tasks = [send_message_async(session, bot_token, chat_id, message, semaphore) for chat_id in chat_ids]
            send_results = await asyncio.gather(*send_tasks)

            # Check if all messages were sent successfully
            if all(send_results):
                logger.info(f"New post found: ID {item_id}, Title: {title}, Price: {price}")
                sent_posts.add(item_id)  # Mark as sent
                count += 1
            else:
                logger.error(f"Failed to send all messages for post ID {item_id}. Post marked as sent to prevent duplicates.")

        except Exception as e:
            logger.error(f"Error processing post {d}: {e}")
            continue

    logger.debug(f"Processed {count} new posts for neighborhood '{neighborhood_name}'")
    return count

# Main task for each neighborhood
async def main_task(params, bot_token, chat_ids, session, sent_posts):
    """Process a single neighborhood: fetch data, process feed items, and send messages."""
    base_url = "https://gw.yad2.co.il/feed-search-legacy/realestate/rent"
    max_pages = params.get('max_pages', 10)  # Default to 10 pages if not specified
    neighborhood_code = params.get('neighborhood')
    neighborhood_name = params.get('name', 'Unknown Neighborhood')
    expected_minimum = 1  # Minimum items expected to continue pagination

    new_posts_count = 0

    for page in range(1, max_pages + 1):
        params_with_page = params.copy()  # Avoid modifying the original params
        params_with_page['page'] = page

        # Log the neighborhood and page being processed
        logger.info(f"Searching in '{neighborhood_name}' (Page {page})")

        # Fetch data from the URL
        encoded_params = urlencode(params_with_page, doseq=True)
        final_url = f"{base_url}?{encoded_params}"

        logger.info(f"Fetching URL: {final_url}")

        response_json = await fetch_json(session, final_url)

        if response_json and 'feed' in response_json.get('data', {}):
            # Log the number of feed items
            feed_items = response_json['data']['feed'].get('feed_items', [])
            logger.info(f"Page {page} of '{neighborhood_name}' contains {len(feed_items)} feed items.")

            if len(feed_items) < expected_minimum:
                logger.info(f"Page {page} of '{neighborhood_name}' has fewer items ({len(feed_items)}) than expected ({expected_minimum}). Stopping pagination.")
                break  # Stop fetching further pages if fewer items are found

            # Process the feed and count new posts
            new_count = await process_feed_items(
                response_json,
                bot_token,
                chat_ids,
                neighborhood_name,
                session,
                sent_posts
            )

            # Update the count of new posts found
            new_posts_count += new_count

            # Introduce a delay to prevent rate limiting
            await asyncio.sleep(1)  # Wait for 1 second between page requests
        else:
            logger.warning(f"No valid feed found for '{neighborhood_name}' (Page {page})")
            break  # Stop pagination if no feed is found

    return new_posts_count

# Main bot run logic
async def run_bot(neighborhoods_file):
    """Run the Yad2SearchBot: load configurations, process neighborhoods, and send notifications."""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    # Collect all chat_ids from environment variables
    chat_id_dict = {}
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

    chat_ids = list(chat_id_dict.values())
    logger.info(f"SEND TO: {', '.join(chat_id_dict.keys())}")

    # Load neighborhoods from JSON file
    try:
        async with aiofiles.open(neighborhoods_file, 'r', encoding='utf-8') as file:
            content = await file.read()
            neighborhoods_params = json.loads(content)
    except Exception as e:
        logger.error(f"Error loading neighborhoods file: {e}")
        return

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        sent_posts = load_sent_posts()
        total_new_posts = 0
        for params in neighborhoods_params:
            # Process each neighborhood one at a time for sequential processing
            new_count = await main_task(params, bot_token, chat_ids, session, sent_posts)
            total_new_posts += new_count

        # Summarize the total number of new posts
        logger.info(f"Summary: Searched in {len(neighborhoods_params)} neighborhoods and found {total_new_posts} new apartments matching your criteria. Notifications sent via Telegram.")

        # Save sent posts after processing all neighborhoods
        save_sent_posts(sent_posts)

    logger.info("Bot run completed successfully.")

# Run the bot
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Yad2 Apartment Notifier Bot")
    parser.add_argument('--neighborhoods', type=str, default='neighborhoods.json', help='Path to the neighborhoods JSON file')
    args = parser.parse_args()
    asyncio.run(run_bot(args.neighborhoods))
