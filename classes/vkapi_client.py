import time
from http.client import responses
from urllib.parse import urlencode
import requests
from classes.vkapi import ApiCity, ApiUser, ApiPhoto, ApiCountry
from classes.vkapi import log, prepare_params
from classes.vkapi_cons import BASE_URL


class ApiResult:

    def __init__(self, json_object=None, success=False,
                 message='Not initialised', raw_content=None, headers=None):
        self.json_object = json_object
        self.success = success
        self.message = message
        self.raw_content = raw_content
        self.headers = headers


class VkApiClient:
    API_BASE_URL = ''

    def __init__(self, token, app_id, user_id=None, version='5.131',
                 debug_mode=False, base_url=None):
        super().__init__()
        self.API_BASE_URL = base_url if base_url else BASE_URL
        self.debug_mode = debug_mode
        self.__vksite = 'https://vk.com/'
        self.token = token
        self.app_id = app_id
        self.__version = version
        self.__required_user_fields = ['sex', 'bdate', 'domain', 'country',
                                       'city', 'last_seen', 'home_town']
        self.__headers = {'User-Agent': 'Mem'}
        self.__params = {'access_token': self.token, 'v': self.__version}
        self.__img_types = {'s': 1, 'm': 2, 'x': 3, 'o': 4, 'p': 5,
                            'q': 6, 'r': 7, 'y': 8, 'z': 9, 'w': 10}
        self.request_delay = 0.33
        self.__initialized = True
        user = self.__get_users(user_ids=user_id)
        is_deactivated = False
        if user.success:
            is_deactivated = user.json_object[0].get('deactivated', False)
        if user.success and not is_deactivated:
            self.__initialized = True
            self.__user_id = str(user.json_object[0]['id'])
            self.__first_name = user.json_object[0]['first_name']
            self.__last_name = user.json_object[0]['last_name']
            self.__domain = user.json_object[0]['domain']
            self.__status = f'{type(self).__name__} initialised with user: ' \
                            f'{self.__first_name} {self.__last_name} ' \
                            f'(#{self.__user_id})'
        else:
            self.__initialized = False
            self.__user_id = None
            self.__first_name = None
            self.__last_name = None
            self.__domain = None
            if is_deactivated:
                user.message = 'User is deactivated'
            self.__status = f'{type(self).__name__} init failed: ' +\
                            user.message
            self.__status += f'\nPls check a personal token via this URL:\n' \
                             f'{self.get_auth_link(self.app_id, "offline,photos,status,groups")}'
        log(self.__status, debug_mode)

    @property
    def is_initialized(self):
        return self.__initialized

    @property
    def get_id(self):
        return self.__user_id

    @property
    def get_fname(self):
        return self.__first_name

    @property
    def get_lname(self):
        return self.__last_name

    @property
    def get_domain(self):
        return self.__domain

    @property
    def get_status(self):
        return self.__status

    @staticmethod
    def get_auth_link(app_id, scope='status'):
        oauth_api_base_url = 'https://oauth.vk.com/authorize'
        redirect_uri = 'https://oauth.vk.com/blank.html'
        oauth_params = {
            'redirect_uri': redirect_uri,
            'scope': scope,
            'response_type': 'token',
            'client_id': app_id
        }
        return '?'.join([oauth_api_base_url, urlencode(oauth_params)])

    def __get_countries(self, count=1000, offset=0, code=None, need_all=None):
        params = {'count': prepare_params(count),
                  'offset': prepare_params(offset)}
        if code:
            params.update({'code': code})
        if need_all:
            params.update({'need_all': '1'})
        response = requests.get(self.API_BASE_URL + 'database.getCountries',
                                params={**self.__params, **params},
                                headers=self.__headers)
        return get_response_content(response, path='response')

    def get_countries(self, code: str = None) -> list[ApiCountry]:
        result = []
        if not self.__initialized:
            log(f'Error in get_countries: {type(self).__name__} '
                f'not initialized', self.debug_mode)
            return result
        offset = 0
        count = 1000
        log(f'\nRequesting max {count} countries at once from VK...',
            self.debug_mode)
        while True:
            if code:
                countries = self.__get_countries(count=count,
                                                 offset=offset,
                                                 code=code)
            else:
                countries = self.__get_countries(count=count,
                                                 offset=offset,
                                                 need_all=True)
            if not countries.success:
                log(f'Loading countries failed: {countries.message}',
                    self.debug_mode)
                break
            items_count = len(countries.json_object['items'])
            log(f'Loaded {items_count} countries', self.debug_mode)
            if items_count == 0:
                break
            result += countries.json_object['items']
            if items_count < count:
                break
            offset += count
            time.sleep(self.request_delay)
        result = [ApiCountry(dict(row)) for row in result]
        return result

    def __search_cities(self, count=1000, offset=0, country_id=None,
                        region_id=None, need_all=False, q=None):
        params = {'count': prepare_params(count),
                  'offset': prepare_params(offset)}
        if country_id:
            params.update({'country_id': prepare_params(country_id)})
        if region_id:
            params.update({'region_id': prepare_params(region_id)})
        if need_all:
            params.update({'need_all': '1'})
        if q:
            params.update({'q': q})
        response = requests.get(self.API_BASE_URL + 'database.getCities',
                                params={**self.__params, **params},
                                headers=self.__headers)
        return get_response_content(response, path='response')

    def search_cities(self, country_id=None, city_name=None):
        result = []
        if not self.__initialized:
            log(f'Error in search_cities: '
                f'{type(self).__name__} not initialized', self.debug_mode)
            return result
        offset = 0
        count = 1000
        log(f'\nSearching city name: "{city_name}" at country {country_id} '
            f'...', self.debug_mode)
        while True:
            if city_name:
                cities = self.__search_cities(count=count,
                                              offset=offset,
                                              country_id=country_id,
                                              q=city_name)
            else:
                cities = self.__search_cities(count=count,
                                              offset=offset,
                                              country_id=country_id,
                                              need_all=True)
            if not cities.success:
                log(f'Loading cities failed: {cities.message}',
                    self.debug_mode)
                break
            items_count = len(cities.json_object['items'])
            log(f'Loaded {items_count} cities', self.debug_mode)
            if items_count == 0:
                break
            result += cities.json_object['items']
            if items_count < count:
                break
            offset += count
            time.sleep(self.request_delay)
        result = [ApiCity(dict(row)) for row in result]
        return result

    def __search_users(self, count=1000, offset=0, city_id=None, sex_id=None,
                       love_status_id=None, age_from=None, age_to=None, q=None,
                       has_photo=True, hometown=None, sort=True, fields=None):
        params = {'count': prepare_params(count),
                  'offset': prepare_params(offset), 'online': '0',
                  'fields': prepare_params(fields,
                                           self.__required_user_fields)}
        if city_id:
            params.update({'city': prepare_params(city_id)})
        if sex_id:
            params.update({'sex': prepare_params(sex_id)})
        if love_status_id:
            params.update({'status': prepare_params(love_status_id)})
        if age_from:
            params.update({'age_from': prepare_params(age_from)})
        if age_to:
            params.update({'age_to': prepare_params(age_to)})
        if q:
            params.update({'q': q})
        if hometown:
            params.update({'hometown': hometown})
        if has_photo:
            params.update({'has_photo': '1'})
        if sort:
            params.update({'sort': '1'})
        response = requests.get(self.API_BASE_URL + 'users.search',
                                params={**self.__params, **params},
                                headers=self.__headers)
        return get_response_content(response, path='response')

    def search_users(self, city_id=None, sex_id=None, love_status_id=None,
                     age_from=None, age_to=None, q=None, has_photo=True,
                     hometown=None, sort=True):
        result = []
        if not self.__initialized:
            log(f'Error in search_users: {type(self).__name__} not '
                f'initialized', self.debug_mode)
            return result
        offset = 0
        count = 1000
        log(f'\nSearching users...', self.debug_mode)
        while True:
            users = self.__search_users(count=count, offset=offset,
                                        city_id=city_id, sex_id=sex_id,
                                        love_status_id=love_status_id,
                                        age_from=age_from, age_to=age_to, q=q,
                                        has_photo=has_photo,
                                        hometown=hometown,
                                        sort=sort)
            if not users.success:
                log(f'Loading users failed: {users.message}', self.debug_mode)
                break
            items_count = len(users.json_object['items'])
            log(f'Loaded {items_count} users', self.debug_mode)
            if items_count == 0:
                break
            result += users.json_object['items']
            if items_count < count:
                break
            offset += count
            time.sleep(self.request_delay)
        result = [ApiUser(dict(row)) for row in result]
        return result

    def __get_user_photos(self, owner_id, count=1000, offset=0,
                          album_id='profile', rev=True, extended=True,
                          photo_sizes=True):
        params = {'count': prepare_params(count),
                  'offset': prepare_params(offset)}
        params.update({'owner_id': prepare_params(owner_id)})
        params.update({'album_id': prepare_params(album_id)})
        if rev:
            params.update({'rev': '1'})
        if extended:
            params.update({'extended': '1'})
        if photo_sizes:
            params.update({'photo_sizes': '1'})
        response = requests.get(self.API_BASE_URL + 'photos.get',
                                params={**self.__params, **params},
                                headers=self.__headers)
        return get_response_content(response, path='response')

    def get_user_photos(self, owner_id=None, album_id='profile', rev=True,
                        extended=True, photo_sizes=True, sort_by='popularity',
                        needed_qty=3):
        result = []
        if not self.__initialized:
            log(f'Error in get_user_photos: {type(self).__name__} '
                f'not initialized', self.debug_mode)
            return result
        owner_id = owner_id if owner_id else self.__user_id
        offset = 0
        count = 1000
        log(f'Getting user {owner_id} photos from {album_id}...',
            self.debug_mode)
        while True:
            photos = self.__get_user_photos(count=count, offset=offset,
                                            owner_id=owner_id,
                                            album_id=album_id, rev=rev,
                                            extended=extended,
                                            photo_sizes=photo_sizes)
            if not photos.success:
                log(f'Loading photos failed: {photos.message}',
                    self.debug_mode)
                break
            items_count = len(photos.json_object['items'])
            log(f'Loaded {items_count} photos more...', self.debug_mode)
            if items_count == 0:
                break
            result += photos.json_object['items']
            if items_count < count:
                break
            offset += count
            time.sleep(self.request_delay)
        log(f'Loaded totally {len(result)} photos', self.debug_mode)
        result = self.__process_photos(result, sort_by=sort_by,
                                       needed_qty=needed_qty)
        result = [ApiPhoto(row) for row in result]
        return result

    def __process_photos(self, photos, sort_by='popularity', needed_qty=3):
        result = []
        if sort_by == 'popularity':
            photos.sort(key=lambda x: x['likes']['count'] + x['comments']
                        ['count'] + x['reposts']['count'] * 3, reverse=True)
        else:
            photos.sort(key=lambda x: x['date'], reverse=True)
        needed_qty = needed_qty if needed_qty > 0 else len(photos)
        for photo in photos[:needed_qty]:
            img_url = ''
            img_url_fallback = ''
            max_type = -1
            max_res = -1
            for size in photo['sizes']:
                res = size['height'] * size['width']
                if max_res < res:
                    max_res = res
                    img_url = size['url']
                size_type = self.__img_types.get(size['type'], 0)
                if max_type < size_type:
                    max_type = size_type
                    img_url_fallback = size['url']
            if max_res == 0:
                img_url = img_url_fallback
            likes_count = str(photo['likes']['count'])
            comments_count = str(photo['comments']['count'])
            reposts_count = str(photo['reposts']['count'])
            result.append({'likes_count': likes_count,
                           'comments_count': comments_count,
                           'reposts_count': reposts_count,
                           'url': img_url, 'owner_id': photo['owner_id'],
                           'id': photo['id']})
        return result

    def __get_users(self, user_ids=None, fields=None):
        params = {}
        params.update({'fields': {prepare_params
                                  (fields, self.__required_user_fields)}})
        if user_ids:
            params.update({'user_ids': prepare_params(user_ids)})
        try:
            response = requests.get(self.API_BASE_URL + 'users.get',
                                    params={**self.__params, **params},
                                    headers=self.__headers)
        except requests.exceptions.ConnectionError:
            response = requests.Response()
        return get_response_content(response, path='response')

    def get_users(self, user_ids=None, fields=None):
        result = []
        if not self.__initialized:
            log(f'Error in get_users: {type(self).__name__} not initialized',
                self.debug_mode)
            return result
        log(f'Getting users...', self.debug_mode)
        users = self.__get_users(user_ids=user_ids, fields=fields)
        if not users.success:
            log(f'Getting users failed: {users.message}', self.debug_mode)
            return result
        items_count = len(users.json_object)
        log(f'Got {items_count} users', self.debug_mode)
        result += users.json_object
        result = [ApiUser(dict(row)) for row in result]
        return result


def get_response_content(response: requests.Response, path='', sep=',',
                         error_code='error_code', error_msg='error_msg',
                         no_decode=False):
    result = ApiResult(None, False, '', None, response.headers)
    if not (200 <= response.status_code < 300):
        result.message = f'Request error: {str(response.status_code)} ' \
                         f'({responses[response.status_code]})'
        return result
    if (path == '' or path is None) and len(response.content) == 0:
        result.success = True
        result.message = 'Response body is empty'
        return result
    result.raw_content = response.content
    if no_decode:
        result.success = True
        return result
    try:
        result.json_object = response.json()
    except ValueError:
        result.json_object = None
        result.message = 'JSON decode error'
        return result
    error = result.json_object.get('error')
    if error:
        result.message = f'Error {error.get(error_code)}: ' \
                         f'{error.get(error_msg)}'
        result.json_object = None
        return result
    for key in path.split(sep):
        if key == '':
            continue
        if type(result.json_object) is list:
            result.success = True
            return result
        else:
            found = result.json_object.get(key.strip())
        if found is None:
            result.json_object = None
            result.message = 'Object not found'
            return result
        result.json_object = found
    result.success = True
    return result


def download_file(self, url, folder='photos', filename=None):
    response = requests.get(url, allow_redirects=True, headers=self._headers)
    response = get_response_content(response, no_decode=True)
    if response.success:
        filename = filename if filename else 'image.jpg'
        open(f'{folder}/{filename}', 'wb').write(response.raw_content)
        return True
    return False
