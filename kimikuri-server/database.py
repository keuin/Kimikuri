import json
from threading import Lock
from typing import Optional, Iterator


class UserDict:
    """
    The user data structure used in Database internal.
    """

    def __init__(self, user_id=None, token=None, chat_id=None):
        if not user_id:
            raise ValueError('Invalid user_id')
        if not token:
            raise ValueError('Invalid token')
        if not chat_id:
            raise ValueError('Invalid chat_id')
        self.user_id = user_id
        self.token = token
        self.chat_id = chat_id

    def to_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'token': self.token,
            'chat_id': self.chat_id
        }

    @staticmethod
    def from_dict(d: dict):
        return UserDict(d['user_id'], d['token'], d['chat_id'])


class KuriDatabase:
    """
    The ORM for Kimikuri.
    """
    __users_by_token = dict()  # token -> user_dict
    __users_by_user_id = dict()  # user_id -> user_dict

    __lock_user_structure = Lock()  # lock for two dicts above
    __lock_is_user_registered = Lock()
    __lock_register = Lock()

    __dirty = False

    @staticmethod
    def from_file(fp):
        """
        Load serialized (array-like) database from file.
        """
        j = json.load(fp)
        if not isinstance(j, list):
            raise ValueError('JSON object must be a list')
        db = KuriDatabase()
        for d in j:
            user = UserDict.from_dict(d)
            db.__users_by_token[user.token] = user
            db.__users_by_user_id[user.user_id] = user
        return db

    def to_file(self, fp):
        """
        Save database to file.
        """

        with self.__lock_user_structure:
            l = [x.to_dict() for x in self.__users_by_token.values()]
        json.dump(l, fp, indent=4)
        self.__dirty = False

    def is_dirty(self):
        """
        If modifications have not been written back to disk.
        """
        return self.__dirty

    def is_user_registered(self, user_id=None, token=None) -> bool:
        """
        Either `user_id` or `token` should be present.
        """
        with self.__lock_is_user_registered:
            if not user_id and not token:
                raise ValueError('Either `user_id` or `token` should be present.')
            if user_id and token:
                user_dict = self.__users_by_user_id.get(user_id)
                return isinstance(user_dict, UserDict) and user_dict.token == token
            if user_id:
                return isinstance(self.__users_by_user_id.get(user_id), UserDict)
            if token:
                return isinstance(self.__users_by_token.get(token), UserDict)

    def register(self, user_id=None, token=None, chat_id=None):
        """
        Register a user with given `user_id` and token.
        """
        with self.__lock_register:
            if self.is_user_registered(user_id=user_id):
                raise ValueError('Given user is already registered.')
            if self.is_user_registered(token=token):
                raise ValueError('Given token is already taken.')
            user = UserDict(user_id=user_id, token=token, chat_id=chat_id)
            with self.__lock_user_structure:
                self.__users_by_token[token] = user
                self.__users_by_user_id[user_id] = user
                self.__dirty = True

    def get_user(self, user_id=None, token=None) -> Optional[UserDict]:
        if user_id:
            d = self.__users_by_user_id.get(user_id)
        elif token:
            d = self.__users_by_token.get(token)
        else:
            raise ValueError('Either user_id or token must be provided')

        if isinstance(d, UserDict):
            return UserDict.from_dict(d.to_dict())
        else:
            return None

    def get_users(self) -> Iterator[UserDict]:
        with self.__lock_user_structure:
            return filter(lambda x: isinstance(x, UserDict), self.__users_by_token.values())

    # def get_user_token_by_user_id(self, user_id: int) -> Optional[str]:
    #     """
    #     Get the user's token.
    #     :param user_id: user's telegram id.
    #     :return: return the user's token by his id if he has already registered. Otherwise, return None.
    #     """
    #     if not isinstance(user_id, int):
    #         raise ValueError()
    #     return self.__users_by_token.get(user_id)
    #
    # def set_user_token_by_user_id(self, user_id: int, token: str) -> Optional[str]:
    #     """
    #     Set the user's token.
    #     :param user_id: user's telegram id.
    #     :param token: user's token.
    #     :return: return the user's token by his id if he has already registered. Otherwise, return None.
    #     """
    #     if not isinstance(user_id, int):
    #         raise ValueError()
    #     if not isinstance(token, str):
    #         raise ValueError()
    #     old_value = self.__users_by_token.get(user_id)
    #     self.__users_by_token[user_id] = token
    #     return old_value
