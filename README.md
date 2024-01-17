```python
from pyband.band import NaverBand


if __name__ == "__main__":
    band = NaverBand(client_id, client_secret, 'http://localhost:8000/redirect')
    band.set_access_token()
    band_user_profile = band.profile()
    print(band_user_profile)
    bands= band.get_bands()
    가입스 = filter(lambda x: x['name'] == '가입스', bands)
    subscribe_key = next(가입스, {}).get('band_key')
    band_subscribe_user_profile = band.profile(subscribe_key)
    print(band_subscribe_user_profile)
    band.writ_post(subscribe_key, 'API 테스트')
```