import jwt
from coincurve import PublicKey

secret_key = "my_secret_key"
options = {
    'verify_signature': True,
    'verify_exp': True,
    'verify_nbf': False,
    'verify_iat': True,
    'verify_aud': False
}


def jwtauthwallet(handler_class):
    ''' Handle Tornado JWT Auth '''
    def wrap_execute(handler_execute):
        def require_auth(handler, kwargs):

            auth = handler.request.headers.get('Authorization')
            if auth:
                parts = auth.split()

                if len(parts) != 2:
                    return False
                elif parts[0].lower() != 'bearer':
                    return False

                token = parts[1]
                try:
                    from Crypto.PublicKey import ECC
                    handler.jwt = jwt.decode(
                        token,
                        handler.config.jwt_public_key,
                        verify=True,
                        algorithms=['ES256'],
                        options=handler.config.jwt_options
                    )
                    mongo_jwt = handler.config.mongo.db.config.find_one(
                        {
                            'key': 'jwt',
                            'value.key_or_wif': 'true'
                        }
                    )
                    if not mongo_jwt or handler.jwt['timestamp'] < mongo_jwt.get('value', {}).get('timestamp', 0):
                        return False

                except:
                    return False
            else:
                return False

            return True

        def _execute(self, transforms, *args, **kwargs):

            try:
                require_auth(self, kwargs)
            except Exception:
                return False

            return handler_execute(self, transforms, *args, **kwargs)

        return _execute

    handler_class._execute = wrap_execute(handler_class._execute)
    return handler_class


def jwtauthwebuser(handler_class):
    ''' Handle Tornado JWT Auth '''
    def wrap_execute(handler_execute):
        def require_auth(handler, kwargs):

            auth = handler.request.headers.get('Authorization')

            if auth:
                parts = auth.split()
                if len(parts) != 3:
                    return False
                elif parts[0].lower() != 'bearer':
                    return False

                token = parts[1]
                rid = parts[2]
                try:
                    from Crypto.PublicKey import ECC
                    handler.jwt = jwt.decode(
                        token,
                        handler.config.jwt_public_key,
                        verify=True,
                        algorithms=['ES256'],
                        options=handler.config.jwt_options
                    )
                    mongo_jwt = handler.config.mongo.site_db.web_tokens.find_one(
                        {
                            'token': token,
                            'rid': rid
                        }
                    )
                    if not mongo_jwt or handler.jwt['timestamp'] < mongo_jwt.get('value', {}).get('timestamp', 0):
                        return False

                except:
                    return False
            else:
                return False

            return True

        def _execute(self, transforms, *args, **kwargs):

            try:
                require_auth(self, kwargs)
            except Exception:
                return False

            return handler_execute(self, transforms, *args, **kwargs)

        return _execute

    handler_class._execute = wrap_execute(handler_class._execute)
    return handler_class