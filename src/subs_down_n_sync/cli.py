from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn

from subs_down_n_sync.core import DEFAULT_LANG, RunSummary, run
from subs_down_n_sync.exceptions import SubsDownError

console = Console()
err_console = Console(stderr=True)

_STEP_LABELS: dict[str, str] = {
    "validando": "Validando vídeo...",
    "buscando": "Buscando legenda no OpenSubtitles...",
    "baixado": "Legenda encontrada e baixada",
    "referencia": "Baixando legenda EN de referência...",
    "sem_referencia": "Referência EN não encontrada — sincronização ignorada",
    "sincronizando": "Alinhando com embeddings semânticos...",
    "sincronizado": "Sincronização concluída",
    "sem_sync": "Legenda já sincronizada",
    "erro_sync": "Erro na sincronização",
    "concluido": "Finalizado",
}

_STEPS_WITH_SYNC = [
    "validando",
    "buscando",
    "baixado",
    "referencia",
    "sincronizando",
    "concluido",
]

_STEPS_NO_SYNC = [
    "validando",
    "buscando",
    "baixado",
    "concluido",
]


def _make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        TextColumn("[dim]{task.fields[detail]}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )


def _print_summary(summary: RunSummary) -> None:
    if summary.sync_error:
        status_line = (
            f"[yellow]Aviso:[/yellow] sincronização falhou — legenda original mantida.\n"
            f"Detalhe: {summary.sync_error}"
        )
        border = "yellow"
    elif summary.synced:
        status_line = (
            f"[green]Sincronizada[/green] "
            f"(ajuste médio: {summary.offset_seconds:.2f}s, modo: {summary.sync_mode})"
        )
        border = "green"
    else:
        status_line = (
            f"[cyan]Já sincronizada[/cyan] (offset médio: {summary.offset_seconds:.2f}s < 0.10s)"
        )
        border = "cyan"

    body = (
        f"Idioma: [bold]{summary.lang_tag}[/bold]  |  "
        f"Provider: {summary.provider}  |  "
        f"Match: {summary.match_type}\n"
        f"{status_line}\n"
        f"Tempo total: {summary.elapsed_seconds:.2f}s"
    )

    console.print(Panel(body, title="subs-down-n-sync", border_style=border))


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

    progress = _make_progress()
    task_id: TaskID | None = None

    completed_steps: list[str] = []

    def on_progress(step: str, detail: str) -> None:
        nonlocal task_id

        label = _STEP_LABELS.get(step, step)

        if task_id is None:
            task_id = progress.add_task(label, detail=detail, total=None)
        else:
            progress.update(task_id, description=label, detail=detail)

        completed_steps.append(step)

        if step in ("baixado", "sincronizado", "sem_sync", "sem_referencia", "erro_sync"):
            console.log(f"[dim]{label}[/dim] {detail}")

    with progress:
        try:
            summary = run(args.video, lang_tag=args.lang, on_progress=on_progress)
        except SubsDownError as e:
            progress.stop()
            err_console.print(f"[bold red]Erro:[/bold red] {e}")
            return 1

    _print_summary(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
