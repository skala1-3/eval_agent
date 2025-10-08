# [KO] fallback 노드의 단계별 실행 스모크
def test_step_run_noop():
    from graph.graph import run_step_by_step
    from graph.state import PipelineState

    s = PipelineState(query="ai finance")
    out = run_step_by_step(s)
    assert out.query == s.query
    assert isinstance(out.companies, list)
    assert isinstance(out.chunks, list)
    assert isinstance(out.scorecard, dict)
    assert isinstance(out.reports, dict)
