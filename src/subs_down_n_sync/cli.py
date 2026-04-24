from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from subs_down_n_sync.core import DEFAULT_LANG, VIDEO_EXTENSIONS, RunSummary, run
from subs_down_n_sync.exceptions import SubsDownError

MAX_PARALLEL_WORKERS = 2

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


def _make_batch_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[detail]}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )


def _process_video(
    video: Path,
    lang_tag: str,
    progress: Progress,
) -> RunSummary:
    task_id = progress.add_task(video.name, detail="aguardando...", total=None)

    def on_progress(step: str, detail: str) -> None:
        label = _STEP_LABELS.get(step, step)
        progress.update(task_id, description=f"{video.name} — {label}", detail=detail)

    try:
        return run(str(video), lang_tag=lang_tag, on_progress=on_progress)
    finally:
        progress.remove_task(task_id)


def _run_directory(
    dir_path: Path,
    lang_tag: str,
    overwrite: bool,
    parallel: bool = False,
) -> tuple[list[RunSummary], list[Path], list[tuple[Path, str]]]:
    videos = sorted(p for p in dir_path.rglob("*") if p.suffix.lower() in VIDEO_EXTENSIONS)

    results: list[RunSummary] = []
    skipped: list[Path] = []
    errors: list[tuple[Path, str]] = []

    to_process: list[Path] = []
    for video in videos:
        srt_path = video.with_suffix("").with_suffix(f".{lang_tag}.srt")
        if srt_path.exists() and not overwrite:
            skipped.append(video)
            continue
        to_process.append(video)

    if not to_process:
        return results, skipped, errors

    progress = _make_batch_progress()
    overall = progress.add_task(
        f"Lote ({len(to_process)} vídeo(s))",
        detail="",
        total=len(to_process),
    )

    with progress:
        if parallel:
            with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as pool:
                futures = {
                    pool.submit(_process_video, v, lang_tag, progress): v for v in to_process
                }
                for fut in as_completed(futures):
                    video = futures[fut]
                    try:
                        results.append(fut.result())
                    except SubsDownError as e:
                        errors.append((video, str(e)))
                    progress.advance(overall)
        else:
            for video in to_process:
                try:
                    results.append(_process_video(video, lang_tag, progress))
                except SubsDownError as e:
                    errors.append((video, str(e)))
                progress.advance(overall)

    return results, skipped, errors


def _print_batch_summary(
    results: list[RunSummary],
    skipped: list[Path],
    errors: list[tuple[Path, str]],
) -> None:
    table = Table(title="subs-down-n-sync — lote", show_lines=False)
    table.add_column("Arquivo", style="bold")
    table.add_column("Status")
    table.add_column("Idioma")
    table.add_column("Provider")
    table.add_column("Offset")

    for s in results:
        if s.sync_error:
            status = "[yellow]aviso[/yellow]"
        elif s.synced:
            status = "[green]sincronizado[/green]"
        else:
            status = "[cyan]ok[/cyan]"
        table.add_row(
            s.output_path.name,
            status,
            s.lang_tag,
            s.provider,
            f"{s.offset_seconds:.2f}s",
        )

    for path in skipped:
        table.add_row(path.name, "[dim]pulado[/dim]", "-", "-", "-")

    for path, _msg in errors:
        table.add_row(path.name, "[red]erro[/red]", "-", "-", "-")

    console.print(table)

    parts = []
    if results:
        parts.append(f"[green]{len(results)} processado(s)[/green]")
    if skipped:
        parts.append(f"[dim]{len(skipped)} pulado(s)[/dim]")
    if errors:
        parts.append(f"[red]{len(errors)} erro(s)[/red]")

    console.print("  ".join(parts) if parts else "[dim]Nenhum vídeo encontrado.[/dim]")

    if errors:
        console.print()
        for path, msg in errors:
            err_console.print(f"[bold red]Erro[/bold red] {path.name}: {msg}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subs-down-n-sync",
        description="Busca e sincroniza legenda para arquivo(s) de vídeo.",
    )
    parser.add_argument("path", help="Caminho para arquivo de vídeo ou diretório.")
    parser.add_argument(
        "-l",
        "--lang",
        default=DEFAULT_LANG,
        help=f"Código de idioma BCP 47 (ex: pt-BR, en, es). Default: {DEFAULT_LANG}.",
    )
    parser.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        default=False,
        help=(
            "Sobrescrever legendas existentes. Por padrão, vídeos com legenda "
            "já existente são pulados."
        ),
    )
    parser.add_argument(
        "-p",
        "--parallel",
        action="store_true",
        default=False,
        help=(
            f"Processar vídeos em paralelo (até {MAX_PARALLEL_WORKERS} simultâneos) "
            "quando o caminho for um diretório."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    p = Path(args.path).expanduser()

    if p.is_dir():
        results, skipped, errors = _run_directory(
            p,
            lang_tag=args.lang,
            overwrite=args.overwrite,
            parallel=args.parallel,
        )
        _print_batch_summary(results, skipped, errors)
        return 1 if errors else 0

    if not p.exists():
        err_console.print(f"[bold red]Erro:[/bold red] Caminho não existe: {p}")
        return 1

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
            summary = run(args.path, lang_tag=args.lang, on_progress=on_progress)
        except SubsDownError as e:
            progress.stop()
            err_console.print(f"[bold red]Erro:[/bold red] {e}")
            return 1

    _print_summary(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
