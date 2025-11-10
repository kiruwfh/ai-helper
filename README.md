# Telegram Page Extractor Bot

This repository contains a Telegram bot that downloads the full HTML of a web page – including inline images – and extracts a plain-text representation. The bot sends both the HTML and plain-text files back to the user so the content can be shared with other tools.

## Features

- Accepts any message containing an `http://` or `https://` URL.
- Downloads the referenced page and follows redirects.
- Inlines linked stylesheets and images directly into the generated HTML file.
- Produces a `.txt` file with the readable text extracted from the page.
- Sends both files back to the Telegram chat as downloadable documents.

## Prerequisites

- Python 3.10 or higher.
- A Telegram bot token. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token it provides.

## Installation

1. Clone this repository and move into it.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Export your Telegram bot token as an environment variable before running the bot (replace `YOUR_TOKEN_HERE` with the actual token from BotFather):

   ```bash
   export TELEGRAM_BOT_TOKEN="YOUR_TOKEN_HERE"
   ```

   On Windows PowerShell use:

   ```powershell
   setx TELEGRAM_BOT_TOKEN "YOUR_TOKEN_HERE"
   ```

## Running the bot

Start the bot with:

```bash
python bot.py
```

Once the bot is running, send any URL to your Telegram bot. The bot replies with two documents:

1. `page.html` – the HTML content with images and stylesheets embedded as data URIs so it can be viewed offline.
2. `page.txt` – the plain text extracted from the page for quick reference or sharing with other AI tools.

## Notes

- Large pages and very large images are truncated to keep the response size manageable. The current limit for individual assets is 8 MB.
- Only publicly accessible resources that do not require JavaScript rendering are supported.
- Keep your bot token private. Never commit it to version control.

