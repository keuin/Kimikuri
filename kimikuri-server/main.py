import logging.config
import os
import platform
import time
from queue import Queue
from threading import Thread

import fastapi
import uvicorn
from fastapi import FastAPI
from starlette.responses import HTMLResponse
from telegram import Bot, Update
from telegram.ext import Updater, CallbackContext, Dispatcher
from telegram.utils.request import Request

from command_register import CommandRegister
from database import KuriDatabase
from kuri_config import KuriConfig
from secret_generator import generate_secret
from token_manager import TokenManager

# error numbers
ERR_FAILED_TO_LOG_CONFIG = -10
ERR_FAILED_TO_LOAD_DATABASE = -11

# version
KURI_VERSION = '0.3.0'
KURI_VERSION_SUFFIX = 'alpha'

# some basic editable configurations
CONFIG_FILE = 'kimikuri.json'
WEBHOOK_NONCE_LENGTH = 128
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
# logging.config.dictConfig({
#     'version': 1,
#     'disable_existing_loggers': True,
# })
# TODO: configure logger with handler and write them to file and console.
# TODO: set 3rd-party libs' logger to WARN or ERR
log_level = config.get_log_level()
print(f'Set log level to {log_level}')
logger = logging.getLogger('KimikuriMain')
logger.setLevel(log_level)
logging.basicConfig(format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s',
                    level=log_level)

# initialize database
if os.path.isfile(db_file_name := config.get_database_file_name()):
    try:
        # load database form file
        with open(db_file_name, 'r', encoding='utf-8') as f:
            database = KuriDatabase.from_file(f)
        print(f'Loaded {sum(1 for _ in database.get_users())} user(s) into memory.')
    except IOError as e:
        logger.error(f'Failed to load database file `{db_file_name}`: {e}')
        exit(ERR_FAILED_TO_LOAD_DATABASE)
else:
    database = KuriDatabase()
    print(f'User database file does not exist. Create an empty one.')


def __save_database():
    logger.debug('Database save thread is starting...')
    while True:
        time.sleep(10)
        try:
            if database.is_dirty():
                with open(db_file_name, 'w', encoding='utf-8') as f:
                    database.to_file(f)
                logger.info('Saved the database.')
        except IOError as e:
            logger.error(f'Failed to save database to file `{db_file_name}`: {e}')


db_save_thread = Thread(target=__save_database)
db_save_thread.setName('DatabaseSaveThread')
db_save_thread.setDaemon(True)
db_save_thread.start()

# initialize token manager
token_manager = TokenManager(database)

# initialize FastAPI core
webapi = FastAPI()

# initialize bot and telegram framework
proxy_url = config.get_proxy_address()
bot = Bot(token=config.get_bot_token(), request=Request(proxy_url=proxy_url))

logger.info(f'Recognized bot as {bot.get_me().username}')

# generate secret and bind webhook (even if it is not used, for convince and secure reason)
webhook_secret = str(generate_secret(WEBHOOK_NONCE_LENGTH), encoding='ascii')
logger.debug(f'WebHook secret: {webhook_secret}')

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
register = CommandRegister(dispatcher)


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

    logger.debug(f'User {sender_id} want to register.')
    if user := database.get_user(user_id=sender_id):
        token = user.token
        logger.debug(f'The user has already registered. Previous token: {token}')
    else:
        token = token_manager.generate_unused_token()
        database.register(user_id=sender_id, token=token, chat_id=chat_id)
        logger.debug(f'Registered user {sender_id} with chat_id={chat_id}, token={token}')
    context.bot.send_message(chat_id=update.effective_chat.id, text=
    f'Your token: {token}\n' +
    f'Treat this as a password!')


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


greeting_string = __get_greeting_str()


# register FastAPI handlers
@webapi.get('/', response_class=HTMLResponse)
async def webapi_root():
    return greeting_string


@webapi.get('/message')
async def webapi_send_message(token: str, message: str):
    return {'success': bool(notify(token, message))}


@webapi.get(f'/{webhook_secret}')
async def webapi_webhook(request: fastapi.Request):
    if not config.use_webhook():
        return {'message': 'Uh, uhh. This makes no sense.'}  # filter out undesired requests
    webhook_update_queue.put(Update.de_json(await request.json(), bot))


# start polling or register webhook
if config.use_webhook():
    logger.info('Registering WebHook...')
    webhook_addr = config.get_webhook_base() + webhook_secret
    bot.set_webhook(url=webhook_addr, certificate=config.get_webhook_cert_file_name())
else:
    logger.info('Start polling...')
    assert updater is not None, 'Updater should have been initialized in polling mode.'
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
