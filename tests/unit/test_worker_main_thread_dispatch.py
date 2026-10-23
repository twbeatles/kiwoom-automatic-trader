import gc
import weakref
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QThread, QThreadPool

from app.mixins.api_account import APIAccountMixin
from app.support.worker import Worker


def test_result_and_finished_run_on_gui_thread_after_worker_is_released(qapp):
    pool = QThreadPool()
    calls = []
    task_threads = []
    payload = object()

    def task():
        task_threads.append(QThread.currentThread() == qapp.thread())
        return payload

    worker = Worker(task)
    worker.signals.result.connect(
        lambda value: calls.append(("result", value, QThread.currentThread() == qapp.thread()))
    )
    worker.signals.finished.connect(
        lambda value: calls.append(("finished", value, QThread.currentThread() == qapp.thread()))
    )
    signals_ref = weakref.ref(worker.signals)
    pool.start(worker)
    assert pool.waitForDone(2000)
    del worker
    gc.collect()
    assert signals_ref() is not None
    # The GUI event loop has not run while the task completed.
    assert calls == []
    qapp.processEvents()
    assert task_threads == [False]
    assert calls == [("result", payload, True), ("finished", payload, True)]
    gc.collect()
    assert signals_ref() is None


def test_error_runs_on_gui_thread_without_success_signals(qapp):
    pool = QThreadPool()
    calls = []
    error = RuntimeError("account lookup failed")

    def task():
        raise error

    worker = Worker(task)
    worker.signals.result.connect(lambda value: calls.append("result"))
    worker.signals.finished.connect(lambda value: calls.append("finished"))
    worker.signals.error.connect(
        lambda value: calls.append((value, QThread.currentThread() == qapp.thread()))
    )
    pool.start(worker)
    assert pool.waitForDone(2000)
    del worker
    gc.collect()
    assert calls == []
    qapp.processEvents()
    assert calls == [(error, True)]


@pytest.mark.parametrize("fails", [False, True])
def test_account_refresh_lambda_updates_ui_on_gui_thread(qapp, fails):
    class Harness(APIAccountMixin):
        threadpool: QThreadPool
        logger: MagicMock
        lbl_deposit: MagicMock
        lbl_profit: MagicMock

    trader = Harness()
    trader.current_account = "12345678"
    trader._account_refresh_pending = False
    trader._last_account_refresh_ts = 0
    trader.threadpool = QThreadPool()
    trader.rest_client = MagicMock()
    info = SimpleNamespace(available_amount=1000, total_eval_amount=2000, total_profit=50)
    trader.rest_client.get_account_info.return_value = info
    trader.logger = MagicMock()
    if fails:
        trader.rest_client.get_account_info.side_effect = RuntimeError("lookup failed")
    trader.initial_deposit = 0
    trader.daily_initial_deposit = 0
    trader._last_profit_sign = 1
    ui_threads = []
    trader.lbl_deposit = MagicMock()
    trader.lbl_profit = MagicMock()
    trader.lbl_deposit.setText.side_effect = lambda text: ui_threads.append(
        QThread.currentThread() == qapp.thread()
    )

    trader._refresh_account_info_async(force=True)
    assert trader.threadpool.waitForDone(2000)
    gc.collect()
    assert trader._account_refresh_pending
    qapp.processEvents()
    assert not trader._account_refresh_pending
    if fails:
        trader.logger.warning.assert_called_once()
        assert ui_threads == []
    else:
        assert trader.deposit == 1000
        assert trader.total_equity == 3000
        assert ui_threads == [True]
    trader.rest_client.get_account_info.assert_called_once_with("12345678")
