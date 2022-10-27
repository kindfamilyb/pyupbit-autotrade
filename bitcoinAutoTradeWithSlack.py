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
DISCORD_WEBHOOK_URL = _cfg['DISCORD_WEBHOOK_URL']

access = upbit_access
secret = upbit_secret
myToken = slack_myToken

try_symbol_list = ["KRW-BTC","KRW-XRP","KRW-ETH"] # 매수 희망 종목 리스트

def post_message(token, channel, text):
    """슬랙 메시지 전송"""
    response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer "+token},
        data={"channel": channel,"text": text}
    )

def send_message(msg):
    """디스코드 메세지 전송"""
    now = datetime.datetime.now()
    message = {"content": f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {str(msg)}"}
    requests.post(DISCORD_WEBHOOK_URL, data=message)
    print(message)

def get_target_price(ticker, k):
    """변동성 돌파 전략으로 매수 목표가 조회"""
    df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)[-2:]
    target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]

def get_start_time(ticker):
    """시작 시간 조회"""
    df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)[-1:]
    start_time = df.index[0]
    return start_time

def get_ma5(ticker):
    """5일 이동 평균선 조회"""
    df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)[4:]
    ma5 = df['close'].rolling(5).mean().iloc[-1]
    return ma5

def get_ma5_checked_try_symbol_list(try_symbol_list):
    ma5_checked_try_symbol_list = []
    for try_symbol in try_symbol_list:
        if get_ma5(try_symbol) < get_current_price(try_symbol):
            ma5_checked_try_symbol_list.append(try_symbol)
    return ma5_checked_try_symbol_list

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
    bought_list = [x['currency'] for x in upbit.get_balances() if x['currency'] != "KRW"]
    return bought_list

def get_target_price_buy_percent(try_symbol_list):
    # 5일 이평선인 종목 숫자와 투자비중가져오기
    ma5_checked_try_symbol_list = []
    for try_symbol in try_symbol_list:
        if get_ma5(try_symbol) < get_current_price(try_symbol):
            ma5_checked_try_symbol_list.append(try_symbol)

    if len(ma5_checked_try_symbol_list) == 3:
        target_buy_count = 3
        buy_percent = 0.33
    elif len(ma5_checked_try_symbol_list) == 2:
        target_buy_count = 2
        buy_percent = 0.5
    elif len(ma5_checked_try_symbol_list) == 1:
        target_buy_count = 1
        buy_percent = 1
    elif len(ma5_checked_try_symbol_list) == 0:
        target_buy_count = 0
        buy_percent = 0
    return target_buy_count, buy_percent

def check_target_alert(try_symbol_list):
    """접속확인 및 타겟프라이스 확인"""
    ma5_checked_try_symbol_list = []
    ma5_checked_try_symbol_list = get_ma5_checked_try_symbol_list(try_symbol_list)
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if len(ma5_checked_try_symbol_list) == 0:
        print(f"하락장-매수예정코인없음({now})")
        send_message(f"하락장-매수예정코인없음({now})")
        return

    print(f"상승장-매수예정코인리스트({now})")
    send_message(f"상승장-매수예정코인리스트({now})") 
    for ma5_checked_try_symbol in ma5_checked_try_symbol_list:
        message = f'{ma5_checked_try_symbol} : {get_current_price(ma5_checked_try_symbol)} / {get_target_price(ma5_checked_try_symbol, 0.5)}'
        print(message)
        send_message(message) 

# 업비트 로그인
upbit = pyupbit.Upbit(access, secret)

# 시작 메세지(잔고,시작메시지) 슬랙 전송
print("autotrade start")
send_message("autotrade start") 
check_target_alert(try_symbol_list)

try:
    while True:
        # 매수 희망 종목 리스트중 '5일 이평선 이상' 조건 종목만 추려내기
        ma5_checked_try_symbol_list = []
        ma5_checked_try_symbol_list = get_ma5_checked_try_symbol_list(try_symbol_list)

        bought_list = [] # 매수 완료된 코인 리스트
        total_cash = get_balance("KRW") # 보유 현금 조회
        stock_dict = get_stock_balance() # 보유 코인 조회
        for purchased_sym in stock_dict:
            bought_list.append(purchased_sym)

        # target_buy_count, buy_percent 변수 초기화 
        # 5일이평선 이상인 코인에 대해 투자비중유동적으로 적용될 수 있도록 수정
        target_buy_count = 0 # 최대 매수 코인수
        buy_percent = 0 # 코인당 매수 비중
        target_buy_count = get_target_price_buy_percent(try_symbol_list)[0]
        buy_percent = get_target_price_buy_percent(try_symbol_list)[1]

        buy_amount = total_cash * buy_percent  # 종목별 주문 금액 계산
        soldout = False
        now = datetime.datetime.now()
        start_time = get_start_time("KRW-BTC")
        end_time = start_time + datetime.timedelta(days=1)

        # 매일 3의 배수 시간 30분에 접속확인 알람
        if now.minute == 30 and now.second <= 5:
            print(f"현재구매목록: {bought_list}")
            send_message(f"현재구매목록: {bought_list}")
            check_target_alert(try_symbol_list)
            time.sleep(5)

        if start_time < now < end_time - datetime.timedelta(seconds=10):
            if len(bought_list) < target_buy_count:
                for ma5_checked_try_symbol in ma5_checked_try_symbol_list:
                    if ma5_checked_try_symbol not in bought_list:
                        target_price = get_target_price(ma5_checked_try_symbol, 0.5)
                        current_price = get_current_price(ma5_checked_try_symbol)
                        if target_price < current_price:
                            krw = get_balance("KRW")
                            if krw > 5000 and buy_amount > 5000:
                                print(f"구매직전구매목록: {bought_list}/구매직전타겟가격: {target_price}/구매직전요청금액: {buy_amount}")
                                send_message(f"구매직전구매목록: {bought_list}/구매직전타겟가격: {target_price}/구매직전요청금액: {buy_amount}")
                                buy_result = upbit.buy_market_order(ma5_checked_try_symbol, buy_amount*0.9995)
                                send_message(f"{ma5_checked_try_symbol} buy : {str(buy_result)}" )
                                check_target_alert(try_symbol_list)
                                soldout = False
        else:
            for sym in bought_list:
                coin_balance = get_balance(sym)
                changed_sym_for_sell = 'KRW-' + sym[0:]
                sell_result = upbit.sell_market_order(changed_sym_for_sell, coin_balance)
                send_message(f"{sym} sell :{str(sell_result)}")
            soldout = True
        time.sleep(1)
except Exception as e:
    print(e)
    send_message(e)
    time.sleep(1)
