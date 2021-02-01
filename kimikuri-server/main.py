import logging
import os
import platform
import time
from threading import Thread

import uvicorn
from fastapi import FastAPI
from starlette.responses import HTMLResponse
from telegram import Bot, Update
from telegram.ext import Updater, CallbackContext
from telegram.utils.request import Request

from command_register import CommandRegister
from database import KuriDatabase
from kuri_config import KuriConfig
from token_manager import TokenManager

# some basic configurations

CONFIG_FILE = 'kimikuri.json'
ERR_FAILED_TO_LOG_CONFIG = -10
ERR_FAILED_TO_LOAD_DATABASE = -11
KURI_VERSION = '0.2.0'
KURI_VERSION_SUFFIX = 'alpha'
DEBUG_HOST = "0.0.0.0"
DEBUG_PORT = 8000

# initialize config
print(f'Loading config file {CONFIG_FILE}...')

config = None
try:
    config = KuriConfig(CONFIG_FILE)
except IOError as e:
    print(f'Failed to load config file. {e}')
    exit(ERR_FAILED_TO_LOG_CONFIG)

# alert if run in debug mode
if debug_mode := config.is_debug_mode():
    print('WARNING: Kimikuri is running in debug mode.')

# initialize logger
log_level = config.get_log_level()
print(f'Set log level to {log_level}')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=log_level)

# initialize database
if os.path.isfile(db_file_name := config.get_database_file_name()):
    try:
        # load database form file
        with open(db_file_name, 'r', encoding='utf-8') as f:
            database = KuriDatabase.from_file(f)
        print(f'Loaded {sum(1 for _ in database.get_users())} user(s) into memory.')
    except IOError as e:
        logging.error(f'Failed to load database file `{db_file_name}`: {e}')
        exit(ERR_FAILED_TO_LOAD_DATABASE)
else:
    database = KuriDatabase()
    print(f'User database file does not exist. Create an empty one.')


def __save_database():
    logging.debug('Database save thread is starting...')
    while True:
        time.sleep(10)
        try:
            if database.is_dirty():
                with open(db_file_name, 'w', encoding='utf-8') as f:
                    database.to_file(f)
                logging.info('Saved the database.')
        except IOError as e:
            logging.error(f'Failed to save database to file `{db_file_name}`: {e}')


db_save_thread = Thread(target=__save_database)
db_save_thread.setName('DatabaseSaveThread')
db_save_thread.setDaemon(True)
db_save_thread.start()

# initialize token manager
token_manager = TokenManager(database)

# initialize bot and telegram framework
proxy_url = config.get_proxy_address()
bot = Bot(token=config.get_bot_token(), request=Request(proxy_url=proxy_url))

logging.info(f'Recognized bot as {bot.get_me().username}')

updater = Updater(bot=bot, use_context=True, request_kwargs={
    'proxy_url': proxy_url
} if proxy_url else None)

dispatcher = updater.dispatcher
register = CommandRegister(dispatcher)


# register command handlers
@register.user_command('start')
def start(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text=
    "Hello, this is Kimikuri!\n" +
    "Type '/start' to show this help menu.\n" +
    "Type '/register' to get your private token.\n")
    # context.bot.send_message(chat_id=update.effective_chat.id, text=str(update))


@register.user_command('register')
def register(update: Update, context: CallbackContext):
    sender_id = update['message']['from_user']['id']
    chat_id = update['message']['chat_id']

    logging.debug(f'User {sender_id} want to register.')
    if user := database.get_user(user_id=sender_id):
        token = user.token
        logging.debug(f'The user has already registered. Previous token: {token}')
    else:
        token = token_manager.generate_unused_token()
        database.register(user_id=sender_id, token=token, chat_id=chat_id)
        logging.debug(f'Registered user {sender_id} with chat_id={chat_id}, token={token}')
    context.bot.send_message(chat_id=update.effective_chat.id, text=
    f'Your token: {token}\n' +
    f'Treat this as a password!')


# internal APIs

def notify(token: str, message: str) -> bool:
    user = database.get_user(token=token)
    if user:
        logging.info(f'Offer user {user.user_id} (chat_id={user.chat_id}) message {message}')
        bot.send_message(chat_id=user.chat_id, text=message)
        return True
    else:
        logging.info(f'Invalid token {token}')


def __get_greeting_str():
    greeting = f'Kimikuri {KURI_VERSION}'
    if KURI_VERSION_SUFFIX:
        greeting += f' - {KURI_VERSION_SUFFIX}'
    greeting += f' @ Python {platform.python_version()}'
    return greeting


greeting_string = __get_greeting_str()

# initialize FastAPI handlers

webapi = FastAPI()


@webapi.get('/', response_class=HTMLResponse)
def webapi_root():
    return greeting_string


@webapi.get('/message')
def webapi_send_message(token: str, message: str):
    return {'success': bool(notify(token, message))}


# start the main loop in another thread
logging.info('Start polling...')
updater.start_polling()


# start internal debugging uvicorn server
def __uvicorn_runner():
    uvicorn.run(webapi, host=DEBUG_HOST, port=DEBUG_PORT)


if __name__ == "__main__":

    if debug_mode:
        print('Start internal uvicorn server (for debugging only)')
        uvicorn_thread = Thread(target=__uvicorn_runner)
        uvicorn_thread.setName('UvicornRunner')
        uvicorn_thread.setDaemon(True)
        uvicorn_thread.start()

    print(greeting_string)

    while True:
        inp = input('>>>')
        inp_lower = inp.lower()
        if inp_lower == 'help' or inp_lower == 'h' or inp_lower == '?':
            print(
                'Usage:\n' +
                'users: show all registered users\n' +
                'help/h/?: show help menu\n' +
                'exit: stop and quit'
            )
        elif inp_lower == 'exit':
            print('Stopping...')
            exit(0)
        elif inp_lower == 'users':
            users = database.get_users()
            print('Users:')
            counter = 0
            for user in users:
                print(f'User ID: {user.user_id}, Chat ID: {user.chat_id}, Token: {user.token}')
                counter += 1
            if counter:
                print(f'{counter} user(s) totally.')
            else:
                print('(no user registered)')
        else:
            print('Invalid input. run `help` to show usages.')
