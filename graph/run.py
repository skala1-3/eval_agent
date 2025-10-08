# graph/run.py
# Agentic RAG v2 - CLI entrypoint with logging & progress
# Python 3.11+
#
# [KO] 이 파일은 파이프라인 실행 진입점입니다.
#      - argparse로 질의(--query)와 로그레벨을 받아 실행합니다.
#      - rich.Progress로 주요 단계를 시각화합니다.
#      - 로그 파일은 outputs/logs/run_YYYYMMDD_HHMM.log 로 저장합니다.
#      - agents/* 미구현 상태에서도 최소 실행이 가능하도록 설계되었습니다.
#
# [TIP]
#  - 실제 에이전트 구현 후에도 본 파일은 변경 없이 사용할 수 있습니다.
#  - 보고서(PDF) 생성은 ReportWriterAgent에서 수행되며, 여기서는 결과 경로만 출력합니다.

from __future__ import annotations

import argparse
import logging
from logging import Logger
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn

# [KO] 파이프라인 그래프/상태 임포트
from .graph import run_step_by_step  # 단계별 진행을 위해 스텝 실행 유틸 사용
from .state import PipelineState


# ─────────────────────────────────────────────────────────────
# [KO] 경로/로그 설정 유틸
# ─────────────────────────────────────────────────────────────


def _ensure_dirs() -> dict[str, Path]:
    """Create required output directories if not exist."""
    root = Path.cwd()
    outputs = root / "outputs"
    logs = outputs / "logs"
    reports = outputs / "reports"
    for p in (outputs, logs, reports):
        p.mkdir(parents=True, exist_ok=True)
    return {"root": root, "outputs": outputs, "logs": logs, "reports": reports}


def _setup_logging(log_dir: Path, level: str = "INFO") -> Logger:
    """Configure console + file logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Clear existing handlers to avoid duplication in some environments
    logger.handlers.clear()

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch_fmt = logging.Formatter("[%(levelname)s] %(message)s")
    ch.setFormatter(ch_fmt)
    logger.addHandler(ch)

    # File handler
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    fh = logging.FileHandler(log_dir / f"run_{ts}.log", encoding="utf-8")
    fh.setLevel(log_level)
    fh_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(fh_fmt)
    logger.addHandler(fh)

    logging.getLogger(__name__).info("Logging initialized.")
    return logger


# ─────────────────────────────────────────────────────────────
# [KO] 실행 본문
# ─────────────────────────────────────────────────────────────


def main():
    """
    CLI entrypoint to run the Agentic RAG v2 pipeline.

    Steps visualized:
      - Discovery/Filter
      - Augment (crawl+chunk)
      - RAG + Scoring
      - Report (PDF if invest)
    """
    parser = argparse.ArgumentParser(description="Run Agentic RAG v2 pipeline")
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Discovery query (e.g., 'AI financial advisory startup')",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    args = parser.parse_args()

    # Prepare folders and logging
    paths = _ensure_dirs()
    _setup_logging(paths["logs"], args.log_level)

    console = Console()
    console.rule("[bold]Agentic RAG v2 — Run")

    # Initialize shared state
    state = PipelineState(query=args.query)

    # ── Progress Bars (각 단계별 1칸씩 증가하는 스텁 형태)
    with Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,  # [KO] 실행 후에도 로그 보존
    ) as progress:
        t1 = progress.add_task("▶ Discovery/Filter      ", total=1)
        t2 = progress.add_task("▶ Augment (crawl+chunk)", total=1)
        t3 = progress.add_task(
            "▶ RAG + Scoring        ", total=2
        )  # RAG, Scoring 두 구간
        t4 = progress.add_task("▶ Report (PDF)         ", total=1)

        # [KO] Seraph → Filter
        state = run_step_by_step_step(state, steps=("seraph", "filter"))
        progress.update(t1, advance=1, refresh=True)

        # [KO] Augment
        state = run_step_by_step_step(state, steps=("augment",))
        progress.update(t2, advance=1, refresh=True)

        # [KO] RAG → Scoring
        state = run_step_by_step_step(state, steps=("rag",))
        progress.update(t3, advance=1, refresh=True)
        state = run_step_by_step_step(state, steps=("scoring",))
        progress.update(t3, advance=1, refresh=True)

        # [KO] Report
        state = run_step_by_step_step(state, steps=("report",))
        progress.update(t4, advance=1, refresh=True)

    # ── 출력 요약
    _print_summary(console, state, paths["reports"])


# ─────────────────────────────────────────────────────────────
# [KO] 보조 유틸: 특정 단계만 부분 실행 (fallback/실제 에이전트 모두 지원)
# ─────────────────────────────────────────────────────────────


def run_step_by_step_step(
    state: PipelineState, steps: tuple[str, ...]
) -> PipelineState:
    """
    Run a subset of nodes in fixed order using run_step_by_step logic.
    This function calls the globally defined run_step_by_step but constrains to `steps`.
    """
    # [KO] run_step_by_step는 전체 순차를 실행하므로, 여기서는 최소한의
    #      방어적 구현으로 노드별 부분 실행을 지원하도록 분리합니다.
    #      (간단한 형태로 다시 호출하여 단계 구간을 확정적으로 보장)
    from .graph import load_nodes  # lazy import to avoid cycles

    nodes = load_nodes()
    for key in steps:
        node = nodes[key]
        state = node(state)
    return state


def _print_summary(console: Console, state: PipelineState, report_dir: Path) -> None:
    """Pretty-print a short run summary, including generated reports."""
    console.rule("[bold green]Run Summary")
    # Companies
    n_companies = len(state.companies)
    console.print(f"[bold]Discovered Companies:[/bold] {n_companies}")

    # Scorecards
    n_scored = len(state.scorecard)
    console.print(f"[bold]Scored Companies:[/bold] {n_scored}")

    # Reports
    if state.reports:
        console.print("[bold]Generated Reports:[/bold]")
        for cid, path in state.reports.items():
            console.print(f"  • [cyan]{cid}[/cyan] → {path}")
    else:
        console.print("[yellow]No reports generated (no 'invest' decisions).[/yellow]")

    console.print(f"\n[dim]Reports directory: {report_dir}[/dim]")


# ─────────────────────────────────────────────────────────────
# [KO] 메인 가드
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.getLogger(__name__).warning("Interrupted by user (Ctrl+C).")
    except Exception as e:
        logging.getLogger(__name__).exception(f"Unhandled error: {e}")
        raise
