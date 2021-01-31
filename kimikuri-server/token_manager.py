import os
from threading import Lock

import base58

from database import KuriDatabase


class TokenManager:
    __token_generating_lock = Lock()

    def __init__(self, database: KuriDatabase):
        self.__database = database
        self.__present_tokens = []  # TODO: load from db

    def generate_unused_token(self) -> str:
        """
        Generate a token which is not used by any user.
        :return: a fresh token.
        """

        def __gen():
            return str(base58.b58encode(os.urandom(32)), 'utf-8')

        token = None
        with self.__token_generating_lock:
            while not token or token in self.__present_tokens:
                token = __gen()
            self.__present_tokens.append(token)
        return token
