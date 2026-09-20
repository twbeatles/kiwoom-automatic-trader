"""REST transport base (SRP: session/rate-limit/request/TR codes only)."""

import logging
import threading
import time
from typing import Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import KiwoomAuth
from .endpoints import LIVE_REST_BASE_URL


class RestTransport:
    """Transport + TR-code table. Domain mixins build on this."""

    BASE_URL = LIVE_REST_BASE_URL

    TR_CODES = {
        # 시세 조회
        "STOCK_CURRENT": "ka10001",      # 주식기본정보요청/현재가
        "STOCK_HOGA": "ka10004",         # 주식호가요청
        "STOCK_DAILY": "ka10005",        # 일봉차트
        "STOCK_MINUTE": "ka10006",       # 분봉차트
        "STOCK_TICK": "ka10007",         # 틱차트
        "STOCK_WEEKLY": "ka10008",       # 주봉/월봉차트
        "SECTOR_INDEX": "ka10010",       # 업종지수차트/시세
        
        # 계좌 조회
        "ACCOUNT_BALANCE": "ka30001",    # 계좌평가잔고
        "ACCOUNT_DEPOSIT": "ka30002",    # 예수금상세
        "ACCOUNT_LIST": "ka30003",       # 계좌목록조회
        
        # 주문 (키움 REST 국내주식 주문 표준 api-id)
        "ORDER_BUY": "kt10000",          # 주식매수주문
        "ORDER_SELL": "kt10001",         # 주식매도주문
        "ORDER_MODIFY": "kt10002",       # 주식정정주문
        "ORDER_CANCEL": "kt10003",       # 주식취소주문
        "ORDER_STOCK": "kt10000",        # 호환용 매수 alias
        
        # 순위/기타
        "RANK_VOLUME": "ka20001",        # 거래량상위
        "RANK_FLUCTUATION": "ka20002",   # 등락률상위
        "CONDITION_LIST": "ka20003",     # 조건식목록
        "CONDITION_SEARCH": "ka20004",   # 조건검색
        "INVESTOR_TRADING": "ka20005",   # 투자자별매매동향
        "PROGRAM_TRADING": "ka20006",    # 프로그램매매동향
        "MARKET_STATUS": "ka20007",      # 시장운영정보
        "INDEX_QUOTE": "ka20008",        # 지수현재가
        "VI_STATUS": "ka20009",          # VI발동현황

        # 미체결 / 체결
        "ORDER_OPEN": "ka10075",         # 미체결주문조회
        "ORDER_EXECUTED": "ka10076",     # 당일체결주문조회
    }

    def __init__(self, auth: KiwoomAuth, base_url: Optional[str] = None):
        """
        Args:
            auth: KiwoomAuth 인스턴스 (인증 관리)
        """
        self.auth = auth
        self.logger = logging.getLogger('KiwoomRESTClient')
        self.base_url = str(base_url or getattr(auth, "base_url", self.BASE_URL) or self.BASE_URL).rstrip("/")
        self.session_namespace = str(getattr(auth, "session_namespace", "kiwoom_live") or "kiwoom_live")
        
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
        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            **self.auth.get_auth_header(),
            "cont-yn": str(cont_yn or "N"),
        }
        if tr_code:
            headers["api-id"] = str(tr_code)
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
