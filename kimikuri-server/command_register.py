import logging

from telegram import Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext


class CommandRegister:

    def __init__(self, dispatcher: Dispatcher):
        self.__dispatcher = dispatcher
        self.__registered_commands = set()

    def command(self, name: str):
        """
        The decorator that marks a function as a bot command handler function.
        Just use this like Flask's `app.get` or `app.post`.
        :param name: the command's full name.
        :return: the desired function wrapper. The command will be registered once the wrapper is called.
        """

        def command_wrapper(func):
            if name in self.__registered_commands:
                logging.error(f'Command `{name}` has already been registered. Cannot register more than once.')
            else:
                self.__registered_commands.add(name)
                self.__dispatcher.add_handler(CommandHandler(name, func))
                logging.debug(f'Registered command {name}.')
            return func

        return command_wrapper

    def user_command(self, name: str):
        """
        The decorator that marks a function as a bot command handler function.
        The process function will be called only if the invoker is a user.
        Just use this like Flask's `app.get` or `app.post`.
        :param name: the command's full name.
        :return: the desired function wrapper. The command will be registered once the wrapper is called.
        """
        outer_wrapper = self.command(name)

        def user_command_wrapper(func):
            def wrapper_func(update: Update, context: CallbackContext):
                if 'message' not in dir(update):
                    return
                if 'from_user' not in dir(update.message):
                    return
                func(update, context)

            return wrapper_func

        def compounded_wrapper(outer, inner):
            return lambda func: outer(inner(func))

        return compounded_wrapper(outer_wrapper, user_command_wrapper)
