"""Project-specific document indexes reuse M2 embeddings, chunks and ranking."""

import hashlib
import json
from uuid import uuid4

from services.retrieval.extract import split_text
from services.retrieval.projects import Projects, bounded
from services.retrieval.search import Gateway, rank_scored
from services.retrieval.store import Chunk


class ProjectDocuments:
    def __init__(self, projects: Projects, gateway: Gateway) -> None:
        self.projects, self.gateway = projects, gateway
        with projects.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS project_documents (
                id TEXT PRIMARY KEY, project TEXT REFERENCES projects(id),
                name TEXT, chunks TEXT)""")

    def add(self, project: str, name: str, text: str, lang: str) -> str:
        self.projects.get(project)
        bounded(name, 120)
        bounded(text, 32000)
        if lang not in {"fr", "de", "es", "it", "en"}:
            raise ValueError("invalid_language")
        parts = split_text(text)
        vectors, revision = self.gateway.embed(parts, "document")
        identifier = str(uuid4())
        digest = hashlib.sha256(text.encode()).hexdigest()
        chunks = [
            Chunk(
                chunk_id=hashlib.sha256(
                    f"{project}:{identifier}:{i}".encode()
                ).hexdigest(),
                doc_id=identifier,
                source=name,
                langue=lang,
                source_sha256=digest,
                embedding_revision=revision,
                position=i,
                text=part,
                embedding=vector,
            )
            for i, (part, vector) in enumerate(zip(parts, vectors, strict=True))
        ]
        with self.projects.connection() as db:
            self.projects.require(db, project)
            db.execute(
                "INSERT INTO project_documents VALUES (?,?,?,?)",
                (
                    identifier,
                    project,
                    name,
                    json.dumps([c.model_dump() for c in chunks]),
                ),
            )
        return identifier

    def listing(self, project: str) -> list[dict[str, object]]:
        with self.projects.connection() as db:
            self.projects.require(db, project)
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,name FROM project_documents WHERE project=? ORDER BY rowid",
                    (project,),
                )
            ]

    def chunks(self, project: str) -> list[Chunk]:
        with self.projects.connection() as db:
            self.projects.require(db, project)
            return [
                Chunk.model_validate(c)
                for r in db.execute(
                    "SELECT chunks FROM project_documents WHERE project=? ORDER BY rowid",
                    (project,),
                )
                for c in json.loads(r["chunks"])
            ]

    def resolve(self, project: str, key: str) -> Chunk:
        for chunk in self.chunks(project):
            if chunk.chunk_id == key:
                return chunk
        raise KeyError("not_found")

    def search(self, project: str, query: str) -> list[dict[str, object]]:
        return [
            {
                **chunk.model_dump(include={"chunk_id", "doc_id", "source", "text"}),
                "score": score,
            }
            for chunk, score in rank_scored(query, self.chunks(project), self.gateway)
        ]
