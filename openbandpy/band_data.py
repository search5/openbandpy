import json
import locale
import urllib.parse
from datetime import datetime
from functools import cached_property

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
        json_obj = json.loads(response.content)
        return json_obj
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


class BandWrite:
    def __init__(self, content, do_push):
        self.content = content
        self.do_push = do_push

    def params(self):
        return dict(content=self.content, do_push=self.do_push)


class BandComment:
    def __init__(self, band=None, **data):
        self.band_base_url = 'https://openapi.band.us'
        self.band = band
        self.body = data.get('body')
        if 'author' in data:
            self.author = BandAuthor(**data.get('author'))
        if 'created_at' in data:
            self.created_at = timestamptodatetime(data['created_at'])
        self.band_key = data.get('band_key')
        self.post_key = data.get('post_key')
        self.comment_key = data.get('comment_key')
        self.content = data.get('content')
        self.emotion_count = data.get('emotion_count')
        self.is_audio_included = data.get('is_audio_included')
        if data.get('photo'):
            self.photo = BandCommentPhoto(**data.get('photo'))

    def __repr__(self):
        content = self.body or self.content
        return f"<BandComment {content} {self.created_at}>"

    def __getitem__(self, item):
        return getattr(self, item)

    @property
    def access_token(self):
        return keyring.get_password("OPENBAND",
                                    'access_token')

    def params(self):
        return dict(body=self.body)

    def delete(self):
        if self.author.user_key != self.band.me_profile['user_key']:
            # If the user you are approaching is not the same as
            # the user who wrote the post, look at the band's permissions.
            # In this case, the leader may have the post/reply
            # delete permission, so we add the logic below.
            if 'contents_deletion' not in self.band.permissions:
                raise BandAPIException(
                    "The band doesn't have delete permissions.")

        params = {'access_token': self.access_token,
                  'band_key': self.band_key,
                  'post_key': self.post_key,
                  'comment_key': self.comment_key}

        res = requests.post(f'{self.band_base_url}/v2/band/post/comment/remove',
                            params=params)
        parse_result = response_parse(res)
        result_data = parse_result.get('result_data', {})

        return (parse_result.get('result_code'),
                result_data.get('message', 'Error!'))


class Band:
    def __init__(self, name, band_key, cover, member_count):
        self.name = name
        self.band_key = band_key
        self.cover = cover
        self.member_count = member_count
        self.band_base_url = 'https://openapi.band.us'

    def __repr__(self):
        return f"'{self.name}'"

    def __getitem__(self, name):
        return getattr(self, name)

    @property
    def access_token(self):
        return keyring.get_password("OPENBAND",
                                    'access_token')

    @property
    def me_profile(self):
        return Profile(self.band_key).request()

    def posts(self, next_params=None):
        return Post(band_key=self.band_key, next_params=next_params,
                    band=self).list()

    def write(self, data: BandWrite):
        if 'posting' not in self.permissions:
            raise BandAPIException("The band doesn't have write permissions.")

        params = data.params()
        params.update(access_token=self.access_token, band_key=self.band_key)
        res = requests.post(f'{self.band_base_url}/v2.2/band/post/create',
                            params=params)
        data = response_parse(res).get('result_data', {})

        return dict(post_key=data['post_key'])

    @cached_property
    def permissions(self):
        params = dict(access_token=self.access_token, band_key=self.band_key,
                      permissions='posting,commenting,contents_deletion')
        res = requests.get(f'{self.band_base_url}/v2/band/permissions',
                            params=params)
        data = response_parse(res).get('result_data', {})

        return data['permissions']

    def albums(self):
        # TODO
        """[GET] https://openapi.band.us/v2/band/albums
        Parameters
        Name	Type	Mandatory	Description
        access_token	string	Y	사용자 인증 접근 토큰
        band_key	string	Y	밴드 식별자"""
        pass

    def photos(self):
        # TODO
        pass


class Profile:
    def __init__(self, band_key=None):
        self.band_key = band_key
        self.band_base_url = 'https://openapi.band.us'
        self.profile_data = {}

    @property
    def access_token(self):
        return keyring.get_password("OPENBAND",
                                    'access_token')

    def request(self):
        params = {'access_token': self.access_token}
        if self.band_key:
            params['band_key'] = self.band_key

        res = requests.get(f'{self.band_base_url}/v2/profile',
                           params=params)
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
        return (f"{user_name} / Join "
                f"{timestamptodatetime(self.profile_data['member_joined_at'])}")

    def __dir__(self):
        keys = ['is_app_member', 'request', 'user_key', 'profile_image_url',
                'name', 'member_joined_at', 'message_allowed']

        return keys


class Post:
    def __init__(self, *, band_key=None, next_params=None, band=None, **post_data):
        self.band_key = band_key or post_data['band_key']
        self.band = band
        self.band_base_url = 'https://openapi.band.us'
        self.post_data = {}
        self.next_params = next_params
        self.content = post_data.get('content')
        self.author = post_data.get('author')
        self.post_key = post_data.get('post_key')
        self.comment_count = post_data.get('comment_count')
        self.created_at = post_data.get('created_at')
        self.photos = post_data.get('photos')
        self.emotion_count = post_data.get('emotion_count')
        self.latest_comments = post_data.get('latest_comments')
        self.post_read_count = post_data.get('post_read_count', -1)

    @property
    def access_token(self):
        return keyring.get_password("OPENBAND",
                                    'access_token')

    def list(self):
        params = {'access_token': self.access_token,
                  'band_key': self.band_key,
                  'locale': "_".join(locale.getlocale())}
        if self.next_params:
            params.update(self.next_params)

        res = requests.get(f'{self.band_base_url}/v2/band/posts',
                           params=params)
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
            band_key=x['band_key'],
            band=self.band), post_list)), paging['next_params']

    def __repr__(self):
        return f'<Band: {self.content}>'

    def get(self):
        params = {'access_token': self.access_token,
                  'band_key': self.band_key,
                  'post_key': self.post_key}

        res = requests.get(f'{self.band_base_url}/v2/band/post',
                           params=params)
        res_json = response_parse(res).get('result_data', {}).get('post', {})

        return Post(
            content=res_json['content'],
            author=BandAuthor(**res_json['author']),
            post_key=res_json['post_key'],
            created_at=timestamptodatetime(res_json['created_at']),
            comment_count=res_json['comment_count'],
            photos=makeobjectlist(BandPhoto, res_json['photos']),
            emotion_count=res_json['emotion_count'],
            latest_comments=makeobjectlist(BandComment,
                                           res_json.get('latest_comments', [])),
            band_key=res_json.get('band_key'),
            post_read_count=res_json['post_read_count'],
            band=self.band
        )

    def __getitem__(self, item):
        return getattr(self, item)

    def delete(self):
        if self.author.user_key != self.band.me_profile['user_key']:
            # If the user you are approaching is not the same as
            # the user who wrote the post, look at the band's permissions.
            # In this case, the leader may have the post/reply
            # delete permission, so we add the logic below.
            if 'contents_deletion' not in self.band.permissions:
                raise BandAPIException(
                    "The band doesn't have delete permissions.")

        params = {'access_token': self.access_token,
                  'band_key': self.band_key,
                  'post_key': self.post_key}

        res = requests.post(f'{self.band_base_url}/v2/band/post/remove',
                            params=params)
        parse_result = response_parse(res)
        result_data = parse_result.get('result_data', {})

        return (parse_result.get('result_code'),
                result_data.get('message', 'Error!'))

    def comments(self, sort='+', next_params=None):
        params = {'access_token': self.access_token,
                  'band_key': self.band_key,
                  'post_key': self.post_key,
                  'sort': f'{sort}created_at'}

        if next_params:
            params.update(next_params)

        res = requests.get(f'{self.band_base_url}/v2/band/post/comments',
                           params=params)

        res_json = response_parse(res).get('result_data', {})

        comment_list = res_json.get('items', [])
        paging = res_json.get('paging')

        return (tuple(map(lambda x: BandComment(
            band=self.band, **x), comment_list)),
                paging['next_params'])

    def write_comment(self, data: BandComment):
        if 'commenting' not in self.band.permissions:
            raise BandAPIException("You don't have permission to comment on the band")

        params = data.params()
        params.update(access_token=self.access_token,
                      band_key=self.band_key,
                      post_key=self.post_key)
        req_url = f'{self.band_base_url}/v2/band/post/comment/create'
        res = requests.post(req_url, params=params)
        data = response_parse(res).get('result_data', {})

        return dict(message=data['message'])


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
        return self.role == 'leader' or self.role == 'coleader'

    def __repr__(self):
        return f'<Author {self.name} / {self.description} / {self.role}>'

    def __getitem__(self, item):
        return getattr(self, item)


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
        return (f'<Photo {self.url} / {self.width}x{self.height} '
                f'/ {self.created_at}>')

    def __getitem__(self, item):
        return getattr(self, item)


class BandCommentPhoto:
    def __init__(self, **data):
        self.url = data.get('url')
        self.height = data.get('height')
        self.width = data.get('width')

    def __repr__(self):
        return (f'<CommentPhoto {self.url} / '
                f'{self.width}x{self.height}>')

    def __getitem__(self, item):
        return getattr(self, item)


class BandPhotoAlbum:
    def __init__(self, **data):
        self.photo_album_key = data['photo_album_key']
        self.name = data['name']
        self.photo_count = data['photo_count']
        self.created_at = timestamptodatetime(data['created_at'])
        self.author = BandAuthor(**data['author'])

    def __repr__(self):
        return (f'<BandPhotoAlbum {self.name} / {self.photo_count} / '
                f'{self.created_at}>')

    def __getitem__(self, item):
        return getattr(self, item)
