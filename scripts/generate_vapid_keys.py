from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import base64


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


private_key = ec.generate_private_key(ec.SECP256R1())
private_numbers = private_key.private_numbers()
private_value = private_numbers.private_value.to_bytes(32, "big")

public_key = private_key.public_key()
public_numbers = public_key.public_numbers()
x = public_numbers.x.to_bytes(32, "big")
y = public_numbers.y.to_bytes(32, "big")
uncompressed = b"\x04" + x + y

print("WEB_PUSH_VAPID_PRIVATE_KEY=", b64url(private_value))
print("WEB_PUSH_VAPID_PUBLIC_KEY=", b64url(uncompressed))
print("WEB_PUSH_VAPID_SUBJECT=mailto:your@email.com")