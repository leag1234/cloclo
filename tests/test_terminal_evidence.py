"""Large complete terminal output enters M10 before the next model reservation."""

from decimal import Decimal
import os
import tempfile
import unittest
from unittest.mock import patch

from services.orchestrator.chat_pipeline import ChatTools
from services.orchestrator.interactions import Interaction
from services.orchestrator.model import Configuration, GatewayModel
from packages.profiles import PROFILES


class EvidenceTests(unittest.TestCase):
    def test_large_output_is_synthesized_and_measured_without_expanding_budget(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as root,
            patch.dict(os.environ, {"ATLAS_WEB_CACHE": root + "/cache.sqlite"}),
        ):
            tools = ChatTools(Interaction(), "Summarize the complete document")
            model = GatewayModel(
                "http://127.0.0.1",
                Configuration(
                    input_eur_per_mtok=Decimal("1"),
                    output_eur_per_mtok=Decimal("1"),
                    max_tokens=2048,
                ),
            )
            model.configure_quality(PROFILES[0], 3000, has_attachments=True)
            tools.model = model
            source = (
                "Document section: record every inspection and retain evidence.\n"
                * 12000
            )
            output = tools.document_evidence(
                {"exit_code": 0, "output": [{"type": "output", "data": source}]}
            )
            self.assertLess(len(str(output)), 12000)
            self.assertEqual(tools.item.documents[0]["source_characters"], len(source))
            self.assertTrue(tools.item.documents[0]["hierarchical_synthesis"])
            self.assertEqual(model.allowance, Decimal("0.30"))
            failure = {"exit_code": 1, "output": [{"data": "password protected"}]}
            self.assertEqual(tools.document_evidence(failure), failure)
