import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from schema_engine import check_schema_parity


class SchemaParityTest(unittest.TestCase):
    def test_faq_parity_success(self):
        content_pack = {
            "faq": [
                {"question": "Como contratar?", "answer": "Use o formulario oficial."},
                {"question": "Quais documentos?", "answer": "Documento oficial com foto."},
            ]
        }
        schema = {
            "@graph": [
                {
                    "@type": "FAQPage",
                    "mainEntity": [
                        {"name": "Como contratar?", "acceptedAnswer": {"text": "Use o formulario oficial."}},
                        {"name": "Quais documentos?", "acceptedAnswer": {"text": "Documento oficial com foto."}},
                    ],
                }
            ]
        }
        ok, errors = check_schema_parity(schema, content_pack)
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_faq_parity_failure(self):
        content_pack = {"faq": [{"question": "Como contratar?", "answer": "Use o formulario oficial."}]}
        schema = {
            "@graph": [
                {
                    "@type": "FAQPage",
                    "mainEntity": [{"name": "Pergunta errada", "acceptedAnswer": {"text": "Resposta errada"}}],
                }
            ]
        }
        ok, errors = check_schema_parity(schema, content_pack)
        self.assertFalse(ok)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()

