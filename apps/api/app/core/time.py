from zoneinfo import ZoneInfo
import datetime as dt

BOGOTA_TZ = ZoneInfo("America/Bogota")

def today_colombia():
    return dt.datetime.now(BOGOTA_TZ).date()
