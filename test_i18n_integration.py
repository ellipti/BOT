#!/usr/bin/env python3
"""
i18n Integration Test Suite
===========================

Монгол хэлний орчуулгын системийн интеграци тест

Шалгах зүйлс:
1. Telegram алерт системийн Монгол орчуулга
2. Дэглэм тогтоолтын системийн Монгол орчуулга
3. Арилжааны pipeline-н Монгол орчуулга
4. Нэвтрэх системийн Монгол орчуулга
5. Захиалгын амьдралын мөчлөгийн Монгол орчуулга
"""

import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings  # Correct import for settings
from utils.i18n import alert_message, get_message, log_message, t


class TestI18nIntegration(unittest.TestCase):
    """Монгол хэлний орчуулгын интегрэци тест"""

    def setUp(self):
        """Test тохиргоо"""
        self.test_logger = logging.getLogger("test_i18n")
        self.test_logger.setLevel(logging.DEBUG)

    def test_basic_translation_system(self):
        """Үндсэн орчуулгын системийн тест"""
        # Basic translation
        self.assertEqual(t("system_startup"), "Систем эхэлж байна...")
        self.assertEqual(t("system_shutdown"), "Систем унтарч байна")

        # Translation with parameters
        msg = t("order_placed", symbol="EURUSD", side="BUY", qty=1.0)
        self.assertIn("EURUSD", msg)
        self.assertIn("BUY", msg)
        self.assertIn("1.0", msg)

        # Fallback for unknown key
        self.assertEqual(t("unknown_key"), "unknown_key")

        print("✓ Үндсэн орчуулгын систем ажиллаж байна")

    def test_risk_telegram_alerts_integration(self):
        """Эрсдэлийн Telegram алертуудын интеграци тест"""
        # Test risk alert translations
        self.assertIn("Эрсдэлийн хориг", t("risk_block", reason="Test"))
        self.assertIn("Систем эхэлж байна", t("system_startup"))
        self.assertIn("Мэдээллийн эх холбогдлоо", t("feed_connected", feed_type="MT5"))

        # Test system error messages
        error_msg = t("system_error", error="Connection timeout")
        self.assertIn("Системийн алдаа", error_msg)
        self.assertIn("Connection timeout", error_msg)

        print("✓ Эрсдэлийн Telegram алерт системийн монгол орчуулга")

    def test_regime_detection_integration(self):
        """Дэглэм тогтоолтын системийн интеграци тест"""
        # Test regime detection messages
        init_msg = t("regime_detector_init", active=True, thresholds={"low": 0.003})
        self.assertIn("RegimeDetector эхэллээ", init_msg)
        self.assertIn("идэвхтэй=True", init_msg)

        # Test regime detection results
        detection_msg = t(
            "regime_detection",
            symbol="EURUSD",
            norm_atr=0.005,
            ret_vol=0.002,
            raw_regime="normal",
            stable_regime="normal",
        )
        self.assertIn("Дэглэм тогтоох", detection_msg)
        self.assertIn("EURUSD", detection_msg)

        # Test error conditions
        error_msg = t(
            "regime_detection_failed", symbol="GBPUSD", error="Insufficient data"
        )
        self.assertIn("Дэглэм тогтоох алдаатай", error_msg)
        self.assertIn("GBPUSD", error_msg)

        print("✓ Дэглэм тогтоолтын системийн монгол орчуулга")

    def test_trading_pipeline_integration(self):
        """Арилжааны pipeline-н интеграци тест"""
        # Test order placement messages
        order_msg = t("order_placed", symbol="EURUSD", side="BUY", qty=1.0)
        self.assertIn("Захиалга илгээгдлээ", order_msg)
        self.assertIn("EURUSD", order_msg)

        # Test order fill messages
        fill_msg = t("order_filled", symbol="GBPUSD", filled_qty=0.5, price=1.2345)
        self.assertIn("Захиалга биелэв", fill_msg)
        self.assertIn("GBPUSD", fill_msg)

        print("✓ Арилжааны pipeline-н монгол орчуулга")

    def test_dashboard_auth_integration(self):
        """Dashboard нэвтрэх системийн интеграци тест"""
        # Test authentication success
        auth_ok = t("auth_login_ok")
        self.assertIn("Нэвтрэлт амжилттай", auth_ok)

        # Test authentication failure
        auth_fail = t("auth_login_fail")
        self.assertIn("Нэвтрэлт амжилтгүй", auth_fail)

        print("✓ Dashboard нэвтрэх системийн монгол орчуулга")

    def test_order_lifecycle_integration(self):
        """Захиалгын амьдралын мөчлөгийн интеграци тест"""
        # Test OrderBook initialization
        init_msg = t("orderbook_initialized", db_path="/tmp/orders.db")
        self.assertIn("OrderBook", init_msg)
        self.assertIn("эхэллээ", init_msg)
        self.assertIn("/tmp/orders.db", init_msg)

        # Test order creation
        create_msg = t(
            "order_created_pending", coid="ORD123", side="BUY", qty=1.5, symbol="EURUSD"
        )
        self.assertIn("Хүлээгдэж буй захиалга", create_msg)
        self.assertIn("ORD123", create_msg)
        self.assertIn("BUY", create_msg)

        # Test order acceptance
        accept_msg = t(
            "order_accepted", coid="ORD123", broker_id="MT5_123", status="ACCEPTED"
        )
        self.assertIn("Захиалга хүлээн авагдсан", accept_msg)
        self.assertIn("ORD123", accept_msg)

        # Test order cancellation
        cancel_msg = t("order_cancelled", coid="ORD123")
        self.assertIn("Захиалга цуцлагдсан", cancel_msg)
        self.assertIn("ORD123", cancel_msg)

        print("✓ Захиалгын амьдралын мөчлөгийн монгол орчуулга")

    def test_convenience_functions(self):
        """Тусламжийн функцүүдийн тест"""
        # Test convenience aliases
        alert = alert_message("risk_block", reason="High volatility")
        log = log_message("system_startup")

        self.assertIn("Эрсдэлийн хориг", alert)
        self.assertIn("Систем эхэлж байна", log)

        # Test locale override
        en_msg = get_message("test_key", locale="en")
        mn_msg = get_message("test_key", locale="mn")

        print("✓ Тусламжийн функцүүд ажиллаж байна")

    def test_configuration_integration(self):
        """Тохиргооны интеграци тест"""
        # Verify locale configuration
        self.assertEqual(settings.LOCALE, "mn", "Locale должен быть установлен на 'mn'")
        self.assertEqual(
            settings.TZ, "Asia/Ulaanbaatar", "Timezone должен быть Ulaanbaatar"
        )

        print("✓ Тохиргооны интеграци зөв")

    def test_error_handling(self):
        """Алдааны боловсруулалтын тест"""
        # Test formatting errors
        try:
            # This should not crash even with invalid format parameters
            result = t("order_placed", invalid_param="test")
            self.assertIsInstance(result, str)
        except Exception as e:
            self.fail(f"i18n should handle formatting errors gracefully: {e}")

        print("✓ Алдааны боловсруулалт зөв ажиллаж байна")

    def test_mongolian_characters(self):
        """Монгол үсгийн дэмжлэгийн тест"""
        # Test that Mongolian characters are properly handled
        test_msg = t("system_startup")

        # Check for common Mongolian characters
        mongolian_chars = ["ө", "ү", "ё", "ы", "э", "ъ", "ь"]
        has_mongolian = any(char in test_msg for char in mongolian_chars)
        self.assertTrue(has_mongolian, f"Монгол үсэг олдсонгүй: {test_msg}")

        print("✓ Монгол үсгийн дэмжлэг зөв ажиллаж байна")

    def tearDown(self):
        """Test цэвэрлэх"""
        pass


def run_integration_test():
    """Интеграци тест ажиллуулах"""
    print("=" * 50)
    print("i18n Integration Test Suite")
    print("Монгол хэлний орчуулгын системийн интеграци тест")
    print("=" * 50)
    print()

    # Configure logging for test
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run tests
    unittest.main(argv=[""], exit=False, verbosity=2)

    print("\n" + "=" * 50)
    print("i18n интеграци тест дууслаа!")
    print("=" * 50)


if __name__ == "__main__":
    run_integration_test()
