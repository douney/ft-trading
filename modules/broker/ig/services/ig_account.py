import logging

from urllib.parse import urlparse, parse_qs

from datetime import datetime

from modules.broker.ig.ig_exception import *
from modules.broker.ig.services.ig_session import IGSession

from ..utils.utils import expand_columns, parse_response, pd, conv_to_ms


logger = logging.getLogger(__name__)


class IGAccount:
    def __init__(self, ig_session: IGSession):
        self.ig_session = ig_session

    def fetch_accounts(self):
        """Returns a list of accounts belonging to the logged-in client"""
        version = "1"
        params = {}
        endpoint = "/accounts"
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data

    def fetch_account_preferences(self):
        """
        Gets the preferences for the logged in account
        :param session: session object. Optional
        :type session: requests.Session
        :return: preference values
        :rtype: dict
        """
        version = "1"
        params = {}
        endpoint = "/accounts/preferences"
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        prefs = parse_response(response.text)
        return prefs

    def update_account_preferences(self, trailing_stops_enabled=False):
        """
        Updates the account preferences. Currently only one value supported -
            trailing stops
        :param trailing_stops_enabled: whether trailing stops should be enabled for
            the account
        :type trailing_stops_enabled: bool
        :param session: session object. Optional
        :type session: requests.Session
        :return: status of the update request
        :rtype: str
        """
        version = "1"
        params = {}
        endpoint = "/accounts/preferences"
        action = IGAction.UPDATE
        params["trailingStopsEnabled"] = "true" if trailing_stops_enabled else "false"
        response = self.ig_session.request(action, endpoint, params, version)
        update_status = parse_response(response.text)
        return update_status["status"]

    def fetch_account_activity_by_period(self, milliseconds):
        """
        Returns the account activity history for the last specified period
        """
        version = "1"
        milliseconds = conv_to_ms(milliseconds)
        params = {}
        url_params = {"milliseconds": milliseconds}
        endpoint = "/history/activity/{milliseconds}".format(**url_params)
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data

    def fetch_account_activity_by_date(self, from_date: datetime, to_date: datetime):
        """
        Returns the account activity history for period between the specified dates
        """
        version = "1"
        if from_date is None or to_date is None:
            raise IGException("Both from_date and to_date must be specified")
        if from_date > to_date:
            raise IGException("from_date must be before to_date")

        params = {}
        url_params = {
            "fromDate": from_date.strftime("%d-%m-%Y"),
            "toDate": to_date.strftime("%d-%m-%Y"),
        }
        endpoint = "/history/activity/{fromDate}/{toDate}".format(**url_params)
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data

    def fetch_account_activity_v2(
        self,
        from_date: datetime = None,
        to_date: datetime = None,
        max_span_seconds: int = None,
        page_size: int = 20
    ):
        """
        Returns the account activity history (v2)

        If the result set spans multiple 'pages', this method will automatically get
        all the results and bundle them into one object.

        :param from_date: start date and time. Optional
        :type from_date: datetime
        :param to_date: end date and time. A date without time refers to the end of
            that day. Defaults to today. Optional
        :type to_date: datetime
        :param max_span_seconds: Limits the timespan in seconds through to current
            time (not applicable if a date range has been specified). Default 600.
            Optional
        :type max_span_seconds: int
        :param page_size: number of records per page. Default 20. Optional. Use 0 to
            turn off paging
        :type page_size: int
        :param session: session object. Optional
        :type session: Session
        :return: results set
        :rtype: Pandas DataFrame if configured, otherwise a dict
        """
        version = "2"
        params = {}
        if from_date:
            params["from"] = from_date.strftime("%Y-%m-%dT%H:%M:%S")
        if to_date:
            params["to"] = to_date.strftime("%Y-%m-%dT%H:%M:%S")
        if max_span_seconds:
            params["maxSpanSeconds"] = max_span_seconds
        params["pageSize"] = page_size
        endpoint = "/history/activity/"
        action = IGAction.READ
        data = {}
        activities = []
        pagenumber = 1
        more_results = True

        while more_results:
            params["pageNumber"] = pagenumber
            response = self.ig_session.request(action, endpoint, params, version)
            data = parse_response(response.text)
            activities.extend(data["activities"])
            page_data = data["metadata"]["pageData"]
            if page_data["totalPages"] == 0 or (
                page_data["pageNumber"] == page_data["totalPages"]
            ):
                more_results = False
            else:
                pagenumber += 1

        data["activities"] = activities

        return data

    def fetch_account_activity(
        self,
        from_date: datetime = None,
        to_date: datetime = None,
        detailed=False,
        deal_id: str = None,
        fiql_filter: str = None,
        page_size: int = 50,
    ):
        """
        Returns the account activity history (v3)

        If the result set spans multiple 'pages', this method will automatically get
        all the results and bundle them into one object.

        :param from_date: start date and time. Optional
        :type from_date: datetime
        :param to_date: end date and time. A date without time refers to the end of
            that day. Defaults to today. Optional
        :type to_date: datetime
        :param detailed: Indicates whether to retrieve additional details about the
            activity. Default False. Optional
        :type detailed: bool
        :param deal_id: deal ID. Optional
        :type deal_id: str
        :param fiql_filter: FIQL filter (supported operators: ==|!=|,|;). Optional
        :type fiql_filter: str
        :param page_size: page size (min: 10, max: 500). Default 50. Optional
        :type page_size: int
        :param session: session object. Optional
        :type session: Session
        :return: results set
        :rtype: Pandas DataFrame if configured, otherwise a dict
        """
        version = "3"
        params = {}
        if from_date:
            params["from"] = from_date.strftime("%Y-%m-%dT%H:%M:%S")
        if to_date:
            params["to"] = to_date.strftime("%Y-%m-%dT%H:%M:%S")
        if detailed:
            params["detailed"] = "true"
        if deal_id:
            params["dealId"] = deal_id
        if fiql_filter:
            params["filter"] = fiql_filter

        params["pageSize"] = page_size
        endpoint = "/history/activity/"
        action = IGAction.READ
        data = {}
        activities = []
        more_results = True

        while more_results:
            response = self.ig_session.request(action, endpoint, params, version)
            data = parse_response(response.text)
            activities.extend(data["activities"])
            paging = data["metadata"]["paging"]
            if paging["next"] is None:
                more_results = False
            else:
                parse_result = urlparse(paging["next"])
                query = parse_qs(parse_result.query)
                logger.debug(f"fetch_account_activity() next query: '{query}'")
                if "from" in query:
                    params["from"] = query["from"][0]
                else:
                    del params["from"]
                if "to" in query:
                    params["to"] = query["to"][0]
                else:
                    del params["to"]

        data["activities"] = activities

        return data

    @staticmethod
    def format_activities(raw_json):
        df = pd.json_normalize(
            raw_json["activities"],
            record_path=["details", ["actions"]],
            meta=[
                "date",
                "epic",
                "period",
                "dealId",
                "channel",
                "type",
                "status",
                "description",
                ["details", "marketName"],
                ["details", "goodTillDate"],
                ["details", "currency"],
                ["details", "size"],
                ["details", "direction"],
                ["details", "level"],
                ["details", "stopLevel"],
                ["details", "stopDistance"],
                ["details", "guaranteedStop"],
                ["details", "trailingStopDistance"],
                ["details", "trailingStep"],
                ["details", "limitLevel"],
                ["details", "limitDistance"],
            ],
        )

        df = df.rename(
            columns={
                "details.marketName": "marketName",
                "details.goodTillDate": "goodTillDate",
                "details.currency": "currency",
                "details.size": "size",
                "details.direction": "direction",
                "details.level": "level",
                "details.stopLevel": "stopLevel",
                "details.stopDistance": "stopDistance",
                "details.guaranteedStop": "guaranteedStop",
                "details.trailingStopDistance": "trailingStopDistance",
                "details.trailingStep": "trailingStep",
                "details.limitLevel": "limitLevel",
                "details.limitDistance": "limitDistance",
            }
        )

        cols = df.columns.tolist()
        cols = cols[2:] + cols[:2]
        data = df[cols]

        return data

    def fetch_transaction_history_by_type_and_period(self, milliseconds, trans_type):
        """Returns the transaction history for the specified transaction
        type and period"""
        version = "1"
        milliseconds = conv_to_ms(milliseconds)
        params = {}
        url_params = {"milliseconds": milliseconds, "trans_type": trans_type}
        endpoint = "/history/transactions/{trans_type}/{milliseconds}".format(
            **url_params
        )
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data

    def fetch_transaction_history(
        self,
        trans_type=None,
        from_date=None,
        to_date=None,
        max_span_seconds=None,
        page_size=None,
        page_number=None,
    ):
        """Returns the transaction history for the specified transaction
        type and period"""
        version = "2"
        params = {}
        if trans_type:
            params["type"] = trans_type
        if from_date:
            if hasattr(from_date, "isoformat"):
                from_date = from_date.isoformat()
            params["from"] = from_date
        if to_date:
            if hasattr(to_date, "isoformat"):
                to_date = to_date.isoformat()
            params["to"] = to_date
        if max_span_seconds:
            params["maxSpanSeconds"] = max_span_seconds
        if page_size:
            params["pageSize"] = page_size
        if page_number:
            params["pageNumber"] = page_number

        endpoint = "/history/transactions"
        action = IGAction.READ

        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data
