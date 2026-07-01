from base64 import b64decode, b64encode
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
from typing import Optional
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

from requests import Session, Response

from modules.broker.ig.ig_exception import *

from ..utils.utils import (
    api_limit_hit,
    parse_response,
    token_invalid,
)

logger = logging.getLogger(__name__)

class IGAction(Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


class IGSession(object):
    def __init__(self, base_url: str, api_key: str, username: str, acc_number: Optional[str] = None, use_rate_limiter: bool = False):
        self.base_url: str = base_url
        self.api_key: str = api_key
        self.username: str = username
        self.acc_number: Optional[str] = acc_number
        self.session = Session()
        self.sessionResponse = None

        self._use_rate_limiter = use_rate_limiter
        self._bucket_threads_run = False

        self._refresh_token = None
        self._valid_until = None

        self.session.headers.update(
            {
                "X-IG-API-KEY": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json; charset=UTF-8",
            }
        )

    def _url(self, endpoint: str) -> str:
        """Returns url from endpoint and base url"""
        return self.base_url + endpoint

    # CRUD operations

    def create(self, endpoint: str, params: dict[str, str], version: str) -> Response:
        """Create = POST"""
        url = self._url(endpoint)
        self.session.headers.update({"VERSION": version})
        response = self.session.post(url, data=json.dumps(params))
        
        logger.info(f"POST '{endpoint}', resp {response.status_code}")

        if response.status_code in [401, 403]:
            if api_limit_hit(response.text):
                raise ApiExceededException()
            if "error.public-api.failure.kyc.required" in response.text:
                raise KycRequiredException(
                    "KYC issue: you need to login manually to the web interface and "
                    "complete IGs occasional Know Your Customer checks"
                )
            else:
                raise IGException(
                    f"HTTP error: {response.status_code} {response.text}")

        return response

    def read(self, endpoint: str, params: dict[str, str], version: str) -> Response:
        url = self._url(endpoint)
        self.session.headers.update({"VERSION": version})
        response = self.session.get(url, params=params)
        # handle 'read_session' with 'fetchSessionTokens=true'
        handle_session_tokens(response, self.session)
        logger.info(f"GET '{endpoint}', resp {response.status_code}")

        return response

    def update(self, endpoint: str, params: dict[str, str], version: str) -> Response:
        url = self._url(endpoint)
        self.session.headers.update({"VERSION": version})
        response = self.session.put(url, data=json.dumps(params))
        logger.info(f"PUT '{endpoint}', resp {response.status_code}")

        return response

    def delete(self, endpoint: str, params: dict[str, str], version: str) -> Response:
        url = self._url(endpoint)
        self.session.headers.update({"VERSION": version})
        self.session.headers.update({"_method": "DELETE"})
        response = self.session.post(url, data=json.dumps(params))
        logger.info(f"DELETE (POST) '{endpoint}', resp {response.status_code}")

        if "_method" in self.session.headers:
            del self.session.headers["_method"]

        return response

    # Requests

    def request(self, action: IGAction, endpoint: str, params: dict[str, str], version:str = "1", check: bool = True):
        """Creates a CRUD request and returns response"""
        if check:
            self._check_session()

        response = None

        match action:
            case IGAction.CREATE:
                response = self.create(endpoint, params, version)
            case IGAction.READ:
                response = self.read(endpoint, params, version)
            case IGAction.UPDATE:
                response = self.update(endpoint, params, version)
            case IGAction.DELETE:
                response = self.delete(endpoint, params, version)
            case _:
                raise IGException(f"Unknown action '{action}'")

        if response.status_code >= 500:
            raise (
                IGException(
                    f"Server problem: status code: {response.status_code}, "
                    f"reason: {response.reason}"
                )
            )

        response.encoding = "utf-8"
        if api_limit_hit(response.text):
            raise ApiExceededException()

        if token_invalid(response.text):
            logger.warning("Invalid session token, triggering refresh...")
            self._valid_until = datetime.now() - timedelta(seconds=15)
            raise TokenInvalidException()

        return response

    def _manage_headers(self, response: Response):
        """
        Manages authentication headers - different behaviour depending on the
            session creation version
        :param response: HTTP response
        :type response: requests.Response
        """
        # handle v1 and v2 logins
        handle_session_tokens(response, self.session)
        # handle v3 logins
        if response.text:
            self.session.headers.update(
                {"IG-ACCOUNT-ID": self.acc_number})
            payload = json.loads(response.text)
            if "oauthToken" in payload:
                self._handle_oauth(payload["oauthToken"])

    def _handle_oauth(self, oauth):
        """
        Handle the v3 headers during session creation and refresh
        :param oauth: 'oauth' portion of the response body
        :type oauth: dict
        """
        access_token = oauth["access_token"]
        token_type = oauth["token_type"]
        self.session.headers.update(
            {"Authorization": f"{token_type} {access_token}"})
        self._refresh_token = oauth["refresh_token"]
        validity = int(oauth["expires_in"])
        self._valid_until = datetime.now() + timedelta(seconds=validity)

    # IG Login API

    def logout(self):
        """Log out of the current session"""
        version = "1"
        params = {}
        endpoint = "/session"
        action = IGAction.DELETE
        self.request(action, endpoint, params, version)
        self.session.close()
        # self._exit_bucket_threads() TODO

    def get_encryption_key(self):
        """Get encryption key to encrypt the password"""
        endpoint = "/session/encryptionKey"
        response = self.session.get(self.base_url + endpoint)
        if not response.ok:
            raise IGException("Could not get encryption key for login.")
        data = response.json()
        return data["encryptionKey"], data["timeStamp"]

    def read_session(self, fetch_session_tokens="false"):
        """Retrieves current session details"""
        version = "1"
        params = {"fetchSessionTokens": fetch_session_tokens}
        endpoint = "/session"
        action = IGAction.READ
        response = self.request(action, endpoint, params, version)
        if not response.ok:
            raise IGException("Error in read_session() %s" %
                              response.status_code)
        data = parse_response(response.text)
        return data

    def switch_account(self, account_id, default_account):
        """Switches active accounts, optionally setting the default account"""
        version = "1"
        params = {"accountId": account_id, "defaultAccount": default_account}
        endpoint = "/session"
        action = IGAction.UPDATE
        response = self.request(
            action, endpoint, params, version)
        self._manage_headers(response)
        data = parse_response(response.text)
        return data

    def create_session(self, password: str, encryption: bool = False, version: str = "2"):
        """
        :param session: HTTP session
        :type session: requests.Session
        :param encryption: whether or not the password should be encrypted.
            Required for some regions
        :type encryption: Boolean
        :param version: API method version
        :type version: str
        :return: JSON response body, parsed into dict
        :rtype: dict
        """
        if version == "3" and self.acc_number is None:
            raise IGException("Account number must be set for v3 sessions")

        logger.info(
            f"Creating new v{version} session for user '{self.username}' at "
            f"'{self.base_url}'"
        )
        if encryption:
            password = self.encrypt_password(password)

        params = {"identifier": self.username, "password": password}
        
        if encryption:
            params["encryptedPassword"] = str(True)

        endpoint = "/session"
        action = IGAction.CREATE
        response = self.request(action, endpoint, params, version, check=False)
        self._manage_headers(response)
        data = parse_response(response.text)

        self.sessionResponse = data

        # if self.ig_service._use_rate_limiter: TODO
        #     self.ig_service.setup_rate_limiter()

        return data

    def refresh_session(self, version: str = "1"):
        """
        Refreshes a v3 session. Tokens only last for 60 seconds, so need to be
            renewed regularly
        :param session: HTTP session object
        :type session: requests.Session
        :param version: API method version
        :type version: str
        :return: HTTP status code
        :rtype: int
        """
        logger.info(f"Refreshing session '{self.username}'")
        params = {"refresh_token": self._refresh_token}
        endpoint = "/session/refresh-token"
        action = IGAction.CREATE
        response = self.request(action, endpoint, params, version, check=False)
        self._handle_oauth(json.loads(response.text))
        return response.status_code

    def _check_session(self):
        """
        Check the v3 session status before making an API request:
            - v3 tokens only last for 60 seconds
            - if possible, the session can be renewed with a special refresh token
            - if not, a new session will be created
        """
        logger.debug("Checking session status...")
        if self._valid_until is not None and datetime.now() > self._valid_until:
            if self._refresh_token:
                # we are in a v3 session, need to refresh
                try:
                    logger.info("Current session has expired, refreshing...")
                    self.refresh_session()
                except IGException:
                    logger.info("Refresh failed, logging in again...")
                    self._refresh_token = None
                    self._valid_until = None
                    del self.session.headers["Authorization"]
                    self.create_session(version="3")

    def encrypt_password(self, password):
        """Encrypt password for login"""
        key, timestamp = self.get_encryption_key(self.session)
        rsakey = RSA.importKey(b64decode(key))
        string = password + "|" + str(int(timestamp))
        message = b64encode(string.encode())
        return b64encode(PKCS1_v1_5.new(rsakey).encrypt(message)).decode()


def handle_session_tokens(response, session):
    """
    Copy session tokens from response to headers, so they will be present for all
        future requests
    :param response: HTTP response object
    :type response: requests.Response
    :param session: HTTP session object
    :type session: requests.Session
    """
    if "CST" in response.headers:
        session.headers.update({"CST": response.headers["CST"]})
    if "X-SECURITY-TOKEN" in response.headers:
        session.headers.update(
            {"X-SECURITY-TOKEN": response.headers["X-SECURITY-TOKEN"]}
        )
