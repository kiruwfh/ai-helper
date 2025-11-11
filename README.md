# Telegram Page Extractor Bot

This repository contains a Telegram bot that downloads the full HTML of a web page – including inline images – and extracts a plain-text representation. The bot sends both the HTML and plain-text files back to the user and can forward the content to the Minimax M2 reasoning model to answer your follow-up questions.

## Features

- Accepts any message containing an `http://` or `https://` URL.
- Downloads the referenced page and follows redirects.
- Inlines linked stylesheets and images directly into the generated HTML file.
- Produces a `.txt` file with the readable text extracted from the page.
- Sends both files back to the Telegram chat as downloadable documents.
- Uses the [Minimax M2](https://openrouter.ai/minimax/minimax-m2) model via OpenRouter to answer questions about the downloaded page.
- Remembers the latest exchange with Minimax (включая `reasoning_details`), чтобы продолжить рассуждения при последующих вопросах.
- Automatically splits very long AI answers into several Telegram messages to avoid hitting the 4096-character limit.

## Prerequisites

- Python 3.10 or higher.
- A Telegram bot token. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token it provides.
- An [OpenRouter](https://openrouter.ai/) API key with access to the `minimax/minimax-m2:free` model.

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

4. Provide your OpenRouter API key to the bot. Replace `YOUR_OPENROUTER_KEY` with the real key from your OpenRouter account:

   ```bash
   export OPENROUTER_API_KEY="YOUR_OPENROUTER_KEY"
   ```

   On Windows PowerShell:

   ```powershell
   setx OPENROUTER_API_KEY "YOUR_OPENROUTER_KEY"
   ```

## Running the bot

Start the bot with:

```bash
python bot.py
```

Once the bot is running, send any URL to your Telegram bot. The bot replies with two documents:

1. `page.html` – the HTML content with images and stylesheets embedded as data URIs so it can be viewed offline.
2. `page.txt` – the plain text extracted from the page for quick reference or sharing with other AI tools.

After the files are delivered you can ask questions in two ways:

1. Write a message that contains both the URL and your question (for example: `https://example.com Какие ключевые выводы?`). The bot will download the page, send the files, and then forward the content to Minimax for an immediate answer.
2. Send a URL first, then send one or more follow-up messages with your questions. The bot keeps the most recently downloaded page in memory for the current chat and reuses it when a question arrives without a new URL. Ответы от модели сохраняются вместе с `reasoning_details` и последним вопросом, поэтому ИИ продолжает рассуждение и может учитывать предыдущие ответы.

## Notes

- Large pages and very large images are truncated to keep the response size manageable. The current limit for individual assets is 8 MB.
- Only publicly accessible resources that do not require JavaScript rendering are supported.
- Keep your bot token private. Never commit it to version control.
- The AI answer is limited by the amount of HTML/text that can be sent to the model. The bot truncates very large pages before sending them to Minimax.

