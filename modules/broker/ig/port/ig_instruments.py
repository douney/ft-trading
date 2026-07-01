from modules.base_type.instrument import Instrument
from modules.base_type.currency import Currency
from types import SimpleNamespace

DAX_1E = Instrument(
    symbol="IX.D.DAX.IFMM.IP",
    currency=Currency.EUR,
    point_value=1,
    min_size=0.5,
    open_hour=9,
    close_hour=17.5,
    label="DAX"
)

DAX_F_5E = Instrument(
    symbol="IX.D.DAX.FWM1.IP",
    currency=Currency.EUR,
    point_value=5,
    min_size=0.5,
    open_hour=8,
    close_hour=22,
    label="DAX Future"
)

US_TECH_1E = Instrument(
    symbol="IX.D.NASDAQ.IFE.IP",
    currency=Currency.USD,
    point_value=1,
    min_size=0.1,
    open_hour=9,
    close_hour=17.5,
    label="Nasdaq 100"
)

US_TECH_F_20D = Instrument(
    symbol="IX.D.NASDAQ.FWM1.IP",
    currency=Currency.USD,
    point_value=5,
    min_size=0.1,
    open_hour=8,
    close_hour=22,
    label="Nasdaq 100 Future"
)

CAC40_1E = Instrument(
    symbol="IX.D.CAC.IMF.IP",
    currency=Currency.EUR,
    point_value=1,
    min_size=0.5,
    open_hour=9,
    close_hour=17.5,
    label="CAC 40"
)

CAC40_F_1E = Instrument(
    symbol="IX.D.CAC.FFM1.IP",
    currency=Currency.EUR,
    point_value=5,
    min_size=0.5,
    open_hour=8,
    close_hour=22,
    label="CAC 40 Future"
)

SP500_1E = Instrument(
    symbol="IX.D.SPTRD.IFE.IP",
    currency=Currency.USD,
    point_value=1,
    min_size=0.1,
    open_hour=9,
    close_hour=17.5,
    label="S&P 500"
)

SP500_F_50D = Instrument(
    symbol="IX.D.SPTRD.FWM1.IP",
    currency=Currency.USD,
    point_value=5,
    min_size=0.1,
    open_hour=8,
    close_hour=22,
    label="S&P 500 Future"
)

DOWJONES_1E = Instrument(
    symbol="IX.D.DOW.IFE.IP",
    currency=Currency.USD,
    point_value=1,
    min_size=0.1,
    open_hour=9,
    close_hour=17.5,
    label="Dow Jones"
)

ETHER = Instrument(
    symbol="CS.D.ETHUSD.CFE.IP",
    currency=Currency.USD,
    point_value=1,
    min_size=0.01,
    open_hour=0,
    close_hour=24,
    label="Ether"
)

IG_INSTRUMENTS = SimpleNamespace(
    DAX_1E = DAX_1E,
    DAX_F_5E = DAX_F_5E,
    US_TECH_1E = US_TECH_1E,
    US_TECH_F_20D = US_TECH_F_20D,
    CAC40_1E = CAC40_1E,
    CAC40_F_1E = CAC40_F_1E,
    SP500_1E = SP500_1E,
    SP500_F_50D = SP500_F_50D,
    DOWJONES_1E = DOWJONES_1E,
    ETHER = ETHER,
)
