# [KO] 기본 임포트/그래프 컴파일 스모크
def test_imports_and_compile():
    from graph.graph import build_graph
    from graph.state import PipelineState

    compiled = build_graph()
    assert compiled is not None
    # 간단한 상태로 invoke까지 확인(예외만 안 나면 통과)
    _ = compiled.invoke(PipelineState(query="ai finance"))
