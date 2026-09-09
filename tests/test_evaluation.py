import unittest
from unittest.mock import Mock

from services.retrieval.answer import answer
from services.retrieval.search import Gateway
from services.retrieval.store import Chunk, Store


class EvaluationTests(unittest.TestCase):
    def test_resolution_and_rejections(self) -> None:
        chunk = Chunk(
            chunk_id="a" * 64,
            doc_id="doc",
            langue="fr",
            source="doc.md",
            source_sha256="b" * 64,
            embedding_revision="test",
            position=0,
            text="source",
            embedding=[1.0],
        )
        gateway = Mock(spec=Gateway)
        store = Mock(spec=Store)
        store.resolve.return_value = chunk
        good = {
            "text": "Fact [" + chunk.chunk_id + "].",
            "citations": [chunk.chunk_id],
            "refused": False,
        }
        gateway.post.return_value = good
        self.assertEqual(
            answer("q", [chunk], gateway, store).citations, [chunk.chunk_id]
        )
        changes: list[dict[str, object]] = [
            {"citations": []},
            {"citations": ["c" * 64]},
            {"refused": True},
            {"text": "no reference"},
            {"citations": [chunk.chunk_id] * 2},
        ]
        for change in changes:
            gateway.post.return_value = good | change
            with self.assertRaises(ValueError):
                answer("q", [chunk], gateway, store)
        gateway.post.return_value = good
        store.resolve.side_effect = KeyError("deleted")
        with self.assertRaises(KeyError):
            answer("q", [chunk], gateway, store)
        store.resolve.side_effect = None
        store.resolve.return_value = chunk.model_copy(update={"text": "changed"})
        with self.assertRaisesRegex(ValueError, "citation_changed"):
            answer("q", [chunk], gateway, store)
