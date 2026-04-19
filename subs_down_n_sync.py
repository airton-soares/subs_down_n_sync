"""subs_down_n_sync: busca e sincroniza legendas pt-BR."""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subs_down_n_sync",
        description="Busca e sincroniza legenda pt-BR para um arquivo de vídeo.",
    )
    parser.add_argument("video", help="Caminho para o arquivo de vídeo.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # A lógica real virá nas próximas tasks.
    print(f"video: {args.video}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
