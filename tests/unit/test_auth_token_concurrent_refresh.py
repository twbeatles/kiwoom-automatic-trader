"""A2: 인증 토큰 갱신 동시성 보호 검증.

멀티스레드에서 동시에 get_token(force_refresh=True) 호출 시 네트워크 발급
요청(_request_new_token)이 정확히 1회만 실행되는지 확인한다.
"""
import tempfile
import threading
import unittest
from typing import List, Optional
from unittest.mock import patch

from api.auth import KiwoomAuth


_TOKEN_VALUE = "token-from-server"


def _make_auth_with_spy(tmpdir, app_key="appkey", secret_key="secretkey"):
    """_request_new_token 호출 수를 추적하는 KiwoomAuth 인스턴스를 만든다.

    KiwoomAuth.get_token 은 내부적으로 self._request_new_token() 을 호출한다.
    인스턴스의 메서드를 직접 카운팅 래퍼로 교체하여, lock 보호 하에서
    네트워크 발급 요청이 정확히 1회만 수행되는지 검증한다.
    """
    call_count = {"n": 0}
    count_lock = threading.Lock()
    original_request = KiwoomAuth._request_new_token

    auth = KiwoomAuth(app_key, secret_key, is_mock=True, cache_dir=tmpdir)
    # 캐시된 토큰을 무효화하여 항상 새 발급 경로를 타도록 한다.
    auth._access_token = None
    auth._expires_at = 0

    def counting_request_new_token(self_inner):
        with count_lock:
            call_count["n"] += 1
        # 다른 스레드가 lock 경쟁 중임을 확인하기 위해 약간 대기
        import time as _t
        _t.sleep(0.05)
        # 원래 발급 로직(requests.post)은 patch 로 가로챈 뒤 고정 토큰 반환
        self_inner._access_token = _TOKEN_VALUE
        self_inner._token_type = "bearer"
        self_inner._expires_at = 9_999_999_999.0
        return _TOKEN_VALUE

    auth._request_new_token = counting_request_new_token.__get__(auth, KiwoomAuth)
    return auth, counting_request_new_token, call_count


class TestAuthTokenConcurrentRefresh(unittest.TestCase):
    def test_concurrent_get_token_calls_request_new_token_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            auth, _fake, count = _make_auth_with_spy(tmpdir)
            num_threads = 8
            barrier = threading.Barrier(num_threads)
            results: List[Optional[str]] = [None] * num_threads
            errors = []

            def worker(idx):
                try:
                    barrier.wait()
                    # force_refresh=False: 캐시 만료 시점에 여러 스레드가 동시 도달해도
                    # double-checked locking 으로 발급이 1회로 수렴함을 검증.
                    results[idx] = auth.get_token(force_refresh=False)
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            self.assertEqual(errors, [])
            # 모든 스레드가 동일한 토큰을 받았다.
            self.assertTrue(all(r == _TOKEN_VALUE for r in results), f"results={results}")
            # 발급 요청은 정확히 1회만 수행되었다(double-checked locking 효과).
            self.assertEqual(count["n"], 1, f"expected 1 token request, got {count['n']}")

    def test_cached_token_does_not_trigger_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            auth, _fake, count = _make_auth_with_spy(tmpdir)
            # 유효한 캐시 토큰 세팅
            auth._access_token = "cached"
            auth._expires_at = 9_999_999_999.0

            token = auth.get_token()

            self.assertEqual(token, "cached")
            self.assertEqual(count["n"], 0)


if __name__ == "__main__":
    unittest.main()
