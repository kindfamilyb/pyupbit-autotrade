import time
import pyupbit
import datetime
import schedule
import requests
import yaml
from fbprophet import Prophet
import pprint


with open('config.yaml', encoding='UTF-8') as f:
    _cfg = yaml.load(f, Loader=yaml.FullLoader)
upbit_access = _cfg['UPBIT_ACCESS']
upbit_secret = _cfg['UPBIT_SECRET']
slack_myToken = _cfg['SLACK_TOKEN']
DISCORD_WEBHOOK_URL = _cfg['DISCORD_WEBHOOK_URL']
TRY_COIN_LIST = _cfg['TRY_COIN_LIST']

HOST = _cfg['HOST']
PORT = int(_cfg['PORT'])
DB = _cfg['DB']
USER = _cfg['USER']
PASSWD = _cfg['PASSWD']

access = upbit_access
secret = upbit_secret

upbit = pyupbit.Upbit(access, secret)

def get_target_price(ticker, k):
    """변동성 돌파 전략으로 매수 목표가 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
    target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price

def get_start_time(ticker):
    """시작 시간 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
    start_time = df.index[0]
    return start_time

def get_balance(ticker):
    """잔고 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]

predict_price_list = {}
# predicted_close_price = 0
def predict_price():
    """Prophet으로 당일 종가 가격 예측"""
    # global predicted_close_price
    global predict_price_list
    for coin in TRY_COIN_LIST:
        df = pyupbit.get_ohlcv(coin, interval="minute60")
        df = df.reset_index()
        df['ds'] = df['index']
        df['y'] = df['close']
        data = df[['ds','y']]
        model = Prophet()
        model.fit(data)
        future = model.make_future_dataframe(periods=24, freq='H')
        forecast = model.predict(future)
        closeDf = forecast[forecast['ds'] == forecast.iloc[-1]['ds'].replace(hour=9)]
        if len(closeDf) == 0:
            closeDf = forecast[forecast['ds'] == data.iloc[-1]['ds'].replace(hour=9)]
        closeValue = closeDf['yhat'].values[0]
        predict_price_list[coin] = closeValue
    pprint.pprint(f"예측가격갱신({datetime.datetime.now()}):{predict_price_list}")
    return predict_price_list
predict_price()
# schedule.every().hour.do(lambda: predict_price())

predict_price_list2 = {}
# predicted_close_price = 0
def predict_price2():
    """Prophet으로 당일 종가 가격 예측"""
    # global predicted_close_price
    global predict_price_list2
    for coin in TRY_COIN_LIST:
        df = pyupbit.get_daily_ohlcv_from_base(coin, base=23.99)
        df = df.reset_index()
        df['ds'] = df['index']
        df['y'] = df['close']
        data = df[['ds','y']]
        model = Prophet()
        model.fit(data)
        future = model.make_future_dataframe(periods=24, freq='H')
        forecast = model.predict(future)
        closeDf = forecast[forecast['ds'] == forecast.iloc[-1]['ds'].replace(hour=9)]
        if len(closeDf) == 0:
            closeDf = forecast[forecast['ds'] == data.iloc[-1]['ds'].replace(hour=9)]
        closeValue = closeDf['yhat'].values[0]
        predict_price_list2[coin] = closeValue
    pprint.pprint(f"예측가격갱신2({datetime.datetime.now()}):{predict_price_list2}")
    return predict_price_list2
predict_price2()
# schedule.every().hour.do(lambda: predict_price())


# 로그인
upbit = pyupbit.Upbit(access, secret)
print("autotrade start")
print(predict_price_list['KRW-BTC'])

# 자동매매 시작
# while True:
#     try:
#         now = datetime.datetime.now()
#         start_time = get_start_time("KRW-BTC")
#         end_time = start_time + datetime.timedelta(days=1)
#         schedule.run_pending()

#         if start_time < now < end_time - datetime.timedelta(seconds=10):
#             target_price = get_target_price("KRW-BTC", 0.5)
#             current_price = get_current_price("KRW-BTC")
#             if target_price < current_price and current_price < predicted_close_price:
#                 krw = get_balance("KRW")
#                 if krw > 5000:
#                     upbit.buy_market_order("KRW-BTC", krw*0.9995)
#         else:
#             btc = get_balance("BTC")
#             if btc > 0.00008:
#                 upbit.sell_market_order("KRW-BTC", btc*0.9995)
#         time.sleep(1)
#     except Exception as e:
#         print(e)
#         time.sleep(1)
