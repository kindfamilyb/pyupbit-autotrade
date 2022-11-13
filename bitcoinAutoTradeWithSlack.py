import time
import pyupbit
import datetime
import requests
import yaml
import pymysql
import warnings 
import pandas as pd
warnings.simplefilter(action='ignore', category=FutureWarning) # FutureWarning 제거

with open('config.yaml', encoding='UTF-8') as f:
    _cfg = yaml.load(f, Loader=yaml.FullLoader)
upbit_access = _cfg['UPBIT_ACCESS']
upbit_secret = _cfg['UPBIT_SECRET']
slack_myToken = _cfg['SLACK_TOKEN']
DISCORD_WEBHOOK_URL = _cfg['DISCORD_WEBHOOK_URL']
TRY_COIN_LIST = _cfg['TRY_COIN_LIST']

access = upbit_access
secret = upbit_secret
myToken = slack_myToken

try_symbol_list = TRY_COIN_LIST # 매수 희망 종목 리스트 비트코인, 이더리룸, 이더리움클래식, 리플, 도지코인, 비트코인골드

conn = pymysql.connect(
    host='localhost', 
    port=3306, 
    db='coin_auto_trade', 
    user='root', 
    passwd='17442638', 
    autocommit=True
)

# 업비트 로그인
upbit = pyupbit.Upbit(access, secret)

# def post_message(token, channel, text):
#     """슬랙 메시지 전송"""
#     response = requests.post("https://slack.com/api/chat.postMessage",
#         headers={"Authorization": "Bearer "+token},
#         data={"channel": channel,"text": text}
#     )

def send_message(msg):
    """디스코드 메세지 전송"""
    now = datetime.datetime.now()
    message = {"content": f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {str(msg)}"}
    requests.post(DISCORD_WEBHOOK_URL, data=message, headers={'User-Agent': 'Mozilla/5.0'})
    print(message)

def get_target_price(ticker, k):
    """변동성 돌파 전략으로 매수 목표가 조회"""
    df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)
    df = df[-2:]

    target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]

def get_start_time(ticker):
    """시작 시간 조회"""
    df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)
    df = df[-1:]
    start_time = df.index[0]
    return start_time

def get_ma5(ticker):
    """5일 이평선 조회"""
    df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)
    df = df[4:]
    ma5 = df['close'].rolling(5).mean().iloc[-1]
    return ma5

def get_ma5_checked_try_symbol_list(try_symbol_list):
    """구매희망종목 중 5일 이평선이상종목"""
    ma5_checked_try_symbol_list = []
    for try_symbol in try_symbol_list:
        if get_ma5(try_symbol) < get_current_price(try_symbol):
            ma5_checked_try_symbol_list.append(try_symbol)
    return ma5_checked_try_symbol_list

# 구매할 종목리스트 = 구매희망종목들 - 오늘구매한종목들
def get_today_plan_to_buy_list(ma5_checked_try_symbol_list_list):
    today_bought_coin_list_cursor = conn.cursor()
    for_today_bought_coin_list_sql = "select * from coin_order_log where order_type = 'buy' and TO_CHAR(datetime, 'YYYYMMDD') = TO_CHAR(NOW(), 'YYYYMMDD') order by datetime;"
    today_bought_coin_list_cursor.execute(for_today_bought_coin_list_sql)
    today_bought_coin_list = today_bought_coin_list_cursor.fetchall()

    today_bought_coin_list = []
    for today_bought_coin_tuple in today_bought_coin_list:
        today_bought_coin_list.append(today_bought_coin_tuple[0])

    today_bought_coin_list = set(today_bought_coin_list)
    ma5_checked_try_symbol_list = set(ma5_checked_try_symbol_list_list)

    today_plan_to_buy_list = ma5_checked_try_symbol_list - today_bought_coin_list
    today_plan_to_buy_list = list(today_plan_to_buy_list)

    return today_plan_to_buy_list

def get_balances(ticker):
    """잔고 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0

def get_coin_balance_list():
    """매수종목리스트"""
    bought_list = [x['currency'] for x in upbit.get_balances() if x['currency'] != "KRW"]
    return bought_list

def check_target_alert(try_symbol_list):
    """접속확인 및 타겟프라이스 확인"""
    ma5_checked_try_symbol_list = []
    ma5_checked_try_symbol_list = get_ma5_checked_try_symbol_list(try_symbol_list)
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if len(ma5_checked_try_symbol_list) == 0:
        print(f"하락장-매수예정코인없음({now})")
        send_message(f"하락장-매수예정코인없음({now})")
        return

    print(f"상승장-매수예정코인리스트")
    send_message(f"상승장-매수예정코인리스트") 
    for ma5_checked_try_symbol in ma5_checked_try_symbol_list:
        message = f"{ma5_checked_try_symbol} : {get_current_price(ma5_checked_try_symbol)} (현재가) / {get_target_price(ma5_checked_try_symbol, 0.5)} (타겟가)"
        print(message)
        send_message(message) 

def send_buy_order(today_plan_to_buy_coin, today_plan_to_buy_list, fluid_buy_amount):
    """매수"""
    print(f"구매직전구매목록: {today_plan_to_buy_list}/구매직전타겟가: {target_price}/구매직전요청금액: {fluid_buy_amount}")
    send_message(f"구매직전구매목록: {today_plan_to_buy_list}/구매직전타겟가: {target_price}/구매직전요청금액: {fluid_buy_amount}")
    
    buy_result = upbit.buy_market_order(today_plan_to_buy_coin, fluid_buy_amount*0.9995)

    send_message(f"{today_plan_to_buy_coin} buy : {str(buy_result)}" )
    check_target_alert(today_plan_to_buy_list)

    # 매수기록 db에 저장
    now = datetime.datetime.now()
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO coin_order_log (ticker, buy_amount, order_type, datetime, buy_percent) VALUE ('{ma5_checked_try_symbol}','{buy_amount}' ,'buy' ,'{now}'), '{buy_percent}'") 
    cursor.fetchall()

def send_all_balances_sell_order(bought_list):
    """전량매도"""
    for sym in bought_list:
        coin_balance = get_balances(sym)
        changed_sym_for_sell = 'KRW-' + sym[0:]
        sell_result = upbit.sell_market_order(changed_sym_for_sell, coin_balance)
        send_message(f"{sym} sell :{str(sell_result)}")
        
        # 매도기록 db에 저장
        now = datetime.datetime.now()
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO coin_order_log (ticker, buy_amount, order_type, datetime, buy_percent) VALUE ('{sym}','0' ,'sell' ,'{now}'), '0'") 
        cursor.fetchall()

def get_total_value_rate():
    """계좌수익률"""
    # 수익률 = ((현재주식가격-구매가격)/구매가격)*100
    # 총수익률 = (평가액총액(:현재가*매수수량)/매입금총액(:평균매입금*매수수량))-1
    # 평가액총액 = (현재가*매수수량)  
    # 매입금총액 = 평균매입금*매수수량
    bought_list_full_info = [x for x in upbit.get_balances() if x['currency'] != "KRW"]
    balance_value_total = 0
    balance_buyed_total = 0
    total_value_rate = 0

    for boughted_stock in bought_list_full_info:
        changed_ticker = 'KRW-' + boughted_stock['currency']
        current_price = float(get_current_price(changed_ticker))
        boughted_stock_f = float(boughted_stock['balance'])
        avg_buy_price_f = float(boughted_stock['avg_buy_price'])
        
        balance_value_total = balance_value_total + current_price * boughted_stock_f
        balance_buyed_total = balance_buyed_total + avg_buy_price_f * boughted_stock_f
    
    if bought_list_full_info != 0 and balance_buyed_total != 0 and balance_value_total != 0:
        total_value_rate = (balance_value_total/balance_buyed_total) - 1
        total_value_rate = round(total_value_rate*100, 2)

        return total_value_rate

    return total_value_rate


def get_today_total_cash():
    """새벽 1시1분 3초이하에서 db에 저장한 기준 예수금 가져오기"""
    today_total_cash_cursor = conn.cursor()                
    today_total_cash_sql = "select total_cash from total_cash where TO_CHAR(datetime, 'YYYYMMDD') = TO_CHAR(NOW(), 'YYYYMMDD') order by datetime limit 1;"
    today_total_cash_cursor.execute(today_total_cash_sql)
    today_today_total_cash = today_total_cash_cursor.fetchall()

    today_total_cash = today_today_total_cash[0][0]
    return today_total_cash


def target_time_buy_coin_sell(total_value_rate):
    """타겟시간에 구매한 종목은 +-2에서 매도"""
    cursor_for_target_time = conn.cursor()
    sql_for_target_time = "select ticker from coin_order_log where order_type = 'buy' and TO_CHAR(datetime, 'YYYYMMDD') = TO_CHAR(NOW(), 'YYYYMMDD') and date_format(datetime, '%H') > 13 and date_format(datetime, '%H') < 23 order by datetime;"
    cursor_for_target_time.execute(sql_for_target_time)
    today_target_time_bought_list_tuple = cursor_for_target_time.fetchall()

    today_target_time_bought_list = []
    for today_target_time_bought_tuple in today_target_time_bought_list_tuple:
        today_target_time_bought_list.append(today_target_time_bought_tuple[0])

    if total_value_rate > 2 or total_value_rate < -2:
        send_all_balances_sell_order(today_target_time_bought_list)

# 시작 메세지(잔고,시작메시지) 슬랙 전송
print("autotrade start")
send_message("autotrade start") 
check_target_alert(try_symbol_list)

try:
    while True:
        target_buy_count = 3 # 최대 매수 코인수

        ma5_checked_try_symbol_list = [] # 구매희망 종목 중 5일이평선 이상인 종목들 
        ma5_checked_try_symbol_list_list = get_ma5_checked_try_symbol_list(try_symbol_list)

        bought_list = [] # 매수 완료된 코인 리스트
        coin_list = get_coin_balance_list() # 보유 코인 조회
        for purchased_sym in coin_list:
            bought_list.append(purchased_sym)

        now = datetime.datetime.now()
        start_time = get_start_time("KRW-BTC")
        end_time = start_time + datetime.timedelta(days=1)
        
        now_total_cash = get_balances("KRW") # 현재 보유 현금 조회

        # 1시1분3초 기준으로 오늘 예수금 기준액 저장
        if now.hour == 1 and now.minute == 1 and now.second <=3:    
            for_total_cash_cursor = conn.cursor()
            for_total_cash_sql_massage = f"INSERT INTO total_cash (total_cash, datetime) VALUE ('{now_total_cash}','{now}')"
            for_total_cash_cursor.execute(for_total_cash_sql_massage) 
            row = for_total_cash_cursor.fetchall()

        # 매시간 30분에 접속확인 알람
        if now.minute == 30 and now.second <= 5:
            print(f"현재구매목록: {bought_list}")
            send_message(f"현재구매목록: {bought_list}")
            if len(bought_list) > 0:
                total_value_rate = get_total_value_rate() # 현재 계좌 수익률
                
            check_target_alert(try_symbol_list)
            time.sleep(5)

        # 실행부(비지니스로직)
        if start_time < now < end_time - datetime.timedelta(seconds=10):
            # print("step0")
            # 오늘 매수한 종목이 하나라도 있으면
            if len(bought_list) > 0:
                
                # print("step1")
                total_value_rate = get_total_value_rate()
                # 오늘 구매한 종목중에 타겟시간에 매수한 종목이 있다면 전체계좌수익률 +-2구간에서 전량매도
                # [to-do]개별종목이 +-2일때 매도하는 방향으로 수정해야할것으로 보임
                if int(now.strftime('%H')) > 13 and int(now.strftime('%H')) < 24:
                    target_time_buy_coin_sell(total_value_rate)
                    continue
                
                # print("step2")
                # 만약 계좌 수익률이 -10%를 넘으면 전량 매도
                if float(total_value_rate) < -10 or float(total_value_rate) < +10:
                    send_all_balances_sell_order(bought_list)
                    continue
            
            # print("step3")
            # 구매코인의 숫자가 최대구매희망 코인 수 보다 크면 빠져나가기
            if len(bought_list) >= target_buy_count:
                continue

            # print("step4")
            # 현재 예수금 5천원 이하이면 빠져나가기
            if now_total_cash < 5000:
                continue

            # print("step5")
            # 오늘 매수할 종목리스트(ma5, 오늘 안산종목)
            # [로직점검 상황1]  상승장인 종목은 많지만 산게 하나도 없으면 today_plan_to_buy_list로 ma5_checked_try_symbol_list_list가 다 들어와야 하는 상황
            today_plan_to_buy_list = []
            today_plan_to_buy_list = get_today_plan_to_buy_list(ma5_checked_try_symbol_list_list)

            # print("step6")
            for today_plan_to_buy_coin in today_plan_to_buy_list:
                target_price = get_target_price(today_plan_to_buy_coin, 0.5)
                current_price = get_current_price(today_plan_to_buy_coin)
                
                # print("step7")
                # 매수희망가격이 현재가격보다 높으면 빠져나가기
                if target_price > current_price:
                    continue
                
                # print("step8")
                # 오늘 기준에 적합하지만 안산종목이 한개도 없으면 빠져나가기( 살 종목은 다 산상태 )
                if len(today_plan_to_buy_list) == 0:
                    continue
                
                # print("step9")
                # 전날변동성에 따라서 투자비중조절
                df = pyupbit.get_daily_ohlcv_from_base(ticker=today_plan_to_buy_coin, base=23.99)
                df = df[-1:]
                yesterday_target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * 0.5
                
                # print("step10")
                # (타깃변동성(2%)/전일변동성((전일고점-전일저점)/현재가)/투자대상가상화폐수
                today_total_cash = get_today_total_cash()

                fluid_target_percent = round(2/(yesterday_target_price/get_current_price(today_plan_to_buy_coin))/3, 2)
                fluid_buy_amount = fluid_target_percent*today_total_cash
                send_buy_order(today_plan_to_buy_coin, today_plan_to_buy_list, fluid_buy_amount)
        else:
            send_all_balances_sell_order(bought_list)
        time.sleep(1)
except Exception as e:
    print(e)
    send_message(e)
    time.sleep(2)