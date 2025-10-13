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
from rich.logging import RichHandler
from rich.table import Table
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn

# [KO] 파이프라인 그래프/상태 임포트
from .graph import load_nodes
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


def _setup_logging(log_dir: Path, level: str = "INFO") -> tuple[Logger, Console]:
    log_level = getattr(logging, level.upper(), logging.INFO)

    # ★ 하나의 Console 인스턴스 준비 (soft_wrap로 줄바꿈 자연스러움)
    console = Console(soft_wrap=True)

    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.handlers.clear()

    # ★ 콘솔 핸들러 → RichHandler (Progress와 공존 안전)
    ch = RichHandler(
        console=console, show_time=False, show_level=True, markup=True, rich_tracebacks=True
    )
    ch.setLevel(log_level)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

    # 파일 핸들러 (기존 유지)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    fh = logging.FileHandler(log_dir / f"run_{ts}.log", encoding="utf-8")
    fh.setLevel(log_level)
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(fh)

    logging.getLogger(__name__).info("Logging initialized.")
    return logger, console


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
    logger, console = _setup_logging(paths["logs"], args.log_level)

    console.rule("[bold]Agentic RAG v2 — Run")

    state = PipelineState(query=args.query)

    nodes = load_nodes()

    # ★ Progress에도 같은 console 사용 + stdout/stderr 리다이렉트
    with Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
        redirect_stdout=True,  # ★ 중요
        redirect_stderr=True,  # ★ 중요
    ) as progress:
        t1 = progress.add_task("▶ Discovery/Filter", total=1)
        t2 = progress.add_task("▶ Augment (crawl+chunk)", total=1)
        t3 = progress.add_task("▶ RAG", total=1)
        t4 = progress.add_task("▶ Scoring", total=1)
        t5 = progress.add_task("▶ Report (PDF)", total=1)

        # Seraph → Filter
        state = run_step_by_step_step(state, steps=("seraph", "filter"), nodes=nodes)
        progress.update(t1, advance=1)

        # Augment
        state = run_step_by_step_step(state, steps=("augment",), nodes=nodes)
        progress.update(t2, advance=1)

        # RAG
        state = run_step_by_step_step(state, steps=("rag",), nodes=nodes)
        progress.update(t3, advance=1)

        # Scoring
        state = run_step_by_step_step(state, steps=("scoring",), nodes=nodes)
        progress.update(t4, advance=1)

        # Report
        state = run_step_by_step_step(state, steps=("report",), nodes=nodes)
        progress.update(t5, advance=1)

    # ── 출력 요약
    _print_summary(console, state, paths["reports"])


# ─────────────────────────────────────────────────────────────
# [KO] 보조 유틸: 특정 단계만 부분 실행 (fallback/실제 에이전트 모두 지원)
# ─────────────────────────────────────────────────────────────


def run_step_by_step_step(
    state: PipelineState, steps: tuple[str, ...], nodes=None
) -> PipelineState:
    """
    Run a subset of nodes in fixed order.
    Pass a preloaded `nodes` dict to avoid re-resolving agents repeatedly.
    """
    nodes = nodes or load_nodes()
    for key in steps:
        state = nodes[key](state)
    return state


def _print_summary(console: Console, state: PipelineState, report_dir: Path) -> None:
    """Pretty-print a run summary with per-company scores."""
    console.rule("[bold green]Run Summary")

    discovered = len(state.companies)
    scored = len(state.scorecard)
    console.print(f"[bold]Discovered Companies:[/bold] {discovered}")
    console.print(f"[bold]Scored Companies:[/bold] {scored}")

    # 회사별 점수 테이블
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", justify="right", width=3)
    table.add_column("Company", overflow="fold")
    table.add_column("Total", justify="right", width=6)
    table.add_column("Decision", justify="center", width=10)

    # 총점 기준 내림차순 정렬
    def _total_of(cid: str) -> float:
        sc = state.scorecard.get(cid)
        return sc.total if sc else -1.0

    sorted_companies = sorted(state.companies, key=lambda c: _total_of(c.id), reverse=True)

    for idx, comp in enumerate(sorted_companies, start=1):
        sc = state.scorecard.get(comp.id)
        if sc:
            total = f"{sc.total:.2f}"
            decision = sc.decision
        else:
            total = "-"
            decision = "-"

        table.add_row(str(idx), comp.name or comp.id, total, decision)

    if discovered:
        console.print(table)
    else:
        console.print("[yellow]No companies discovered.[/yellow]")

    # 리포트 목록
    if state.reports:
        console.print("\n[bold]Generated Reports:[/bold]")
        for cid, path in state.reports.items():
            console.print(f"  • [cyan]{cid}[/cyan] → {path}")
    else:
        console.print("\n[yellow]No reports generated (no 'invest' decisions).[/yellow]")

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
