import json
from typing import Optional


class NoSuchConfigEntryException(Exception):
    pass


class KuriConfig(dict):
    """
    JSON Keys:
    - bot_token
    - proxy (optional)
    """

    def __init__(self, file_name):
        dict.__init__(self)
        with open(file_name, encoding='utf-8') as f:
            j = json.load(f)
            for k, v in j.items():
                self[k] = v
        essentials = [
            ('db_file', 'users.json'),
            'bot_token'
        ]
        for e in essentials:
            if isinstance(e, str):
                k = e
                txt = ''
            else:
                k, txt = e
            if k not in self:
                raise NoSuchConfigEntryException(
                    f'{k} is not defined in configuration file. ' +
                    (f'Recommend value is `{txt}`.' if txt else f'You must set it in `{file_name}`.'))

    def is_debug_mode(self) -> bool:
        return bool(self.get('debug'))

    def get_bot_token(self) -> str:
        return self.get('bot_token')

    def get_proxy_address(self) -> Optional[str]:
        return self.get('proxy')

    def get_log_level(self) -> str:
        """
        Only support `INFO` or `DEBUG`.
        """
        level = self.get('log_level')
        if level:
            return str(level).upper()
        return 'DEBUG' if self.is_debug_mode() else 'INFO'

    def get_max_length(self) -> int:
        max_length = self.get('max_length')
        return max_length if isinstance(max_length, int) else 100

    def get_database_file_name(self) -> str:
        return self.get('db_file')
