import requests

from TavernCrier import config
from TavernCrier.redis import rdb


def make_twitch_request(route, method: str, params: dict | str = None, body: dict = None) -> (int, dict | None):
    if not rdb.exists("twitch_access_token"):
        success, expire = refresh_access_token()
        if not success:
            return 401, None

    url = route

    request_method = getattr(requests, method.lower())

    response = request_method(url, params=params, json=body, headers={
        "Client-Id": config.twitch_login['client_id'],
        "Authorization": f"Bearer {rdb.get('twitch_access_token')}"
    })

    if response.status_code == 401:
        success, expire = refresh_access_token()
        if success:
            return make_twitch_request(route, method, params=params, body=body)
        else:
            return 401, response.json()

    return response.status_code, response.json() if len(response.content) != 0 else None


def refresh_access_token(refresh_token=None):
    url = "https://id.twitch.tv/oauth2/token"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    client_id = config.twitch_login['client_id']
    client_secret = config.twitch_login['client_secret']
    grant_type = "refresh_token"

    if not refresh_token:
        refresh_token = config.twitch_login['refresh_token']

    response = requests.post(url, headers=headers, params={'client_id': client_id,
                                                           'client_secret': client_secret,
                                                           'grant_type': grant_type,
                                                           'refresh_token': refresh_token})

    if response.status_code == 200:
        rjson = response.json()

        rdb.set("twitch_access_token", rjson['access_token'], ex=rjson['expires_in'])

        return True, rjson['expires_in']

    return False, None
