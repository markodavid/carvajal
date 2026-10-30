"""Pruebas del módulo RAG del corpus."""

from pathlib import Path

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from carvajal.corpus import load_gold_documents
from carvajal.rag import (
    DEFAULT_SYSTEM_PROMPT,
    ask,
    build_llm,
    build_retriever,
    build_system_prompt,
    evaluate,
    load_questions,
    render_results_markdown,
)


def test_load_gold_documents_devuelve_corpus() -> None:
    """Carga los entregables Gold disponibles en ``data/gold``."""

    documents = load_gold_documents()

    assert len(documents) > 0
    assert all(isinstance(document, Document) for document in documents)


def test_build_system_prompt_restringe_respuesta() -> None:
    """El prompt del sistema define restricciones de respuesta sobre el corpus."""

    prompt = build_system_prompt([])

    assert DEFAULT_SYSTEM_PROMPT in prompt
    assert "CORPUS CARVAJAL" in prompt
    assert "no lo sabes" in prompt.lower()


def test_ask_genera_respuesta_con_contexto() -> None:
    """El pipeline RAG recupera contexto y delega la respuesta al LLM."""

    captured_messages: list = []

    def fake_retriever(query: str) -> list[Document]:
        return [Document(page_content="Contexto de prueba.", metadata={"source": "test.md"})]

    def fake_llm(messages: list) -> AIMessage:
        captured_messages.append(messages)
        return AIMessage(content="Respuesta de prueba")

    retriever = RunnableLambda(fake_retriever)
    llm = RunnableLambda(fake_llm)

    answer = ask("pregunta", retriever, system_prompt="Sos el asistente.", llm=llm)

    assert answer == "Respuesta de prueba"
    assert len(captured_messages) == 1
    first_message = captured_messages[0][1]
    assert "Contexto:" in first_message.content


def test_build_llm_devuelve_ollama_cuando_se_configura(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con ``LLM_PROVIDER=ollama`` el LLM es Ollama."""

    monkeypatch.setattr("carvajal.rag.LLM_PROVIDER", "ollama")

    assert isinstance(build_llm(), ChatOllama)


def test_build_llm_devuelve_claude_cuando_se_configura(monkeypatch: pytest.MonkeyPatch) -> None:
    """El proveedor Claude (vía API) se selecciona con ``LLM_PROVIDER=claude``."""

    monkeypatch.setattr("carvajal.rag.LLM_PROVIDER", "claude")
    monkeypatch.setattr("carvajal.rag.ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("carvajal.rag.CLAUDE_MODEL", "claude-sonnet-4-5")

    assert isinstance(build_llm(), ChatAnthropic)


def test_build_llm_devuelve_deepseek_cuando_se_configura(monkeypatch: pytest.MonkeyPatch) -> None:
    """El proveedor DeepSeek (API compatible con OpenAI) se selecciona con ``LLM_PROVIDER``."""

    monkeypatch.setattr("carvajal.rag.LLM_PROVIDER", "deepseek")
    monkeypatch.setattr("carvajal.rag.DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("carvajal.rag.DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setattr("carvajal.rag.DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    assert isinstance(build_llm(), ChatOpenAI)


def test_build_system_prompt_consolida_corpus() -> None:
    """El prompt de sistema incluye el texto limpio del corpus consolidado."""

    documents = load_gold_documents()
    prompt = build_system_prompt(documents)

    assert DEFAULT_SYSTEM_PROMPT in prompt
    assert "=== CORPUS CARVAJAL ===" in prompt
    assert "### Fuente:" in prompt
    assert "Carvajal" in prompt
    assert "captured_at:" not in prompt


def test_build_system_prompt_omite_la_capa_extendida() -> None:
    """El prompt consolida el núcleo, no la capa extendida."""

    documents = [
        Document(
            page_content="---\ntitle: Núcleo\n---\n\nTexto del núcleo.",
            metadata={"slug": "nucleo", "layer": "core"},
        ),
        Document(
            page_content="---\ntitle: Externo\n---\n\nTexto extendido.",
            metadata={"slug": "externo", "layer": "extended"},
        ),
    ]

    prompt = build_system_prompt(documents)

    assert "Texto del núcleo." in prompt
    assert "Texto extendido." not in prompt


def test_ask_etiqueta_los_fragmentos_con_su_fuente() -> None:
    """El contexto entregado al LLM identifica la fuente y la capa del fragmento."""

    captured_messages: list = []

    def fake_retriever(query: str) -> list[Document]:
        return [
            Document(
                page_content="Contenido externo.",
                metadata={
                    "slug": "ext_abc",
                    "domain": "carvajalempaques.com",
                    "source_type": "colaborador",
                    "page": "4",
                },
            )
        ]

    def fake_llm(messages: list) -> AIMessage:
        captured_messages.append(messages)
        return AIMessage(content="Respuesta")

    ask(
        "pregunta",
        RunnableLambda(fake_retriever),
        system_prompt="Sistema.",
        llm=RunnableLambda(fake_llm),
    )

    human = captured_messages[0][1].content
    assert "[Fuente: ext_abc · carvajalempaques.com · colaborador · página 4]" in human
    assert "Contenido externo." in human


def test_load_questions_carga_preguntas(tmp_path: Path) -> None:
    """Carga las preguntas de prueba desde un archivo JSON."""

    questions_file = tmp_path / "questions.json"
    questions_file.write_text('["¿Pregunta uno?", "¿Pregunta dos?"]', encoding="utf-8")

    questions = load_questions(questions_file)

    assert questions == ["¿Pregunta uno?", "¿Pregunta dos?"]


def test_evaluate_genera_resultados_por_pregunta() -> None:
    """Ejecuta cada pregunta y conserva pregunta y respuesta."""

    def fake_retriever(query: str) -> list[Document]:
        return [Document(page_content="Contexto de prueba.", metadata={"source": "test.md"})]

    def fake_llm(messages: list) -> AIMessage:
        return AIMessage(content="Respuesta de prueba")

    results = evaluate(
        ["¿Pregunta uno?", "¿Pregunta dos?"],
        RunnableLambda(fake_retriever),
        system_prompt="Sos el asistente.",
        llm=RunnableLambda(fake_llm),
    )

    assert len(results) == 2
    assert results[0]["question"] == "¿Pregunta uno?"
    assert results[0]["answer"] == "Respuesta de prueba"


def test_render_results_markdown_incluye_preguntas_y_respuestas() -> None:
    """Renderiza los resultados como secciones Markdown numeradas."""

    markdown = render_results_markdown([{"question": "¿Pregunta uno?", "answer": "Respuesta uno"}])

    assert "# Resultados de la evaluación" in markdown
    assert "## 1. ¿Pregunta uno?" in markdown
    assert "Respuesta uno" in markdown


class _FakeVectorStore:
    """Vector store mínimo para probar la persistencia del índice."""

    def __init__(self, texts: list[str] | None = None) -> None:
        self.texts = texts or []

    def as_retriever(self, search_kwargs: dict | None = None) -> str:
        return "retriever"

    def save_local(self, folder_path: str) -> None:
        (Path(folder_path) / "index.faiss").write_text("indice", encoding="utf-8")


def _fake_faiss(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Sustituye FAISS y los embeddings por dobles que registran su uso."""

    calls: list[str] = []

    def fake_from_texts(texts: list[str], embedding: object, metadatas: list) -> _FakeVectorStore:
        calls.append("from_texts")
        return _FakeVectorStore(texts)

    def fake_load_local(
        folder_path: str, embeddings: object, allow_dangerous_deserialization: bool = False
    ) -> _FakeVectorStore:
        calls.append("load_local")
        return _FakeVectorStore()

    monkeypatch.setattr("carvajal.rag.FAISS.from_texts", fake_from_texts)
    monkeypatch.setattr("carvajal.rag.FAISS.load_local", fake_load_local)
    monkeypatch.setattr("carvajal.rag.OllamaEmbeddings", lambda model: "embeddings")
    return calls


def test_build_retriever_reutiliza_el_indice_en_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El índice FAISS se guarda en disco y se reutiliza si el corpus no cambia."""

    calls = _fake_faiss(monkeypatch)
    index_dir = tmp_path / "index"
    documents = [Document(page_content="Contenido del corpus.", metadata={"source": "x.md"})]

    first = build_retriever(documents, index_dir)
    second = build_retriever(documents, index_dir)

    assert first == "retriever"
    assert second == "retriever"
    assert calls == ["from_texts", "load_local"]
    assert (index_dir / "fingerprint.txt").exists()


def test_build_retriever_reconstruye_cuando_cambia_el_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si el corpus cambia, el índice en caché se descarta y se recalcula."""

    calls = _fake_faiss(monkeypatch)
    index_dir = tmp_path / "index"

    build_retriever([Document(page_content="Versión uno.", metadata={"source": "x.md"})], index_dir)
    build_retriever([Document(page_content="Versión dos.", metadata={"source": "x.md"})], index_dir)

    assert calls == ["from_texts", "from_texts"]
