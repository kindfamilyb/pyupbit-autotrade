import time
import pyupbit
import datetime
import requests
import yaml

with open('config.yaml', encoding='UTF-8') as f:
    _cfg = yaml.load(f, Loader=yaml.FullLoader)
upbit_access = _cfg['UPBIT_ACCESS']
upbit_secret = _cfg['UPBIT_SECRET']
slack_myToken = _cfg['SLACK_TOKEN']

access = upbit_access
secret = upbit_secret
myToken = slack_myToken

def post_message(token, channel, text):
    """슬랙 메시지 전송"""
    response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer "+token},
        data={"channel": channel,"text": text}
    )

def get_target_price(ticker, k):
    """변동성 돌파 전략으로 매수 목표가 조회"""
    df = pyupbit.get_daily_ohlcv_from_base(ticker="KRW-BTC", base=23.99)[-2:]
    target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price

def get_start_time(ticker):
    """시작 시간 조회"""
    df = pyupbit.get_daily_ohlcv_from_base(ticker="KRW-BTC", base=23.99)[-1:]
    start_time = df.index[0]
    return start_time

def get_ma5(ticker):
    """5일 이동 평균선 조회"""
    df = pyupbit.get_daily_ohlcv_from_base(ticker="KRW-BTC", base=23.99)[4:]
    ma5 = df['close'].rolling(5).mean().iloc[-1]
    return ma5

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

def get_stock_balance():
    bought_list = [x['currency'] for x in upbit.get_balances()]
    return bought_list

def get_total_balances_alert():
    """접속확인 및 잔고표시 알람"""
    total_balances = upbit.get_balances()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print('============')
    post_message(myToken,"#crypto", "============")
    for x in total_balances:
        for i in x:
            print(f'{i} : {x[i]}')
            post_message(myToken,"#crypto", f'{i} : {x[i]}')
    print(now)
    post_message(myToken,"#crypto", f'업데이트시간: {now}')
    print('============')
    post_message(myToken,"#crypto", "============")
    post_message(myToken,"#crypto", "            ")

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]

# 로그인
upbit = pyupbit.Upbit(access, secret)

# 시작 메세지(잔고,시작메시지) 슬랙 전송
get_total_balances_alert()
print("autotrade start")
post_message(myToken,"#crypto", "autotrade start") 

while True:
    try:
        stock_dict = get_stock_balance() # 보유 코인 조회
        now = datetime.datetime.now()
        start_time = get_start_time("KRW-BTC")
        end_time = start_time + datetime.timedelta(days=1)

        # 매일 3,6,9,12,15,18,21,24시 30분에 접속확인 알람
        if now.hour % 3 == 0 and now.minute == 30 and now.second <= 5:
            get_total_balances_alert()
            time.sleep(5)

        if start_time < now < end_time - datetime.timedelta(seconds=10):
            target_price = get_target_price("KRW-BTC", 0.5)
            ma5 = get_ma5("KRW-BTC")
            current_price = get_current_price("KRW-BTC")
            if target_price < current_price and ma5 < current_price:
                krw = get_balance("KRW")
                if krw > 5000:
                    buy_result = upbit.buy_market_order("KRW-BTC", krw*0.9995)
                    post_message(myToken,"#crypto", "BTC buy : " +str(buy_result))
        else:
            btc = get_balance("BTC")
            if btc > 0.00008:
                sell_result = upbit.sell_market_order("KRW-BTC", btc*0.9995)
                post_message(myToken,"#crypto", "BTC buy : " +str(sell_result))
        time.sleep(1)
    except Exception as e:
        print(e)
        post_message(myToken,"#crypto", e)
        time.sleep(1)
