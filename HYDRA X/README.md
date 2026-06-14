# HydraX

A lightweight Discord music bot built with **discord.py** and **wavelink**,
backed by a public **Lavalink v4** node. Single-file, easy to host.

*Developed by Rajnikant.*

## Features
- Play from YouTube, SoundCloud, and Spotify* (`/play`)
- Queue: `/queue`, `/remove`, `/clear`, `/shuffle`
- Controls: `/pause`, `/resume`, `/skip`, `/stop`, `/volume`, `/loop`
- `/nowplaying` with interactive buttons: ⏸️ ⏭️ 🔀 🔁 ⏹️
- `/help`

> \*Spotify plays the matching audio from YouTube (bots can't stream Spotify
> directly). It only works if the Lavalink node has the **LavaSrc** plugin enabled.

## Requirements
- Python 3.10 or newer
- A Discord bot token
- A reachable Lavalink **v4** node

### Dependencies
All Python packages are listed in `requirements.txt`:

| Package        | Purpose                                            |
| -------------- | -------------------------------------------------- |
| `discord.py`   | Discord API library (commands, embeds, buttons)    |
| `wavelink`     | Lavalink client for audio playback                 |
| `python-dotenv`| Loads configuration from the `.env` file           |
| `PyNaCl`       | Required for Discord voice support                  |

Install them all with:
```bash
pip install -r requirements.txt
```

Or individually:
```bash
pip install discord.py wavelink python-dotenv PyNaCl
```

## Setup

1. **Create the bot**
   - https://discord.com/developers/applications → New Application → Bot.
   - Reset and copy the token.
   - Invite it via OAuth2 → URL Generator with scopes `bot` and
     `applications.commands`, and permissions: Connect, Speak, Send Messages,
     Embed Links.

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure**
   Create a `.env` file next to `bot.py` (see `.env.example`):
   ```
   DISCORD_TOKEN=your_token_here
   GUILD_ID=
   LAVALINK_HOST=lavalink.jirayu.net
   LAVALINK_PORT=443
   LAVALINK_PASS=youshallnotpass
   LAVALINK_SECURE=true
   ```

4. **Run**
   ```bash
   python bot.py
   ```
   You should see `Lavalink node ... is ready.` and `Logged in as ...`.

## Hosting on a panel (Pterodactyl / Orihost / Wispbyte)
- This panel runs **one** startup command and may not chain with `&&`.
- Install packages once via the Console:
  ```
  pip install -r requirements.txt
  ```
- Set the startup command to: `python bot.py`
- Put your secrets in the panel's variables if `.env` isn't picked up.

## Project structure
```
.
├── bot.py             # The bot (single file)
├── requirements.txt   # Python dependencies
├── .env.example       # Example configuration (copy to .env)
├── .gitignore         # Keeps .env out of git
└── README.md
```

## Notes
- Public Lavalink nodes are **unreliable** — they go offline and rotate often.
  If playback fails with `Name or service not known` or an auth error, swap in
  a fresh **v4** node from a public node list.
- Set `GUILD_ID` to your server ID for instant slash-command syncing.
- Keep `DISCORD_TOKEN` private. If it leaks, reset it in the Developer Portal.

## License
Free to use and modify.
