import os
import requests
import logging
from logging import Formatter
from telegram import Bot
from dotenv import load_dotenv
import time
from http import HTTPStatus

from exceptions import (
    TelegramMessageError,
    EndpointError,
    HomeworksNotFound,
    RequestExceptionError
)

load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('main.log', 'w', 'utf-8')
handler.setFormatter(Formatter(
    fmt='%(asctime)s, %(levelname)s, %(message)s, %(name)s'))
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляем сообщение в телеграме."""
    info_message = f'Начинаем отправку сообщения "{message}"'
    logger.info(info_message)
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramMessageError as error:
        raise TelegramMessageError(error)
    info_message = f'Сообщение "{message}" отправлено'
    logger.info(info_message)


def get_api_answer(current_timestamp):
    """Обращаемся к серверу Практикума и получаем ответ."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    info_message = 'Начинаем запрос к API'
    logger.info(info_message)
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        raise RequestExceptionError(error)
    if response.status_code != HTTPStatus.OK:
        message = (f'Эндпоинт {ENDPOINT} недоступен. '
                   f'Код ответа: {response.status_code}')
        raise EndpointError(message)
    return response.json()


def check_response(response):
    """Проверяем, собержит ли ответ ожидаемую информацию."""
    if not isinstance(response, dict):
        message = f'Объект {response} не является словарем'
        raise TypeError(message)
    if not isinstance(response.get('homeworks'), list):
        message = 'Объект "homeworks" не является списком'
        raise TypeError(message)
    homeworks = response.get('homeworks')
    if not homeworks:
        message = 'Не передан параметр homework'
        raise HomeworksNotFound(message)
    return homeworks


def parse_status(homework):
    """Присваеваем статус домашке."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError('Статус работы не опознан')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем, есть ли переменные окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    status = ''
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework and status != homework[0]['status']:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                message = 'Новых заданий не обнаружено'
                logger.info(message)
            current_timestamp = int(time.time())
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
