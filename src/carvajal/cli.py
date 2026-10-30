"""Interfaz de línea de comandos: capture / ask / summarize / faq / import / eval / status."""

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path

from carvajal.config import (
    EXTERNAL_CORPUS_DIR,
    EXTERNAL_DIR,
    EXTERNAL_SEEDS,
    GOLD_DIR,
    IMPORT_CATEGORIES,
    IMPORT_MAX_CHARS,
    IMPORT_MAX_DOC_CHARS,
    IMPORT_MAX_DOCS,
    IMPORT_MAX_PAGES,
    INDEX_FILE,
    QUESTIONS_FILE,
    REQUEST_DELAY_SECONDS,
    RESULTS_FILE,
    SEEDS,
)
from carvajal.corpus import load_gold_documents
from carvajal.fetching import WebClient
from carvajal.importer import ImportReport, import_external
from carvajal.pipeline import CaptureReport
from carvajal.pipeline import capture as run_capture
from carvajal.rag import (
    ask as run_ask,
)
from carvajal.rag import (
    build_retriever,
    build_system_prompt,
    evaluate,
    generate_faq,
    load_questions,
    render_results_markdown,
    summarize,
)


def build_parser() -> argparse.ArgumentParser:
    """Construye el parser de argumentos de la CLI.

    Returns:
        Parser con los subcomandos ``capture``, ``ask``, ``eval``, ``status`` y ``list``.
    """

    parser = argparse.ArgumentParser(
        prog="carvajal",
        description="Pipeline de captura y curaduría del corpus web de Carvajal.",
    )
    subparsers = parser.add_subparsers(dest="command")

    capture_parser = subparsers.add_parser(
        "capture",
        help="Captura las páginas de las semillas y genera el entregable Gold.",
    )
    capture_parser.add_argument(
        "--seed",
        action="append",
        default=None,
        help="Semilla adicional a capturar (puede repetirse).",
    )
    capture_parser.add_argument(
        "--scope",
        choices=("all", "oficial", "terceros"),
        default="all",
        help="Qué semillas capturar: todo, solo el sitio oficial o solo fuentes de terceros.",
    )
    capture_parser.add_argument(
        "--list-seeds",
        action="store_true",
        help="Lista las semillas configuradas y termina.",
    )
    capture_parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Segundos de espera entre peticiones al mismo host (rate limit).",
    )
    capture_parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="No consultar robots.txt (solo para pruebas locales).",
    )

    ask_parser = subparsers.add_parser(
        "ask",
        help="Genera una respuesta RAG para una pregunta del corpus.",
    )
    ask_parser.add_argument(
        "question",
        help="Pregunta del usuario.",
    )

    eval_parser = subparsers.add_parser(
        "eval",
        help="Ejecuta las preguntas de prueba y genera el informe de resultados.",
    )
    eval_parser.add_argument(
        "--questions",
        type=Path,
        default=QUESTIONS_FILE,
        help="Archivo JSON con las preguntas de prueba.",
    )
    eval_parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_FILE,
        help="Archivo Markdown donde se escriben los resultados.",
    )

    summarize_parser = subparsers.add_parser(
        "summarize",
        help="Genera un resumen ejecutivo del corpus (tarea de LLM).",
    )
    summarize_parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs") / "resumen.md",
        help="Archivo Markdown donde se escribe el resumen.",
    )
    summarize_parser.add_argument(
        "--focus",
        default=None,
        help="Tema opcional sobre el que centrar el resumen.",
    )

    faq_parser = subparsers.add_parser(
        "faq",
        help="Genera una FAQ del corpus para un cliente primerizo (tarea de LLM).",
    )
    faq_parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs") / "faq.md",
        help="Archivo Markdown donde se escribe la FAQ.",
    )

    import_parser = subparsers.add_parser(
        "import",
        help="Importa un corpus externo a la capa extendida (solo recuperación).",
    )
    import_parser.add_argument(
        "--from",
        dest="corpus_root",
        type=Path,
        default=EXTERNAL_CORPUS_DIR,
        help="Raíz del repositorio del corpus donante (solo lectura).",
    )
    import_parser.add_argument(
        "--source",
        default="alejandro",
        help="Nombre corto de la fuente; se usa en el manifiesto y en ``origin``.",
    )
    import_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Destino de la capa extendida (por defecto data/external/<fuente>).",
    )
    import_parser.add_argument(
        "--release",
        default="",
        help="Etiqueta de la captura donante (por ejemplo, corpus-2026-10-23).",
    )
    import_parser.add_argument(
        "--categories",
        default=",".join(IMPORT_CATEGORIES),
        help="Categorías del catálogo donante, separadas por comas.",
    )
    import_parser.add_argument(
        "--max-docs",
        type=int,
        default=IMPORT_MAX_DOCS,
        help="Máximo de documentos a importar.",
    )
    import_parser.add_argument(
        "--max-chars",
        type=int,
        default=IMPORT_MAX_CHARS,
        help="Presupuesto de caracteres del cuerpo importado.",
    )
    import_parser.add_argument(
        "--max-doc-chars",
        type=int,
        default=IMPORT_MAX_DOC_CHARS,
        help="Tamaño máximo estimado por documento.",
    )
    import_parser.add_argument(
        "--max-pages",
        type=int,
        default=IMPORT_MAX_PAGES,
        help="Páginas máximas por PDF (0 desactiva los PDF).",
    )
    import_parser.add_argument(
        "--min-chars",
        type=int,
        default=200,
        help="Longitud mínima de un documento para conservarlo.",
    )

    subparsers.add_parser(
        "status",
        help="Muestra el estado del corpus (semillas y entregables Gold).",
    )

    subparsers.add_parser(
        "list",
        help="Lista las semillas del corpus.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la CLI.

    Args:
        argv: Argumentos de línea de comandos (por defecto: ``sys.argv[1:]``).

    Returns:
        Código de salida del comando.
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "capture":
        seeds = (*_seeds_for(args.scope), *(args.seed or []))
        if args.list_seeds:
            for seed in seeds:
                print(seed)
            return 0
        client = _build_client(args)
        report = run_capture(seeds, client=client)
        for page in report.pages:
            print(f"Capturada: {page.url} -> data/gold/{page.slug}.md")
        print_report(report)
        return 0

    if args.command == "ask":
        documents = load_gold_documents()
        retriever = build_retriever(documents)
        answer = run_ask(args.question, retriever, system_prompt=build_system_prompt(documents))
        print(answer)
        return 0

    if args.command == "eval":
        documents = load_gold_documents()
        retriever = build_retriever(documents)
        questions = load_questions(args.questions)
        results = evaluate(questions, retriever, system_prompt=build_system_prompt(documents))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_results_markdown(results), encoding="utf-8")
        print(f"Evaluación completada: {len(results)} preguntas -> {args.output}")
        return 0

    if args.command == "summarize":
        documents = load_gold_documents()
        content = summarize(documents, focus=args.focus)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(_task_document("Resumen ejecutivo del corpus", content), "utf-8")
        print(f"Resumen generado: {args.output}")
        return 0

    if args.command == "faq":
        documents = load_gold_documents()
        content = generate_faq(documents)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(_task_document("FAQ del corpus", content), "utf-8")
        print(f"FAQ generada: {args.output}")
        return 0

    if args.command == "import":
        output_dir = _import_output_dir(args)
        if output_dir is None:
            return 1
        try:
            report = import_external(
                corpus_root=args.corpus_root,
                output_dir=output_dir,
                source=args.source,
                categories=_parse_categories(args.categories),
                max_docs=args.max_docs,
                max_chars=args.max_chars,
                max_doc_chars=args.max_doc_chars,
                max_pages=args.max_pages,
                min_chars=args.min_chars,
                release=args.release,
            )
        except (FileNotFoundError, ValueError) as error:
            print(error)
            return 1
        print_import_report(report, output_dir)
        return 0

    if args.command == "list":
        for seed in (*SEEDS, *EXTERNAL_SEEDS):
            print(seed)
        return 0

    if args.command == "status":
        print(f"Semillas oficiales: {len(SEEDS)}")
        print(f"Semillas de terceros: {len(EXTERNAL_SEEDS)}")
        _print_corpus_status()
        return 0

    parser.print_help()
    return 0


SOURCE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _import_output_dir(args: argparse.Namespace) -> Path | None:
    """Valida la fuente y confina el destino de la importación a ``data/external``.

    Sin esta validación, ``--source ../..`` haría que el importador borrase el
    repositorio con ``shutil.rmtree``.
    """

    if not SOURCE_PATTERN.match(args.source):
        print(f"Fuente inválida: {args.source!r}. Usa minúsculas, números, guion o guion bajo.")
        return None
    root = EXTERNAL_DIR.resolve()
    target = (args.output or EXTERNAL_DIR / args.source).resolve()
    if target == root or not target.is_relative_to(root):
        print(f"El destino debe quedar dentro de {root} (recibido: {target}).")
        return None
    return target


def _build_client(args: argparse.Namespace) -> WebClient:
    """Construye el cliente HTTP con el rate limit y la política pedidos."""

    delay = REQUEST_DELAY_SECONDS if args.delay is None else args.delay
    return WebClient(delay=delay, respect_robots=not args.ignore_robots)


def _task_document(title: str, content: str) -> str:
    """Envuelve la salida de una tarea de LLM con un encabezado y la fecha."""

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return f"# {title}\n\n> Generado con LLM sobre el corpus Gold · {generated}\n\n{content}\n"


def print_report(report: CaptureReport) -> None:
    """Imprime las métricas de la ejecución del pipeline."""

    print()
    print("Resumen de la captura")
    print(f"  Descubiertas (semillas): {report.discovered}")
    print(f"  Descargadas:             {report.fetched}")
    print(f"  Escritas en Gold:        {report.written}")
    print(f"  Descartadas:             {report.discarded}")
    print(f"     - por robots.txt:     {len(report.robots_denied)}")
    print(f"     - duplicadas:         {len(report.duplicates)}")
    print(f"     - con error:          {len(report.errors)}")
    print(f"  Caracteres:              {report.chars:,}")
    print(f"  Tokens (estimados):      {report.tokens_estimate:,}")
    print(f"  Duración:                {report.duration_seconds} s")
    for error in report.errors:
        print(f"  ! {error}")


def print_import_report(report: ImportReport, output_dir: Path) -> None:
    """Imprime las métricas de la importación del corpus externo."""

    print()
    print("Resumen de la importación")
    print(f"  Fuente:                    {report.source}")
    print(f"  Registros en el catálogo:  {report.catalog_records}")
    print(f"  Seleccionados:             {report.selected}")
    print(f"  Importados:                {report.imported}")
    print(f"  Duplicados:                {report.duplicates}")
    print(f"  Sin texto suficiente:      {report.empty}")
    print(f"  Fuera del presupuesto:     {report.over_budget}")
    print(f"  Caracteres:                {report.chars:,}")
    print(f"  Tokens (estimados):        {report.tokens_estimate:,}")
    print(f"  Duración:                  {report.duration_seconds} s")
    print(f"  Destino:                   {output_dir}")


def _parse_categories(value: str) -> tuple[str, ...]:
    """Convierte una lista separada por comas en categorías normalizadas."""

    return tuple(category.strip().lower() for category in value.split(",") if category.strip())


def _print_corpus_status() -> None:
    """Resume el corpus: núcleo, capa extendida y tamaño total."""

    core = sorted(GOLD_DIR.glob("*.md"))
    external = sorted(EXTERNAL_DIR.glob("*/gold/*.md"))
    official = sum(1 for path in core if _front_matter_value(path, "source_type") == "oficial")
    chars = sum(path.stat().st_size for path in (*core, *external))

    print(f"Documentos en Gold (núcleo): {len(core)}")
    print(f"  - oficiales: {official}")
    print(f"  - terceros:  {len(core) - official}")
    print(f"Capa extendida: {len(external)}")
    for source_dir in sorted(
        path for path in EXTERNAL_DIR.glob("*") if path.is_dir() and not path.name.endswith(".tmp")
    ):
        count = len(list((source_dir / "gold").glob("*.md")))
        print(f"  - {source_dir.name}: {count}")
    print(f"Caracteres: {chars:,} (aprox. {round(chars / 4):,} tokens)")
    print(f"Índice JSONL: {'sí' if INDEX_FILE.exists() else 'no'}")


def _front_matter_value(path: Path, key: str) -> str:
    """Lee un campo del front matter de un Markdown Gold."""

    for line in path.read_text(encoding="utf-8").splitlines()[1:20]:
        if line.startswith("---"):
            break
        name, separator, value = line.partition(":")
        if separator and name.strip() == key:
            return value.strip()
    return ""


def _seeds_for(scope: str) -> tuple[str, ...]:
    """Selecciona las semillas según el alcance solicitado."""

    if scope == "oficial":
        return SEEDS
    if scope == "terceros":
        return EXTERNAL_SEEDS
    return (*SEEDS, *EXTERNAL_SEEDS)
