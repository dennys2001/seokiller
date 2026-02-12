import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scoring_engine import compute_aeo_score


class ScoringEngineTest(unittest.TestCase):
    def test_answer_first_scores_when_top_direct_answer_exists(self):
        content_pack = {
            "markdown": "# Titulo\n\n**Resposta direta:** Resposta objetiva.\n\n### Como funciona?\nDetalhe.",
            "direct_answer": "Resposta objetiva.",
            "faq": [{"question": "Como funciona?", "answer": "Funciona assim."}] * 5,
        }
        schema = {
            "@graph": [
                {
                    "@type": "FAQPage",
                    "mainEntity": [{"name": "Como funciona?", "acceptedAnswer": {"text": "Funciona assim."}}] * 5,
                }
            ]
        }
        score = compute_aeo_score(
            intent="informacional_comparativa",
            primary_question="Como funciona?",
            entities=[{"entity_type": "Brand", "entity_name": "Peugeot", "evidence": {"snippet": "x"}}] * 5,
            content_pack=content_pack,
            schema=schema,
            secondary_questions=["Como funciona?", "Quais versoes existem?", "Quanto custa?"],
        )
        self.assertGreaterEqual(score["breakdown"]["answer_first"]["score"], 12)
        self.assertGreater(score["total"], 0)


if __name__ == "__main__":
    unittest.main()

