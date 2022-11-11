import time
import pyupbit
import datetime
import requests
import yaml
import pymysql
import warnings 
import pandas as pd
warnings.simplefilter(action='ignore', category=FutureWarning) # FutureWarning 제거

from Package import coinAutoTradeModule
ct = coinAutoTradeModule.CoinAutoTradeModule()

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

try_symbol_list:list = TRY_COIN_LIST # 매수 희망 종목 리스트 비트코인, 이더리룸, 이더리움클래식, 리플, 도지코인, 비트코인골드

conn = pymysql.connect(
    host=HOST, 
    port=PORT, 
    db=DB, 
    user=USER, 
    passwd=PASSWD, 
    autocommit=True
)

# 업비트 로그인
upbit = pyupbit.Upbit(access, secret)

# 시작 메세지(잔고,시작메시지) 슬랙 전송
ct.send_message("autotrade start") 
ct.check_target_alert(try_symbol_list)

try:
    while True:
        target_buy_count:int = 3 # 최대 매수 코인수

        ma5_checked_try_symbol_list:list = [] # 구매희망 종목 중 5일이평선 이상인 종목들 
        ma5_checked_try_symbol_list:list = ct.get_ma5_checked_try_symbol_list(try_symbol_list=try_symbol_list)

        bought_list:list = [] # 매수 완료된 코인 리스트
        coin_list:list = ct.get_coin_balance_list() # 보유 코인 조회
        for purchased_sym in coin_list:
            bought_list.append(purchased_sym)

        now:datetime = datetime.datetime.now()
        start_time:datetime = ct.get_start_time()
        end_time:datetime = start_time + datetime.timedelta(days=1)
        
        now_total_cash:float = ct.get_balances() # 현재 보유 현금 조회

        # 1시1분3초 기준으로 오늘 예수금 기준액 저장
        if now.hour == 1 and now.minute == 1 and now.second <=3:    
            for_total_cash_cursor = conn.cursor()
            for_total_cash_sql_massage:str = f"INSERT INTO total_cash (total_cash, datetime) VALUE ('{now_total_cash}','{now}')"
            for_total_cash_cursor.execute(for_total_cash_sql_massage) 
            row = for_total_cash_cursor.fetchall()

        # 매시간 30분에 접속확인 알람
        if now.minute == 30 and now.second <= 5:
            ct.send_message(f"현재구매목록: {bought_list}")
            if len(bought_list) > 0:
                total_value_rate = ct.get_total_value_rate() # 현재 계좌 수익률
                
            ct.check_target_alert(try_symbol_list=try_symbol_list)
            time.sleep(5)

        # 실행부(비지니스로직)
        if start_time < now < end_time - datetime.timedelta(seconds=10):
            # print("step0")
            # 오늘 매수한 종목이 하나라도 있으면
            if len(bought_list) > 0:
                
                # print("step1")
                total_value_rate:float = ct.get_total_value_rate()
                # 오늘 구매한 종목중에 타겟시간에 매수한 종목이 있다면 전체계좌수익률 +-2구간에서 전량매도
                # [to-do]개별종목이 +-2일때 매도하는 방향으로 수정해야할것으로 보임
                if int(now.strftime('%H')) > 13 and int(now.strftime('%H')) < 24:
                    ct.terget_time_buy_coin_sell(total_value_rate=total_value_rate)
                    continue
                
                # print("step2")
                # 만약 계좌 수익률이 -10%를 넘으면 전량 매도
                if float(total_value_rate) < -10 or float(total_value_rate) < +10:
                    ct.send_all_balances_sell_order(bought_list=bought_list)
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
            # [로직점검 상황1]  상승장인 종목은 많지만 산게 하나도 없으면 today_plan_to_buy_list로 ma5_checked_try_symbol_list:list가 다 들어와야 하는 상황
            today_plan_to_buy_list:list = []
            today_plan_to_buy_list:list = ct.get_today_plan_to_buy_list(ma5_checked_try_symbol_list)

            # print("step6")
            for today_plan_to_buy_coin in today_plan_to_buy_list:
                target_price:float = ct.get_target_price(ticker=today_plan_to_buy_coin)
                current_price:float = ct.get_current_price(ticker=today_plan_to_buy_coin)
                
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
                today_total_cash:float = ct.get_today_total_cash()

                fluid_target_percent:float = round(2/(yesterday_target_price/ct.get_current_price(today_plan_to_buy_coin))/3, 2)
                fluid_buy_amount:float = fluid_target_percent*today_total_cash
                ct.send_buy_order(today_plan_to_buy_coin, today_plan_to_buy_list, target_price, fluid_buy_amount)
        else:
            ct.send_all_balances_sell_order(bought_list=bought_list)
        time.sleep(1)
except Exception as e:
    ct.send_message(msg=e)
    time.sleep(2)