import base64
import logging
import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin
import tempfile

import httpx
from bs4 import BeautifulSoup
from telegram import InputFile, Update
from telegram.ext import (Application, ApplicationBuilder, CommandHandler,
                          ContextTypes, MessageHandler, filters)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger(__name__)
URL_REGEX = re.compile(r"(https?://\S+)")
MAX_ASSET_SIZE = 8 * 1024 * 1024  # 8 MB per asset
HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MAX_TEXT_CONTEXT = 15_000
MAX_HTML_CONTEXT = 10_000


@dataclass
class PageAssets:
    html: str
    text: str
    final_url: str


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send usage instructions when the /start command is issued."""
    message = (
        "Отправьте мне ссылку (http или https), и я пришлю файлы `page.html` и "
        "`page.txt` с содержимым страницы. После этого можно задать вопросы по странице — "
        "я подключу ИИ и отвечу."
    )
    await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message."""
    await start(update, context)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages that contain URLs."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    match = URL_REGEX.search(text)

    if match:
        url = match.group(1).rstrip(').,"\'">')
        question = extract_question(text, match.group(0))
        status_message = await update.message.reply_text(
            "Загружаю страницу, пожалуйста подождите…"
        )

        try:
            assets = await fetch_page_assets(url)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("Failed to fetch page %s", url)
            await status_message.edit_text(
                f"Не удалось загрузить страницу: {exc}"
            )
            return

        await status_message.delete()
        await send_assets(update, assets)
        context.user_data["last_assets"] = assets

        if question:
            await send_ai_answer(update, question, assets)
        else:
            await update.message.reply_text(
                "Страница обработана. Задайте вопрос текстом, и я постараюсь ответить с учётом содержимого."
            )
        return

    last_assets: Optional[PageAssets] = context.user_data.get("last_assets")
    if not last_assets:
        await update.message.reply_text(
            "Отправьте ссылку, чтобы я смог загрузить страницу и ответить на вопросы."
        )
        return

    question = text
    if not question:
        return

    await send_ai_answer(update, question, last_assets)


async def send_assets(update: Update, assets: PageAssets) -> None:
    """Send the generated HTML and text files back to the user."""
    if not update.message:
        return

    with TemporaryDirectoryPath() as tmpdir:
        html_path = tmpdir / "page.html"
        text_path = tmpdir / "page.txt"

        html_path.write_text(assets.html, encoding="utf-8")
        text_path.write_text(assets.text, encoding="utf-8")

        html_caption = (
            f"Источник: {assets.final_url}\n"
            "HTML содержит встроенные изображения и стили."
        )

        with html_path.open("rb") as html_file:
            await update.message.reply_document(
                document=InputFile(html_file, filename=html_path.name),
                caption=html_caption,
            )

        with text_path.open("rb") as text_file:
            await update.message.reply_document(
                document=InputFile(text_file, filename=text_path.name),
                caption="Извлечённый текст",
            )


class TemporaryDirectoryPath:
    """Context manager that creates and cleans up a temporary directory."""

    def __init__(self) -> None:
        self._tempdir: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> Path:
        self._tempdir = tempfile.TemporaryDirectory()
        return Path(self._tempdir.name)

    def __exit__(self, exc_type, exc, exc_tb) -> None:  # type: ignore[override]
        if self._tempdir is not None:
            self._tempdir.cleanup()


def extract_question(text: str, url_fragment: str) -> str:
    """Return text without the matched URL fragment."""
    cleaned = text.replace(url_fragment, " ")
    return " ".join(cleaned.split()).strip()


async def fetch_page_assets(url: str) -> PageAssets:
    """Download the page and inline its assets."""
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(headers=headers, timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        html_content = response.text
        final_url = str(response.url)

        soup = BeautifulSoup(html_content, "html.parser")
        inlined_soup = BeautifulSoup(html_content, "html.parser")

        await inline_stylesheets(inlined_soup, client, final_url)
        await inline_images(inlined_soup, client, final_url)
        ensure_meta_charset(inlined_soup)

        html_output = f"<!-- Source: {final_url} -->\n" + inlined_soup.prettify()
        text_output = extract_plain_text(soup)
        if text_output:
            text_output = f"Источник: {final_url}\n\n{text_output}"
        else:
            text_output = f"Источник: {final_url}"

        return PageAssets(html=html_output, text=text_output, final_url=final_url)


async def send_ai_answer(update: Update, question: str, assets: PageAssets) -> None:
    """Send a response from the Minimax model back to the user."""
    if not update.message:
        return

    if not OPENROUTER_API_KEY:
        await update.message.reply_text(
            "ИИ недоступен: переменная OPENROUTER_API_KEY не установлена."
        )
        return

    status_message = await update.message.reply_text(
        "Отправляю содержимое в модель, пожалуйста подождите…"
    )

    try:
        answer = await ask_minimax(question, assets)
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Failed to query Minimax for %s", assets.final_url)
        await status_message.edit_text(
            f"Не удалось получить ответ от модели: {exc}"
        )
        return

    await status_message.edit_text(answer)


async def inline_stylesheets(soup: BeautifulSoup, client: httpx.AsyncClient, base_url: str) -> None:
    """Replace external stylesheets with inline <style> tags."""
    for link_tag in list(soup.find_all("link")):
        rel = link_tag.get("rel") or []
        if not any(r.lower() == "stylesheet" for r in rel):
            continue

        href = link_tag.get("href")
        if not href:
            continue

        stylesheet_url = urljoin(base_url, href)
        try:
            content, _, encoding = await fetch_text_asset(client, stylesheet_url)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.warning("Failed to inline stylesheet %s: %s", stylesheet_url, exc)
            continue

        style_tag = soup.new_tag("style")
        style_tag.string = content
        style_tag["data-source"] = stylesheet_url
        if encoding:
            style_tag["data-encoding"] = encoding
        link_tag.replace_with(style_tag)


async def inline_images(soup: BeautifulSoup, client: httpx.AsyncClient, base_url: str) -> None:
    """Convert <img> sources to base64 data URIs."""
    cached_data: Dict[str, str] = {}

    for img in soup.find_all("img"):
        src = img.get("src")
        if not src or src.startswith("data:"):
            continue

        image_url = urljoin(base_url, src)
        try:
            data_uri = cached_data[image_url]
        except KeyError:
            try:
                data, content_type = await fetch_binary_asset(client, image_url)
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.warning("Failed to inline image %s: %s", image_url, exc)
                continue

            encoded = base64.b64encode(data).decode("ascii")
            data_uri = f"data:{content_type};base64,{encoded}"
            cached_data[image_url] = data_uri

        img["src"] = data_uri
        if img.has_attr("srcset"):
            del img["srcset"]
        img["data-source"] = image_url


async def fetch_text_asset(client: httpx.AsyncClient, url: str) -> Tuple[str, str, str]:
    """Fetch a text-based asset and return content, mime-type, encoding."""
    response = await client.get(url)
    response.raise_for_status()
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            length = int(content_length)
        except (TypeError, ValueError):
            length = None
        if length is not None and length > MAX_ASSET_SIZE:
            raise ValueError("Размер файла превышает ограничение в 8 МБ")
    content_type = response.headers.get("Content-Type", "text/plain")
    encoding = response.encoding or "utf-8"
    text = response.text
    if len(response.content) > MAX_ASSET_SIZE:
        raise ValueError("Размер файла превышает ограничение в 8 МБ")
    return text, content_type, encoding


async def fetch_binary_asset(client: httpx.AsyncClient, url: str) -> Tuple[bytes, str]:
    """Fetch a binary asset and return the data and MIME type."""
    response = await client.get(url)
    response.raise_for_status()
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            length = int(content_length)
        except (TypeError, ValueError):
            length = None
        if length is not None and length > MAX_ASSET_SIZE:
            raise ValueError("Размер файла превышает ограничение в 8 МБ")

    data = response.content
    if len(data) > MAX_ASSET_SIZE:
        raise ValueError("Размер файла превышает ограничение в 8 МБ")

    content_type = response.headers.get("Content-Type")
    if content_type:
        content_type = content_type.split(";")[0]
    else:
        guess, _ = mimetypes.guess_type(url)
        content_type = guess or "application/octet-stream"

    return data, content_type


def truncate_content(content: str, limit: int) -> str:
    """Return content truncated to a maximum number of characters."""
    if len(content) <= limit:
        return content
    return content[:limit] + "\n…(truncated)…"


async def ask_minimax(question: str, assets: PageAssets) -> str:
    """Call the Minimax M2 model via OpenRouter and return the response text."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    text_context = truncate_content(assets.text, MAX_TEXT_CONTEXT)
    html_context = truncate_content(assets.html, MAX_HTML_CONTEXT)

    messages = [
        {
            "role": "system",
            "content": (
                "Ты — помощник, который отвечает на вопросы по содержимому веб-страниц. "
                "Используй предоставленные HTML и текст, чтобы отвечать максимально точно. "
                "Если данных недостаточно, честно сообщи об этом."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Адрес страницы: {assets.final_url}\n\n"
                f"Текст страницы (может быть сокращён):\n{text_context}\n\n"
                f"HTML страницы (может быть сокращён):\n{html_context}\n\n"
                f"Вопрос пользователя: {question}"
            ),
        },
    ]

    payload = {
        "model": "minimax/minimax-m2:free",
        "messages": messages,
        "extra_body": {"reasoning": {"enabled": True}},
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    message = data.get("choices", [{}])[0].get("message", {})
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content)
    if not content:
        raise RuntimeError("Пустой ответ от модели")
    return content.strip()


def ensure_meta_charset(soup: BeautifulSoup) -> None:
    """Ensure the HTML output declares UTF-8 charset for offline viewing."""
    head = soup.head
    if not head:
        head = soup.new_tag("head")
        soup.insert(0, head)

    meta = head.find("meta", attrs={"charset": True})
    if meta:
        meta["charset"] = "utf-8"
    else:
        meta = soup.new_tag("meta", charset="utf-8")
        head.insert(0, meta)


def extract_plain_text(soup: BeautifulSoup) -> str:
    """Extract human-readable text from the HTML."""
    text_soup = BeautifulSoup(str(soup), "html.parser")
    for element in text_soup(["script", "style", "noscript"]):
        element.decompose()

    text = text_soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned


def build_application(token: str) -> Application:
    return ApplicationBuilder().token(token).build()


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Переменная окружения TELEGRAM_BOT_TOKEN не установлена."
        )

    application = build_application(token)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()


if __name__ == "__main__":
    main()
