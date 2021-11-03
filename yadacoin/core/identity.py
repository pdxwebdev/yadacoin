import hashlib

from coincurve import PublicKey


class Identity:
    @classmethod
    def from_dict(cls, data):
        inst = cls()
        inst.public_key = data['public_key']
        inst.username = data['username']
        inst.username_signature = data['username_signature']
        return inst

    def generate_rid(self, username_signature, collection=''):
        username_signatures = sorted(
            [
                str(self.username_signature),
                str(username_signature)
            ],
            key=str.lower
        )
        return hashlib.sha256((
            str(username_signatures[0]) + str(username_signatures[1] + collection)
        ).encode('utf-8')).digest().hex()

    @property
    def user_dict(self):
        return {
            'user_public_key': self.public_key_hex,
            'user_username_signature': self.username_signature,
            'user_username': self.username
        }

    @property
    def their_dict(self):
        return {
            'their_public_key': self.public_key_hex,
            'their_username_signature': self.username_signature,
            'their_username': self.username
        }

    @property
    def my_dict(self):
        return {
            'my_public_key': self.public_key_hex,
            'my_username_signature': self.username_signature,
            'my_username': self.username
        }

    @property
    def to_dict(self):
        return {
            'public_key': self.public_key_hex,
            'username_signature': self.username_signature,
            'username': self.username
        }

    @property
    def public_key_hex(self):
        if isinstance(self.public_key, PublicKey):
            return self.public_key.format().hex()
        else:
            return self.public_key