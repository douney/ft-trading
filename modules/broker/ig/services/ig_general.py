from modules.broker.ig.utils.utils import parse_response

from modules.broker.ig.services.ig_session import IGSession


class IGGeneral:
    def __init__(self, ig_session: IGSession):
        self.ig_session = ig_session

    def get_client_apps(self):
        """Returns a list of client-owned applications"""
        version = "1"
        params = {}
        endpoint = "/operations/application"
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)
        return data

    def update_client_app(
        self,
        allowance_account_overall,
        allowance_account_trading,
        api_key,
        status
    ):
        """Updates an application"""
        version = "1"
        params = {
            "allowanceAccountOverall": allowance_account_overall,
            "allowanceAccountTrading": allowance_account_trading,
            "apiKey": api_key,
            "status": status,
        }
        endpoint = "/operations/application"
        action = IGAction.UPDATE
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)
        return data

    def disable_client_app_key(self):
        """
        Disables the current application key from processing further requests.
        Disabled keys may be re-enabled via the My Account section on
        the IG Web Dealing Platform.
        """
        version = "1"
        params = {}
        endpoint = "/operations/application/disable"
        action = IGAction.UPDATE
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)
        return data
