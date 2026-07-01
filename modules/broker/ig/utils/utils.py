#!/usr/bin/env python
# -*- coding:utf-8 -*-

import logging
import traceback
from typing import Any
import six
import json
import pandas as pd

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

DATE_FORMATS = {1: "%Y:%m:%d-%H:%M:%S", 2: "%Y/%m/%d %H:%M:%S", 3: "%Y/%m/%d %H:%M:%S"}

def conv_resol(resolution):
    from pandas.tseries.frequencies import to_offset

    d = {
        to_offset("1s"): "SECOND",
        to_offset("1Min"): "MINUTE",
        to_offset("2Min"): "MINUTE_2",
        to_offset("3Min"): "MINUTE_3",
        to_offset("5Min"): "MINUTE_5",
        to_offset("10Min"): "MINUTE_10",
        to_offset("15Min"): "MINUTE_15",
        to_offset("30Min"): "MINUTE_30",
        to_offset("1h"): "HOUR",
        to_offset("2h"): "HOUR_2",
        to_offset("3h"): "HOUR_3",
        to_offset("4h"): "HOUR_4",
        to_offset("D"): "DAY",
        to_offset("W"): "WEEK",
        to_offset("ME"): "MONTH",
    }
    offset = to_offset(resolution)
    if offset in d:
        return d[offset]
    else:
        logger.error(traceback.format_exc())
        logger.warning("conv_resol returns '%s'" % resolution)
        return resolution


def conv_datetime(dt, version=2):
    """Converts dt to string like
    version 1 = 2014:12:15-00:00:00
    version 2 = 2014/12/15 00:00:00
    version 3 = 2014/12/15 00:00:00
    """
    try:
        if isinstance(dt, six.string_types):
            dt = pd.to_datetime(dt)

        fmt = DATE_FORMATS[int(version)]
        return dt.strftime(fmt)
    
    except (ValueError, TypeError):
        logger.warning("conv_datetime returns %s" % dt)
        return dt


def conv_to_ms(td):
    """Converts td to integer number of milliseconds"""
    try:
        if isinstance(td, six.integer_types):
            return td
        else:
            return int(td.total_seconds() * 1000.0)
    except ValueError:
        logger.error(traceback.format_exc())
        logger.warning("conv_to_ms returns '%s'" % td)
        return td

def print_full(x):
    """
    Prints out a full data frame, no column hiding
    """
    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 2000)
    # pd.set_option('display.float_format', '{:20,.2f}'.format)
    pd.set_option("display.max_colwidth", None)
    pd.reset_option("display.max_rows")
    pd.reset_option("display.max_columns")
    pd.reset_option("display.width")
    pd.reset_option("display.float_format")
    pd.reset_option("display.max_colwidth")


def api_limit_hit(response_text: str):
    # note we don't check for historical data allowance - it only gets reset
    # once a week
    return (
        "exceeded-api-key-allowance" in response_text
        or "exceeded-account-allowance" in response_text
        or "exceeded-account-trading-allowance" in response_text
    )


def token_invalid(response_text):
    return (
        "oauth-token-invalid" in response_text
        or "client-token-invalid" in response_text
    )

def parse_response(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Parses JSON response
    returns dict
    exception raised when error occurs"""
    response = json.loads(*args, **kwargs)

    if "errorCode" in response:
        raise (Exception(response["errorCode"]))
    
    return response

def colname_unique(d_cols):
    """Returns a set of column names (unique)"""
    s = set()
    for lst in d_cols.values():
        s.update(lst)
    return list(s)

def expand_columns(data, d_cols, flag_col_prefix=False, col_overlap_allowed=None):
    """Expand columns"""
    if col_overlap_allowed is None:
        col_overlap_allowed = []
    for col_lev1, lst_col in d_cols.items():
        ser = data[col_lev1]
        del data[col_lev1]
        for col in lst_col:
            if col not in data.columns or col in col_overlap_allowed:
                if flag_col_prefix:
                    colname = col_lev1 + "_" + col
                else:
                    colname = col
                data[colname] = ser.map(lambda x: x[col], na_action="ignore")
            else:
                raise (NotImplementedError("col overlap: %r" % col))
    return data