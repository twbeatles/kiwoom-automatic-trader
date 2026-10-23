"""Background worker utilities for thread pool execution."""

from PySide6.QtCore import QCoreApplication, QObject, QRunnable, Signal, Slot


# QThreadPool releases auto-deleted runnables before queued GUI callbacks run.
# Keep their signal objects alive until the GUI has consumed the outcome.
_pending_signals = set()


class WorkerSignals(QObject):
    result = Signal(object)
    finished = Signal(object)
    error = Signal(Exception)
    progress = Signal(int)
    _outcome = Signal(bool, object)

    def __init__(self):
        super().__init__()
        app = QCoreApplication.instance()
        if app is not None:
            self.moveToThread(app.thread())
        self._outcome.connect(self._deliver_outcome)

    def publish(self, success, value):
        _pending_signals.add(self)
        if QCoreApplication.instance() is None:
            self._deliver_outcome(success, value)
        else:
            self._outcome.emit(success, value)

    @Slot(bool, object)
    def _deliver_outcome(self, success, value):
        """Emit public signals on the GUI thread, including lambda receivers."""
        try:
            if success:
                self.result.emit(value)
                # Compatibility: finished carries the result on success only.
                self.finished.emit(value)
            else:
                self.error.emit(value)
        finally:
            _pending_signals.discard(self)


class Worker(QRunnable):
    """Run fn in a pool and deliver its outcome on the Qt application thread."""

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            self.signals.publish(False, e)
        else:
            self.signals.publish(True, result)

