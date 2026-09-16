# Yad2 Apartment Notifier Bot

Polls [Yad2](https://www.yad2.co.il/) rent listings and sends every new match to Telegram.
Runs on GitHub Actions once an hour; `sent_posts.json` (committed back after each run) is the memory of what was already sent.

## How it works

Yad2 sits behind Radware bot-manager, so plain HTTP clients get a 302 challenge page.
The bot launches headless Chromium (Playwright), loads `yad2.co.il/realestate/rent` once to earn the cookies,
then calls `https://gw.yad2.co.il/realestate-feed/rent/feed` via `fetch()` inside that page.
Every listing bucket in the response (`private`, `agency`, `platinum`, …) is scanned, deduped by `token`, and new ones are sent.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

`.env`:

```env
TELEGRAM_BOT_TOKEN=<bot token from @BotFather>
CHAT_ID_USER=<your chat id>        # any number of CHAT_ID_* vars, one per recipient
```

Chat id: message your bot once, then open `https://api.telegram.org/bot<token>/getUpdates` and read `message.chat.id`.

## Run

```bash
python main.py --dry-run   # print matches, send nothing, save nothing
python main.py --seed      # mark everything currently listed as sent, send nothing (do this once before going live)
python main.py             # send new matches, update sent_posts.json
```

## Searches (`searches.json`)

One entry per query. `params` are passed straight to the Yad2 feed API, so any key the site URL uses works.
Unknown keys return `400 <key> is not allowed`, which is logged.

| key | meaning |
|---|---|
| `region` | required. 3 = תל אביב והסביבה, 1 = מרכז והשרון |
| `city` / `multiCity` | 5000 ת"א, 8600 רמת גן, 6300 גבעתיים, 6400 הרצליה. `multiCity` is comma-separated, same region only |
| `area` | needed with single `city` outside region 3 (הרצליה = 18) |
| `property` | 1 דירה, 3 דירת גן, 4 סטודיו, 6 גג/פנטהאוז, 7 דופלקס, 11 יחידת דיור. Comma-separated |
| `minRooms` / `maxRooms` | 2 / 3 covers 2, 2.5, 3 |
| `balcony` | 1 = must have balcony |
| `minPrice` / `maxPrice` | ₪ / month |
| `max_pages` | bot-side cap, default 200 (feed is not date-sorted, so all pages are scanned) |

Current searches: 2–3 rooms with a balcony, or a garden apartment, in ת"א / רמת גן / גבעתיים and הרצליה.

## Scheduling

Radware blocks GitHub-hosted runner IPs outright (`Radware Bot Manager Block`), so the hourly cron lives on a Mac with a residential IP via launchd.
`run.sh` runs the bot and pushes `sent_posts.json`; `~/Library/LaunchAgents/com.roybidani.yad2bot.plist` fires it every 3600s (missed runs fire on wake).

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.roybidani.yad2bot.plist   # install
launchctl kickstart -k gui/$(id -u)/com.roybidani.yad2bot                            # run now
launchctl bootout gui/$(id -u)/com.roybidani.yad2bot                                 # remove
tail -f launchd.log
```

`.github/workflows/yad2bot.yml` is kept for manual dispatch only; it will fail until the IP block changes.
