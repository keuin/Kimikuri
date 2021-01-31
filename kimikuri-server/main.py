import logging

from telegram import Update
from telegram.ext import Updater, CallbackContext

from command_register import CommandRegister
from database import KuriDatabase
from kuri_config import KuriConfig
from token_manager import TokenManager

# some basic configurations
CONFIG_FILE = 'kimikuri.json'
ERR_FAILED_TO_LOG_CONFIG = -10

# initialize config
print(f'Loading config file {CONFIG_FILE}...')

config = None
try:
    config = KuriConfig(CONFIG_FILE)
except IOError as e:
    print(f'Failed to load config file. {e}')
    exit(ERR_FAILED_TO_LOG_CONFIG)

# initialize logger
log_level = config.get_log_level()
print(f'Set log level to {log_level}')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=log_level)

# initialize database
database = KuriDatabase()

# initialize token manager
token_manager = TokenManager(database)

# initialize telegram framework
proxy_url = config.get_proxy_address()
updater = Updater(token=config.get_bot_token(), use_context=True, request_kwargs={
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

    logging.debug(f'User {sender_id} want to register.')
    if token := database.get_user_token_by_user_id(sender_id):
        logging.debug(f'The user has already registered. Previous token: {token}')
    else:
        token = token_manager.generate_unused_token()
        database.set_user_token_by_user_id(sender_id, token)
        logging.debug(f'New token: {token}')
    context.bot.send_message(chat_id=update.effective_chat.id, text=f'Your token: {token}\nTreat this as a password!')


# go into the main loop
updater.start_polling()
