import hashlib
import binascii
import base58
from mnemonic import Mnemonic
from bip32utils import BIP32Key
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey, PublicKey

from yadacoin.core.collections import Collections
from yadacoin.core.config import get_config
from yadacoin.core.transactionutils import TU


class Identity:
    def __init__(
        self,
        public_key,
        username,
        username_signature,
        collection=Collections.CONTACT.value,
        parent=None,
        wif=None,
    ):
        self.public_key = public_key
        self.username = username
        self.username_signature = username_signature
        self.collection = collection
        self.parent = parent
        self.wif = wif

    @classmethod
    def generate(cls, username="", collection=None, parent=None):
        if not collection:
            collection = Collections.CONTACT.value
        mnemonic = Mnemonic("english")
        seed = mnemonic.generate(256)
        entropy = mnemonic.to_entropy(seed)
        key = BIP32Key.fromEntropy(entropy)
        private_key = key.PrivateKey().hex()
        public_key = (
            PublicKey.from_point(key.K.pubkey.point.x(), key.K.pubkey.point.y())
            .format()
            .hex()
        )
        wif = cls.generate_wif(private_key)
        username_signature = cls.generate_username_signature(private_key, username)
        return cls(
            public_key=public_key,
            username=username,
            username_signature=username_signature,
            parent=parent,
            wif=wif,
        )

    @classmethod
    def from_dict(cls, data):
        return cls(
            public_key=data["public_key"],
            username=data["username"],
            username_signature=data["username_signature"],
            collection=data.get("collection", ""),
            parent=data.get("parent", ""),
        )

    def generate_rid(self, username_signature, collection=""):
        username_signatures = sorted(
            [str(self.username_signature), str(username_signature)], key=str.lower
        )
        return (
            hashlib.sha256(
                (
                    str(username_signatures[0])
                    + str(username_signatures[1] + collection)
                ).encode("utf-8")
            )
            .digest()
            .hex()
        )

    @classmethod
    def get_username_signature(self, private_key, username):
        return TU.generate_deterministic_signature(
            private_key=private_key, message=username
        )

    @classmethod
    def generate_wif(cls, private_key):
        private_key_static = private_key
        extended_key = "80" + private_key_static + "01"
        first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key)).hexdigest()
        second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
        final_key = extended_key + second_sha256[:8]
        wif = base58.b58encode(binascii.unhexlify(final_key)).decode("utf-8")
        return wif

    @property
    def to_dict(self):
        return {
            "public_key": self.public_key_hex,
            "username_signature": self.username_signature,
            "username": self.username,
            "collection": self.collection,
            "parent": self.parent,
        }

    @property
    def public_key_hex(self):
        if isinstance(self.public_key, PublicKey):
            return self.public_key.format().hex()
        else:
            return self.public_key


class PrivateIdentity(Identity):
    @classmethod
    def from_dict(cls, data):
        return cls(
            public_key=data["public_key"],
            username=data["username"],
            username_signature=data["username_signature"],
            collection=data.get("collection", ""),
            parent=data.get("parent", ""),
            wif=data.get("wif", ""),
        )

    @property
    def to_dict(self):
        return {
            "public_key": self.public_key_hex,
            "username_signature": self.username_signature,
            "username": self.username,
            "collection": self.collection,
            "parent": self.parent,
            "wif": self.wif,
        }


class PublicIdentity(Identity):
    @property
    def to_dict(self):
        return {
            "public_key": self.public_key_hex,
            "username_signature": self.username_signature,
            "username": self.username,
            "collection": self.collection,
            "parent": self.parent,
        }
