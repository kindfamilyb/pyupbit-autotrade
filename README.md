# 파이썬 비트코인 투자 자동화 강의 코드
## by 유튜브 조코딩 채널
### pyupbit 라이브러리를 활용하여 upbit 거래소에서 비트코인 자동매매를 하는 코드입니다.

### 파일 구성
- test.py : 잔고 조회 (1강)
- backtest.py : 백테스팅 코드 (2강)
- bestK.py : 가장 좋은 k 값을 찾는 코드 (2강)
- bitcoinAutoTrade.py : 변동성 돌파 전략 비트코인 자동매매 코드 (2강)
- bitcoinAutoTradeWithAI.py : 변동성 돌파 전략 + 인공지능(Prophet) 비트코인 자동매매 코드 (3강)
- bitcoinAutoTradeWithMA.py : 변동성 돌파 전략 + 15일 이동평균선 이상 비트코인 자동매매 코드 (2강)
- bitcoinAutoTradeWithSlack.py : 위 코드에 슬랙 붙여 놓은 것 (2강)
- 강의 보러가기:  https://youtube.com/playlist?list=PLU9-uwewPMe3KKFMiIm41D5Nzx_fx2PUJ
- 위 코드는 "파이썬을 이용한 비트코인 자동매매 (개정판)"을 참고하여 제작되었습니다.
- 참고 문헌: https://wikidocs.net/book/1665

### Ubuntu 서버 명령어
- (*추가)한국 기준으로 서버 시간 설정: sudo ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime
- 현재 경로 상세 출력: ls -al
- 경로 이동: cd 경로
- vim 에디터로 파일 열기: vim bitcoinAutoTrade.py
- vim 에디터 입력: i
- vim 에디터 저장: :wq!
- 패키지 목록 업데이트: sudo apt update
- pip3 설치: sudo apt install python3-pip
- pip3로 pyupbit 설치: pip3 install pyupbit
- 백그라운드 실행: nohup python3 bitcoinAutoTrade.py > output.log &
- 실행되고 있는지 확인: ps ax | grep .py
- 프로세스 종료(PID는 ps ax | grep .py를 했을때 확인 가능): kill -9 PID

![PID설명](https://user-images.githubusercontent.com/58558338/115999411-9133ef00-a626-11eb-8aa0-82a1114936e8.PNG)


### Windows 인공지능 (Prophet) 자동매매 환경 설치 방법
- 아나콘다(https://www.anaconda.com/) 설치
- pip install pyupbit
- pip install schedule
- conda install -c conda-forge fbprophet
- pip install pystan --upgrade

### Ubuntu 20.4 인공지능 (Prophet) 자동매매 환경 설치 방법
- 4GB이상 RAM 필요 (AWS t2.medium 이상)
- sudo apt update
- sudo ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime
- sudo apt install python3-pip
- pip3 install pyupbit
- pip3 install schedule
- pip3 install pystan==2.19.1.1
- pip3 install convertdate
- pip3 install fbprophet

### 카인드패밀리 추가수정 내용 ( 기준일 : 2022-10-21 )
### 업데이트내용
- yaml 파일 이용한 키관리  
- 접속확인용 슬랙알람  
- 15일 -> 5일 이동평균선기준으로 변경  
- 다중코인 거래 및 5일이동평균선에 통과한 코인에 따라 투자비중 조절(원하는데로 매수가 안되서 RDB사용해서 제작예정)  
- 계좌 전체 수익률 -10%일때 전량 매도  
- 코드개선작업  
- 전날레인지에 따라서 투자비중 가중치 주기  
- 매매기록 db저장  
- 오늘 매수이력 있으면 매수안함  
- 타겟시간(pm1~pm24)에 매수한 코인은 +-2수익률에서 매도  
- 로직점검용 step0~10  

### 최적화할부분  
- 함수선언부를 패키지로 분리해서 실행부(비지니스로직)과 분리  
- type hinting  

### 고도화할 부분 - 코드  
- ai예측 적용해서 매수 
- 거래소 전체 코인 모벤텀 반영해서 코인추려내기  
- 최적의 k값으로 적용되도록 수정  
- 상대모멘텀 | 최근 1~4주 많이 오른코인 4주간 보유  
- 역추세 | 최근 1~2주간 가장 많이 떨어진 코인 10~12주 보유  
- 거래량 상위 TOP3 코인에 가중치  
- am 6~8 거래에 가중치  

### 데브옵스  
- 젠킨스를 활용한 파일온오프  
- 장고를 활용한 관리사이트 구축  

### 참고자료  
- [책] 파이썬 증권데이터 분석  
- 조코딩유튜브  