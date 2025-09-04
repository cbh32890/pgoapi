"""
pgoapi - Pokemon Go API
Copyright (c) 2016 tjado <https://github.com/tejado>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
OR OTHER DEALINGS IN THE SOFTWARE.

Author: tjado <https://github.com/tejado>
"""

from __future__ import absolute_import
from future.standard_library import install_aliases
install_aliases()

import requests
from urllib.parse import parse_qs, urlsplit
from six import string_types

from pgoapi.auth import Auth
from pgoapi.utilities import get_time
from pgoapi.exceptions import AuthException, AuthTimeoutException, InvalidCredentialsException

from requests.exceptions import RequestException, Timeout, TooManyRedirects

class AuthPtc(Auth):
    PTC_LOGIN_URL1 = 'https://access.pokemon.com/oauth2/auth?client_id=pokemon-go&redirect_uri=https://www.pokemongolive.com/dl?app=pokemongo%26dl_action=OPEN_LOGIN&response_type=code&state=ZrQ4gWPIi7V3GTiHYw7s6xLd&scope=openid+offline+email+dob+pokemon_go+member_id+username'
    PTC_LOGIN_URL2 = 'https://sso.pokemon.com/sso/login?service=http%3A%2F%2Fsso.pokemon.com%2Fsso%2Foauth2.0%2FcallbackAuthorize'
    PTC_LOGIN_OAUTH = 'https://sso.pokemon.com/sso/oauth2.0/accessToken'
    PTC_LOGIN_CLIENT_SECRET = 'w8ScCUXJQc6kXKw8FiOhd8Fixzht18Dq3PEVkUCP5ZPxtgyWsbTvWHFLm2wNY0JR'

    def __init__(self, username=None, password=None, user_agent=None, timeout=None):
        Auth.__init__(self)
        self._auth_provider = 'ptc'
        print("I'm in auth_ptc")
        self._session = requests.Session()
        self._session.max_redirects = 50  # Increase redirect limit
        self._session.headers = {
            'User-Agent': user_agent or 'pokemongo/1 CFNetwork/811.4.18 Darwin/16.5.0',
            'Host': 'access.pokemon.com',
            'X-Unity-Version': '5.5.1f1'
        }
        self._username = username
        self._password = password
        self.timeout = timeout or 15

    def set_proxy(self, proxy_config):
        self._session.proxies = proxy_config

    def user_login(self, username=None, password=None, retry=True):
        self._username = username or self._username
        self._password = password or self._password
        if not isinstance(self._username, string_types) or not isinstance(self._password, string_types):
            raise InvalidCredentialsException("Username/password not correctly specified")

        self.log.info('PTC User Login for: {}'.format(self._username))
        self._session.cookies.clear()
        now = get_time()

        try:
            self.log.debug(f"Sending GET to {self.PTC_LOGIN_URL1}")
            r = self._session.get(self.PTC_LOGIN_URL1, timeout=self.timeout, allow_redirects=True)
            self.log.debug(f"GET response: {r.status_code}, {r.text[:100]}...")
        except Timeout:
            raise AuthTimeoutException('Auth GET timed out.')
        except TooManyRedirects as e:
            self.log.error(f"Too many redirects on GET: {e}")
            raise AuthException(f"Too many redirects: {e}")
        except RequestException as e:
            raise AuthException(f"Caught RequestException: {e}")

        try:
            data = r.json()
            data.update({
                '_eventId': 'submit',
                'username': self._username,
                'password': self._password,
            })
        except (ValueError, AttributeError) as e:
            self.log.error(f"Invalid JSON response from GET: {e}")
            raise AuthException(f"Invalid JSON response: {e}")

        try:
            self.log.debug(f"Sending POST to {self.PTC_LOGIN_URL2}")
            r = self._session.post(self.PTC_LOGIN_URL2, data=data, timeout=self.timeout, allow_redirects=False)
            self.log.debug(f"POST response: {r.status_code}, {r.text[:100]}...")
        except Timeout:
            raise AuthTimeoutException('Auth POST timed out.')
        except TooManyRedirects as e:
            self.log.error(f"Too many redirects on POST: {e}")
            raise AuthException(f"Too many redirects: {e}")
        except RequestException as e:
            raise AuthException(f"Caught RequestException: {e}")

        try:
            qs = parse_qs(urlsplit(r.headers['Location'])[3])
            self._refresh_token = qs.get('ticket')[0]
        except Exception as e:
            raise AuthException(f"Could not retrieve token: {e}")

        self._access_token = self._session.cookies.get('CASTGC')
        if self._access_token:
            self._login = True
            self._access_token_expiry = int(now) + 7200
            self.log.info('PTC User Login successful.')
        elif self._refresh_token and retry:
            self.get_access_token()
        else:
            self._login = False
            raise AuthException("Could not retrieve a PTC Access Token")
        return self._login

    def set_refresh_token(self, refresh_token):
        self.log.info('PTC Refresh Token provided by user')
        self._refresh_token = refresh_token

    def get_access_token(self, force_refresh=False):
        token_validity = self.check_access_token()

        if token_validity is True and force_refresh is False:
            self.log.debug('Using cached PTC Access Token')
            return self._access_token
        else:
            if force_refresh:
                self.log.info('Forced request of PTC Access Token!')
            else:
                self.log.info('Request PTC Access Token...')

            data = {
                'client_id': 'mobile-app_pokemon-go',
                'redirect_uri': 'https://www.nianticlabs.com/pokemongo/error',
                'client_secret': self.PTC_LOGIN_CLIENT_SECRET,
                'grant_type': 'refresh_token',
                'code': self._refresh_token,
            }

            try:
                self.log.debug(f"Sending POST to {self.PTC_LOGIN_OAUTH}")
                r = self._session.post(self.PTC_LOGIN_OAUTH, data=data, timeout=self.timeout)
                self.log.debug(f"OAuth response: {r.status_code}, {r.text[:100]}...")
            except Timeout:
                raise AuthTimeoutException('Auth POST timed out.')
            except TooManyRedirects as e:
                self.log.error(f"Too many redirects on OAuth POST: {e}")
                raise AuthException(f"Too many redirects: {e}")
            except RequestException as e:
                raise AuthException(f"Caught RequestException: {e}")

            token_data = parse_qs(r.text)

            access_token = token_data.get('access_token')
            if access_token is not None:
                self._access_token = access_token[0]
                expires = int(token_data.get('expires', [0])[0]) - 3600
                if expires > 0:
                    self._access_token_expiry = expires + get_time()
                else:
                    self._access_token_expiry = 0
                self._login = True
                self.log.info('PTC Access Token successfully retrieved.')
                self.log.debug('PTC Access Token: {}'.format(self._access_token))
            else:
                self._access_token = None
                self._login = False
                if force_refresh:
                    self.log.info('Reauthenticating with refresh token failed, using credentials instead.')
                    return self.user_login(retry=False)
                raise AuthException("Could not retrieve a PTC Access Token")