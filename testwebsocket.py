import websockets
import datetime
import warnings
import asyncio 
import json
import requests
import pymysql
import yaml
import pyupbit
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

def get_target_price(ticker:str, k:float=0.5) -> float:
    """변동성 돌파 전략으로 매수 목표가 조회"""
    df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)
    df = df[-2:]

    target_price:float = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price

def get_ma5(ticker:str):
    df = pyupbit.get_daily_ohlcv_from_base(ticker=ticker, base=23.99)
    df = df[4:]
    ma5 = df['close'].rolling(5).mean().iloc[-1]
    return ma5

def get_balances(ticker:str="KRW") -> float:
    """잔고 조회"""
    balances:object = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0

async def upbit_ws_client():
    uri = "wss://api.upbit.com/websocket/v1"

    async with websockets.connect(uri,  ping_interval=60) as websocket:
        subscribe_fmt = [ 
            {"ticket":"multiple_coins"},
            {
                "type": "trade",
                "codes":["KRW-BTC","KRW-ETC","KRW-ETH", "KRW-XRP","KRW-DOGE","KRW-SOL"],
                "isOnlyRealtime": True
            },
            {"format":"SIMPLE"}
        ]
        subscribe_data = json.dumps(subscribe_fmt)
        await websocket.send(subscribe_data)
        
        while True:
            data = await websocket.recv()
            data = json.loads(data)
            target_price = get_target_price(ticker={data['cd']})
            ma5 = get_ma5(ticker={data['cd']})
            now_total_cash:float = get_balances() # 현재 보유 현금 조회
            # print(f"코인명 :{data['cd']} 현재가/타겟가 :{data['tp']}/{target_price} ma5 :{ma5}")

            # ma5이상 and 타겟가이상 and 미매수
            if data['tp'] > ma5 and target_price == data['tp'] and len([x['currency'] for x in upbit.get_balances() if x['currency'] != data['cd']]) != 1:
                """매수로직"""
                today_total_cash:float = upbit.get_balances()
                
                # 전날변동성에 따라서 투자비중조절
                df = pyupbit.get_daily_ohlcv_from_base(ticker=data['cd'], base=23.99)
                df = df[-1:]
                yesterday_target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * 0.5
                fluid_target_percent:float = round(2/(yesterday_target_price/data['tp'])/3, 2)
                fluid_buy_amount:float = fluid_target_percent*today_total_cash
                
                # fluid_buy_amount요청금액이 현재 예수금보다 클때 매수요청 넣기
                if fluid_buy_amount < now_total_cash:
                    buy_result = upbit.buy_market_order(data['cd'], fluid_buy_amount*0.9995)
                    
                    now:datetime = datetime.datetime.now()
                    cursor = conn.cursor()
                    cursor.execute(f"INSERT INTO coin_order_log (ticker, buy_amount, order_type, datetime) VALUE ('{data['cd']}','{fluid_buy_amount}' ,'buy' ,'{now}')") 
                    cursor.fetchall()

            """매도로직"""
            # 현재매수한 코인이 있다면 계좌 수익률계산
            if len([x for x in upbit.get_balances() if x['currency'] != "KRW"]) !=0:
                bought_list_full_info:object = [x for x in upbit.get_balances() if x['currency'] != "KRW"]
                balance_value_total:float = 0
                balance_buyed_total:float = 0
                total_value_rate:float = 0

                # 매수한코인 리스트
                bought_list:list = [] # 매수 완료된 코인 리스트
                coin_list:list = [x['currency'] for x in upbit.get_balances() if x['currency'] != "KRW"]
                for purchased_sym in coin_list:
                    bought_list.append(purchased_sym)

                # 계좌 수익률계산
                for boughted_stock in bought_list_full_info:
                    changed_ticker = 'KRW-' + boughted_stock['currency']
                    current_price = float({data['tp']})
                    boughted_stock_f = float(boughted_stock['balance'])
                    avg_buy_price_f = float(boughted_stock['avg_buy_price'])
                    
                    balance_value_total = balance_value_total + current_price * boughted_stock_f
                    balance_buyed_total = balance_buyed_total + avg_buy_price_f * boughted_stock_f
                
                if bought_list_full_info != 0 and balance_buyed_total != 0 and balance_value_total != 0:
                    total_value_rate = (balance_value_total/balance_buyed_total) - 1
                    total_value_rate = round(total_value_rate*100, 2)
                    total_value_rate

                # 계좌수익률 +-2에서 전량매도
                if float(total_value_rate) < -2 or float(total_value_rate) > +2:
                    for sym in bought_list:
                        coin_balance:float = get_balances(sym)
                        changed_sym_for_sell:str = 'KRW-' + sym[0:]
                        sell_result = upbit.sell_market_order(changed_sym_for_sell, coin_balance)
                        
                        # 매도기록 db에 저장
                        now:datetime = datetime.datetime.now()
                        cursor = conn.cursor()
                        cursor.execute(f"INSERT INTO coin_order_log (ticker, buy_amount, order_type, datetime) VALUE ('{sym}','0' ,'sell' ,'{now}')") 
                        cursor.fetchall()


async def main():
    await upbit_ws_client()

asyncio.run(main())