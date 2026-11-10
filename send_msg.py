# __author__ = 'InfSub'
# __contact__ = 'ADmin@TkYD.ru'
# __copyright__ = 'Copyright (C) 2024, [LegioNTeaM] InfSub'
# __date__ = '2025/10/22'
# __deprecated__ = False
# __email__ = 'ADmin@TkYD.ru'
# __maintainer__ = 'InfSub'
# __status__ = 'Production'  # 'Production / Development'
# __version__ = '1.8.1.2'

from typing import Dict
from aiohttp import ClientSession as aio_ClientSession
import re

from config import Config
from logger import logging

logging = logging.getLogger(__name__)


def escape_markdown_v2(text: str) -> str:
    """
    Экранирует текст для Telegram MarkdownV2.
    Список символов, которые требуют экранирования в MarkdownV2:
    _ * [ ] ( ) ~ ` > # + - = | { } !
    """
    return re.sub(r'([_\*\[\]\(\)~`>#+\-\=\|{}\.!])', r'\\\1', text)


async def send_telegram_message(message: str, emoji: str = '') -> dict:
    """
    Sends a message to the specified Telegram chat using the API with optional Markdown support.

    :param message: The text of the message to be sent.
    :param emoji: The emoji of the message to be sent.
    :return: The response from the Telegram API as a dictionary (JSON) or an empty dictionary in case of an error.
    --
    Отправляет сообщение в указанный чат Телеграм с использованием API.
    Поддерживает Markdown через конфигурацию Telegram (parse_mode).
    """
    env: Dict[str, int | str] = Config().get_config('telegram')

    logging.info('Preparing to send a message to Telegram.')

    # Поддержка parse_mode (Markdown / MarkdownV2 / HTML)
    parse_mode = (env.get('telegram_parse_mode') or '').strip()

    url = f"https://api.telegram.org/bot{env['telegram_token']}/sendMessage"

    # Разделение chat_id и message_thread_id, если требуется
    parts = env['telegram_chat_id'].split('/')
    chat_id = parts[0]
    message_thread_id = parts[1] if len(parts) > 1 else None

    text_to_send = message
    if parse_mode == 'MarkdownV2':
        text_to_send = escape_markdown_v2(message)

    payload = {
        'chat_id': chat_id,
        'text': text_to_send
    }

    if parse_mode:
        payload['parse_mode'] = parse_mode

    if message_thread_id:
        payload['message_thread_id'] = message_thread_id

    logging.debug(f'Payload for Telegram: {payload}')

    if emoji:
        payload['text'] = f'{emoji} {payload['text']}'

    # HTTP-запрос к Telegram Bot API
    async with aio_ClientSession() as session:
        try:
            async with session.post(url, data=payload) as response:
                if response.status == 200:
                    logging.info('Message successfully sent to Telegram.')
                    return await response.json()
                else:
                    error_text = await response.text()
                    logging.error(f'Error sending message: {error_text}')
                    return {}  # Return an empty dictionary in case of an error
        except Exception as e:
            # Условное логирование трассировки стека
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.exception('Exception occurred while trying to send a message to Telegram.')
            else:
                logging.error(f'Error sending message: {e}')
            return {}  # Return an empty dictionary in case of an error


if __name__ == '__main__':
    from asyncio import run as aio_run

    aio_run(send_telegram_message('Test message.'))
