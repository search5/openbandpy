import urllib.parse

from openbandpy.band_exception import BandAPIException


class BandAuthorize:
    def __init__(self, *, client_id=None, client_secret=None, code=None,
                 redirect_uri=None, response_type=None, grant_type=None):
        self.response_type = response_type
        self.grant_type = grant_type
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.code = code

    def authorize_params(self):
        if self.response_type != 'code':
            raise BandAPIException('Invalid response_type')

        return urllib.parse.urlencode({'response_type': self.response_type,
                                       'client_id': self.client_id,
                                       'redirect_uri': self.redirect_uri})

    def token_params(self):
        if self.grant_type != 'authorization_code':
            raise BandAPIException('Invalid grant_type')

        return urllib.parse.urlencode({
            'code': self.code,
            'grant_type': self.grant_type
        })
