"""UI text helpers for beginner-friendly Korean labels."""

from __future__ import annotations

from typing import Any, Iterable, Sequence, Tuple


ChoiceItem = Tuple[str, str]


STRATEGY_CHOICES: Sequence[ChoiceItem] = (
    ("변동성 돌파 (volatility_breakout)", "volatility_breakout"),
    ("시계열 모멘텀 (time_series_momentum)", "time_series_momentum"),
    ("단면 모멘텀 (cross_sectional_momentum)", "cross_sectional_momentum"),
    ("이동평균 채널 추세 (ma_channel_trend)", "ma_channel_trend"),
    ("시가범위/돈치안 돌파 (orb_donchian_breakout)", "orb_donchian_breakout"),
    ("쌍거래 공적분 (pairs_trading_cointegration)", "pairs_trading_cointegration"),
    ("통계 차익 잔차 (stat_arb_residual)", "stat_arb_residual"),
    ("RSI/볼린저 역추세 (rsi_bollinger_reversion)", "rsi_bollinger_reversion"),
    ("DMI 추세 강도 (dmi_trend_strength)", "dmi_trend_strength"),
    ("FF5 팩터 롱숏 (ff5_factor_ls)", "ff5_factor_ls"),
    ("퀄리티/가치/저변동성 (quality_value_lowvol)", "quality_value_lowvol"),
    ("투자자/프로그램 수급 (investor_program_flow)", "investor_program_flow"),
    ("변동성 타깃 오버레이 (volatility_targeting_overlay)", "volatility_targeting_overlay"),
    ("리스크 패리티 포트폴리오 (risk_parity_portfolio)", "risk_parity_portfolio"),
    ("집행 알고리즘 TWAP/VWAP/POV (execution_algo_twap_vwap_pov)", "execution_algo_twap_vwap_pov"),
    ("스프레드 마켓메이킹 (market_making_spread)", "market_making_spread"),
)

PORTFOLIO_MODE_CHOICES: Sequence[ChoiceItem] = (
    ("단일 전략", "single_strategy"),
    ("복합 전략", "multi_strategy"),
)

ASSET_SCOPE_CHOICES: Sequence[ChoiceItem] = (
    ("국내 주식 실거래", "kr_stock_live"),
    ("국내 ETF/ETN", "kr_stock_etf"),
    ("멀티자산 모의/연구", "multi_asset_sim"),
)

EXECUTION_POLICY_CHOICES: Sequence[ChoiceItem] = (
    ("시장가 우선", "market"),
    ("지정가 우선", "limit"),
)

BACKTEST_TIMEFRAME_CHOICES: Sequence[ChoiceItem] = (
    ("일봉", "1d"),
    ("1분봉", "1m"),
    ("5분봉", "5m"),
    ("15분봉", "15m"),
)

DAILY_LOSS_BASIS_CHOICES: Sequence[ChoiceItem] = (
    ("총자산 기준", "total_equity"),
    ("주문가능금액 기준", "available_amount"),
)

AI_PROVIDER_CHOICES: Sequence[ChoiceItem] = (
    ("Google Gemini", "gemini"),
    ("OpenAI", "openai"),
)

REPLAY_SCOPE_CHOICES: Sequence[ChoiceItem] = (
    ("전체", "all"),
    ("시장", "market"),
    ("업종", "sector"),
    ("테마", "theme"),
    ("종목", "symbol"),
)

REPLAY_AUDIT_CHOICES: Sequence[ChoiceItem] = (
    ("전체", "all"),
    ("허용만", "allowed"),
    ("차단만", "blocked"),
)

SOURCE_NAME_LABELS = {
    "news": "뉴스",
    "dart": "공시",
    "datalab": "검색량",
    "macro": "매크로",
    "ai": "AI",
}

STATUS_LABELS = {
    "idle": "대기",
    "fresh": "최신",
    "stale": "지연",
    "partial": "부분 수집",
    "error": "오류",
    "disabled": "사용 안 함",
    "ok_with_data": "데이터 있음",
    "ok_empty": "결과 없음",
    "watch": "감시",
    "holding": "보유",
    "buying": "매수 중",
    "selling": "매도 중",
    "buy_submitted": "매수 접수",
    "sell_submitted": "매도 접수",
    "sync_failed": "동기화 실패",
    "submitted": "접수",
    "partial_fill": "부분 체결",
    "partial": "부분 수집",
    "rejected": "거절",
    "done": "완료",
    "normal": "정상",
    "degraded": "주의",
    "shock": "시장 충격",
}

ACTION_POLICY_LABELS = {
    "allow": "허용",
    "watch_only": "관찰만",
    "reduce_size": "비중 축소",
    "tighten_exit": "청산 강화",
    "block_entry": "진입 차단",
    "force_exit": "즉시 청산",
    "none": "없음",
}

EXIT_POLICY_LABELS = {
    "none": "없음",
    "watch_only": "관찰만",
    "reduce_size": "비중 축소",
    "tighten_exit": "청산 강화",
    "force_exit": "즉시 청산",
}

MARKET_STATE_LABELS = {
    "normal": "정상",
    "vi": "VI 상태",
    "halt": "거래정지",
    "reopen_cooldown": "재개 후 대기",
    "unknown": "미확인",
}

REGIME_LABELS = {
    "normal": "정상",
    "neutral": "중립",
    "low": "낮음",
    "medium": "보통",
    "high": "높음",
    "critical": "매우 높음",
    "risk_on": "위험 선호",
    "risk_off": "위험 회피",
    "shock": "시장 충격",
    "degraded": "주의",
    "elevated": "확대",
    "extreme": "매우 높음",
    "unknown": "미확인",
}

EVENT_TYPE_LABELS = {
    "funding": "자금조달",
    "governance": "지배구조/법률",
    "earnings": "실적",
    "contract": "수주/계약",
    "halt": "거래정지",
    "correction": "정정공시",
    "headline_velocity": "뉴스 급증",
    "market_risk_mode": "시장 위험 모드",
    "sector_block": "업종 차단",
    "sector_block_release": "업종 차단 해제",
    "theme_heat": "테마 과열",
    "theme_cooldown": "테마 과열 해제",
}

EVENT_SEVERITY_LABELS = {
    "low": "낮음",
    "medium": "보통",
    "high": "높음",
    "critical": "매우 높음",
}

NEWS_SENTIMENT_LABELS = {
    "positive": "긍정",
    "neutral": "중립",
    "negative": "부정",
    "mixed": "혼합",
    "uncertain": "불확실",
}

GUARD_REASON_LABELS = {
    "shock_guard": "시장 쇼크 보호",
    "vi_guard": "VI/정지 보호",
    "order_health_guard": "주문 안정성 보호",
    "liquidity_stress_guard": "유동성 스트레스 보호",
    "slippage_guard": "슬리피지 보호",
    "sync_failed": "동기화 실패",
    "market_intel_block_entry": "인텔리전스 진입 차단",
    "market_intel_force_exit": "인텔리전스 즉시 청산",
    "market_intel_reduce_size": "인텔리전스 비중 축소",
    "daily_loss_guard": "일일 손실 한도",
    "cooldown": "재진입 대기",
}


def populate_combo(combo: Any, items: Iterable[ChoiceItem], current_value: Any | None = None):
    combo.clear()
    for label, value in items:
        combo.addItem(str(label), str(value))
    if current_value is not None:
        set_combo_value(combo, current_value)


def combo_value(combo: Any, default: str = "") -> str:
    if combo is None:
        return str(default)
    try:
        data = combo.currentData()
    except Exception:
        data = None
    if data not in (None, ""):
        return str(data)
    try:
        text = combo.currentText()
    except Exception:
        text = default
    return str(text or default)


def set_combo_value(combo: Any, value: Any):
    text = str(value or "")
    if combo is None:
        return
    try:
        index = combo.findData(text)
        if isinstance(index, int) and index >= 0:
            combo.setCurrentIndex(index)
            return
    except Exception:
        pass
    try:
        index = combo.findText(text)
        if isinstance(index, int) and index >= 0:
            combo.setCurrentIndex(index)
            return
    except Exception:
        pass
    try:
        combo.setCurrentText(text)
    except Exception:
        return


def _display_from_map(value: Any, mapping: dict[str, str]) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return mapping.get(text, text)


def display_source_name(value: Any) -> str:
    return _display_from_map(value, SOURCE_NAME_LABELS)


def display_status(value: Any) -> str:
    return _display_from_map(value, STATUS_LABELS)


def display_action_policy(value: Any) -> str:
    return _display_from_map(value, ACTION_POLICY_LABELS)


def display_exit_policy(value: Any) -> str:
    return _display_from_map(value, EXIT_POLICY_LABELS)


def display_market_state(value: Any) -> str:
    return _display_from_map(value, MARKET_STATE_LABELS)


def display_regime(value: Any) -> str:
    return _display_from_map(value, REGIME_LABELS)


def display_event_type(value: Any) -> str:
    return _display_from_map(value, EVENT_TYPE_LABELS)


def display_event_severity(value: Any) -> str:
    return _display_from_map(value, EVENT_SEVERITY_LABELS)


def display_news_sentiment(value: Any) -> str:
    return _display_from_map(value, NEWS_SENTIMENT_LABELS)


def display_guard_reason(value: Any) -> str:
    return _display_from_map(value, GUARD_REASON_LABELS)


def display_replay_scope(value: Any) -> str:
    return _display_from_map(value, {item_value: label for label, item_value in REPLAY_SCOPE_CHOICES})


def display_yes_no(flag: Any, true_text: str = "예", false_text: str = "아니오") -> str:
    return true_text if bool(flag) else false_text


def display_allowed(flag: Any) -> str:
    return "허용" if bool(flag) else "차단"


def display_source_health(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parts = []
    for chunk in text.split(","):
        item = chunk.strip()
        if not item:
            continue
        if ":" not in item:
            parts.append(item)
            continue
        source, status = item.split(":", 1)
        parts.append(f"{display_source_name(source)}:{display_status(status)}")
    return ", ".join(parts)
