"""RAG del corpus: recuperación, prompt del sistema y generación de respuesta."""

import hashlib
import json
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from carvajal.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    GOLD_DIR,
    INDEX_DIR,
    LLM_PROVIDER,
    QUESTIONS_FILE,
)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDINGS_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.2"
MAX_SYSTEM_PROMPT_CHARS = 100_000

DEFAULT_SYSTEM_PROMPT = (
    "Eres el asistente del corpus Carvajal. Tu fuente es el CORPUS CARVAJAL incluido en "
    "este mensaje de sistema, complementado con los fragmentos recuperados que se "
    "adjuntan. Responde únicamente con esa información. Sé completo: si la pregunta pide "
    "una lista, cronología o explicación, incluye todos los elementos relevantes del "
    "corpus. Si la respuesta no está en el corpus, di claramente que no lo sabes; si solo "
    "hay información parcial, responde con lo disponible e indica qué falta. No inventes "
    "datos ni uses conocimiento externo. Cita las fuentes consultadas. Distingue siempre "
    "entre fuentes oficiales (carvajal.com) y de terceros (prensa, analistas): si una cifra "
    "proviene de un tercero, dilo y menciona el medio y la fecha."
)


def load_gold_documents(gold_dir: Path = GOLD_DIR) -> list[Document]:
    """Carga los entregables Gold (Markdown con front matter) como documentos.

    Args:
        gold_dir: Directorio con los Markdown del corpus.

    Returns:
        Lista de documentos listos para embeddear y recuperar.
    """

    documents: list[Document] = []
    if not gold_dir.exists():
        return documents
    for path in sorted(gold_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        front_matter = _parse_front_matter(content)
        metadata = {
            "source": str(path),
            "slug": path.stem,
            "title": front_matter.get("title", path.stem),
            "domain": front_matter.get("domain", "carvajal.com"),
            "source_type": front_matter.get("source_type", "oficial"),
        }
        documents.append(Document(page_content=content, metadata=metadata))
    return documents


def _parse_front_matter(content: str) -> dict[str, str]:
    """Lee el *front matter* YAML simple del Markdown Gold (clave: valor)."""

    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) != 3:
        return {}
    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip():
            metadata[key.strip()] = value.strip()
    return metadata


def build_retriever(documents: list[Document], index_dir: Path = INDEX_DIR) -> BaseRetriever:
    """Construye o reutiliza un retriever FAISS sobre los documentos del corpus.

    Los documentos se dividen en chunks (``RecursiveCharacterTextSplitter``) antes de
    embedirse. El índice se persiste en ``index_dir`` y se reutiliza mientras el corpus
    no cambie: los embeddings se calculan en CPU y tardan minutos, por lo que
    recalcularlos en cada arranque haría inutilizable la interfaz. Para forzar la
    reconstrucción basta con borrar ese directorio.

    Args:
        documents: Documentos cargados desde ``data/gold/``.
        index_dir: Directorio donde se guarda el índice FAISS (por defecto ``data/index``).

    Returns:
        Retriever con similitud (embeddings de Ollama, modelo ``nomic-embed-text``).
    """

    chunks = _split_documents(documents)
    fingerprint = _fingerprint(chunks)
    embeddings = OllamaEmbeddings(model=EMBEDDINGS_MODEL)
    index_path = index_dir / "faiss"
    fingerprint_file = index_dir / "fingerprint.txt"

    if (
        index_path.exists()
        and fingerprint_file.exists()
        and fingerprint_file.read_text(encoding="utf-8").strip() == fingerprint
    ):
        vectorstore = FAISS.load_local(
            str(index_path),
            embeddings,
            allow_dangerous_deserialization=True,
        )
    else:
        vectorstore = FAISS.from_texts(
            texts=[chunk.page_content for chunk in chunks],
            embedding=embeddings,
            metadatas=[chunk.metadata for chunk in chunks],
        )
        index_path.mkdir(parents=True, exist_ok=True)
        vectorstore.save_local(str(index_path))
        fingerprint_file.write_text(fingerprint, encoding="utf-8")

    return vectorstore.as_retriever(search_kwargs={"k": 5})


def _split_documents(documents: list[Document]) -> list[Document]:
    """Divide los documentos del corpus en chunks con metadatos heredados."""

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks: list[Document] = []
    for document in documents:
        metadata = dict(document.metadata)
        body = Document(
            page_content=_strip_front_matter(document.page_content),
            metadata=metadata,
        )
        for chunk in splitter.split_documents([body]):
            chunk.metadata = {**metadata, "source": metadata.get("source", "")}
            chunks.append(chunk)
    return chunks


def _fingerprint(chunks: list[Document]) -> str:
    """Calcula la huella del corpus para invalidar el índice cuando cambie."""

    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk.page_content.encode("utf-8"))
    return digest.hexdigest()


def index_is_fresh(documents: list[Document], index_dir: Path = INDEX_DIR) -> bool:
    """Indica si el índice FAISS en caché corresponde al corpus actual.

    Args:
        documents: Documentos cargados desde ``data/gold/``.
        index_dir: Directorio del índice (por defecto ``data/index``).

    Returns:
        ``True`` si la huella del corpus coincide con la del índice guardado.
    """

    fingerprint_file = index_dir / "fingerprint.txt"
    if not fingerprint_file.exists():
        return False
    stored = fingerprint_file.read_text(encoding="utf-8").strip()
    return stored == _fingerprint(_split_documents(documents))


def build_system_prompt(documents: list[Document]) -> str:
    """Consolida el corpus limpio en el prompt de sistema (la 'memoria' del asistente).

    Args:
        documents: Documentos cargados desde ``data/gold/``.

    Returns:
        Instrucciones de sistema con el corpus consolidado como contexto permanente.
    """

    sections: list[str] = []
    for document in documents:
        slug = str(document.metadata.get("slug", "documento"))
        domain = document.metadata.get("domain", "carvajal.com")
        kind = document.metadata.get("source_type", "oficial")
        body = _strip_front_matter(document.page_content)
        sections.append(f"### Fuente: {slug} · {domain} ({kind})\n\n{body}")

    corpus = "\n\n".join(sections)
    if len(corpus) > MAX_SYSTEM_PROMPT_CHARS:
        corpus = f"{corpus[:MAX_SYSTEM_PROMPT_CHARS]}\n\n[corpus truncado por longitud]"

    return f"{DEFAULT_SYSTEM_PROMPT}\n\n=== CORPUS CARVAJAL ===\n\n{corpus}"


def _strip_front_matter(content: str) -> str:
    """Quita el *front matter* YAML del Markdown Gold."""

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return content.strip()


def build_llm() -> Runnable:
    """Construye el LLM configurado mediante variables de entorno.

    Returns:
        ``ChatOllama`` con ``LLM_PROVIDER=ollama`` (por defecto),
        ``ChatOpenAI`` apuntando a DeepSeek con ``LLM_PROVIDER=deepseek`` o
        ``ChatAnthropic`` con ``LLM_PROVIDER=claude``.
    """

    if LLM_PROVIDER == "deepseek":
        return ChatOpenAI(
            model=DEEPSEEK_MODEL,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0,
        )
    if LLM_PROVIDER == "claude":
        return ChatAnthropic(model=CLAUDE_MODEL, api_key=ANTHROPIC_API_KEY, temperature=0)
    return ChatOllama(model=LLM_MODEL, temperature=0)


def ask(
    question: str,
    retriever: Runnable,
    system_prompt: str | None = None,
    llm: Runnable | None = None,
) -> str:
    """Genera una respuesta RAG a partir de la pregunta y el retriever.

    Args:
        question: Pregunta del usuario.
        retriever: Retriever sobre el corpus.
        system_prompt: Instrucciones de sistema (por defecto: ``DEFAULT_SYSTEM_PROMPT``).
        llm: LLM invocable (por defecto: el LLM configurado por ``LLM_PROVIDER``).

    Returns:
        Respuesta generada por el LLM.
    """

    answer, _ = ask_with_sources(question, retriever, system_prompt=system_prompt, llm=llm)
    return answer


def ask_with_sources(
    question: str,
    retriever: Runnable,
    system_prompt: str | None = None,
    llm: Runnable | None = None,
) -> tuple[str, list[Document]]:
    """Genera la respuesta y devuelve también los fragmentos que la sustentan.

    Args:
        question: Pregunta del usuario.
        retriever: Retriever sobre el corpus.
        system_prompt: Instrucciones de sistema (por defecto: ``DEFAULT_SYSTEM_PROMPT``).
        llm: LLM invocable (por defecto: el LLM configurado por ``LLM_PROVIDER``).

    Returns:
        Tupla con la respuesta generada y la lista de documentos recuperados.
    """

    retrieved_documents = retriever.invoke(question)
    context = "\n\n".join(document.page_content for document in retrieved_documents)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt or DEFAULT_SYSTEM_PROMPT),
            ("human", "Contexto:\n{context}\n\nPregunta: {question}"),
        ]
    )
    messages = prompt.format_messages(context=context, question=question)
    response = (llm if llm is not None else build_llm()).invoke(messages)
    return str(response.content), list(retrieved_documents)


def load_questions(path: Path = QUESTIONS_FILE) -> list[str]:
    """Carga las preguntas de prueba desde un archivo JSON.

    Args:
        path: Archivo JSON con una lista de preguntas.

    Returns:
        Lista de preguntas de evaluación.
    """

    data = json.loads(path.read_text(encoding="utf-8"))
    return [str(question) for question in data]


def evaluate(
    questions: list[str],
    retriever: Runnable,
    system_prompt: str | None = None,
    llm: Runnable | None = None,
) -> list[dict[str, str]]:
    """Ejecuta el pipeline RAG sobre cada pregunta de prueba.

    Args:
        questions: Preguntas de evaluación.
        retriever: Retriever sobre el corpus.
        system_prompt: Instrucciones de sistema con el corpus consolidado.
        llm: LLM invocable (por defecto: el configurado por ``LLM_PROVIDER``).

    Returns:
        Resultados con la pregunta y la respuesta generada.
    """

    results: list[dict[str, str]] = []
    for question in questions:
        answer = ask(question, retriever, system_prompt=system_prompt, llm=llm)
        results.append({"question": question, "answer": answer})
    return results


def render_results_markdown(results: list[dict[str, str]]) -> str:
    """Renderiza los resultados de la evaluación como Markdown.

    Args:
        results: Preguntas y respuestas generadas.

    Returns:
        Documento Markdown con la tabla de resultados.
    """

    lines = ["# Resultados de la evaluación", ""]
    for index, result in enumerate(results, start=1):
        lines.append(f"## {index}. {result['question']}")
        lines.append("")
        lines.append(result["answer"])
        lines.append("")
    return "\n".join(lines)
