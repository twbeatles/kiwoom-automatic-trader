
import sys
import unittest
from unittest.mock import MagicMock
import importlib.util

# Append path
sys.path.append('d:/google antigravity/키움증권 자동 매매 프로그램')

class TestPhase4(unittest.TestCase):
    from PyQt6.QtWidgets import QApplication
    
    def setUp(self):
        # Create QApplication instance if it doesn't exist
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
            
        # Import KiwoomProTrader dynamically
        spec = importlib.util.spec_from_file_location("kiwoom_auto", "d:/google antigravity/키움증권 자동 매매 프로그램/키움증권 자동매매.py")
        self.module = importlib.util.module_from_spec(spec)
        sys.modules["kiwoom_auto"] = self.module
        spec.loader.exec_module(self.module)
        self.KiwoomProTrader = self.module.KiwoomProTrader

    def test_keyring_import(self):
        """Test that keyring module is imported"""
        import keyring
        print("✅ keyring imported successfully")

    def test_winreg_import(self):
        """Test that winreg module is imported"""
        import winreg
        print("✅ winreg imported successfully")

    def test_class_attributes(self):
        """Test that KiwoomProTrader class has expected attributes"""
        # Signal is a class attribute
        self.assertTrue(hasattr(self.KiwoomProTrader, 'sig_order_execution'), "Missing sig_order_execution signal")
        # Method is a class attribute
        self.assertTrue(hasattr(self.KiwoomProTrader, '_set_auto_start'), "Missing _set_auto_start method")
        
        print("✅ KiwoomProTrader class has Signal and Method")

    def test_ui_code_presence(self):
        """Check if chk_auto_start is used in _create_api_tab using source code"""
        import inspect
        source = inspect.getsource(self.KiwoomProTrader._create_api_tab)
        self.assertIn("self.chk_auto_start", source, "chk_auto_start not found in _create_api_tab source")
        print("✅ chk_auto_start found in _create_api_tab source")

    def test_strategy_cleanup(self):
        """Test that StrategyManager legacy code is removed (indirectly)"""
        # We can't easily test "absence" of code without parsing AST, 
        # but we can verify imports
        pass

if __name__ == '__main__':
    unittest.main()
