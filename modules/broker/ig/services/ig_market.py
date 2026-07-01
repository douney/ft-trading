import logging
import time

from datetime import timedelta, datetime

from modules.broker.ig.services.ig_session import IGSession

from ..utils.utils import (
    parse_response,
    pd,
    conv_resol,
    conv_datetime,
    DATE_FORMATS,
)

from pandas import json_normalize

logger = logging.getLogger(__name__)


class IGMarket:
    def __init__(self, ig_session: IGSession):
        self.ig_session = ig_session

    def fetch_client_sentiment_by_instrument(self, market_id):
        """Returns the client sentiment for the given instrument's market"""
        version = "1"
        params = {}
        if isinstance(market_id, (list,)):
            market_ids = ",".join(market_id)
            url_params = {"market_ids": market_ids}
            endpoint = "/clientsentiment/?marketIds={market_ids}".format(
                **url_params)
        else:
            url_params = {"market_id": market_id}
            endpoint = "/clientsentiment/{market_id}".format(**url_params)
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data

    def fetch_related_client_sentiment_by_instrument(self, market_id):
        """Returns a list of related (also traded) client sentiment for
        the given instrument's market"""
        version = "1"
        params = {}
        url_params = {"market_id": market_id}
        endpoint = "/clientsentiment/related/{market_id}".format(**url_params)
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)
        
        return data

    def fetch_top_level_navigation_nodes(self):
        """Returns all top-level nodes (market categories) in the market
        navigation hierarchy."""
        version = "1"
        params = {}
        endpoint = "/marketnavigation"
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data

    def fetch_sub_nodes_by_node(self, node):
        """Returns all sub-nodes of the given node in the market
        navigation hierarchy"""
        version = "1"
        params = {}
        url_params = {"node": node}
        endpoint = "/marketnavigation/{node}".format(**url_params)
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)


        return data

    def fetch_market_by_epic(self, epic):
        """Returns the details of the given market"""
        version = "3"
        params = {}
        url_params = {"epic": epic}
        endpoint = "/markets/{epic}".format(**url_params)
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data

    def fetch_markets_by_epics(self, epics, detailed=True, version="2"):
        """
        Returns the details of the given markets
        :param epics: comma separated list of epics
        :type epics: str
        :param detailed: Whether to return detailed info or snapshot data only.
            Only supported for version 2. Optional, default True
        :type detailed: bool
        :param session: session object. Optional, default None
        :type session: requests.Session
        :param version: IG API method version. Optional, default '2'
        :type version: str
        :return: list of market details
        :rtype: Munch instance if configured, else dict
        """
        params = {"epics": epics}
        if version == "2":
            params["filter"] = "ALL" if detailed else "SNAPSHOT_ONLY"
        endpoint = "/markets"
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)
        data = data["marketDetails"]

        return data

    def search_markets(self, search_term):
        """Returns all markets matching the search term"""
        version = "1"
        endpoint = "/markets"
        params = {"searchTerm": search_term}
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data

    def format_prices(self, prices, version, flag_calc_spread=False):
        """
        Format prices data as a DataFrame with hierarchical columns

        Do not call this method directly - it is designed to be passed into
        the fetch_historical_prices*() methods. See tests for examples

        param prices: raw price data
        :type prices: list of dict
        :param version: API endpoint version
        :type version: str
        :param flag_calc_spread: include spread
        :type flag_calc_spread: bool
        :return: prices as pandas.DataFrame
        :rtype: pandas.DataFrame
        """

        if len(prices) == 0:
            raise (Exception("Historical price data not found"))

        def cols(typ):
            return {
                "openPrice.%s" % typ: "Open",
                "highPrice.%s" % typ: "High",
                "lowPrice.%s" % typ: "Low",
                "closePrice.%s" % typ: "Close",
                "lastTradedVolume": "Volume",
            }

        last = prices[0]["lastTradedVolume"] or prices[0]["closePrice"]["lastTraded"]
        df = json_normalize(prices)
        df = df.set_index("snapshotTime")
        df.index = pd.to_datetime(df.index, format=DATE_FORMATS[int(version)])
        df.index.name = "DateTime"

        df_ask = df[
            ["openPrice.ask", "highPrice.ask", "lowPrice.ask", "closePrice.ask"]
        ]
        df_ask = df_ask.rename(columns=cols("ask"))

        df_bid = df[
            ["openPrice.bid", "highPrice.bid", "lowPrice.bid", "closePrice.bid"]
        ]
        df_bid = df_bid.rename(columns=cols("bid"))

        if flag_calc_spread:
            df_spread = df_ask - df_bid

        if last:
            df_last = df[
                [
                    "openPrice.lastTraded",
                    "highPrice.lastTraded",
                    "lowPrice.lastTraded",
                    "closePrice.lastTraded",
                    "lastTradedVolume",
                ]
            ]
            df_last = df_last.rename(columns=cols("lastTraded"))

        data = [df_bid, df_ask]
        keys = ["bid", "ask"]
        if flag_calc_spread:
            data.append(df_spread)
            keys.append("spread")

        if last:
            data.append(df_last)
            keys.append("last")

        df2 = pd.concat(data, axis=1, keys=keys)

        # force all object columns to be numeric, NaN if error
        for col in df2.select_dtypes(include=["object"]).columns:
            df2[col] = pd.to_numeric(df2[col], errors="coerce")

        return df2

    def flat_prices(self, prices, version):
        """
        Format prices data as a flat DataFrame, no hierarchy

        Do not call this method directly - it is designed to be passed into
        the fetch_historical_prices*() methods. See tests for examples

        param prices: raw price data
        :type prices: list of dict
        :param version: API endpoint version
        :type version: str
        :return: prices as pandas.DataFrame
        :rtype: pandas.DataFrame
        """

        if len(prices) == 0:
            raise (Exception("Historical price data not found"))

        df = json_normalize(prices)
        if version == "3":
            df = df.set_index("snapshotTimeUTC")
            df = df.drop(columns=["snapshotTime"])
            date_format = "%Y-%m-%dT%H:%M:%S"
        else:
            df = df.set_index("snapshotTime")
            date_format = DATE_FORMATS[int(version)]
        df.index = pd.to_datetime(df.index, format=date_format)
        df.index.name = "DateTime"
        df = df.drop(
            columns=[
                "openPrice.lastTraded",
                "closePrice.lastTraded",
                "highPrice.lastTraded",
                "lowPrice.lastTraded",
            ]
        )
        df = df.rename(
            columns={
                "openPrice.bid": "open.bid",
                "openPrice.ask": "open.ask",
                "closePrice.bid": "close.bid",
                "closePrice.ask": "close.ask",
                "highPrice.bid": "high.bid",
                "highPrice.ask": "high.ask",
                "lowPrice.bid": "low.bid",
                "lowPrice.ask": "low.ask",
                "lastTradedVolume": "volume",
            }
        )
        return df

    def mid_prices(self, prices, version):
        """
        Format price data as a flat DataFrame, no hierarchy, calculating
        mid-prices

        Do not call this method directly - it is designed to be passed into
        the fetch_historical_prices*() methods. See tests for examples

        param prices: raw price data
        :type prices: list of dict
        :param version: API endpoint version
        :type version: str
        :return: prices as pandas.DataFrame
        :rtype: pandas.DataFrame
        """

        if len(prices) == 0:
            raise (Exception("Historical price data not found"))

        df = json_normalize(prices)
        if version == "3":
            df = df.set_index("snapshotTimeUTC")
            df = df.drop(columns=["snapshotTime"])
            date_format = "%Y-%m-%dT%H:%M:%S"
        else:
            df = df.set_index("snapshotTime")
            date_format = DATE_FORMATS[int(version)]
        df.index = pd.to_datetime(df.index, format=date_format)
        df.index.name = "DateTime"

        df["Open"] = df[["openPrice.bid", "openPrice.ask"]].mean(axis=1)
        df["High"] = df[["highPrice.bid", "highPrice.ask"]].mean(axis=1)
        df["Low"] = df[["lowPrice.bid", "lowPrice.ask"]].mean(axis=1)
        df["Close"] = df[["closePrice.bid", "closePrice.ask"]].mean(axis=1)

        df = df.drop(
            columns=[
                "openPrice.lastTraded",
                "closePrice.lastTraded",
                "highPrice.lastTraded",
                "lowPrice.lastTraded",
                "openPrice.bid",
                "openPrice.ask",
                "closePrice.bid",
                "closePrice.ask",
                "highPrice.bid",
                "highPrice.ask",
                "lowPrice.bid",
                "lowPrice.ask",
            ]
        )
        df = df.rename(columns={"lastTradedVolume": "Volume"})

        return df

    def fetch_historical_prices_by_epic(
        self,
        epic,
        resolution=None,
        start_date=None,
        end_date=None,
        numpoints=None,
        pagesize=20,
        format=None,
        wait=1,
    ):
        """
        Fetches historical prices for the given epic.

        This method wraps the IG v3 /prices/{epic} endpoint. With this method you can
        choose to get either a fixed number of prices in the past, or to get the
        prices between two points in time. By default it will return the last 10
        prices at 1 minute resolution.

        If the result set spans multiple 'pages', this method will automatically
        get all the results and bundle them into one object.

        :param epic: (str) The epic key for which historical prices are being
            requested
        :param resolution: (str, optional) timescale resolution. Expected values
            are 1Min, 2Min, 3Min, 5Min, 10Min, 15Min, 30Min, 1H, 2H, 3H, 4H, D,
            W, M. Default is 1Min
        :param start_date: (datetime, optional) date range start, format
            yyyy-MM-dd'T'HH:mm:ss
        :param end_date: (datetime, optional) date range end, format
            yyyy-MM-dd'T'HH:mm:ss
        :param numpoints: (int, optional) number of data points. Default is 10
        :param pagesize: (int, optional) number of data points. Default is 20
        :param session: (Session, optional) session object
        :param format: (function, optional) function to convert the raw
            JSON response
        :param wait: (int, optional) how many seconds to wait between successive
            calls in a multi-page scenario. Default is 1
        :returns: Pandas DataFrame if configured, otherwise a dict
        :raises Exception: raises an exception if any error is encountered
        """

        version = "3"
        params = {}

        if start_date:
            params["from"] = start_date
        if end_date:
            params["to"] = end_date
        if numpoints:
            params["max"] = numpoints

        params["pageSize"] = pagesize
        url_params = {"epic": epic}
        endpoint = "/prices/{epic}".format(**url_params)
        action = IGAction.READ
        prices = []
        pagenumber = 1
        more_results = True

        while more_results:
            params["pageNumber"] = pagenumber
            response = self.ig_session.request(action, endpoint, params, version)
            data = parse_response(response.text)
            prices.extend(data["prices"])
            page_data = data["metadata"]["pageData"]
            if page_data["totalPages"] == 0 or (
                page_data["pageNumber"] == page_data["totalPages"]
            ):
                more_results = False
            else:
                pagenumber += 1
            time.sleep(wait)

        data["prices"] = prices

        if format is None:
            format = self.ig_session.format_prices

        self.ig_session.log_allowance(data["metadata"])
        return data

    def fetch_historical_prices_by_epic_and_num_points(self, epic, resolution, numpoints, format=None):
        """Returns a list of historical prices for the given epic, resolution,
        number of points"""
        version = "2"

        params = {}
        url_params = {"epic": epic,
                      "resolution": resolution, "numpoints": numpoints}
        endpoint = "/prices/{epic}/{resolution}/{numpoints}".format(
            **url_params)
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)
        if format is None:
            format = self.ig_session.format_prices

        return data

    def fetch_historical_prices_by_epic_and_date_range(
        self,
        epic,
        resolution,
        start_date,
        end_date,
        format=None,
        version="2",
    ):
        """
        Returns a list of historical prices for the given epic, resolution, multiplier
        and date range. Supports both versions 1 and 2
        :param epic: IG epic
        :type epic: str
        :param resolution: timescale for returned data. Expected values 'M', 'D',
            '1H' etc
        :type resolution: str
        :param start_date: start date for returned data. For v1, format
            '2020:09:01-00:00:00', for v2 use '2020-09-01 00:00:00'
        :type start_date: str
        :param end_date: end date for returned data. For v1, format
            '2020:09:01-00:00:00', for v2 use '2020-09-01 00:00:00'
        :type end_date: str
        :param session: HTTP session
        :type session: requests.Session
        :param format: function defining how the historic price data should be
            converted into a Dataframe
        :type format: function
        :param version: API method version
        :type version: str
        :return: historic data
        :rtype: dict, with 'prices' element as pandas.Dataframe
        """

        params = {}
        if version == "1":
            start_date = conv_datetime(start_date, version)
            end_date = conv_datetime(end_date, version)
            params = {"startdate": start_date, "enddate": end_date}
            url_params = {"epic": epic, "resolution": resolution}
            endpoint = "/prices/{epic}/{resolution}".format(**url_params)
        else:
            url_params = {
                "epic": epic,
                "resolution": resolution,
                "startDate": start_date,
                "endDate": end_date,
            }
            endpoint = "/prices/{epic}/{resolution}/{startDate}/{endDate}".format(
                **url_params
            )
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        del self.ig_session.session.headers["VERSION"]
        data = parse_response(response.text)
        if format is None:
            format = self.ig_session.format_prices

        return data

    def log_allowance(self, data):
        remaining_allowance = data["allowance"]["remainingAllowance"]
        allowance_expiry_secs = data["allowance"]["allowanceExpiry"]
        allowance_expiry = datetime.today() + timedelta(seconds=allowance_expiry_secs)
        logger.info(
            "Historic price data allowance: %s remaining until %s"
            % (remaining_allowance, allowance_expiry)
        )
