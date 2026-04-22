from __future__ import annotations

import argparse
import sys

from subs_down_n_sync.core import DEFAULT_LANG, RunSummary, run
from subs_down_n_sync.exceptions import SubsDownError


def _print_summary(summary: RunSummary) -> None:
    print(f"Legenda ({summary.lang_tag}): {summary.provider} (match: {summary.match_type})")

    if summary.sync_error:
        print(
            f"Aviso: sincronização falhou — mantendo legenda original. "
            f"Detalhe: {summary.sync_error}"
        )
    elif summary.synced:
        print(f"Sincronizada (ajuste médio: {summary.offset_seconds:.2f}s)")
    else:
        print(f"Já sincronizada (offset médio: {summary.offset_seconds:.2f}s < 0.10s)")

    print(f"Arquivo: {summary.output_path}")
    print(f"Tempo total: {summary.elapsed_seconds:.2f}s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subs-down-n-sync",
        description="Busca e sincroniza legenda para um arquivo de vídeo.",
    )
    parser.add_argument("video", help="Caminho para o arquivo de vídeo.")
    parser.add_argument(
        "-l",
        "--lang",
        default=DEFAULT_LANG,
        help=f"Código de idioma BCP 47 (ex: pt-BR, en, es). Default: {DEFAULT_LANG}.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        summary = run(args.video, lang_tag=args.lang)
    except SubsDownError as e:
        print(str(e), file=sys.stderr)
        return 1

    _print_summary(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
