import requests
import webbrowser
import json
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qsl, urlparse
from urllib.parse import urlencode
from requests.auth import HTTPBasicAuth
from .band_data import BandAuthorize, Band, response_parse, Profile
import keyring

from .band_exception import BandAPIException


class WebRequestHandler(BaseHTTPRequestHandler):
    def url(self):
        return urlparse(self.path)
    
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        url_query = dict(parse_qsl(self.url().query))
        keyring.set_password('OPENBAND',
                             'authorization_code',
                             url_query['code'])


class NaverBand:
    def __init__(self, client_id, client_secret) -> None:
        self.keyring_name = 'OPENBAND'
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = 'http://localhost:8000'
        self.band_base_url = 'https://openapi.band.us'
        self.auth_base_url = 'https://auth.band.us'

    @property
    def access_token(self):
        return keyring.get_password("OPENBAND", 'access_token')

    def set_access_token(self):
        if not self.access_token:
            req_data = BandAuthorize(client_id=self.client_id,
                                     client_secret=self.client_secret,
                                     response_type='code',
                                     grant_type='authorization_code')
            req_params = req_data.authorize_params()

            auth_url = f'{self.auth_base_url}/oauth2/authorize?{req_params}'

            webbrowser.open(auth_url)
            one_time_server = HTTPServer(("0.0.0.0", 8000), WebRequestHandler)
            one_time_server.handle_request()

            # Request an access token from auth.band.us
            req_params = req_data.token_params()
            access_token_url = f'{self.auth_base_url}/oauth2/token?{req_params}'

            auth = HTTPBasicAuth(self.client_id, self.client_secret)
            req = requests.get(access_token_url, auth=auth)
            if req.status_code != 200:
                raise BandAPIException('400 Bad Request. For more information, '
                                       'see https://developers.band.us/develop'
                                       '/guide/api'
                                       '/get_authorization_code_from_user')

            res_json = response_parse(req)

            keyring.set_password(self.keyring_name,
                                 'access_token',
                                 res_json.get('access_token'))

    def profile(self):
        return Profile().request()

    def get_bands(self):
        params = {'access_token': self.access_token}

        res = requests.get(f'{self.band_base_url}/v2.1/bands', params=params)
        res_json = response_parse(res)

        band_list = res_json.get('result_data').get('bands', [])
        return tuple(map(lambda x: Band(
            x['name'], x['band_key'], x['cover'], x['member_count']), band_list))

    def writ_post(self, band_key, content, do_push=False):
        params = {'access_token': self.access_token,
                  'band_key': band_key,
                  'content': content,
                  'do_push': do_push}

        res = requests.post(f'{self.band_base_url}/v2.2/band/post/create', params=params)
        res_json = json.loads(res.content)
        if res_json['result_code'] == 1:
            return res_json.get('result_data').get('bands', [])
        else:
            print(res_json)
            raise BandAPIException('The request failed.')
