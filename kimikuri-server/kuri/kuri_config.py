import json
from typing import Optional


class BadConfigException(Exception):
    pass


class NoSuchConfigEntryException(BadConfigException):
    pass


class KuriConfig(dict):
    """
    JSON Keys: (non-optional options are marked with *)
    - users_db_file *
    - debug
    - log_level
    - max_length
    - bot.token *
    - bot.proxy
    - bot.pool_connection_size
    - bot.connect_timeout_seconds
    - bot.read_timeout_seconds
    - webhook
    - webhook.use_webhook
    - webhook.base * (if use_webhook is `true`)
    - webhook.cert_file
    """

    def __init__(self, file_name):
        dict.__init__(self)
        with open(file_name, encoding='utf-8') as f:
            j = json.load(f)
            for assertion, v in j.items():
                self[assertion] = v
        essentials = [
            (lambda x: 'users_db_file' in x, 'users_db_file'),
            (lambda x: 'token' in (x.get('bot') or dict()), 'bot.token')
        ]
        for assertion, name in essentials:
            if not assertion(self):
                raise NoSuchConfigEntryException(
                    f'{name} is not defined in configuration file. '
                )

        if self.use_webhook() and 'base' not in self.get('webhook'):
            raise BadConfigException('`webhook.base` must be defined since `webhook` is set to `true`.')

    def is_debug_mode(self) -> bool:
        return bool(self.get('debug'))

    def get_bot_token(self) -> str:
        return (self.get('bot') or dict()).get('token')

    def get_proxy_address(self) -> Optional[str]:
        return (self.get('bot') or dict()).get('proxy')

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

    # def get_database_file_name(self) -> str:
    #     return self.get('users_db_file')

    def use_webhook(self) -> bool:
        """
        Whether to use WebHook to contact to Telegram server, instead of polling.
        `webhook_base` must be defined if `webhook` is set to true.
        You have to expose {webhook_base}/[0-9A-Za-z-._~]+ to Telegram,
        and redirect all requests to them to Kimikuri like
        localhost:{your_port}/[0-9A-Za-z-._~]+, in order to let Kimikuri register
        an auto-generated secure webhook address.
        """
        return bool((self.get('webhook') or dict()).get('use_webhook'))

    def get_webhook_base(self) -> str:
        base = str((self.get('webhook') or dict()).get('base'))
        return base + ('/' if not base.endswith('/') else '')

    def get_webhook_cert_file_name(self) -> str:
        return (self.get('webhook') or dict()).get('cert_file')

    def get_pool_connection_size(self) -> int:
        return (self.get('bot') or dict()).get('pool_connection_size') or 8

    def get_bot_connect_timeout_seconds(self) -> int:
        return (self.get('bot') or dict()).get('connect_timeout_seconds') or 5

    def get_bot_read_timeout_seconds(self) -> int:
        return (self.get('bot') or dict()).get('read_timeout_seconds') or 5
