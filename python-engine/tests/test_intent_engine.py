import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from intent_engine import detect_intent


class IntentRulesTest(unittest.TestCase):
    def test_transacional_rule_by_path(self):
        parsed = {"title": "Oferta especial", "full_text": "Condicoes e parcelas"}
        self.assertEqual(detect_intent("https://example.com/ofertas/novo", parsed), "transacional")

    def test_informational_rule_by_path(self):
        parsed = {"title": "Linha de modelos", "full_text": "Comparativo de versoes"}
        self.assertEqual(detect_intent("https://example.com/modelos", parsed), "informacional_comparativa")

    def test_local_rule_by_path(self):
        parsed = {"title": "Concessionarias", "full_text": "enderecos e horarios"}
        self.assertEqual(detect_intent("https://example.com/concessionarias", parsed), "local")


if __name__ == "__main__":
    unittest.main()

