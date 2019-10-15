import jwt

secret_key = "my_secret_key"
options = {
    'verify_signature': True,
    'verify_exp': True,
    'verify_nbf': False,
    'verify_iat': True,
    'verify_aud': False
}


def jwtauth(handler_class):
    ''' Handle Tornado JWT Auth '''
    def wrap_execute(handler_execute):
        def require_auth(handler, kwargs):

            auth = handler.request.headers.get('Authorization')
            if auth:
                parts = auth.split()

                if parts[0].lower() != 'bearer':
                    return False
                elif len(parts) == 1:
                    return False
                elif len(parts) > 2:
                    return False

                token = parts[1]
                try:
                    handler.jwt = jwt.decode(
                        token,
                        handler.config.jwt_secret_key,
                        options=handler.config.jwt_options
                    )

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