"""Smoke test manual (camada B): roda o pipeline completo contra um vídeo real.

Uso:
    export OPENSUBTITLES_USERNAME="..."
    export OPENSUBTITLES_PASSWORD="..."
    python scripts/smoke_test.py /caminho/para/filme.mkv [--lang pt-BR]

Consome cota real da API do OpenSubtitles. Não é chamado por pytest.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from subs_down_n_sync.exceptions import SubsDownError
from subs_down_n_sync.core import DEFAULT_LANG, run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test: pipeline completo contra vídeo real.",
    )
    parser.add_argument("video", help="Caminho para o arquivo de vídeo.")
    parser.add_argument("--lang", default=DEFAULT_LANG, help="Idioma BCP 47 (default: pt-BR).")
    args = parser.parse_args()

    try:
        summary = run(args.video, lang_tag=args.lang)
    except SubsDownError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1

    print("=== SMOKE TEST OK ===")
    print(f"Output: {summary.output_path}")
    print(f"Provider: {summary.provider} (match={summary.match_type})")
    print(f"Synced: {summary.synced} (offset={summary.offset_seconds:.3f}s)")

    if summary.sync_error:
        print(f"Sync error: {summary.sync_error}")

    print(f"Elapsed: {summary.elapsed_seconds:.2f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
