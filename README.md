# Yad2 Apartment Notifier Bot

Polls [Yad2](https://www.yad2.co.il/) rent listings every hour and sends every match to your Telegram.
The first run sends everything currently listed; after that only new listings. `sent_posts.json` remembers what was sent.

You define the searches (cities, rooms, price, balcony, garden…) in `searches.json`. The shipped file is one example:
2–3 rooms with a balcony or a garden apartment, up to 5,500 ₪, in Tel Aviv / Ramat Gan / Givatayim and Herzliya.

Runs on a Mac at home. Cloud runners don't work, see [Why not a server](#why-not-a-server--github-actions).

---

## How it works

Yad2 sits behind Radware bot-manager. Plain HTTP clients (curl, requests, aiohttp) get a 302 challenge page,
and datacenter IPs (GitHub Actions, AWS, any VPS) get a hard `Radware Bot Manager Block`.
What passes is a real browser on a residential IP.

Each run:

1. Launches headless Chromium (Playwright), loads `yad2.co.il/realestate/rent` once to earn the cookies.
2. Calls `https://gw.yad2.co.il/realestate-feed/rent/feed` via `fetch()` inside that page, per search, per page.
3. Scans every listing bucket in the response (`private`, `agency`, `platinum`, …), dedupes by `token`.
4. Sends new listings to every `CHAT_ID_*` in `.env`, then appends the tokens to `sent_posts.json`.

The feed is not date-sorted, so all pages are scanned every run (~1,500 listings ≈ 90 seconds).

---

## Setup, end to end

### 1. Create your Telegram bot

1. In Telegram open [@BotFather](https://t.me/BotFather), send `/newbot`.
2. Pick a display name, then a username ending in `bot` (e.g. `MyAptHunter_bot`).
3. BotFather replies with an **HTTP API token** like `123456789:AAH...`. Keep it private, it controls the bot.

### 2. Get your chat id

1. Open your bot (`t.me/<username>`), press **Start**, send any message.
2. In a browser open `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. Find `"message" → "chat" → "id"`. That number is your chat id.
   `"result":[]` means nobody messaged the bot yet.
4. Everyone who wants notifications does steps 1–3 with the same bot; each gets their own id.

### 3. Fork, clone, install

Fork the repo on GitHub first so `sent_posts.json` backups push to **your** remote (optional, but nice).

```bash
git clone https://github.com/<you>/Yad2SearchBot.git ~/Yad2SearchBot
cd ~/Yad2SearchBot
./install.sh
```

`install.sh` creates the venv, installs Playwright + Chromium, and registers an hourly launchd agent
(`com.yad2bot`) pointing at this folder. Re-run it any time; it never touches `.env` or `searches.json`.
macOS ships `python3`, not `python`.

### 4. Configure `.env`

Create `.env` in the repo root (git-ignored):

```env
TELEGRAM_BOT_TOKEN=123456789:AAH...
CHAT_ID_ME=111111111
CHAT_ID_PARTNER=222222222      # optional, any number of CHAT_ID_* lines

# optional second bot/chat, used by searches that set "bot": "BS" (any prefix you like)
BS_TELEGRAM_BOT_TOKEN=987654321:AAG...
BS_CHAT_ID_ME=111111111
```

A search without `"bot"` uses the unprefixed variables. A search with `"bot": "XYZ"` uses `XYZ_TELEGRAM_BOT_TOKEN`
and every `XYZ_CHAT_ID_*`. That is how one hourly job feeds several Telegram bots, e.g. one per city or per friend.

### 5. Define your searches

Edit `searches.json`. Parameter reference below. Changes take effect on the next run, no restart.

### 6. Test

```bash
./venv/bin/python main.py --dry-run
```

Prints every current match, sends nothing, saves nothing. Listings appear = Yad2 access works.
`yad2 page title: Radware Bot Manager Block` = your IP is blocked (VPN? office network?). Try from home.

### 7. Go live

```bash
echo "[]" > sent_posts.json                        # forget whatever the repo's previous owner already saw
launchctl kickstart -k gui/$(id -u)/com.yad2bot
```

The first run sends **every** current match (a few hundred to ~1,500 messages, Telegram paces them at ~1/sec).
From then on, hourly, only new listings.

Don't want the backlog? Run `./venv/bin/python main.py --seed` first: it marks everything currently listed as seen
without sending, so the first live run is quiet. Adding a search later works the same way: its backlog comes in
on the next run unless you seed first.

---

## Scheduling details (launchd)

`run.sh` runs the bot, then commits `sent_posts.json` and pushes to `origin` if you have write access
(no access = message in the log, file still saved locally). `install.sh` writes the plist to
`~/Library/LaunchAgents/com.yad2bot.plist` with a 3600s interval. Missed runs fire on wake.

```bash
launchctl print gui/$(id -u)/com.yad2bot | grep -E 'runs =|last exit|run interval'   # is it alive
grep 'done:' launchd.log                                                          # one line per run
launchctl kickstart -k gui/$(id -u)/com.yad2bot                                   # run now
launchctl bootout gui/$(id -u)/com.yad2bot                                        # uninstall
```

For the push to work from a launchd job, set up git credentials once: `brew install gh && gh auth login -w -p https`.

### Keep the Mac awake

The agent runs while you are logged in, locked screen included. Sleep stops it. On charger, disable idle sleep:

```bash
sudo pmset -c sleep 0 displaysleep 10
```

Lid closed (without an external display) or battery power still sleeps. Keep it plugged in and open.

### Why not a server / GitHub Actions

`.github/workflows/yad2bot.yml` exists for manual dispatch, but GitHub-hosted runners are blocked by Radware
outright, as is every cloud IP tried. A Raspberry Pi or old laptop at home works the same way as the Mac (adapt
`install.sh` to cron/systemd).

---

## Searches (`searches.json`)

One entry per query. `params` are passed straight to the Yad2 feed API, so any key the site URL uses works.
Unknown keys return `400 <key> is not allowed`, which is logged.

```json
{
    "name": "shown as the message title",
    "bot": "BS",
    "params": { "region": 3, "multiCity": "5000,8600", "property": "1,3", "minRooms": 2, "maxRooms": 3, "balcony": 1, "maxPrice": 5500 }
}
```

`bot` is optional, see `.env` above. `name` and `params` are required.

| key | meaning |
|---|---|
| `region` | required. 3 = תל אביב והסביבה, 1 = מרכז והשרון, 2 = דרום, others: read from the site URL |
| `city` / `multiCity` | 5000 ת"א, 8600 רמת גן, 6300 גבעתיים, 6400 הרצליה, 9000 באר שבע. `multiCity` is comma-separated, same region only |
| `area` | needed with a single `city` outside region 3 (הרצליה = 18, באר שבע = 22) |
| `property` | 1 דירה, 3 דירת גן, 4 סטודיו, 6 גג/פנטהאוז, 7 דופלקס, 11 יחידת דיור. Comma-separated |
| `minRooms` / `maxRooms` | 2 / 3 covers 2, 2.5, 3 |
| `balcony` | 1 = must have balcony |
| `minPrice` / `maxPrice` | ₪ / month |
| `max_pages` | bot-side cap, default 200 |

To find codes for another city: search it for rent on yad2.co.il and copy `city=`, `area=` from the URL.
The path (`/rent/tel-aviv-area`, `/rent/center-and-sharon`, …) tells the region; the feed's `address.region.id` confirms it.

---

## Troubleshooting

| symptom | meaning / fix |
|---|---|
| `yad2 page title: Radware Bot Manager Block` | IP blocked. Cloud IP, VPN, or corporate proxy. Run from home |
| `TypeError: Failed to fetch` | Same as above, the challenge was not passed |
| `400 <key> is not allowed` | Typo in a `searches.json` param name |
| `telegram <id> -> 400/403` | Wrong chat id, or that user never pressed Start on the bot |
| `TELEGRAM_BOT_TOKEN / CHAT_ID_* missing` | `.env` missing or not in the repo root |
| no `done:` line for hours in `launchd.log` | Mac was asleep, or agent not loaded (`launchctl print ...`) |
| `push skipped: no write access` | Expected on a clone you don't own. Fork to get backups |
| first live run flooded Telegram | that is the backlog, by design. Use `--seed` before going live to skip it |

Logs: `bot.log` (every run, written by `main.py`) and `launchd.log` (stdout/stderr of the hourly job). Both git-ignored.
