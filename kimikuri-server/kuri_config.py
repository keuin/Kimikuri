import json
from typing import Optional


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

    def is_debug_mode(self) -> bool:
        return bool(self.get('debug'))

    def get_bot_token(self) -> str:
        assert 'bot_token' in self, 'bot_token is not defined in configuration file.'
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
