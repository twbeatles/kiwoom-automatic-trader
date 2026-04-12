from dataclasses import dataclass


LIVE_REST_BASE_URL = "https://api.kiwoom.com"
MOCK_REST_BASE_URL = "https://mockapi.kiwoom.com"
LIVE_WS_URL = "wss://api.kiwoom.com:10000/api/dostk/websocket"
MOCK_WS_URL = "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"


@dataclass(frozen=True)
class KiwoomAPIEndpoints:
    mode: str
    rest_base_url: str
    ws_url: str
    token_cache_file: str
    session_namespace: str


def resolve_api_endpoints(is_mock: bool) -> KiwoomAPIEndpoints:
    if bool(is_mock):
        return KiwoomAPIEndpoints(
            mode="mock",
            rest_base_url=MOCK_REST_BASE_URL,
            ws_url=MOCK_WS_URL,
            token_cache_file="kiwoom_token_cache_mock.json",
            session_namespace="kiwoom_mock",
        )
    return KiwoomAPIEndpoints(
        mode="live",
        rest_base_url=LIVE_REST_BASE_URL,
        ws_url=LIVE_WS_URL,
        token_cache_file="kiwoom_token_cache_live.json",
        session_namespace="kiwoom_live",
    )
