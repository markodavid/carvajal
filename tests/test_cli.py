"""Pruebas de la interfaz de línea de comandos."""

from carvajal.cli import build_parser


def test_parser_lista_subcomandos_validos() -> None:
    """El parser reconoce los subcomandos definidos."""

    parser = build_parser()

    assert parser.parse_args(["list"]) is not None
    assert parser.parse_args(["status"]) is not None
    assert parser.parse_args(["import"]) is not None


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
