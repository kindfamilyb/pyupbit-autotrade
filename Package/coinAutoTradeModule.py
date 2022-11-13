import datetime
import warnings
import pandas as pd
import pymysql
import pyupbit
import requests
import yaml
warnings.simplefilter(action='ignore', category=FutureWarning) # FutureWarning 제거

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
myToken = slack_myToken

try_symbol_list = TRY_COIN_LIST # 매수 희망 종목 리스트 비트코인, 이더리룸, 이더리움클래식, 리플, 도지코인, 비트코인골드

conn = pymysql.connect(
    host=HOST, 
    port=PORT, 
    db=DB, 
    user=USER, 
    passwd=PASSWD, 
    autocommit=True
)

# # 업비트 로그인
upbit = pyupbit.Upbit(access, secret)

class CoinAutoTradeModule:
    # def __init__(self):
        # self.get_current_price()

    def post_message(self, token:str, channel:str, text:str) -> bool:
        """슬랙 메시지 전송"""
        response:str = requests.post("https://slack.com/api/chat.postMessage",
            headers={"Authorization": "Bearer "+token},
            data={"channel": channel,"text": text}
        )

    def send_message(self, msg:str) -> bool:
        """디스코드 메세지 전송"""
        now:datetime = datetime.datetime.now()
        message:str = {"content": f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {str(msg)}"}
        requests.post(DISCORD_WEBHOOK_URL, data=message, headers={'User-Agent': 'Mozilla/5.0'})
        print(message)

    def get_target_price(self, ticker:str, k:float=0.5) -> float:
        """변동성 돌파 전략으로 매수 목표가 조회"""
        df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)
        df = df[-2:]

        target_price:float = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
        return target_price

    def get_current_price(self, ticker:str) -> float:
        """현재가 조회"""
        return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]

    def get_start_time(self, ticker:str="KRW-BTC"):
        """시작 시간 조회"""
        df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)
        df = df[-1:]
        start_time = df.index[0]
        return start_time

    def get_ma5(self, ticker:str):
        """5일 이평선 조회"""
        df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)
        df = df[4:]
        ma5 = df['close'].rolling(5).mean().iloc[-1]
        return ma5

    def get_ma5_checked_try_symbol_list(self, try_symbol_list:list) -> list:
        """구매희망종목 중 5일 이평선이상종목"""
        ma5_checked_try_symbol_list:list = []
        for try_symbol in try_symbol_list:
            if self.get_ma5(try_symbol) < self.get_current_price(ticker=try_symbol):
                ma5_checked_try_symbol_list.append(try_symbol)
        return ma5_checked_try_symbol_list

    # 구매할 종목리스트 = 구매희망종목들 - 오늘구매한종목들
    def get_today_plan_to_buy_list(self, ma5_checked_try_symbol_list:list) -> list:
        today_bought_coin_list_cursor:object = conn.cursor()
        for_today_bought_coin_list_sql:str = "select DISTINCT ticker from coin_order_log where order_type = 'buy' and TO_CHAR(datetime, 'YYYYMMDD') = TO_CHAR(NOW(), 'YYYYMMDD') order by datetime;"
        today_bought_coin_list_cursor.execute(for_today_bought_coin_list_sql)
        today_bought_coin_list_tuple = today_bought_coin_list_cursor.fetchall()
        # print(f"오늘산종목리스트1 {today_bought_coin_list_tuple}")

        today_bought_coin_list:list = []
        for today_bought_coin_tuple in today_bought_coin_list_tuple:
            today_bought_coin_list.append(today_bought_coin_tuple[0])
        # print(f"오늘산종목리스트 {today_bought_coin_list}")

        today_bought_coin_list:set = set(today_bought_coin_list)
        ma5_checked_try_symbol_list:set = set(ma5_checked_try_symbol_list)

        today_plan_to_buy_list:set = ma5_checked_try_symbol_list - today_bought_coin_list
        today_plan_to_buy_list:list = list(today_plan_to_buy_list)

        return today_plan_to_buy_list

    def get_balances(self, ticker:str="KRW") -> float:
        """잔고 조회"""
        balances:object = upbit.get_balances()
        for b in balances:
            if b['currency'] == ticker:
                if b['balance'] is not None:
                    return float(b['balance'])
                else:
                    return 0
        return 0

    def get_coin_balance_list(self) -> list:
        """매수종목리스트"""
        bought_list:list = [x['currency'] for x in upbit.get_balances() if x['currency'] != "KRW"]
        return bought_list

    def check_target_alert(self, try_symbol_list:list) -> bool:
        """접속확인 및 타겟프라이스 확인"""
        ma5_checked_try_symbol_list:list = []
        ma5_checked_try_symbol_list:list = self.get_ma5_checked_try_symbol_list(try_symbol_list=try_symbol_list)
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if len(ma5_checked_try_symbol_list) == 0:
            self.send_message(f"하락장-매수예정코인없음({now})")
            return

        print(f"상승장-매수예정코인리스트")
        self.send_message(f"상승장-매수예정코인리스트") 
        for ma5_checked_try_symbol in ma5_checked_try_symbol_list:
            message = f"{ma5_checked_try_symbol} : {self.get_current_price(ticker=ma5_checked_try_symbol)} (현재가) / {self.get_target_price(ticker=ma5_checked_try_symbol, k=0.5)} (타겟가)"
            self.send_message(message)

    def send_buy_order(self, today_plan_to_buy_coin:str, today_plan_to_buy_list:list, target_price:float, fluid_buy_amount:float) -> bool:
        """매수"""
        self.send_message(f"구매직전구매목록: {today_plan_to_buy_list}/구매직전타겟가: {target_price}/구매직전요청금액: {fluid_buy_amount}")
        print('1')

        check_today_plan_to_buy_coin = []
        check_today_plan_to_buy_coin:list = [x['currency'] for x in upbit.get_balances() if x['currency'] == today_plan_to_buy_coin[4:]]
        
        print(check_today_plan_to_buy_coin)
        if len(check_today_plan_to_buy_coin) == 0:
            # 매수한 코인중에 today_plan_to_buy_coin이 없을때 요청하기
            buy_result = upbit.buy_market_order(today_plan_to_buy_coin, fluid_buy_amount*0.9995)
            self.send_message(f"{today_plan_to_buy_coin} buy : {str(buy_result)}" )
            self.check_target_alert(today_plan_to_buy_list)

        # 매수한 코인중에 today_plan_to_buy_coin이 있을때 기록 남기기
        if len(check_today_plan_to_buy_coin) != 0:
            now:datetime = datetime.datetime.now()
            cursor = conn.cursor()
            cursor.execute(f"INSERT INTO coin_order_log (ticker, buy_amount, order_type, datetime) VALUE ('{today_plan_to_buy_coin}','{fluid_buy_amount}' ,'buy' ,'{now}')") 
            cursor.fetchall()

    def send_all_balances_sell_order(self, bought_list:list) -> bool:
        """전량매도"""
        for sym in bought_list:
            coin_balance:float = self.get_balances(sym)
            changed_sym_for_sell:str = 'KRW-' + sym[0:]
            sell_result = upbit.sell_market_order(changed_sym_for_sell, coin_balance)
            self.send_message(f"{sym} sell :{str(sell_result)}")
            
            # 매도기록 db에 저장
            now:datetime = datetime.datetime.now()
            cursor = conn.cursor()
            cursor.execute(f"INSERT INTO coin_order_log (ticker, buy_amount, order_type, datetime) VALUE ('{sym}','0' ,'sell' ,'{now}')") 
            cursor.fetchall()
    

    def get_total_value_rate(self) -> float:
        """계좌수익률"""
        # 수익률 = ((현재주식가격-구매가격)/구매가격)*100
        # 총수익률 = (평가액총액(:현재가*매수수량)/매입금총액(:평균매입금*매수수량))-1
        # 평가액총액 = (현재가*매수수량)  
        # 매입금총액 = 평균매입금*매수수량
        bought_list_full_info:object = [x for x in upbit.get_balances() if x['currency'] != "KRW"]
        balance_value_total:float = 0
        balance_buyed_total:float = 0
        total_value_rate:float = 0

        for boughted_stock in bought_list_full_info:
            changed_ticker = 'KRW-' + boughted_stock['currency']
            current_price = float(self.get_current_price(ticker=changed_ticker))
            boughted_stock_f = float(boughted_stock['balance'])
            avg_buy_price_f = float(boughted_stock['avg_buy_price'])
            
            balance_value_total = balance_value_total + current_price * boughted_stock_f
            balance_buyed_total = balance_buyed_total + avg_buy_price_f * boughted_stock_f
        
        if bought_list_full_info != 0 and balance_buyed_total != 0 and balance_value_total != 0:
            total_value_rate = (balance_value_total/balance_buyed_total) - 1
            total_value_rate = round(total_value_rate*100, 2)

            return total_value_rate

        return total_value_rate


    def get_today_total_cash(self) -> float:
        """새벽 1시1분 3초이하에서 db에 저장한 기준 예수금 가져오기"""
        today_total_cash_cursor = conn.cursor()                
        today_total_cash_sql:str = "select total_cash from total_cash where TO_CHAR(datetime, 'YYYYMMDD') = TO_CHAR(NOW(), 'YYYYMMDD') order by datetime limit 1;"
        today_total_cash_cursor.execute(today_total_cash_sql)
        today_today_total_cash = today_total_cash_cursor.fetchall()

        today_total_cash:float = today_today_total_cash[0][0]
        return today_total_cash


    def target_time_buy_coin_sell(self, total_value_rate, bought_list) -> bool:
        """타겟시간에 구매한 종목은 +-2에서 매도"""
        cursor_for_target_time = conn.cursor()
        sql_for_target_time = "select ticker from coin_order_log where order_type = 'buy' and TO_CHAR(datetime, 'YYYYMMDD') = TO_CHAR(NOW(), 'YYYYMMDD') and date_format(datetime, '%H') > 13 and date_format(datetime, '%H') < 23 order by datetime;"
        cursor_for_target_time.execute(sql_for_target_time)
        today_target_time_bought_list_tuple = cursor_for_target_time.fetchall()

        today_target_time_bought_list = []
        for today_target_time_bought_tuple in today_target_time_bought_list_tuple:
            today_target_time_bought_list.append(today_target_time_bought_tuple[0])

        if total_value_rate > 2 or total_value_rate < -2:
            print('1')
            self.send_all_balances_sell_order(bought_list=bought_list)