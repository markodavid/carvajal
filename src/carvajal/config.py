"""Configuración del pipeline: semillas, capas, política HTTP y LLM."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_URL: str = "https://www.carvajal.com"
USER_AGENT: str = "carvajal-corpus/0.1 (+https://github.com/markodavid/carvajal)"
TIMEOUT_SECONDS: int = 30

GOLD_DIR: Path = Path("data") / "gold"
INDEX_DIR: Path = Path("data") / "index"
RAW_DIR: Path = Path("data") / "raw"  # bronze: HTML crudo
PROCESSED_DIR: Path = Path("data") / "processed"  # silver: Markdown limpio
INDEX_FILE: Path = GOLD_DIR / "index.jsonl"  # índice del corpus (JSONL)
REQUEST_DELAY_SECONDS: float = 1.0  # rate limit entre peticiones por host
RESPECT_ROBOTS: bool = True
MIN_DEDUPE_CHARS: int = 200  # no deduplicar páginas casi vacías

SEEDS: tuple[str, ...] = (
    "https://www.carvajal.com/",
    "https://www.carvajal.com/quienes-somos/",
    "https://www.carvajal.com/historia/",
    "https://www.carvajal.com/proposito-superior/",
    "https://www.carvajal.com/sostenibilidad/",
    "https://www.carvajal.com/noticias/",
    "https://www.carvajal.com/empaques/",
    "https://www.carvajal.com/tecnologia/",
    "https://www.carvajal.com/educacion/",
    "https://www.carvajal.com/comunicacion/",
    "https://www.carvajal.com/espacios/",
    "https://www.carvajal.com/propiedades-e-inversiones/",
    "https://www.carvajal.com/inversionistas/inicio/",
    "https://www.carvajal.com/gobierno-corporativo/",
    "https://www.carvajal.com/compromiso-etico/",
)

# Fuentes de terceros: publican los indicadores financieros que el sitio oficial
# solo entrega dentro de PDFs (estados financieros, informe de gestión).
EXTERNAL_SEEDS: tuple[str, ...] = (
    "https://www.larepublica.co/empresas/resultados-empresariales-2024-de-carvajal-4099828",
    "https://www.larepublica.co/empresas/carvajal-reporto-ingresos-por-2-58-billones-a-septiembre-de-2025-4269762",
    "https://www.larepublica.co/empresas/carvajal-reporto-ingresos-por-2-8-billones-con-corte-al-tercer-trimestre-3999096",
    "https://www.larepublica.co/empresas/carvajal-reporto-ingresos-por-1-9-billones-a-junio-un-decrecimiento-de-14-anual-3928992",
    "https://www.elpais.com.co/economia/carvajal-y-sus-empresas-reportan-resultados-0239.html",
    "https://caliescribe.com/2025/04/16/carvajal-s-a-futuro-consolidado-ante-desafios-globales",
)

LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

QUESTIONS_FILE: Path = Path("data") / "questions.json"
RESULTS_FILE: Path = Path("docs") / "resultados.md"
