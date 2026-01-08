"""
키움증권 REST API WebSocket 클라이언트

실시간 시세 및 체결 데이터 수신을 담당합니다.
"""

import json
import logging
import asyncio
import threading
from typing import Optional, Callable, Dict, List, Set
from dataclasses import dataclass

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketClientProtocol = None

from .auth import KiwoomAuth
from .models import StockQuote, ExecutionData


@dataclass
class SubscriptionInfo:
    """구독 정보"""
    code: str
    data_type: str  # "execution", "hoga", "orderbook"
    callback: Callable


class KiwoomWebSocketClient:
    """실시간 데이터 수신을 위한 WebSocket 클라이언트"""
    
    # WebSocket 엔드포인트
    WS_URL = "wss://api.kiwoom.com/ws/realtime"
    
    # 실시간 데이터 타입
    REAL_TYPE = {
        "EXECUTION": "10",      # 주식 체결
        "HOGA": "20",           # 주식 호가
        "ORDER_EXEC": "30",     # 주문 체결
        "INDEX": "40",          # 지수
    }
    
    def __init__(self, auth: KiwoomAuth):
        """
        Args:
            auth: KiwoomAuth 인스턴스
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets 라이브러리가 필요합니다. pip install websockets")
        
        self.auth = auth
        self.logger = logging.getLogger('KiwoomWebSocketClient')
        
        # 연결 상태
        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._reconnecting = False
        
        # 구독 관리
        self._subscriptions: Dict[str, SubscriptionInfo] = {}
        self._subscribed_codes: Set[str] = set()
        
        # 콜백
        self._on_execution: Optional[Callable[[ExecutionData], None]] = None
        self._on_hoga: Optional[Callable[[str, dict], None]] = None
        self._on_order_exec: Optional[Callable[[dict], None]] = None
        self._on_connect: Optional[Callable[[], None]] = None
        self._on_disconnect: Optional[Callable[[], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None
        
        # 이벤트 루프 및 스레드
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    # =========================================================================
    # 연결 관리
    # =========================================================================
    
    def connect(self):
        """WebSocket 연결 시작 (별도 스레드에서 실행)"""
        if self._thread and self._thread.is_alive():
            self.logger.warning("이미 연결되어 있습니다.")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()
        self.logger.info("WebSocket 연결 스레드 시작")
    
    def disconnect(self):
        """WebSocket 연결 종료"""
        self._stop_event.set()
        
        if self._loop and self._ws:
            asyncio.run_coroutine_threadsafe(self._close_connection(), self._loop)
        
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        
        self._connected = False
        self.logger.info("WebSocket 연결 종료됨")
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._connected
    
    def _run_event_loop(self):
        """이벤트 루프 실행 (별도 스레드)"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._connect_and_listen())
        except Exception as e:
            self.logger.error(f"이벤트 루프 오류: {e}")
        finally:
            self._loop.close()
            self._loop = None
    
    async def _connect_and_listen(self):
        """연결 및 메시지 수신 루프"""
        retry_count = 0
        max_retries = 5
        
        while not self._stop_event.is_set():
            try:
                token = self.auth.get_token()
                if not token:
                    self.logger.error("토큰을 가져올 수 없습니다.")
                    await asyncio.sleep(5)
                    continue
                
                # WebSocket 연결
                headers = {"Authorization": f"bearer {token}"}
                
                async with websockets.connect(
                    self.WS_URL,
                    extra_headers=headers,
                    ping_interval=30,
                    ping_timeout=10
                ) as ws:
                    self._ws = ws
                    self._connected = True
                    self._reconnecting = False
                    retry_count = 0
                    
                    self.logger.info("WebSocket 연결 성공")
                    
                    if self._on_connect:
                        self._on_connect()
                    
                    # 기존 구독 복원
                    await self._restore_subscriptions()
                    
                    # 메시지 수신 루프
                    async for message in ws:
                        if self._stop_event.is_set():
                            break
                        await self._handle_message(message)
                
            except websockets.ConnectionClosed as e:
                self.logger.warning(f"WebSocket 연결 끊김: {e}")
                self._connected = False
                
                if self._on_disconnect:
                    self._on_disconnect()
                
            except Exception as e:
                self.logger.error(f"WebSocket 오류: {e}")
                self._connected = False
                
                if self._on_error:
                    self._on_error(e)
            
            # 재연결 대기
            if not self._stop_event.is_set():
                retry_count += 1
                if retry_count > max_retries:
                    self.logger.error("최대 재연결 시도 횟수 초과")
                    break
                
                wait_time = min(2 ** retry_count, 60)
                self.logger.info(f"{wait_time}초 후 재연결 시도 ({retry_count}/{max_retries})")
                await asyncio.sleep(wait_time)
    
    async def _close_connection(self):
        """연결 종료"""
        if self._ws:
            await self._ws.close()
            self._ws = None
    
    # =========================================================================
    # 구독 관리
    # =========================================================================
    
    def subscribe_execution(self, codes: List[str], callback: Callable[[ExecutionData], None]):
        """
        실시간 체결 데이터 구독
        
        Args:
            codes: 종목코드 리스트
            callback: 데이터 수신 시 호출될 콜백 함수
        """
        self._on_execution = callback
        
        for code in codes:
            key = f"exec_{code}"
            self._subscriptions[key] = SubscriptionInfo(
                code=code,
                data_type="execution",
                callback=callback
            )
            self._subscribed_codes.add(code)
        
        if self._connected and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_subscribe(codes, self.REAL_TYPE["EXECUTION"]),
                self._loop
            )
    
    def subscribe_hoga(self, codes: List[str], callback: Callable[[str, dict], None]):
        """
        실시간 호가 데이터 구독
        
        Args:
            codes: 종목코드 리스트
            callback: 데이터 수신 시 호출될 콜백 함수 (code, data)
        """
        self._on_hoga = callback
        
        for code in codes:
            key = f"hoga_{code}"
            self._subscriptions[key] = SubscriptionInfo(
                code=code,
                data_type="hoga",
                callback=callback
            )
        
        if self._connected and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_subscribe(codes, self.REAL_TYPE["HOGA"]),
                self._loop
            )
    
    def subscribe_order_execution(self, callback: Callable[[dict], None]):
        """
        주문 체결 알림 구독
        
        Args:
            callback: 체결 데이터 수신 시 호출될 콜백 함수
        """
        self._on_order_exec = callback
        
        if self._connected and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_subscribe_order(),
                self._loop
            )
    
    def unsubscribe(self, codes: List[str]):
        """구독 해제"""
        for code in codes:
            self._subscribed_codes.discard(code)
            self._subscriptions.pop(f"exec_{code}", None)
            self._subscriptions.pop(f"hoga_{code}", None)
        
        if self._connected and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_unsubscribe(codes),
                self._loop
            )
    
    def unsubscribe_all(self):
        """모든 구독 해제"""
        codes = list(self._subscribed_codes)
        self._subscribed_codes.clear()
        self._subscriptions.clear()
        
        if self._connected and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_unsubscribe(codes),
                self._loop
            )
    
    async def _send_subscribe(self, codes: List[str], real_type: str):
        """구독 요청 전송"""
        if not self._ws:
            return
        
        message = {
            "header": {
                "tr_type": "1",  # 등록
                "real_type": real_type
            },
            "body": {
                "stk_cds": ",".join(codes)
            }
        }
        
        await self._ws.send(json.dumps(message))
        self.logger.info(f"실시간 구독 요청: {codes}")
    
    async def _send_subscribe_order(self):
        """주문 체결 구독 요청"""
        if not self._ws:
            return
        
        message = {
            "header": {
                "tr_type": "1",
                "real_type": self.REAL_TYPE["ORDER_EXEC"]
            },
            "body": {}
        }
        
        await self._ws.send(json.dumps(message))
        self.logger.info("주문 체결 실시간 구독 요청")
    
    async def _send_unsubscribe(self, codes: List[str]):
        """구독 해제 요청 전송"""
        if not self._ws or not codes:
            return
        
        message = {
            "header": {
                "tr_type": "2",  # 해제
                "real_type": self.REAL_TYPE["EXECUTION"]
            },
            "body": {
                "stk_cds": ",".join(codes)
            }
        }
        
        await self._ws.send(json.dumps(message))
        self.logger.info(f"실시간 구독 해제: {codes}")
    
    async def _restore_subscriptions(self):
        """재연결 시 기존 구독 복원"""
        if not self._subscribed_codes:
            return
        
        codes = list(self._subscribed_codes)
        await self._send_subscribe(codes, self.REAL_TYPE["EXECUTION"])
        
        if self._on_order_exec:
            await self._send_subscribe_order()
    
    # =========================================================================
    # 메시지 처리
    # =========================================================================
    
    async def _handle_message(self, message: str):
        """수신된 메시지 처리"""
        try:
            data = json.loads(message)
            
            header = data.get("header", {})
            body = data.get("body", {})
            real_type = header.get("real_type", "")
            
            if real_type == self.REAL_TYPE["EXECUTION"]:
                await self._handle_execution(body)
            elif real_type == self.REAL_TYPE["HOGA"]:
                await self._handle_hoga(body)
            elif real_type == self.REAL_TYPE["ORDER_EXEC"]:
                await self._handle_order_exec(body)
            else:
                self.logger.debug(f"알 수 없는 실시간 타입: {real_type}")
                
        except json.JSONDecodeError:
            self.logger.warning(f"JSON 파싱 실패: {message[:100]}")
        except Exception as e:
            self.logger.error(f"메시지 처리 오류: {e}")
    
    async def _handle_execution(self, body: dict):
        """체결 데이터 처리"""
        if not self._on_execution:
            return
        
        exec_data = ExecutionData(
            code=body.get("stk_cd", ""),
            name=body.get("stk_nm", ""),
            exec_time=body.get("exec_tm", ""),
            exec_price=abs(int(body.get("exec_prc", 0))),
            exec_volume=int(body.get("exec_vol", 0)),
            exec_change=int(body.get("chg_amt", 0)),
            total_volume=int(body.get("acc_vol", 0)),
            ask_price=abs(int(body.get("ask_prc", 0))),
            bid_price=abs(int(body.get("bid_prc", 0)))
        )
        
        # 콜백은 메인 스레드에서 실행되도록 처리 필요
        self._on_execution(exec_data)
    
    async def _handle_hoga(self, body: dict):
        """호가 데이터 처리"""
        if not self._on_hoga:
            return
        
        code = body.get("stk_cd", "")
        self._on_hoga(code, body)
    
    async def _handle_order_exec(self, body: dict):
        """주문 체결 데이터 처리"""
        if not self._on_order_exec:
            return
        
        self._on_order_exec(body)
    
    # =========================================================================
    # 이벤트 콜백 설정
    # =========================================================================
    
    def set_on_connect(self, callback: Callable[[], None]):
        """연결 성공 콜백 설정"""
        self._on_connect = callback
    
    def set_on_disconnect(self, callback: Callable[[], None]):
        """연결 끊김 콜백 설정"""
        self._on_disconnect = callback
    
    def set_on_error(self, callback: Callable[[Exception], None]):
        """오류 발생 콜백 설정"""
        self._on_error = callback
