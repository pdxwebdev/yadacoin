import hashlib

from coincurve import PublicKey


class Identity:
    @classmethod
    def from_dict(cls, data):
        inst = cls()
        inst.public_key = data['public_key']
        inst.username = data['username']
        inst.username_signature = data['username_signature']
        inst.collection = data.get('collection', '')
        inst.parent = data.get('parent', '')
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
    def to_dict(self):
        return {
            'public_key': self.public_key_hex,
            'username_signature': self.username_signature,
            'username': self.username,
            'collection': self.collection,
            'parent': self.parent
        }

    @property
    def public_key_hex(self):
        if isinstance(self.public_key, PublicKey):
            return self.public_key.format().hex()
        else:
            return self.public_key