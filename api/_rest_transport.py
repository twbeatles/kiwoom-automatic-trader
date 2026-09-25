"""REST transport base (SRP: session/rate-limit/request/codes/paths only)."""

import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import KiwoomAuth
from .endpoints import LIVE_REST_BASE_URL

if TYPE_CHECKING:
    from .websocket_client import KiwoomWebSocketClient


class RestTransport:
    """Transport + TR-code table. Domain mixins build on this."""

    ws_client: Optional["KiwoomWebSocketClient"]

    BASE_URL = LIVE_REST_BASE_URL

    TR_CODES = {
        # 시세/종목
        "STOCK_CURRENT": "ka10001",      # 주식기본정보요청
        "STOCK_HOGA": "ka10004",         # 주식호가요청
        "STOCK_DAILY": "ka10081",        # 주식일봉차트조회요청
        "STOCK_MINUTE": "ka10080",       # 주식분봉차트조회요청
        "STOCK_TICK": "ka10079",         # 주식틱차트조회요청
        "STOCK_WEEKLY": "ka10082",       # 주식주봉차트조회요청
        "SECTOR_INDEX": "ka20001",       # 업종현재가 (호환)

        # 계좌
        "ACCOUNT_BALANCE": "kt00018",    # 계좌평가잔고내역요청
        "ACCOUNT_DEPOSIT": "kt00001",    # 예수금상세현황요청
        "ACCOUNT_LIST": "ka00001",       # 계좌번호조회

        # 주문
        "ORDER_BUY": "kt10000",          # 주식매수주문
        "ORDER_SELL": "kt10001",         # 주식매도주문
        "ORDER_MODIFY": "kt10002",       # 주식정정주문
        "ORDER_CANCEL": "kt10003",       # 주식취소주문
        "ORDER_STOCK": "kt10000",        # 호환용 매수 alias

        # 순위/시세 확장 (Kiwoom-Securities/Kiwoom-REST-API 예제 기준)
        "RANK_VOLUME": "ka10030",        # 당일거래량상위요청
        "RANK_FLUCTUATION": "ka10027",   # 전일대비등락률상위요청
        "CONDITION_LIST": "ka10171",     # 조건검색 목록조회 (WebSocket CNSRLST)
        "CONDITION_SEARCH": "ka10172",   # 조건검색 요청 일반 (WebSocket CNSRREQ)
        "INVESTOR_TRADING": "ka10045",   # 종목별기관매매추이요청
        "PROGRAM_TRADING": "ka90013",    # 종목일별프로그램매매추이요청
        "INDEX_QUOTE": "ka20001",        # 업종현재가요청
        "VI_STATUS": "ka10054",          # 변동성완화장치발동종목요청

        # 미체결 / 체결
        "ORDER_OPEN": "ka10075",         # 미체결요청
        "ORDER_EXECUTED": "ka10076",     # 체결요청

        # 실현손익 (공식 TOC: ka10072 일자별종목별실현손익_일자,
        # ka10073 일자별종목별실현손익_기간, ka10074 일자별실현손익)
        "PNL_DAILY": "ka10074",          # 일자별실현손익요청
        "PNL_STOCK_DATE": "ka10072",     # 일자별종목별실현손익요청_일자
        "PNL_STOCK_PERIOD": "ka10073",   # 일자별종목별실현손익요청_기간

        # 증권사 매매동향 (공식 TOC: ka10078 증권사별종목매매동향요청)
        "BROKER_STOCK_TREND": "ka10078",

        # 종목정보 (공식 TOC: ka10100 종목정보조회, ka10101 업종코드,
        # ka10102 회원사 리스트)
        "STOCK_INFO_DETAIL": "ka10100",
        "SECTOR_CODE_LIST": "ka10101",
        "MEMBER_LIST": "ka10102",

        # 조건검색 실시간 (WebSocket 전용: ka10173 CNSRREQ search_type=1,
        # ka10174 CNSRCLR)
        "CONDITION_REALTIME": "ka10173",
        "CONDITION_REALTIME_STOP": "ka10174",
    }

    PATHS = {
        "stkinfo": "/api/dostk/stkinfo",
        "mrkcond": "/api/dostk/mrkcond",
        "chart": "/api/dostk/chart",
        "acnt": "/api/dostk/acnt",
        "ordr": "/api/dostk/ordr",
        "rkinfo": "/api/dostk/rkinfo",
        "sect": "/api/dostk/sect",
    }

    DEFAULT_EXCHANGE = "KRX"

    def __init__(self, auth: KiwoomAuth, base_url: Optional[str] = None):
        """
        Args:
            auth: KiwoomAuth 인스턴스 (인증 관리)
        """
        self.auth = auth
        self.logger = logging.getLogger('KiwoomRESTClient')
        self.base_url = str(base_url or getattr(auth, "base_url", self.BASE_URL) or self.BASE_URL).rstrip("/")
        self.session_namespace = str(getattr(auth, "session_namespace", "kiwoom_live") or "kiwoom_live")
        self.ws_client = None
        
        # 요청 세션 설정 (재시도 로직 포함)
        self.session = self._create_session()
        
        # 요청 속도 제한 (1초에 최대 5건)
        self._last_request_time = 0
        self._min_request_interval = 0.2  # 200ms
        self._lock = threading.Lock()

    def _create_session(self) -> requests.Session:
        """재시도 로직이 포함된 세션 생성"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        
        return session

    def _rate_limit(self):
        """요청 속도 제한 (Thread-Safe)"""
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                time.sleep(self._min_request_interval - elapsed)
            self._last_request_time = time.time()

    def _request(self, method: str, endpoint: str, 
                 tr_code: Optional[str] = None,
                 data: Optional[Dict] = None,
                 params: Optional[Dict] = None,
                 cont_yn: str = "N",
                 next_key: str = "") -> Optional[Dict]:
        """
        API 요청 수행 (키움 필수 헤더 api-id 포함)
        
        Args:
            method: HTTP 메서드 (GET/POST)
            endpoint: API 엔드포인트 경로
            tr_code: 키움 TR 코드 (헤더 api-id로 전송)
            data: POST 바디 데이터
            params: 쿼리 파라미터
            cont_yn: 연속조회 여부 ('Y'/'N')
            next_key: 연속조회 키
            
        Returns:
            응답 JSON 딕셔너리, 실패 시 None
        """
        if not tr_code:
            self.logger.error("API 요청에 api-id(TR 코드)가 없습니다. 키움 REST는 api-id 누락 시 1501 오류가 납니다.")
            return None

        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            **self.auth.get_auth_header(),
            "cont-yn": str(cont_yn or "N"),
            "api-id": str(tr_code),
        }
        if next_key:
            headers["next-key"] = str(next_key)
        
        if not headers.get("Authorization"):
            self.logger.error("인증 토큰이 없습니다. 먼저 로그인해주세요.")
            return None
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=headers, params=params, timeout=10)
            else:
                response = self.session.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # 키움 API 응답 코드 확인
                return_code = result.get("return_code", 0)
                if return_code != 0:
                    error_msg = result.get("return_msg", "알 수 없는 오류")
                    self.logger.warning(f"API 오류 ({return_code}): {error_msg}")
                
                return result
            else:
                self.logger.error(f"HTTP 오류: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            self.logger.error(f"네트워크 오류: {e}")
            return None
        except Exception as e:
            self.logger.error(f"요청 예외: {e}")
            return None

    def _parse_market_type(self, output: Dict) -> str:
        """시장 구분 파싱"""
        mkt_gb = output.get("mkt_gb", "")
        if mkt_gb == "1":
            return "KOSPI"
        elif mkt_gb == "2":
            return "KOSDAQ"
        return "unknown"

    def _rank_market_tp(self, market: str) -> str:
        mapping = {
            "0": "000",
            "1": "001",
            "2": "101",
            "000": "000",
            "001": "001",
            "101": "101",
        }
        return mapping.get(str(market or "").strip(), "000")

    def _index_market_tp(self, index_code: str) -> str:
        code = str(index_code or "").strip()
        if code.startswith("101"):
            return "1"
        if code.startswith("201"):
            return "2"
        return "0"

    def _stk_cd(self, value: Any) -> str:
        text = str(value or "").strip()
        if len(text) >= 7 and text[0] in {"A", "a"}:
            return text[1:]
        return text

    def _condition_ws(self):
        ws = getattr(self, "ws_client", None)
        if ws is not None and hasattr(ws, "request_once"):
            return ws
        try:
            from .websocket_client import KiwoomWebSocketClient
            return KiwoomWebSocketClient(self.auth)
        except Exception as exc:
            self.logger.warning(f"조건검색 WebSocket 클라이언트를 만들 수 없습니다: {exc}")
            return None
