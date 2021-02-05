#!/usr/bin/python3
import requests
import logging


class KimikuriClient:
    """
    A simple Kimikuri API wrapper for python.
    """

    def __init__(self, token: str, api_root: str = None):
        """
        Initialize a Kimikuri client instance.
        :param api_root: the Kimikuri server api URL. Official API (from Keuin) is the default.
        :param token: the token for your Telegram account on Kimikuri.
        """
        if not api_root.endswith('/'):
            api_root += '/'
        self.__api_root = api_root if len(api_root) > len('http://') else 'https://kimikuri.keuin.cc/api/'
        self.__token = token
        self.__logger = logging.getLogger(KimikuriClient.__name__)

    def send_message(self, message: str, **kwargs) -> bool:
        """
        Let Kimikuri send you a message.
        :param message: the message text.
        :param kwargs: other arguments passed to requests.get method. (note that `url` and `params` are already used)
        :return: if success
        """

        r = requests.get(self.__api_root + 'message', params={'token': self.__token, 'message': message}, **kwargs)

        if r.status_code != 200:
            self.__logger.error(f'Bad HTTP status code: {r.status_code}')
            return False

        try:
            return r.json().get('success') is True
        except ValueError:
            self.__logger.error(f'Bad response: {r.text}')
            return False  # not a valid json


if __name__ == '__main__':
    __is_cli = True


    def __print_help_menu():
        print('Kimikuri Client CLI')
        print('You can import this module and use `KimikuriClient` programmatically.')
        print('Or use this script as a CLI tool instead:')
        print('kuriclient.py [--api-root <api_root>] --token <your_token> --message <message>')


    import sys

    args = sys.argv[1:]
    api_root = ''
    token = ''
    message = ''
    valid = True  # if the parsing termination state is valid
    is_switch = True  # if current token is a switch, rather than a data
    try:
        for i, t in enumerate(args):
            if is_switch:
                if t == '--api-root':
                    api_root = args[i + 1]
                if t == '--token':
                    token = args[i + 1]
                elif t == '--message':
                    message = args[i + 1]
                else:
                    # not a valid switch. Just print the help menu.
                    valid = False
                    break
                is_switch = False  # a valid switch. Next token is a data.
            else:
                #  a data. Skip it.
                is_switch = True
    except IndexError:
        valid = False

    if valid and token and message:
        if not KimikuriClient(api_root=api_root, token=token).send_message(message):
            print('Failed to send message.')
            exit(-10)
        else:
            exit(0)
    else:
        __print_help_menu()
        exit()
