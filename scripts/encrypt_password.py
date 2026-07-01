import base64
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad
import getpass

# Generate a random salt
salt = get_random_bytes(16)

# Get password and passphrase
password = getpass.getpass("Enter your broker password: ")
passphrase = getpass.getpass("Enter a passphrase to encrypt the password: ")

# Derive the key from the passphrase using PBKDF2
key = PBKDF2(passphrase.encode(), salt, dkLen=32)  # 256-bit key for AES

# Pad the password to be a multiple of block size (AES.block_size is 16 bytes)
padded_password = pad(password.encode(), AES.block_size)

# Encrypt the password
cipher = AES.new(key, AES.MODE_CBC)
iv = cipher.iv  # Initialization vector (IV)
encrypted_password = cipher.encrypt(padded_password)

encrypted_data = salt + iv + encrypted_password
encrypted_value = base64.b64encode(encrypted_data).decode()

print()
print("Add this line to env:")
print(f"FT_IG_LIVE_PASSWORD_ENCRYPTED={encrypted_value}")

# Clear sensitive data from memory
password = None
passphrase = None
