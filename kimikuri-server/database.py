from typing import Optional


class KuriDatabase:
    """
    The ORM for Kimikuri.
    """
    __tokens = dict()

    def get_user_token_by_user_id(self, user_id: int) -> Optional[str]:
        """
        Get the user's token.
        :param user_id: user's telegram id.
        :return: return the user's token by his id if he has already registered. Otherwise, return None.
        """
        if not isinstance(user_id, int):
            raise ValueError()
        return self.__tokens.get(user_id)

    def set_user_token_by_user_id(self, user_id: int, token: str) -> Optional[str]:
        """
        Set the user's token.
        :param user_id: user's telegram id.
        :param token: user's token.
        :return: return the user's token by his id if he has already registered. Otherwise, return None.
        """
        if not isinstance(user_id, int):
            raise ValueError()
        if not isinstance(token, str):
            raise ValueError()
        old_value = self.__tokens.get(user_id)
        self.__tokens[user_id] = token
        return old_value
