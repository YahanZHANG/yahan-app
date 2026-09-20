import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def encode_base64url(data):

    return (
        base64.urlsafe_b64encode(data)
        .decode("ascii")
        .rstrip("=")
    )


# Generate key pair

private_key = ec.generate_private_key(
    ec.SECP256R1()
)

public_key = private_key.public_key()


# Private key

private_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)


# Public key

public_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)


print(
    "VAPID_PUBLIC_KEY="
    + encode_base64url(public_bytes)
)

print(
    "VAPID_PRIVATE_KEY="
    + encode_base64url(private_bytes)
)