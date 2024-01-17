import requests
import webbrowser
import json
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qsl, urlparse
from urllib.parse import urlencode
from requests.auth import HTTPBasicAuth


class BandAPIHTTPServer(HTTPServer):
    def save_authorization_code(self, data):
        self.__authorization_code = data
    
    def get_authorization_code(self):
        return self.__authorization_code


class WebRequestHandler(BaseHTTPRequestHandler):
    def url(self):
        return urlparse(self.path)
    
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        url_query = dict(parse_qsl(self.url().query))
        # self.wfile.write(b"111")
        self.server.save_authorization_code(url_query['code'])


class BandAPIException(Exception):
    def __init__(self, message):
        super(BandAPIException, self).__init__(message)


class NaverBand:
    def __init__(self, client_id, client_secret, redirect_uri) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.band_base_url = 'https://openapi.band.us'
    
    def auth_url_make(self, auth_type, req_type):
        req_type_query = ''
        if req_type == 'response_type':
            req_type_query = 'response_type=code'
        elif req_type == 'grant_type':
            req_type_query = 'grant_type=authorization_code'
        
        return f'https://auth.band.us/oauth2/{auth_type}?{req_type_query}'
    
    def set_access_token(self):
        auth_url = self.auth_url_make('authorize', 'response_type')
        authorize_code_url = ('{auth_url}'
                              '&client_id={client_id}'
                              '&redirect_uri={redirect_uri}')
        
        webbrowser.open(authorize_code_url.format(
            auth_url=auth_url,
            client_id=self.client_id,
            redirect_uri=self.redirect_uri))
        one_time_server = BandAPIHTTPServer(("0.0.0.0", 8000), WebRequestHandler)
        one_time_server.handle_request()
        authorization_code = one_time_server.get_authorization_code()

        # Request an access token from auth.band.us
        auth_url = self.auth_url_make('token', 'grant_type')
        access_token_url = f'{auth_url}&code={authorization_code}'

        auth = HTTPBasicAuth(self.client_id, self.client_secret)
        req = requests.get(access_token_url, auth=auth)
        res_json = json.loads(req.content)
        self.access_token = res_json.get('access_token')

    def profile(self, band_key=None):
        params = {'access_token': self.access_token}
        if band_key:
            params['band_key'] = band_key

        res = requests.get(f'{self.band_base_url}/v2/profile', params=params)
        res_json = json.loads(res.content)
        if res_json['result_code'] == 1:
            return res_json.get('result_data')
        else:
            raise BandAPIException('The request failed.')

    def get_bands(self):
        params = {'access_token': self.access_token}

        res = requests.get(f'{self.band_base_url}/v2.1/bands', params=params)
        res_json = json.loads(res.content)
        if res_json['result_code'] == 1:
            return res_json.get('result_data').get('bands', [])
        else:
            raise BandAPIException('The request failed.')

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
