"""Pruebas de la interfaz de línea de comandos."""

from pathlib import Path

import pytest

from carvajal.cli import _import_output_dir, build_parser


def test_parser_lista_subcomandos_validos() -> None:
    """El parser reconoce los subcomandos definidos."""

    parser = build_parser()

    assert parser.parse_args(["list"]) is not None
    assert parser.parse_args(["status"]) is not None
    assert parser.parse_args(["import"]) is not None


def test_parser_reconoce_las_tareas_de_llm() -> None:
    """Los subcomandos de Resumen y FAQ existen y aceptan su salida."""

    parser = build_parser()

    resumen = parser.parse_args(["summarize", "--focus", "empaques"])
    faq = parser.parse_args(["faq"])

    assert resumen.command == "summarize"
    assert resumen.focus == "empaques"
    assert faq.command == "faq"
    assert faq.output.name == "faq.md"


def test_parser_import_define_la_fuente_y_el_presupuesto() -> None:
    """El comando de importación acepta fuente, categorías y presupuesto."""

    parser = build_parser()

    args = parser.parse_args(
        [
            "import",
            "--from",
            "../otro-corpus",
            "--source",
            "alejandro",
            "--categories",
            "identity,governance",
            "--max-chars",
            "500000",
            "--max-pages",
            "40",
        ]
    )

    assert args.corpus_root.as_posix() == "../otro-corpus"
    assert args.source == "alejandro"
    assert args.categories == "identity,governance"
    assert args.max_chars == 500000
    assert args.max_pages == 40


def test_import_rechaza_fuente_con_ruta() -> None:
    """Una fuente con ``..`` no puede escapar de ``data/external``."""

    parser = build_parser()
    args = parser.parse_args(["import", "--source", "../.."])

    assert _import_output_dir(args) is None


def test_import_rechaza_salida_fuera_de_la_capa() -> None:
    """Un ``--output`` fuera de ``data/external`` se rechaza antes de borrar nada."""

    parser = build_parser()
    args = parser.parse_args(["import", "--output", str(Path.cwd())])

    assert _import_output_dir(args) is None


def test_import_acepta_destino_valido() -> None:
    """Una fuente normal resuelve dentro de ``data/external``."""

    parser = build_parser()
    args = parser.parse_args(["import", "--source", "alejandro"])

    destino = _import_output_dir(args)

    assert destino is not None
    assert destino.parent.name == "external"


@pytest.mark.parametrize("source", ["alejandro", "corpus-2", "mi_fuente"])
def test_import_acepta_fuentes_validas(source: str) -> None:
    """Las fuentes con minúsculas, números, guion o guion bajo son válidas."""

    parser = build_parser()
    args = parser.parse_args(["import", "--source", source])

    assert _import_output_dir(args) is not None
