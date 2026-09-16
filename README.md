# Yad2 Apartment Notifier Bot

Polls [Yad2](https://www.yad2.co.il/) rent listings every hour and sends every new match to Telegram.
`sent_posts.json` remembers what was already sent, so each listing arrives once.

Current searches: 2–3 rooms, with a balcony or a garden apartment, up to 5,500 ₪, in
Tel Aviv / Ramat Gan / Givatayim and Herzliya. Edit `searches.json` to change that.

---

## How it works

Yad2 sits behind Radware bot-manager. Plain HTTP clients (curl, requests, aiohttp) get a 302 challenge page,
and cloud IPs (GitHub Actions, AWS, any datacenter) get a hard `Radware Bot Manager Block`.
The only thing that passes is a real browser on a residential IP.

So the bot:

1. Launches headless Chromium (Playwright) and loads `yad2.co.il/realestate/rent` once to earn the cookies.
2. Calls `https://gw.yad2.co.il/realestate-feed/rent/feed` via `fetch()` inside that page, one call per search per page.
3. Scans every listing bucket in the response (`private`, `agency`, `platinum`, …), dedupes by `token`.
4. Sends new ones to every `CHAT_ID_*` in `.env`, then appends the tokens to `sent_posts.json`.

The feed is not date-sorted, so all pages are scanned every run (~1,500 listings, ~90 seconds).

---

## Setup, end to end

### 1. Create the Telegram bot

1. Open Telegram, search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot`. Give it a display name, then a username ending in `bot` (e.g. `RoysApt_bot`).
3. BotFather replies with an **HTTP API token** like `123456789:AAH...`. Copy it. Anyone holding it controls the bot.

### 2. Get your chat id

1. Open your new bot in Telegram (`t.me/<username>`), press **Start**, send any message.
2. In a browser open:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. In the JSON find `"message" → "chat" → "id"`. That number is your chat id.
   Empty `"result":[]` means you have not messaged the bot yet.
4. Repeat for every person who should get notifications (each one messages the bot, each gets their own id).

### 3. Clone and install

macOS ships `python3`, not `python`.

```bash
git clone https://github.com/RoyBidani/Yad2SearchBot.git ~/Git/Yad2SearchBot
cd ~/Git/Yad2SearchBot
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/playwright install chromium
```

### 4. Configure `.env`

Create `.env` in the repo root (git-ignored):

```env
TELEGRAM_BOT_TOKEN=123456789:AAH...
CHAT_ID_USER=1621100445
CHAT_ID_PARTNER=987654321      # optional, any number of CHAT_ID_* lines
```

### 5. Test the pipe

```bash
./venv/bin/python main.py --dry-run
```

Prints every current match to the terminal, sends nothing, saves nothing. If you see listings, Yad2 access works.
If the log says `yad2 page title: Radware Bot Manager Block`, your IP is blocked (VPN? office network?). Try from home.

### 6. Seed, once

```bash
./venv/bin/python main.py --seed
```

Marks everything currently listed as already sent, without sending. Skip this and the first live run
dumps ~1,500 messages into your Telegram.

### 7. First live run

```bash
./venv/bin/python main.py
```

Sends whatever appeared since the seed (usually 0–20 listings) and updates `sent_posts.json`.

---

## Running every hour (launchd)

`run.sh` runs the bot, then commits and pushes `sent_posts.json` so GitHub keeps a backup.
`~/Library/LaunchAgents/com.roybidani.yad2bot.plist` fires `run.sh` every 3600 seconds. Missed runs fire on wake.

Install the agent (edit the paths in the plist if the repo is not in `~/Git/Yad2SearchBot`):

```bash
cp com.roybidani.yad2bot.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.roybidani.yad2bot.plist
```

Useful commands:

```bash
launchctl kickstart -k gui/$(id -u)/com.roybidani.yad2bot     # run now
launchctl print gui/$(id -u)/com.roybidani.yad2bot | grep -E 'runs =|last exit|run interval'
launchctl bootout gui/$(id -u)/com.roybidani.yad2bot           # uninstall
grep 'done:' launchd.log                                       # one line per run
```

Pushing from `run.sh` needs git credentials. Easiest: `brew install gh && gh auth login -w -p https -s repo,workflow`.

### Keep the Mac awake

The agent runs while you are logged in, locked screen included. Sleep stops it. On charger, disable idle sleep:

```bash
sudo pmset -c sleep 0 displaysleep 10
```

Lid closed (without an external display) or battery power still sleeps. Keep it plugged and open.

### Why not GitHub Actions

`.github/workflows/yad2bot.yml` still exists for manual dispatch, but GitHub-hosted runners are blocked
by Radware outright. It will fail with `Radware Bot Manager Block` until Yad2 changes its rules.

---

## Searches (`searches.json`)

One entry per query. `params` are passed straight to the Yad2 feed API, so any key the site URL uses works.
Unknown keys return `400 <key> is not allowed`, which is logged.

| key | meaning |
|---|---|
| `region` | required. 3 = תל אביב והסביבה, 1 = מרכז והשרון |
| `city` / `multiCity` | 5000 ת"א, 8600 רמת גן, 6300 גבעתיים, 6400 הרצליה. `multiCity` is comma-separated, same region only |
| `area` | needed with a single `city` outside region 3 (הרצליה = 18) |
| `property` | 1 דירה, 3 דירת גן, 4 סטודיו, 6 גג/פנטהאוז, 7 דופלקס, 11 יחידת דיור. Comma-separated |
| `minRooms` / `maxRooms` | 2 / 3 covers 2, 2.5, 3 |
| `balcony` | 1 = must have balcony |
| `minPrice` / `maxPrice` | ₪ / month |
| `max_pages` | bot-side cap, default 200 |

To find a new city code: open yad2.co.il, search that city for rent, copy `city=`, `area=` and the region from the URL
(the site redirects to `/rent/<region-slug>?area=..&city=..`). Changes take effect on the next run, no restart.

---

## Troubleshooting

| symptom | meaning / fix |
|---|---|
| `yad2 page title: Radware Bot Manager Block` | IP blocked. Cloud IP, VPN, or corporate proxy. Run from home |
| `TypeError: Failed to fetch` | Same as above, the challenge was not passed |
| `400 <key> is not allowed` | Typo in `searches.json` param name |
| `telegram <id> -> 400/403` | Wrong chat id, or that user never pressed Start on the bot |
| `TELEGRAM_BOT_TOKEN / CHAT_ID_* missing` | `.env` missing or not in the repo root |
| no `done:` line for hours in `launchd.log` | Mac was asleep, or agent not loaded (`launchctl print ...`) |
| first live run flooded Telegram | you skipped `--seed` |

Logs: `bot.log` (every run, from `main.py`) and `launchd.log` (stdout/stderr of the hourly job). Both git-ignored.
