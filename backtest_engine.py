"""
Backtest Engine for Kiwoom Pro Algo-Trader
과거 데이터 기반 전략 백테스팅
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class BacktestTrade:
    """백테스트 거래 기록"""
    entry_date: str
    entry_price: int
    exit_date: str
    exit_price: int
    quantity: int
    profit: int
    profit_rate: float
    reason: str  # 매도 사유


@dataclass
class BacktestResult:
    """백테스트 결과"""
    # 기본 정보
    code: str
    name: str
    start_date: str
    end_date: str
    
    # 성과 지표
    initial_capital: int = 10000000      # 초기 자본
    final_capital: int = 0               # 최종 자본
    total_return: float = 0.0            # 총 수익률 %
    total_profit: int = 0                # 총 손익
    
    # 거래 통계
    total_trades: int = 0                # 총 거래 횟수
    win_trades: int = 0                  # 이익 거래
    loss_trades: int = 0                 # 손실 거래
    win_rate: float = 0.0                # 승률 %
    
    # 손익 통계
    avg_profit: float = 0.0              # 평균 수익
    avg_loss: float = 0.0                # 평균 손실
    profit_factor: float = 0.0           # 손익비
    max_profit: int = 0                  # 최대 수익
    max_loss: int = 0                    # 최대 손실
    
    # 리스크 지표
    max_drawdown: float = 0.0            # 최대 낙폭 %
    max_drawdown_amount: int = 0         # 최대 낙폭 금액
    sharpe_ratio: float = 0.0            # 샤프 비율
    
    # 거래 내역
    trades: List[BacktestTrade] = field(default_factory=list)
    
    # 일별 자산 추이
    equity_curve: List[Dict] = field(default_factory=list)


@dataclass
class BacktestParams:
    """백테스트 파라미터"""
    # 기본
    initial_capital: int = 10000000
    betting_ratio: float = 100.0         # 투자 비중 %
    commission: float = 0.015            # 수수료 % (매수+매도)
    slippage: float = 0.1                # 슬리피지 %
    
    # 변동성 돌파
    k_value: float = 0.5
    
    # 트레일링 스톱
    ts_start: float = 3.0                # 발동 수익률 %
    ts_stop: float = 1.5                 # 고점 대비 하락 %
    
    # 손절
    loss_cut: float = 2.0                # 손절률 %
    
    # 필터
    use_rsi: bool = True
    rsi_upper: int = 70
    use_volume: bool = True
    volume_multiplier: float = 1.5


class BacktestEngine:
    """백테스팅 엔진"""
    
    def __init__(self, rest_client=None):
        self.rest_client = rest_client
        self.logger = logging.getLogger('Backtest')
    
    def set_client(self, rest_client):
        """REST 클라이언트 설정"""
        self.rest_client = rest_client
    
    def _get_daily_data(self, code: str, count: int = 250) -> Optional[List[Dict]]:
        """일봉 데이터 조회"""
        if not self.rest_client:
            self.logger.error("REST 클라이언트 없음")
            return None
        
        try:
            candles = self.rest_client.get_daily_chart(code, count)
            if candles:
                # 날짜순 정렬 (오래된 것 먼저)
                data = [{
                    'date': c.date,
                    'open': c.open_price,
                    'high': c.high_price,
                    'low': c.low_price,
                    'close': c.close_price,
                    'volume': c.volume,
                } for c in reversed(candles)]
                return data
        except Exception as e:
            self.logger.error(f"데이터 조회 실패: {e}")
        
        return None
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> List[Optional[float]]:
        """RSI 계산 (시리즈)"""
        rsi_values = [None] * period
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            gains.append(diff if diff > 0 else 0)
            losses.append(-diff if diff < 0 else 0)
        
        if len(gains) < period:
            return [None] * len(prices)
        
        # 첫 번째 평균
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(gains)):
            # Wilder's smoothing
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            rsi_values.append(rsi)
        
        return rsi_values
    
    def _calculate_ma(self, prices: List[float], period: int) -> List[Optional[float]]:
        """이동평균 계산 (시리즈)"""
        result = [None] * (period - 1)
        for i in range(period - 1, len(prices)):
            result.append(sum(prices[i-period+1:i+1]) / period)
        return result
    
    def run(self, code: str, params: Optional[BacktestParams] = None,
            start_date: str = None, end_date: str = None) -> Optional[BacktestResult]:
        """
        백테스트 실행
        
        Args:
            code: 종목코드
            params: 백테스트 파라미터
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
        
        Returns:
            BacktestResult 또는 None
        """
        params = params or BacktestParams()
        
        # 데이터 조회
        daily_data = self._get_daily_data(code, 250)
        if not daily_data or len(daily_data) < 30:
            self.logger.error(f"데이터 부족: {code}")
            return None
        
        # 날짜 필터링
        if start_date:
            daily_data = [d for d in daily_data if d['date'] >= start_date]
        if end_date:
            daily_data = [d for d in daily_data if d['date'] <= end_date]
        
        if len(daily_data) < 10:
            self.logger.error(f"필터 후 데이터 부족: {code}")
            return None
        
        # 종목명 조회
        name = code
        if self.rest_client:
            try:
                quote = self.rest_client.get_stock_quote(code)
                if quote:
                    name = quote.name
            except Exception:
                pass
        
        # 기술적 지표 계산
        closes = [d['close'] for d in daily_data]
        volumes = [d['volume'] for d in daily_data]
        rsi_values = self._calculate_rsi(closes)
        volume_ma = self._calculate_ma(volumes, 20)
        
        # 시뮬레이션
        capital = params.initial_capital
        position = 0          # 보유 수량
        entry_price = 0       # 매입가
        entry_date = ""       # 매수일
        max_profit_rate = 0   # 최고 수익률 (트레일링 스톱)
        
        trades: List[BacktestTrade] = []
        equity_curve = []
        peak_capital = capital
        max_drawdown = 0
        max_drawdown_amount = 0
        
        for i in range(1, len(daily_data)):
            prev = daily_data[i - 1]
            today = daily_data[i]
            
            current_value = capital
            if position > 0:
                current_value = capital + position * today['close']
            
            # 드로다운 계산
            if current_value > peak_capital:
                peak_capital = current_value
            
            dd = (peak_capital - current_value) / peak_capital * 100
            if dd > max_drawdown:
                max_drawdown = dd
                max_drawdown_amount = peak_capital - current_value
            
            equity_curve.append({
                'date': today['date'],
                'equity': current_value,
                'drawdown': dd,
            })
            
            # === 매도 로직 ===
            if position > 0:
                profit_rate = (today['close'] - entry_price) / entry_price * 100
                
                sell_reason = None
                
                # 손절
                if profit_rate <= -params.loss_cut:
                    sell_reason = f"손절 ({profit_rate:.1f}%)"
                
                # 트레일링 스톱
                elif max_profit_rate >= params.ts_start:
                    if profit_rate < max_profit_rate - params.ts_stop:
                        sell_reason = f"트레일링스톱 (최고{max_profit_rate:.1f}% → {profit_rate:.1f}%)"
                
                # 최고 수익률 갱신
                if profit_rate > max_profit_rate:
                    max_profit_rate = profit_rate
                
                # 매도 실행
                if sell_reason:
                    sell_price = int(today['close'] * (1 - params.slippage / 100))
                    sell_amount = position * sell_price
                    commission = int(sell_amount * params.commission / 100)
                    
                    profit = sell_amount - (position * entry_price) - commission
                    
                    trades.append(BacktestTrade(
                        entry_date=entry_date,
                        entry_price=entry_price,
                        exit_date=today['date'],
                        exit_price=sell_price,
                        quantity=position,
                        profit=profit,
                        profit_rate=profit_rate,
                        reason=sell_reason,
                    ))
                    
                    capital += sell_amount - commission
                    position = 0
                    entry_price = 0
                    max_profit_rate = 0
            
            # === 매수 로직 ===
            if position == 0:
                # 변동성 돌파 조건
                volatility = prev['high'] - prev['low']
                target_price = today['open'] + volatility * params.k_value
                
                if today['high'] >= target_price:
                    # 필터 체크
                    can_buy = True
                    
                    # RSI 필터
                    if params.use_rsi and rsi_values[i] is not None:
                        if rsi_values[i] > params.rsi_upper:
                            can_buy = False
                    
                    # 거래량 필터
                    if params.use_volume and volume_ma[i] is not None:
                        if today['volume'] < volume_ma[i] * params.volume_multiplier:
                            can_buy = False
                    
                    if can_buy:
                        buy_price = int(target_price * (1 + params.slippage / 100))
                        invest_amount = int(capital * params.betting_ratio / 100)
                        commission = int(invest_amount * params.commission / 100)
                        
                        quantity = (invest_amount - commission) // buy_price
                        if quantity > 0:
                            position = quantity
                            entry_price = buy_price
                            entry_date = today['date']
                            max_profit_rate = 0
                            capital -= quantity * buy_price + commission
        
        # 마지막 날 청산
        if position > 0:
            last = daily_data[-1]
            sell_price = last['close']
            sell_amount = position * sell_price
            commission = int(sell_amount * params.commission / 100)
            profit_rate = (sell_price - entry_price) / entry_price * 100
            profit = sell_amount - (position * entry_price) - commission
            
            trades.append(BacktestTrade(
                entry_date=entry_date,
                entry_price=entry_price,
                exit_date=last['date'],
                exit_price=sell_price,
                quantity=position,
                profit=profit,
                profit_rate=profit_rate,
                reason="기간 종료 청산",
            ))
            
            capital += sell_amount - commission
        
        # 결과 계산
        final_capital = capital
        total_profit = final_capital - params.initial_capital
        total_return = total_profit / params.initial_capital * 100
        
        win_trades = [t for t in trades if t.profit > 0]
        loss_trades = [t for t in trades if t.profit <= 0]
        
        win_rate = len(win_trades) / len(trades) * 100 if trades else 0
        
        avg_profit = sum(t.profit for t in win_trades) / len(win_trades) if win_trades else 0
        avg_loss = sum(t.profit for t in loss_trades) / len(loss_trades) if loss_trades else 0
        
        total_win = sum(t.profit for t in win_trades)
        total_loss = abs(sum(t.profit for t in loss_trades))
        profit_factor = total_win / total_loss if total_loss > 0 else float('inf')
        
        max_profit_trade = max(trades, key=lambda t: t.profit).profit if trades else 0
        max_loss_trade = min(trades, key=lambda t: t.profit).profit if trades else 0
        
        # 샤프 비율 (간단 계산)
        if len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                ret = (equity_curve[i]['equity'] - equity_curve[i-1]['equity']) / equity_curve[i-1]['equity']
                returns.append(ret)
            
            if returns:
                avg_ret = sum(returns) / len(returns)
                std_ret = (sum((r - avg_ret) ** 2 for r in returns) / len(returns)) ** 0.5
                sharpe_ratio = (avg_ret / std_ret * (252 ** 0.5)) if std_ret > 0 else 0
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        result = BacktestResult(
            code=code,
            name=name,
            start_date=daily_data[0]['date'],
            end_date=daily_data[-1]['date'],
            initial_capital=params.initial_capital,
            final_capital=int(final_capital),
            total_return=total_return,
            total_profit=int(total_profit),
            total_trades=len(trades),
            win_trades=len(win_trades),
            loss_trades=len(loss_trades),
            win_rate=win_rate,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_profit=max_profit_trade,
            max_loss=max_loss_trade,
            max_drawdown=max_drawdown,
            max_drawdown_amount=int(max_drawdown_amount),
            sharpe_ratio=sharpe_ratio,
            trades=trades,
            equity_curve=equity_curve,
        )
        
        self.logger.info(f"백테스트 완료: {code} - 수익률 {total_return:.2f}%, 거래 {len(trades)}회")
        return result
    
    def run_multiple(self, codes: List[str], params: Optional[BacktestParams] = None) -> List[BacktestResult]:
        """다중 종목 백테스트"""
        results = []
        for code in codes:
            result = self.run(code, params)
            if result:
                results.append(result)
        return results
    
    def generate_report(self, result: BacktestResult) -> str:
        """백테스트 보고서 생성 (텍스트)"""
        lines = [
            "=" * 50,
            f"📊 백테스트 보고서: {result.name} ({result.code})",
            "=" * 50,
            f"기간: {result.start_date} ~ {result.end_date}",
            "",
            "📈 수익률",
            f"  초기 자본: {result.initial_capital:,}원",
            f"  최종 자본: {result.final_capital:,}원",
            f"  총 수익률: {result.total_return:+.2f}%",
            f"  총 손익: {result.total_profit:+,}원",
            "",
            "📊 거래 통계",
            f"  총 거래: {result.total_trades}회",
            f"  이익 거래: {result.win_trades}회",
            f"  손실 거래: {result.loss_trades}회",
            f"  승률: {result.win_rate:.1f}%",
            "",
            "💰 손익 분석",
            f"  평균 수익: {result.avg_profit:+,.0f}원",
            f"  평균 손실: {result.avg_loss:+,.0f}원",
            f"  손익비: {result.profit_factor:.2f}",
            f"  최대 수익: {result.max_profit:+,}원",
            f"  최대 손실: {result.max_loss:+,}원",
            "",
            "⚠️ 리스크 지표",
            f"  최대 낙폭 (MDD): {result.max_drawdown:.2f}%",
            f"  MDD 금액: {result.max_drawdown_amount:,}원",
            f"  샤프 비율: {result.sharpe_ratio:.2f}",
            "=" * 50,
        ]
        return "\n".join(lines)
