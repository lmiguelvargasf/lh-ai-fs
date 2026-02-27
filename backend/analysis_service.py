from __future__ import annotations

from pathlib import Path

from orchestrator import PipelineOrchestrator
from schemas import AnalyzeRequest, VerificationReport


DOCUMENTS_DIR = Path(__file__).parent / "documents"


def load_documents(documents_dir: Path | None = None) -> dict[str, str]:
    target_dir = documents_dir or DOCUMENTS_DIR
    documents: dict[str, str] = {}
    for file_path in target_dir.glob("*.txt"):
        documents[file_path.stem] = file_path.read_text()
    return documents


def analyze_documents(
    request: AnalyzeRequest,
    documents: dict[str, str] | None = None,
    authority_overrides: dict[str, dict] | None = None,
) -> VerificationReport:
    orchestrator = PipelineOrchestrator()
    source_documents = documents or load_documents()
    return orchestrator.run(
        source_documents,
        request=request,
        authority_overrides=authority_overrides,
    )
