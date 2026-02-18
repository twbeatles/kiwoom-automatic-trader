"""Market data tabs mixin for KiwoomProTrader."""

from PyQt6.QtWidgets import QPushButton, QTableWidgetItem

from app.support.worker import Worker


class MarketDataTabsMixin:
    def _load_chart(self):
        """차트 데이터 조회 (비동기)."""
        if not self.rest_client:
            self.log("API 연결 필요")
            return

        code = self.chart_code_input.text().strip()
        chart_type = self.chart_type_combo.currentText()

        btn = self.sender()
        if isinstance(btn, QPushButton):
            btn.setEnabled(False)
            btn.setText("조회 중...")

        def worker_fn():
            if "일봉" in chart_type:
                return self.rest_client.get_daily_chart(code, 60)
            if "주봉" in chart_type:
                return self.rest_client.get_weekly_chart(code, 52)
            interval = int(chart_type.replace("분봉", ""))
            return self.rest_client.get_minute_chart(code, interval, 60)

        def on_complete(data):
            if isinstance(btn, QPushButton):
                btn.setEnabled(True)
                btn.setText("차트 조회")

            if not data:
                self.chart_info.setText("데이터 없음")
                self.log(f"차트 데이터 없음: {code}")
                return

            try:
                self.chart_table.setUpdatesEnabled(False)
                self.chart_table.setRowCount(len(data))
                for i, candle in enumerate(data):
                    items = [
                        candle.date,
                        f"{candle.open_price:,}",
                        f"{candle.high_price:,}",
                        f"{candle.low_price:,}",
                        f"{candle.close_price:,}",
                        f"{candle.volume:,}",
                    ]
                    for j, text in enumerate(items):
                        text_str = str(text)
                        item = self.chart_table.item(i, j)
                        if item is None:
                            self.chart_table.setItem(i, j, QTableWidgetItem(text_str))
                        elif item.text() != text_str:
                            item.setText(text_str)
            finally:
                self.chart_table.setUpdatesEnabled(True)

            self.chart_info.setText(f"{code} {chart_type} - {len(data)}개 조회")
            self.log(f"차트 조회 완료: {code} ({chart_type})")

        def on_error(e):
            if isinstance(btn, QPushButton):
                btn.setEnabled(True)
                btn.setText("차트 조회")
            self.log(f"차트 조회 실패: {e}")

        worker = Worker(worker_fn)
        worker.signals.finished.connect(on_complete)
        worker.signals.error.connect(on_error)
        self.threadpool.start(worker)

    def _load_orderbook(self):
        """호가 데이터 조회 (비동기)."""
        if not self.rest_client:
            self.log("API 연결 필요")
            return

        code = self.hoga_code_input.text().strip()
        btn = self.sender()
        if isinstance(btn, QPushButton):
            btn.setEnabled(False)
            btn.setText("조회 중...")

        def worker_fn():
            return self.rest_client.get_order_book(code)

        def on_complete(ob):
            if isinstance(btn, QPushButton):
                btn.setEnabled(True)
                btn.setText("호가 조회")

            if not ob:
                self.log(f"호가 데이터 없음: {code}")
                return

            try:
                self.ask_table.setUpdatesEnabled(False)
                self.bid_table.setUpdatesEnabled(False)
                for i in range(10):
                    idx = 9 - i
                    ask_values = (f"{ob.ask_prices[idx]:,}", f"{ob.ask_volumes[idx]:,}")
                    bid_values = (f"{ob.bid_prices[i]:,}", f"{ob.bid_volumes[i]:,}")
                    for col, value in enumerate(ask_values):
                        item = self.ask_table.item(i, col)
                        if item is None:
                            self.ask_table.setItem(i, col, QTableWidgetItem(value))
                        elif item.text() != value:
                            item.setText(value)
                    for col, value in enumerate(bid_values):
                        item = self.bid_table.item(i, col)
                        if item is None:
                            self.bid_table.setItem(i, col, QTableWidgetItem(value))
                        elif item.text() != value:
                            item.setText(value)
            finally:
                self.ask_table.setUpdatesEnabled(True)
                self.bid_table.setUpdatesEnabled(True)

            self.hoga_info.setText(
                f"총매도물량: {ob.total_ask_volume:,} | 총매수물량: {ob.total_bid_volume:,}"
            )
            self.log(f"호가 조회 완료: {code}")

        def on_error(e):
            if isinstance(btn, QPushButton):
                btn.setEnabled(True)
                btn.setText("호가 조회")
            self.log(f"호가 조회 실패: {e}")

        worker = Worker(worker_fn)
        worker.signals.finished.connect(on_complete)
        worker.signals.error.connect(on_error)
        self.threadpool.start(worker)

    def _load_conditions(self):
        """조건식 목록 조회."""
        if not self.rest_client:
            self.log("API 연결 필요")
            return

        btn = self.sender() if isinstance(self.sender(), QPushButton) else None
        if btn:
            btn.setEnabled(False)
            btn.setText("조회 중...")

        worker = Worker(self.rest_client.get_condition_list)

        def on_complete(conditions):
            if btn:
                btn.setEnabled(True)
                btn.setText("목록 갱신")
            self.condition_combo.clear()
            for cond in conditions or []:
                self.condition_combo.addItem(f"{cond['index']}: {cond['name']}", cond)
            self.log(f"조건식 {len(conditions or [])}개 로드")

        def on_error(e):
            if btn:
                btn.setEnabled(True)
                btn.setText("목록 갱신")
            self.log(f"조건식 조회 실패: {e}")

        worker.signals.result.connect(on_complete)
        worker.signals.error.connect(on_error)
        self.threadpool.start(worker)

    def _execute_condition(self):
        """조건검색 실행."""
        if not self.rest_client:
            return

        cond_data = self.condition_combo.currentData()
        if not cond_data:
            return

        btn = self.sender() if isinstance(self.sender(), QPushButton) else None
        if btn:
            btn.setEnabled(False)
            btn.setText("검색 중...")

        worker = Worker(self.rest_client.search_by_condition, cond_data["index"], cond_data["name"])

        def on_complete(results):
            if btn:
                btn.setEnabled(True)
                btn.setText("검색 실행")
            results = results or []
            self.condition_table.setUpdatesEnabled(False)
            try:
                self.condition_table.setRowCount(len(results))
                for i, stock in enumerate(results):
                    items = [
                        stock["code"],
                        stock["name"],
                        f"{stock['current_price']:,}",
                        f"{stock['change_rate']:.2f}%",
                        f"{stock['volume']:,}",
                    ]
                    for j, text in enumerate(items):
                        text_str = str(text)
                        item = self.condition_table.item(i, j)
                        if item is None:
                            self.condition_table.setItem(i, j, QTableWidgetItem(text_str))
                        elif item.text() != text_str:
                            item.setText(text_str)
            finally:
                self.condition_table.setUpdatesEnabled(True)

            self.condition_info.setText(f"{len(results)}개 종목 검색됨")
            self.log(f"조건검색 완료: {len(results)}개")

        def on_error(e):
            if btn:
                btn.setEnabled(True)
                btn.setText("검색 실행")
            self.log(f"조건검색 실패: {e}")

        worker.signals.result.connect(on_complete)
        worker.signals.error.connect(on_error)
        self.threadpool.start(worker)

    def _apply_condition_result(self):
        """조건검색 결과를 감시 종목에 반영."""
        codes = []
        for i in range(self.condition_table.rowCount()):
            item = self.condition_table.item(i, 0)
            if item:
                codes.append(item.text())

        if codes:
            self.input_codes.setText(",".join(codes[:10]))
            self.log(f"{len(codes[:10])}개 종목 적용")

    def _load_ranking(self):
        """순위 정보 조회."""
        if not self.rest_client:
            self.log("API 연결 필요")
            return

        ranking_type = self.ranking_type.currentText()
        market_idx = self.ranking_market.currentIndex()
        market = str(market_idx)

        btn = self.sender() if isinstance(self.sender(), QPushButton) else None
        if btn:
            btn.setEnabled(False)
            btn.setText("조회 중...")

        if "거래량" in ranking_type:
            worker = Worker(self.rest_client.get_volume_ranking, market, 30)
        elif "상승" in ranking_type:
            worker = Worker(self.rest_client.get_fluctuation_ranking, market, "1", 30)
        else:
            worker = Worker(self.rest_client.get_fluctuation_ranking, market, "2", 30)

        def on_complete(data):
            if btn:
                btn.setEnabled(True)
                btn.setText("순위 조회")
            data = data or []
            self.ranking_table.setUpdatesEnabled(False)
            try:
                self.ranking_table.setRowCount(len(data))
                for i, item in enumerate(data):
                    items = [
                        str(item["rank"]),
                        item["code"],
                        item["name"],
                        f"{item['current_price']:,}",
                        f"{item['change_rate']:.2f}%",
                        f"{item['volume']:,}",
                    ]
                    for j, text in enumerate(items):
                        text_str = str(text)
                        current_item = self.ranking_table.item(i, j)
                        if current_item is None:
                            self.ranking_table.setItem(i, j, QTableWidgetItem(text_str))
                        elif current_item.text() != text_str:
                            current_item.setText(text_str)
            finally:
                self.ranking_table.setUpdatesEnabled(True)

            self.log(f"{ranking_type} 조회 완료")

        def on_error(e):
            if btn:
                btn.setEnabled(True)
                btn.setText("순위 조회")
            self.log(f"순위 조회 실패: {e}")

        worker.signals.result.connect(on_complete)
        worker.signals.error.connect(on_error)
        self.threadpool.start(worker)
