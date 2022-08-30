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
    MainFuncError,
    EndpointError,
    DictKeysError,
    DictNoneError,
    NotListError,
    HomeworkStatusError,
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
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramMessageError as error:
        logger.critical(error)
        raise TelegramMessageError(error)
    info_message = f'Сообщение "{message}" отправлено'
    logger.info(info_message)


def get_api_answer(current_timestamp):
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            message = (f'Эндпоинт {ENDPOINT} недоступен. '
                       f'Код ответа: {response.status_code}')
            logger.error(message)
            raise EndpointError(message)
        return response.json()
    except requests.exceptions.RequestException as error:
        logger.critical(error)
        raise RequestExceptionError(error)


def check_response(response):
    try:
        hw_list = response['homeworks']
    except KeyError as error:
        message = f'Неверное значение ключа homeworks: {error}'
        logger.error(message)
        raise DictKeysError(message)
    if hw_list is None:
        message = 'Словарь не найден'
        logger.error(message)
        raise DictNoneError(message)
    if type(hw_list) != list:
        message = f'Объект {hw_list} не является списком'
        logger.error(message)
        raise NotListError(message)
    return response['homeworks']


def parse_status(homework):
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status == 'approved':
        verdict = HOMEWORK_STATUSES['approved']
    elif homework_status == 'reviewing':
        verdict = HOMEWORK_STATUSES['reviewing']
    else:
        verdict = HOMEWORK_STATUSES['rejected']
    if homework_status not in HOMEWORK_STATUSES:
        message = 'Статус работы не опознан'
        logger.error(message)
        raise HomeworkStatusError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    if not PRACTICUM_TOKEN:
        message = ("Отсутствует обязательная переменная окружения: "
                   "'PRACTICUM_TOKEN'")
        logger.critical(message)
        return False
    if not TELEGRAM_TOKEN:
        message = ("Отсутствует обязательная переменная окружения: "
                   "'TELEGRAM_TOKEN'")
        logger.critical(message)
        return False
    if not TELEGRAM_CHAT_ID:
        message = ("Отсутствует обязательная переменная окружения: "
                   "'TELEGRAM_CHAT_ID'")
        logger.critical(message)
        return False
    else:
        message = 'Все обязательные переменные окружения найдены'
        logger.info(message)
        return True


def main():
    """Основная логика работы бота."""
    status = ''
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    check_tokens()

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework and status != homework[0]['status']:
                message = parse_status(homework[0])
                send_message(bot, message)
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            time.sleep(RETRY_TIME)
            raise MainFuncError(message)


if __name__ == '__main__':
    main()
