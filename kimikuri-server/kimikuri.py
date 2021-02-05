import logging.config
import os
import platform
import sys
from logging import StreamHandler, FileHandler, Formatter
from queue import Queue
from threading import Thread, Event
from typing import IO

import fastapi
import uvicorn
from fastapi import FastAPI
from starlette.responses import HTMLResponse
from telegram import Bot, Update
from telegram.ext import Updater, CallbackContext, Dispatcher
from telegram.utils.request import Request

from kuri.command_register import CommandRegister
from kuri.database import KuriDatabase
from kuri.kuri_config import KuriConfig
from kuri.secret_generator import generate_secret
from kuri.token_manager import TokenManager

# error numbers
ERR_FAILED_TO_LOG_CONFIG = -10
ERR_FAILED_TO_LOAD_DATABASE = -11

# version
KURI_VERSION = '0.6.3'
KURI_VERSION_SUFFIX = 'alpha'

# some basic editable configurations
# some of them can be set by environment variables:
#   KURI_CONFIG_FILE
#   KURI_USERS_DB_FILE
#   KURI_LOG_FILE
#   KURI_WEBHOOK_SECRET_LENGTH
#   KURI_TOKEN_SIZE_BYTES

CONFIG_FILE = os.environ.get('KURI_CONFIG_FILE') or 'kimikuri.json'
USER_DB_FILE = os.environ.get('KURI_USERS_DB_FILE') or 'users.json'
LOG_FILE = os.environ.get('KURI_LOG_FILE') or 'kimikuri.log'
WEBHOOK_SECRET_LENGTH = os.environ.get('KURI_WEBHOOK_SECRET_LENGTH') or 128
TOKEN_SIZE_BYTES = os.environ.get('KURI_TOKEN_SIZE_BYTES') or 32

API_SEND_MESSAGE = 'message'
DEBUG_HOST = "0.0.0.0"
DEBUG_PORT = 7777

print('======== BASIC CONFIG ========')
print(f'Configuration file: {CONFIG_FILE}')
print(f'Log file: {LOG_FILE}')
print(f'WebHook secret length: {WEBHOOK_SECRET_LENGTH}')
print(f'Token size bytes: {TOKEN_SIZE_BYTES}')
print('==============================')

kimikuri_running = True  # flag used to stop internal threads

# initialize logger in WARNING level
# TODO: set 3rd-party libs' logger to WARN or ERR
log_level = logging.WARNING
logger = logging.getLogger('kimikuri')
logger.setLevel(log_level)


# set custom exception handler to log uncaught exceptions
def __uncaught_exception_handler(__type, __value, __traceback):
    global logger
    if logger:
        logger.error(f'Uncaught exception {__type}: {__value}\nTraceback: {__traceback}')
    else:
        # fallback to default handler
        __original_uncaught_exception_handler(__type, __value, __traceback)


__original_uncaught_exception_handler = sys.excepthook
sys.excepthook = __uncaught_exception_handler

# set log handlers (to file & stderr)
log_formatter = Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')

console_handler = StreamHandler()
console_handler.setLevel(log_level)
console_handler.setFormatter(log_formatter)

file_handler = FileHandler(LOG_FILE)
file_handler.setLevel(log_level)
file_handler.setFormatter(log_formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

# initialize config after the logger is initialized,
# to save log of uncaught exceptions into file
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

# update log level when the config is loaded
log_level = config.get_log_level()
logger.setLevel(log_level)
console_handler.setLevel(log_level)
file_handler.setLevel(log_level)
print(f'Set log level to {log_level}.')

# initialize database
if os.path.isfile(USER_DB_FILE):
    try:
        # load database form file
        with open(USER_DB_FILE, 'r', encoding='utf-8') as f:
            database = KuriDatabase.from_file(f)
        logger.debug(f'Loaded {sum(1 for _ in database.get_users())} user(s) into memory.')
    except IOError as e:
        logger.error(f'Failed to load database file `{USER_DB_FILE}`: {e}')
        exit(ERR_FAILED_TO_LOAD_DATABASE)
else:
    database = KuriDatabase()
    logger.debug(f'User database file does not exist. Create an empty one.')

__save_database_loop_interrupt_event = Event()  # used to interrupt loop in `__save_database_loop`


def __save_database_loop():
    __logger = logger.getChild('database-save-loop')
    __logger.debug('Thread starting...')
    while kimikuri_running:
        __save_database_loop_interrupt_event.wait(10)
        try:
            if database.is_dirty():
                with open(USER_DB_FILE, 'w', encoding='utf-8') as f:
                    database.to_file(f)
                __logger.info('Saved the database.')
        except IOError as e:
            __logger.error(f'Failed to save database to file `{USER_DB_FILE}`: {e}')
    __logger.debug('Thread stopped.')


db_save_thread = Thread(target=__save_database_loop)
db_save_thread.setName('DatabaseSaveThread')
db_save_thread.setDaemon(True)
db_save_thread.start()

# initialize token manager
token_manager = TokenManager(database, TOKEN_SIZE_BYTES)

# initialize FastAPI core
webapi = FastAPI()

# initialize bot and telegram framework
proxy_url = config.get_proxy_address()
if proxy_url:
    logger.info(f'Using proxy {proxy_url} to connect to Telegram API.')
bot = Bot(token=config.get_bot_token(), request=Request(
    proxy_url=proxy_url,
    con_pool_size=config.get_pool_connection_size(),
    connect_timeout=config.get_bot_connect_timeout_seconds(),
    read_timeout=config.get_bot_read_timeout_seconds()
))

logger.info('Connecting to Telegram...')

logger.info(f'Recognized bot as {bot.get_me().username}.')

# generate secret and bind webhook (even if it is not used, for convince and secure reason)
webhook_secret = str(generate_secret(WEBHOOK_SECRET_LENGTH), encoding='ascii')
logger.debug(f'WebHook secret ({len(webhook_secret)}): {webhook_secret}')

if config.use_webhook():
    logger.info('Setting up bot in WebHook mode...')
    # Create bot, update queue and dispatcher instances
    webhook_update_queue = Queue()
    dispatcher = Dispatcher(bot, webhook_update_queue)
    updater = None  # to eliminate IDE warning
else:
    logger.info('Setting up bot in polling mode...')
    updater = Updater(bot=bot, use_context=True, request_kwargs={
        'proxy_url': proxy_url
    } if proxy_url else None)
    dispatcher = updater.dispatcher
    webhook_update_queue = None  # to eliminate IDE warning

# register command handlers
command_register = CommandRegister(dispatcher)


@command_register.user_command('start', 'show this help menu')
def start(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hello, this is Kimikuri!\n" + command_register.get_manual_string()
    )
    # context.bot.send_message(chat_id=update.effective_chat.id, text=str(update))


@command_register.user_command('register', 'get your private token')
def register(update: Update, context: CallbackContext):
    sender_id = update['message']['from_user']['id']
    chat_id = update['message']['chat_id']

    logger.debug(f'User {sender_id} want to register.')
    if user := database.get_user(user_id=sender_id):
        token = user.token
        logger.debug(f'The user has already registered. Previous token: {token}')
    else:
        token = token_manager.generate_unused_token()
        database.register(user_id=sender_id, token=token, chat_id=chat_id)
        logger.debug(f'Registered user {sender_id} with chat_id={chat_id}, token={token}')
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Your token: {token}\nTreat this as a password!'
    )


@command_register.user_command('howto', 'learn how to let Kimikuri send you messages')
def howto(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='First, get your token by using `/register`.\n' +
             f'Then, GET or POST on {config.get_api_base()}{API_SEND_MESSAGE} with parameter ' +
             '`token` and `message`.\n' +
             'Finally, Kimikuri will repeat that message to you, via Telegram!'
    )


# start webhook dispatcher thread
if config.use_webhook():
    webhook_dispatcher_thread = Thread(target=dispatcher.start, name='WebHookInBoundDispatcher')
    webhook_dispatcher_thread.start()


# internal APIs

def notify(token: str, message: str) -> bool:
    user = database.get_user(token=token)
    if user:
        logger.info(f'Offer user {user.user_id} (chat_id={user.chat_id}) message {message}')
        bot.send_message(chat_id=user.chat_id, text=message)
        return True
    else:
        logger.info(f'Invalid token {token}')


def __get_greeting_str():
    greeting = f'Kimikuri {KURI_VERSION}'
    if KURI_VERSION_SUFFIX:
        greeting += f' - {KURI_VERSION_SUFFIX}'
    greeting += f' @ Python {platform.python_version()}'
    return greeting


def stop():
    """
    Stop kimikuri.
    """
    global kimikuri_running
    print('Stopping...')
    kimikuri_running = False  # set main running flag to false
    __save_database_loop_interrupt_event.set()  # interrupt database saving loop
    updater.stop() if updater else None  # stop bot updater
    dispatcher.stop()  # stop bot dispatcher
    exit(0)


greeting_string = __get_greeting_str()


# register FastAPI handlers
@webapi.get('/', response_class=HTMLResponse)
async def webapi_root():
    return greeting_string


@webapi.get('/' + API_SEND_MESSAGE)
async def webapi_send_message(token: str, message: str):
    return {'success': bool(notify(token, message))}


@webapi.post(f'/{webhook_secret}')
async def webapi_webhook(request: fastapi.Request):
    if not config.use_webhook():
        return {'message': 'Uh, uhh. This makes no sense.'}  # filter out undesired requests
    json_body = await request.json()
    logger.debug(f'WebHook request: {json_body}')
    webhook_update_queue.put(Update.de_json(json_body, bot))


# start polling or register webhook
if config.use_webhook():
    logger.info('Registering WebHook...')
    webhook_addr = config.get_webhook_base() + webhook_secret
    logger.debug(f'Previous WebHook status: {bot.get_webhook_info()}')
    bot.delete_webhook(drop_pending_updates=True)
    if cert_file_name := config.get_webhook_cert_file_name():
        cert = open(cert_file_name, 'rb')
    else:
        cert = None
    bot.set_webhook(url=webhook_addr, certificate=cert)
    if isinstance(cert, IO):
        cert.close()
    logger.debug(f'Current WebHook status: {bot.get_webhook_info()}')
else:
    logger.info('Start polling...')
    assert updater is not None, 'Updater should have been initialized in polling mode.'
    updater.start_polling()


# start internal debugging uvicorn server
def __uvicorn_runner():
    uvicorn.run(webapi, host=DEBUG_HOST, port=DEBUG_PORT, log_level='warning')


if __name__ == "__main__":

    if debug_mode:
        print('Starting internal uvicorn server (for debugging only)...')
        uvicorn_thread = Thread(target=__uvicorn_runner)
        uvicorn_thread.setName('UvicornRunner')
        uvicorn_thread.setDaemon(True)
        uvicorn_thread.start()

    print('Hello!')
    print(greeting_string)

    try:
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
                stop()
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
    except KeyboardInterrupt:
        stop()
