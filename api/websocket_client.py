"""
키움증권 REST API WebSocket 클라이언트

실시간 시세 및 체결 데이터 수신을 담당합니다.
"""

import json
import logging
import asyncio
import threading
import time
from typing import Any, Optional, Callable, Dict, List, Set, cast
from dataclasses import dataclass
from PyQt6.QtCore import QCoreApplication, QObject, QThread, pyqtSignal

ws_connect: Optional[Callable[..., Any]] = None
try:
    try:
        import websockets.asyncio.client as websockets_client
    except ImportError:
        try:
            import websockets.client as websockets_client
        except ImportError:
            import websockets as websockets_client
    from websockets.exceptions import ConnectionClosed
    ws_connect = cast(Optional[Callable[..., Any]], getattr(websockets_client, "connect", None))
    WEBSOCKETS_AVAILABLE = ws_connect is not None
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    ConnectionClosed = Exception

from .auth import KiwoomAuth
from .endpoints import LIVE_WS_URL
from .models import StockQuote, ExecutionData, IndexTick


def _ws_int(value: Any, default: int = 0) -> int:
    try:
        text = str(value or "").strip().replace(",", "")
        if text in {"", "-", "+", "--"}:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


@dataclass
class SubscriptionInfo:
    """구독 정보"""
    code: str
    data_type: str  # "execution", "hoga", "orderbook"
    callback: Callable


class _MainThreadDispatcher(QObject):
    invoke = pyqtSignal(object, tuple)

    def __init__(self):
        super().__init__()
        self.invoke.connect(self._invoke)

    def _invoke(self, callback: Callable, args: tuple):
        callback(*args)


def _main_thread_dispatcher() -> Optional[_MainThreadDispatcher]:
    app = QCoreApplication.instance()
    if app is None:
        return None
    existing = getattr(app, "_kiwoom_ws_dispatcher", None)
    if isinstance(existing, _MainThreadDispatcher):
        return existing
    if QThread.currentThread() != app.thread():
        return None
    dispatcher = _MainThreadDispatcher()
    dispatcher.moveToThread(app.thread())
    setattr(app, "_kiwoom_ws_dispatcher", dispatcher)
    return dispatcher


class KiwoomWebSocketClient:
    """실시간 데이터 수신을 위한 WebSocket 클라이언트"""
    
    # WebSocket 엔드포인트
    WS_URL = LIVE_WS_URL
    
    # 실시간 데이터 타입 (키움 공식 WebSocket type)
    REAL_TYPE = {
        "EXECUTION": "0B",      # 주식체결
        "HOGA": "0D",           # 주식호가잔량
        "ORDER_EXEC": "00",     # 주문체결
        "INDEX": "0J",          # 업종지수
        "VI": "1h",             # VI발동/해제
    }
    
    def __init__(self, auth: KiwoomAuth, ws_url: Optional[str] = None):
        """
        Args:
            auth: KiwoomAuth 인스턴스
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets 라이브러리가 필요합니다. pip install websockets")
        
        self.auth = auth
        self.logger = logging.getLogger('KiwoomWebSocketClient')
        self.ws_url = str(ws_url or getattr(auth, "ws_url", self.WS_URL) or self.WS_URL)
        self.session_namespace = str(getattr(auth, "session_namespace", "kiwoom_live") or "kiwoom_live")
        
        # 연결 상태
        self._ws: Optional[Any] = None
        self._connected = False
        self._reconnecting = False
        
        # 구독 관리
        self._subscriptions: Dict[str, SubscriptionInfo] = {}
        self._subscribed_codes: Set[str] = set()
        
        # 콜백
        self._on_execution: Optional[Callable[[ExecutionData], None]] = None
        self._on_hoga: Optional[Callable[[str, dict], None]] = None
        self._on_order_exec: Optional[Callable[[dict], None]] = None
        self._on_index: Optional[Callable[[IndexTick], None]] = None
        self._on_vi: Optional[Callable[[dict], None]] = None
        self._on_connect: Optional[Callable[[], None]] = None
        self._on_disconnect: Optional[Callable[[], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None
        self._qt_dispatcher: Optional[_MainThreadDispatcher] = None
        
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
        # 토큰 획득 연속 실패 시 점진적 백오프(인증 서버 부하/lock 경쟁 억제).
        token_fail_count = 0
        token_backoff_schedule = (5, 10, 20, 60)

        while not self._stop_event.is_set():
            try:
                token = self.auth.get_token()
                if not token:
                    idx = min(token_fail_count, len(token_backoff_schedule) - 1)
                    wait = token_backoff_schedule[idx]
                    token_fail_count += 1
                    self.logger.error(f"토큰을 가져올 수 없습니다. {wait}초 후 재시도({idx + 1}).")
                    await asyncio.sleep(wait)
                    continue
                token_fail_count = 0
                
                # WebSocket 연결
                headers = {"Authorization": f"bearer {token}"}
                connect_fn = ws_connect
                if connect_fn is None:
                    raise RuntimeError("websocket connect function unavailable")
                
                async with connect_fn(
                    self.ws_url,
                    extra_headers=headers,
                    ping_interval=30,
                    ping_timeout=10
                ) as ws:
                    self._ws = ws
                    self._connected = True
                    self._reconnecting = False
                    retry_count = 0
                    
                    self.logger.info("WebSocket 연결 성공")
                    await ws.send(json.dumps({"trnm": "LOGIN", "token": token}))
                    
                    if self._on_connect:
                        self._on_connect()
                    
                    # 기존 구독 복원
                    await self._restore_subscriptions()
                    
                    # 메시지 수신 루프
                    async for raw_message in ws:
                        if self._stop_event.is_set():
                            break
                        message = raw_message.decode("utf-8", errors="ignore") if isinstance(raw_message, bytes) else str(raw_message)
                        await self._handle_message(message)
                
            except ConnectionClosed as e:
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
                    self.logger.warning(
                        f"최대 재연결 시도 횟수 초과 ({max_retries}회), "
                        "60초 대기 후 재시도 초기화"
                    )
                    await asyncio.sleep(60)
                    retry_count = 0
                    continue
                
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
        self._qt_dispatcher = _main_thread_dispatcher() or self._qt_dispatcher
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
        self._qt_dispatcher = _main_thread_dispatcher() or self._qt_dispatcher
        self._on_hoga = callback
        
        for code in codes:
            key = f"hoga_{code}"
            self._subscriptions[key] = SubscriptionInfo(
                code=code,
                data_type="hoga",
                callback=callback
            )
            self._subscribed_codes.add(code)
        
        if self._connected and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_subscribe(codes, self.REAL_TYPE["HOGA"]),
                self._loop
            )

    def subscribe_index(self, codes: List[str], callback: Callable[[IndexTick], None]):
        """실시간 지수 데이터 구독"""
        self._qt_dispatcher = _main_thread_dispatcher() or self._qt_dispatcher
        self._on_index = callback

        for code in codes:
            key = f"index_{code}"
            self._subscriptions[key] = SubscriptionInfo(
                code=code,
                data_type="index",
                callback=callback,
            )
            self._subscribed_codes.add(code)

        if self._connected and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_subscribe(codes, self.REAL_TYPE["INDEX"]),
                self._loop,
            )
    
    def subscribe_orderbook(self, codes: List[str], callback: Callable[[str, dict], None]):
        """실시간 호가 데이터 구독 (subscribe_hoga 별칭)"""
        self.subscribe_hoga(codes, callback)

    def subscribe_vi_events(self, codes: List[str], callback: Callable[[dict], None]):
        """
        실시간 변동성완화장치(VI) 이벤트 구독
        
        Args:
            codes: 종목코드 리스트
            callback: VI 이벤트 수신 시 호출될 콜백 함수
        """
        self._qt_dispatcher = _main_thread_dispatcher() or self._qt_dispatcher
        self._on_vi = callback

        for code in codes:
            key = f"vi_{code}"
            self._subscriptions[key] = SubscriptionInfo(
                code=code,
                data_type="vi",
                callback=callback,
            )
            self._subscribed_codes.add(code)

        if self._connected and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_subscribe(codes, self.REAL_TYPE["VI"]),
                self._loop,
            )
    
    def subscribe_order_execution(self, callback: Callable[[dict], None]):
        """
        주문 체결 알림 구독
        
        Args:
            callback: 체결 데이터 수신 시 호출될 콜백 함수
        """
        self._qt_dispatcher = _main_thread_dispatcher() or self._qt_dispatcher
        self._on_order_exec = callback
        
        if self._connected and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_subscribe_order(),
                self._loop
            )
    
    def unsubscribe(self, codes: List[str]):
        """구독 해제"""
        exec_codes: List[str] = []
        hoga_codes: List[str] = []
        index_codes: List[str] = []
        vi_codes: List[str] = []

        for code in codes:
            self._subscribed_codes.discard(code)
            if self._subscriptions.pop(f"exec_{code}", None):
                exec_codes.append(code)
            if self._subscriptions.pop(f"hoga_{code}", None):
                hoga_codes.append(code)
            if self._subscriptions.pop(f"index_{code}", None):
                index_codes.append(code)
            if self._subscriptions.pop(f"vi_{code}", None):
                vi_codes.append(code)
        
        if self._connected and self._loop:
            if exec_codes:
                asyncio.run_coroutine_threadsafe(
                    self._send_unsubscribe(exec_codes, self.REAL_TYPE["EXECUTION"]),
                    self._loop
                )
            if hoga_codes:
                asyncio.run_coroutine_threadsafe(
                    self._send_unsubscribe(hoga_codes, self.REAL_TYPE["HOGA"]),
                    self._loop
                )
            if index_codes:
                asyncio.run_coroutine_threadsafe(
                    self._send_unsubscribe(index_codes, self.REAL_TYPE["INDEX"]),
                    self._loop
                )
            if vi_codes:
                asyncio.run_coroutine_threadsafe(
                    self._send_unsubscribe(vi_codes, self.REAL_TYPE["VI"]),
                    self._loop
                )
    
    def unsubscribe_all(self):
        """모든 구독 해제"""
        exec_codes = [
            sub.code for sub in self._subscriptions.values()
            if sub.data_type == "execution"
        ]
        hoga_codes = [
            sub.code for sub in self._subscriptions.values()
            if sub.data_type == "hoga"
        ]
        index_codes = [
            sub.code for sub in self._subscriptions.values()
            if sub.data_type == "index"
        ]
        vi_codes = [
            sub.code for sub in self._subscriptions.values()
            if sub.data_type == "vi"
        ]

        self._subscribed_codes.clear()
        self._subscriptions.clear()
        
        if self._connected and self._loop:
            if exec_codes:
                asyncio.run_coroutine_threadsafe(
                    self._send_unsubscribe(exec_codes, self.REAL_TYPE["EXECUTION"]),
                    self._loop
                )
            if hoga_codes:
                asyncio.run_coroutine_threadsafe(
                    self._send_unsubscribe(hoga_codes, self.REAL_TYPE["HOGA"]),
                    self._loop
                )
            if index_codes:
                asyncio.run_coroutine_threadsafe(
                    self._send_unsubscribe(index_codes, self.REAL_TYPE["INDEX"]),
                    self._loop
                )
            if vi_codes:
                asyncio.run_coroutine_threadsafe(
                    self._send_unsubscribe(vi_codes, self.REAL_TYPE["VI"]),
                    self._loop
                )
    
    def _build_reg_payload(self, codes: List[str], real_type: str, register: bool = True) -> Dict[str, Any]:
        items = [str(code) for code in codes if str(code).strip()]
        return {
            "trnm": "REG" if register else "REMOVE",
            "grp_no": "1",
            "refresh": "1" if register else "0",
            "data": [{"item": items, "type": [str(real_type)]}],
        }

    async def _send_subscribe(self, codes: List[str], real_type: str):
        """구독 요청 전송"""
        if not self._ws:
            return
        message = self._build_reg_payload(codes, real_type, register=True)
        await self._ws.send(json.dumps(message))
        self.logger.info(f"실시간 구독 요청: type={real_type} codes={codes}")
    
    async def _send_subscribe_order(self):
        """주문 체결 구독 요청"""
        if not self._ws:
            return
        message = self._build_reg_payload([], self.REAL_TYPE["ORDER_EXEC"], register=True)
        await self._ws.send(json.dumps(message))
        self.logger.info("주문 체결 실시간 구독 요청")
    
    async def _send_unsubscribe(self, codes: List[str], real_type: str):
        """구독 해제 요청 전송"""
        if not self._ws:
            return
        message = self._build_reg_payload(codes, real_type, register=False)
        await self._ws.send(json.dumps(message))
        self.logger.info(f"실시간 구독 해제: type={real_type} codes={codes}")
    
    async def _restore_subscriptions(self):
        """재연결 시 기존 구독 복원"""
        exec_codes = [
            sub.code for sub in self._subscriptions.values()
            if sub.data_type == "execution"
        ]
        hoga_codes = [
            sub.code for sub in self._subscriptions.values()
            if sub.data_type == "hoga"
        ]
        index_codes = [
            sub.code for sub in self._subscriptions.values()
            if sub.data_type == "index"
        ]
        vi_codes = [
            sub.code for sub in self._subscriptions.values()
            if sub.data_type == "vi"
        ]

        if exec_codes:
            await self._send_subscribe(exec_codes, self.REAL_TYPE["EXECUTION"])
        if hoga_codes:
            await self._send_subscribe(hoga_codes, self.REAL_TYPE["HOGA"])
        if index_codes:
            await self._send_subscribe(index_codes, self.REAL_TYPE["INDEX"])
        if vi_codes:
            await self._send_subscribe(vi_codes, self.REAL_TYPE["VI"])
        
        if self._on_order_exec:
            await self._send_subscribe_order()
    
    # =========================================================================
    # 메시지 처리
    # =========================================================================
    
    async def _handle_message(self, message: str):
        """수신된 메시지 처리"""
        try:
            data = json.loads(message)
            if not isinstance(data, dict):
                return

            trnm = str(data.get("trnm") or data.get("header", {}).get("trnm") or "")
            if trnm == "PING":
                if self._ws:
                    await self._ws.send(json.dumps({"trnm": "PING"}))
                return
            if trnm in {"LOGIN", "REG", "REMOVE"}:
                return

            if trnm == "REAL":
                for record in data.get("data") or []:
                    if isinstance(record, dict):
                        await self._dispatch_real_type(
                            str(record.get("type") or ""),
                            self._normalize_real_record(record),
                        )
                return

            header = data.get("header", {}) if isinstance(data.get("header"), dict) else {}
            body = data.get("body", {}) if isinstance(data.get("body"), dict) else data
            real_type = str(header.get("real_type") or data.get("type") or "")
            await self._dispatch_real_type(real_type, body if isinstance(body, dict) else {})
                
        except json.JSONDecodeError:
            self.logger.warning(f"JSON 파싱 실패: {message[:100]}")
        except Exception as e:
            self.logger.error(f"메시지 처리 오류: {e}")

    async def _dispatch_real_type(self, real_type: str, body: dict):
        if real_type == self.REAL_TYPE["EXECUTION"]:
            await self._handle_execution(body)
        elif real_type == self.REAL_TYPE["HOGA"]:
            await self._handle_hoga(body)
        elif real_type == self.REAL_TYPE["ORDER_EXEC"]:
            await self._handle_order_exec(body)
        elif real_type == self.REAL_TYPE["INDEX"]:
            await self._handle_index(body)
        elif real_type == self.REAL_TYPE["VI"]:
            await self._handle_vi(body)
        elif real_type:
            self.logger.debug(f"알 수 없는 실시간 타입: {real_type}")

    def _normalize_real_record(self, record: dict) -> dict:
        values = record.get("values") if isinstance(record.get("values"), dict) else {}
        code = str(record.get("item") or record.get("stk_cd") or values.get("9001") or "")
        name = str(record.get("name") or record.get("stk_nm") or values.get("302") or "")
        body = {
            "stk_cd": code,
            "stk_nm": name,
            "exec_tm": values.get("20") or values.get("exec_tm") or "",
            "exec_prc": values.get("10") or values.get("exec_prc") or 0,
            "exec_vol": values.get("15") or values.get("exec_vol") or 0,
            "chg_amt": values.get("11") or values.get("chg_amt") or 0,
            "acc_vol": values.get("13") or values.get("acc_vol") or 0,
            "ask_prc": values.get("27") or values.get("ask_prc") or 0,
            "bid_prc": values.get("28") or values.get("bid_prc") or 0,
            "idx_cd": code,
            "idx_val": values.get("10") or values.get("idx_val") or 0,
            "chg_rt": values.get("12") or values.get("chg_rt") or 0,
            "tm": values.get("20") or "",
            "vi_st": values.get("9068") or values.get("vi_st") or "",
            "vi_status": values.get("1225") or values.get("vi_status") or "",
        }
        body.update(record)
        body.update(values)
        return body
    
    def _invoke_on_main_thread(self, callback: Callable, *args):
        """Run realtime callbacks on the Qt application thread when available."""
        try:
            app = QCoreApplication.instance()
            if app is not None and QThread.currentThread() == app.thread():
                callback(*args)
                return
            dispatcher = getattr(self, "_qt_dispatcher", None) or _main_thread_dispatcher()
            if dispatcher is not None:
                self._qt_dispatcher = dispatcher
                dispatcher.invoke.emit(callback, tuple(args))
                return
        except Exception:
            self.logger.exception("main-thread dispatch failed; falling back to direct callback")
        callback(*args)

    async def _handle_execution(self, body: dict):
        """체결 데이터 처리"""
        if not self._on_execution:
            return

        trading_status = str(
            body.get("trd_st")
            or body.get("trading_status")
            or body.get("market_status")
            or body.get("vi_status")
            or ""
        )
        market_event = str(body.get("market_event") or body.get("event") or "")
        index_code = str(body.get("idx_cd") or body.get("index_code") or "")
        try:
            index_value = float(body.get("idx_val", body.get("index_value", 0)) or 0)
        except (TypeError, ValueError):
            index_value = 0.0
        
        exec_data = ExecutionData(
            code=str(body.get("stk_cd", "") or ""),
            name=str(body.get("stk_nm", "") or ""),
            exec_time=str(body.get("exec_tm", "") or ""),
            exec_price=abs(_ws_int(body.get("exec_prc"))),
            exec_volume=_ws_int(body.get("exec_vol")),
            exec_change=_ws_int(body.get("chg_amt")),
            total_volume=_ws_int(body.get("acc_vol")),
            ask_price=abs(_ws_int(body.get("ask_prc"))),
            bid_price=abs(_ws_int(body.get("bid_prc"))),
            trading_status=trading_status,
            market_event=market_event,
            index_code=index_code,
            index_value=index_value,
        )
        
        # 콜백을 메인 스레드에서 실행
        self._invoke_on_main_thread(self._on_execution, exec_data)
    
    async def _handle_hoga(self, body: dict):
        """호가 데이터 처리"""
        if not self._on_hoga:
            return
        
        code = body.get("stk_cd", "")
        self._invoke_on_main_thread(self._on_hoga, code, body)
    
    async def _handle_order_exec(self, body: dict):
        """주문 체결 데이터 처리"""
        if not self._on_order_exec:
            return
        
        self._invoke_on_main_thread(self._on_order_exec, body)

    async def _handle_index(self, body: dict):
        """지수/시장 이벤트 데이터 처리"""
        if not self._on_index:
            return

        try:
            try:
                value = float(body.get("idx_val", body.get("cur_prc", body.get("value", 0))) or 0)
            except (TypeError, ValueError):
                value = 0.0
            try:
                change = float(body.get("chg_amt", body.get("change", 0)) or 0)
            except (TypeError, ValueError):
                change = 0.0
            try:
                change_rate = float(body.get("chg_rt", body.get("change_rate", 0)) or 0)
            except (TypeError, ValueError):
                change_rate = 0.0

            tick = IndexTick(
                code=str(body.get("idx_cd", body.get("code", ""))),
                value=value,
                change=change,
                change_rate=change_rate,
                timestamp=str(body.get("tm", body.get("timestamp", ""))),
                trading_status=str(body.get("trd_st", body.get("trading_status", "")) or ""),
                market_event=str(body.get("market_event", body.get("event", "")) or ""),
            )
            self._invoke_on_main_thread(self._on_index, tick)
        except Exception as exc:
            self.logger.warning(f"INDEX payload 파싱 실패(안전 폴백): {exc}")

    async def _handle_vi(self, body: dict):
        """VI 발동/해제 이벤트 데이터 처리"""
        if not self._on_vi:
            return
        self._invoke_on_main_thread(self._on_vi, body)
    
    # =========================================================================
    # 이벤트 콜백 설정
    # =========================================================================
    
    def set_on_connect(self, callback: Callable[[], None]):
        """연결 성공 콜백 설정"""
        self._qt_dispatcher = _main_thread_dispatcher() or self._qt_dispatcher
        self._on_connect = callback
    
    def set_on_disconnect(self, callback: Callable[[], None]):
        """연결 끊김 콜백 설정"""
        self._qt_dispatcher = _main_thread_dispatcher() or self._qt_dispatcher
        self._on_disconnect = callback
    
    def set_on_error(self, callback: Callable[[Exception], None]):
        """오류 발생 콜백 설정"""
        self._qt_dispatcher = _main_thread_dispatcher() or self._qt_dispatcher
        self._on_error = callback

    def set_on_index(self, callback: Callable[[IndexTick], None]):
        """지수 데이터 콜백 설정"""
        self._qt_dispatcher = _main_thread_dispatcher() or self._qt_dispatcher
        self._on_index = callback

    def set_on_vi(self, callback: Callable[[dict], None]):
        """VI 이벤트 데이터 콜백 설정"""
        self._qt_dispatcher = _main_thread_dispatcher() or self._qt_dispatcher
        self._on_vi = callback

    def request_once(self, body: Dict[str, Any], timeout: float = 15.0) -> Optional[Dict[str, Any]]:
        """조건검색 등 1회성 WebSocket 요청 (CNSRLST/CNSRREQ)."""
        if not isinstance(body, dict) or not body.get("trnm"):
            return None
        try:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._request_once_async(body, timeout))
            finally:
                loop.close()
        except Exception as exc:
            self.logger.warning(f"WebSocket request_once 실패 ({body.get('trnm')}): {exc}")
            return None

    async def _request_once_async(self, body: Dict[str, Any], timeout: float) -> Optional[Dict[str, Any]]:
        token = self.auth.get_token()
        if not token:
            self.logger.warning("WebSocket request_once: 토큰이 없습니다.")
            return None
        if ws_connect is None:
            self.logger.warning("WebSocket request_once: websockets 연결 함수가 없습니다.")
            return None

        expected = str(body.get("trnm") or "")
        headers = {"Authorization": f"bearer {token}"}
        deadline = time.monotonic() + max(1.0, float(timeout or 15.0))
        async with ws_connect(
            self.ws_url,
            extra_headers=headers,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=3,
        ) as ws:
            await ws.send(json.dumps({"trnm": "LOGIN", "token": token}))
            await ws.send(json.dumps(body))
            while time.monotonic() < deadline:
                remaining = max(0.1, deadline - time.monotonic())
                try:
                    raw_message = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                message = (
                    raw_message.decode("utf-8", errors="ignore")
                    if isinstance(raw_message, bytes)
                    else str(raw_message)
                )
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue
                if not isinstance(data, dict):
                    continue
                trnm = str(data.get("trnm") or "")
                if trnm == "PING":
                    await ws.send(json.dumps({"trnm": "PING"}))
                    continue
                if trnm == "LOGIN":
                    if data.get("return_code") not in (None, 0, "0"):
                        self.logger.warning(
                            f"WebSocket LOGIN 실패: {data.get('return_msg') or data.get('return_code')}"
                        )
                        return None
                    continue
                if expected and trnm == expected:
                    return data
                if trnm not in {"REG", "REMOVE", ""}:
                    return data
        self.logger.warning(f"WebSocket request_once 응답 대기 시간 초과: {expected}")
        return None

