
import sys
import threading
import unittest
from unittest.mock import MagicMock

# Append path
sys.path.append('d:/google antigravity/키움증권 자동 매매 프로그램')

# Import modules to check syntax
try:
    from api.rest_client import KiwoomRESTClient
    from api.auth import KiwoomAuth
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("kiwoom_auto", "d:/google antigravity/키움증권 자동 매매 프로그램/키움증권 자동매매.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["kiwoom_auto"] = module
    spec.loader.exec_module(module)
    KiwoomProTrader = module.KiwoomProTrader
    
    print("✅ Module imports successful (Syntax check passed)")
except ImportError as e:
    print(f"❌ Import failed (Syntax error?): {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Syntax or Init error: {e}")
    sys.exit(1)

class TestPhase3(unittest.TestCase):
    def test_rest_client_lock(self):
        """Test that KiwoomRESTClient has a thread lock"""
        auth = MagicMock(spec=KiwoomAuth)
        client = KiwoomRESTClient(auth)
        
        self.assertTrue(hasattr(client, '_lock'), "KiwoomRESTClient missing _lock attribute")
        self.assertIsInstance(client._lock, type(threading.Lock()), "_lock is not a threading.Lock")
        print("✅ KiwoomRESTClient has threading.Lock")

if __name__ == '__main__':
    unittest.main()
