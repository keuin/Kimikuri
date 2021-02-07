import logging
import os
from threading import Lock

import base58

from kuri.database import KuriDatabase


class TokenManager:
    __token_generating_lock = Lock()
    __logger = logging.getLogger('kimikuri.token_manager')

    def __init__(self, database: KuriDatabase, token_size: int = 32):
        self.__database = database
        self.__token_size = token_size
        self.__present_tokens = list(map(lambda x: x.token, database.get_users()))
        self.__logger.debug(f'Loaded {len(self.__present_tokens)} used token(s).')

    def generate_unused_token(self) -> str:
        """
        Generate a token which is not used by any user.
        :return: a fresh token.
        """

        def __gen():
            return str(base58.b58encode(os.urandom(self.__token_size)), 'utf-8')

        token = None
        with self.__token_generating_lock:
            while not token or token in self.__present_tokens:
                token = __gen()
            self.__present_tokens.append(token)
            self.__logger.info(f'Generated unique u.a.r. token {token}.')
        return token
