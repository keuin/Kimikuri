import logging

from telegram import Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext


class CommandRegister:
    __registered_commands = dict()  # name -> {description}
    __manual = None

    def __init__(self, dispatcher: Dispatcher):
        self.__dispatcher = dispatcher

    def command(self, name: str, description: str):
        """
        The decorator that marks a function as a bot command handler function.
        Just use this like Flask's `app.get` or `app.post`.
        :param name: the command's full name.
        :param description: description of this command.
        :return: the desired function wrapper. The command will be registered once the wrapper is called.
        """

        if not isinstance(name, str):
            raise ValueError('Invalid command name.')
        if not isinstance(description, str):
            raise ValueError('Invalid command description.')

        def command_wrapper(func):
            if name in self.__registered_commands.keys():
                logging.error(f'Command `{name}` has already been registered. Cannot register more than once.')
            else:
                self.__dispatcher.add_handler(CommandHandler(name, func))
                self.__registered_commands[name] = {'description': description}
                logging.debug(f'Registered command {name}.')
            return func

        return command_wrapper

    def user_command(self, name: str, description: str):
        """
        The decorator that marks a function as a bot command handler function.
        The process function will be called only if the invoker is a user.
        Just use this like Flask's `app.get` or `app.post`.
        :param name: full name of this command.
        :param description: description of this command.
        :return: the desired function wrapper. The command will be registered once the wrapper is called.
        """

        if not isinstance(name, str):
            raise ValueError('Invalid command name.')
        if not isinstance(description, str):
            raise ValueError('Invalid command description.')

        outer_wrapper = self.command(name, description)

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

    def get_manual_string(self) -> str:
        """
        Generate usage manual of all commands.
        """
        if self.__manual is None:
            # lazy generating & persistent caching
            manual = ''
            for command, command_dict in self.__registered_commands.items():
                manual += f"Type '/{command}' to {command_dict['description']}.\n"
            self.__manual = manual
        return self.__manual
