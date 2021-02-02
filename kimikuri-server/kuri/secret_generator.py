import base64
import os


def safe_base64_encode(__bytes):
    """
    Removes any `=` used as padding from the encoded string.
    """
    encoded = base64.urlsafe_b64encode(__bytes)
    return encoded.rstrip(b"=")


def safe_base64_decode(string):
    """
    Adds back in the required padding before decoding.
    """
    padding = 4 - (len(string) % 4)
    string = string + ("=" * padding)
    return base64.urlsafe_b64decode(string)


def generate_secret(secret_bytes: int = 128):
    return safe_base64_encode(os.urandom(secret_bytes))


if __name__ == '__main__':
    lens = [8, 16, 24, 32, 48, 64, 72, 84, 96, 128, 192]
    for l in lens:
        print(f'len={l} nonce={generate_secret(l)}')
