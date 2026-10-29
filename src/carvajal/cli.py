"""Interfaz de línea de comandos: capture / ask / eval / status / list."""

import argparse
from pathlib import Path

from carvajal.config import (
    EXTERNAL_SEEDS,
    GOLD_DIR,
    INDEX_FILE,
    QUESTIONS_FILE,
    REQUEST_DELAY_SECONDS,
    RESULTS_FILE,
    SEEDS,
)
from carvajal.fetching import WebClient
from carvajal.pipeline import CaptureReport
from carvajal.pipeline import capture as run_capture
from carvajal.rag import (
    ask as run_ask,
)
from carvajal.rag import (
    build_retriever,
    build_system_prompt,
    evaluate,
    load_gold_documents,
    load_questions,
    render_results_markdown,
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


def _build_client(args: argparse.Namespace) -> WebClient:
    """Construye el cliente HTTP con el rate limit y la política pedidos."""

    delay = REQUEST_DELAY_SECONDS if args.delay is None else args.delay
    return WebClient(delay=delay, respect_robots=not args.ignore_robots)


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


def _print_corpus_status() -> None:
    """Resume el corpus Gold: documentos, tamaño y composición por origen."""

    documents = sorted(GOLD_DIR.glob("*.md"))
    chars = sum(path.stat().st_size for path in documents)
    official = sum(1 for path in documents if _front_matter_value(path, "source_type") == "oficial")
    print(f"Documentos en Gold: {len(documents)}")
    print(f"  - oficiales: {official}")
    print(f"  - terceros:  {len(documents) - official}")
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
