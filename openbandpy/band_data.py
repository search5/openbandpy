import json
import locale
import urllib.parse
from datetime import datetime

import keyring
import requests

from openbandpy.band_exception import BandAPIException


def timestamptodatetime(datestr):
    if not datestr:
        return None
    exclude_microseconds = str(datestr)[:-3]
    return datetime.fromtimestamp(int(exclude_microseconds))


def response_parse(response):
    content_type = response.headers['Content-Type']

    if response.status_code != 200:
        data = json.loads(response.content) \
            if content_type.startswith('application/json') else "{}"
        result_data = data.get('result_data', {})
        result_message = result_data.get('message')
        error_detail = result_data.get('detail', {})
        detail_error = error_detail.get('error', '')
        detail_description = error_detail.get('description', '')
        result_code = data.get('result_code', -1)

        raise BandAPIException(f'{result_code}, {result_message}'
                               f'({detail_error})\n{detail_description}')

    if content_type.startswith('application/json'):
        return json.loads(response.content)
    else:
        raise BandAPIException('Invalid content type')


class BandAuthorize:
    def __init__(self, *, client_id=None, client_secret=None,
                 redirect_uri=None, response_type=None, grant_type=None):
        self.response_type = response_type
        self.grant_type = grant_type
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = 'http://localhost:8000/'
        self.keyring_name = 'OPENBAND'

    def authorize_params(self):
        if self.response_type != 'code':
            raise BandAPIException('Invalid response_type')

        return urllib.parse.urlencode({'response_type': self.response_type,
                                       'client_id': self.client_id,
                                       'redirect_uri': self.redirect_uri})

    def token_params(self):
        if self.grant_type != 'authorization_code':
            raise BandAPIException('Invalid grant_type')

        authorization_code = keyring.get_password(self.keyring_name,
                                                  'authorization_code')

        return urllib.parse.urlencode({
            'code': authorization_code,
            'grant_type': self.grant_type
        })


class Band:
    def __init__(self, name, band_key, cover, member_count):
        self.name = name
        self.band_key = band_key
        self.cover = cover
        self.member_count = member_count

    def __repr__(self):
        return f"'{self.name}'"

    def __getattr__(self, name):
        return getattr(self, name)

    @property
    def me_profile(self):
        return Profile(self.band_key).request()

    def posts(self, next_params=None):
        return Post(band_key=self.band_key, next_params=next_params).list()


class Profile:
    def __init__(self, band_key=None):
        self.band_key = band_key
        self.band_base_url = 'https://openapi.band.us'
        self.profile_data = {}

    @property
    def access_token(self):
        return keyring.get_password("OPENBAND", 'access_token')

    def request(self):
        params = {'access_token': self.access_token}
        if self.band_key:
            params['band_key'] = self.band_key

        res = requests.get(f'{self.band_base_url}/v2/profile', params=params)
        self.profile_data = response_parse(res).get('result_data', {})
        return self

    def __getitem__(self, item):
        if (item in self.profile_data) and item == 'member_joined_at':
            return timestamptodatetime(item['member_joined_at'])
        return self.profile_data.get(item)

    def __repr__(self):
        user_name = self.profile_data['name']
        if 'member_joined_at' not in self.profile_data:
            return user_name
        return f"{user_name} / Join {timestamptodatetime(self.profile_data['member_joined_at'])}"

    def __dir__(self):
        keys = ['is_app_member', 'request', 'user_key', 'profile_image_url',
                'name', 'member_joined_at', 'message_allowed']

        return keys


class Post:
    def __init__(self, *, band_key=None, next_params=None, **post_data):
        self.band_key = band_key or post_data['band_key']
        self.band_base_url = 'https://openapi.band.us'
        self.post_data = {}
        self.next_params = next_params
        self.content = post_data.get('content')
        self.author = post_data.get('author')
        self.post_key = post_data.get('post_key')
        self.comment_count = post_data.get('comment_count')
        self.created_at = timestamptodatetime(post_data.get('created_at'))
        self.photos = post_data.get('photos')
        self.emotion_count = post_data.get('emotion_count')
        self.latest_comments = post_data.get('latest_comments')
        self.post_read_count = post_data.get('post_read_count', -1)

    @property
    def access_token(self):
        return keyring.get_password("OPENBAND", 'access_token')

    def list(self):
        params = {'access_token': self.access_token,
                  'band_key': self.band_key,
                  'locale': "_".join(locale.getlocale())}
        if self.next_params:
            params.update(self.next_params)

        res = requests.get(f'{self.band_base_url}/v2/band/posts', params=params)
        res_json = response_parse(res).get('result_data', {})

        post_list = res_json.get('items', [])
        paging = res_json.get('paging')

        return tuple(map(lambda x: Post(
            content=x['content'],
            author=BandAuthor(**x['author']),
            post_key=x['post_key'],
            created_at=timestamptodatetime(x['created_at']),
            comment_count=x['comment_count'],
            photos=makeobjectlist(BandPhoto, x['photos']),
            emotion_count=x['emotion_count'],
            latest_comments=x.get('latest_comments', []),
            band_key=x['band_key']), post_list)), paging['next_params']

    def __repr__(self):
        return f'<Band: {self.content}>'

    def get(self):
        params = {'access_token': self.access_token,
                  'band_key': self.band_key,
                  'post_key': self.post_key}

        res = requests.get(f'{self.band_base_url}/v2/band/post', params=params)
        res_json = response_parse(res).get('result_data', {})

        return Post(
            content=res_json['content'],
            author=BandAuthor(**res_json['author']),
            post_key=res_json['post_key'],
            created_at=timestamptodatetime(res_json['created_at']),
            comment_count=res_json['comment_count'],
            photos=makeobjectlist(BandPhoto, res_json['photos']),
            emotion_count=res_json['emotion_count'],
            latest_comments=makeobjectlist(BandComment, res_json.get('latest_comments', [])),
            band_key=res_json.get['band_key'],
            post_read_count=res_json['post_read_count']
        )

    def __getitem__(self, item):
        return getattr(self, item)


def makeobjectlist(klass, data):
    return tuple(map(lambda x: klass(**x), data))


class BandAuthor:
    def __init__(self, **data):
        self.name = data['name']
        self.description = data['description']
        self.role = data['role']
        self.profile_image_url = data['profile_image_url']
        self.user_key = data['user_key']

    @property
    def isleader(self):
        return self.role == 'leader'

    def __repr__(self):
        return f'<Author {self.name} / {self.description} / {self.role}>'


class BandPhoto:
    def __init__(self, **data):
        self.height = data['height']
        self.width = data['width']
        self.created_at = timestamptodatetime(data['created_at'])
        self.url = data['url']
        self.author = BandAuthor(**data['author'])
        self.photo_album_key = data['photo_album_key']
        self.photo_key = data['photo_key']
        self.comment_count = data['comment_count']
        self.emotion_count = data['emotion_count']
        self.is_video_thumbnail = data['is_video_thumbnail']

    def __repr__(self):
        return f'<Photo {self.url} / {self.width}x{self.height} / {self.created_at}>'


class BandComment:
    def __init__(self, **data):
        self.body = data.get('body')
        self.author = BandAuthor(**data['author'])
        self.created_at = timestamptodatetime(data['created_at'])
