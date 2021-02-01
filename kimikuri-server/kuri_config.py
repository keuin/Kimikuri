import json
from typing import Optional


class BadConfigException(Exception):
    pass


class NoSuchConfigEntryException(BadConfigException):
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

        if self.get('webhook') and 'webhook_base' not in self:
            raise BadConfigException('`webhook_base` must be defined since `webhook` is true.')

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

    def use_webhook(self) -> bool:
        """
        Whether to use WebHook to contact to Telegram server, instead of polling.
        `webhook_base` must be defined if `webhook` is set to true.
        You have to expose {webhook_base}/[0-9A-Za-z-._~]+ to Telegram,
        and redirect all requests to them to Kimikuri like
        localhost:{your_port}/[0-9A-Za-z-._~]+, in order to let Kimikuri register
        an auto-generated secure webhook address.
        """
        return bool(self.get('webhook'))

    def get_webhook_base(self) -> str:
        base = str(self.get('webhook_base'))
        return base + ('/' if not base.endswith('/') else '')

    def get_webhook_cert_file_name(self) -> str:
        return self.get('webhook_cert_file')
