# visualize.py
# LangGraph 파이프라인 다이어그램 생성 스크립트
# - 1순위: langchain_teddynote.graphs.visualize_graph(app)
# - 2순위: graphviz로 PNG 저장 (outputs/graphs/pipeline.png)

from pathlib import Path

# ① 파이프라인 로드
from graph.graph import build_graph


# ② 1순위: TeddyNote 시각화 시도
def try_teddynote(app) -> bool:
    try:
        from langchain_teddynote.graphs import visualize_graph

        # 주피터가 아닌 CLI에서도 열람할 수 있도록 HTML로 저장 시도
        out_dir = Path("outputs/graphs")
        out_dir.mkdir(parents=True, exist_ok=True)
        # 일부 버전은 output_path 인자를 지원, 일부는 미지원 → 방어 코드
        try:
            visualize_graph(app, output_path=str(out_dir / "pipeline.html"))
        except TypeError:
            # 구버전: 단순 호출 (노트북/리치 출력)
            visualize_graph(app)
        print("✅ TeddyNote 시각화 완료: outputs/graphs/pipeline.html (또는 콘솔/노트북 출력)")
        return True
    except Exception as e:
        print(f"ℹ️ TeddyNote 시각화 스킵: {e}")
        return False


# ③ 2순위: Graphviz로 정적 PNG 생성 (그래프 구조가 고정되어 있어 안전)
def draw_with_graphviz() -> None:
    try:
        from graphviz import Digraph
    except Exception as e:
        print("❌ graphviz 파이썬 패키지가 없습니다. `pip install graphviz` 로 설치해주세요.")
        return

    g = Digraph("agentic_rag_v2", format="png")
    g.attr(rankdir="LR", splines="spline", concentrate="true", fontsize="10")

    # 노드 스타일
    node_style = dict(shape="box", style="rounded,filled", fillcolor="#f5f7fb", color="#d0d7de")
    end_style = dict(shape="doublecircle", style="filled", fillcolor="#e6ffec", color="#2ea043")

    # 파이프라인 노드
    for n in ["seraph", "filter", "augment", "rag", "scoring", "report"]:
        g.node(n, n.capitalize(), **node_style)
    g.node("END", "END", **end_style)

    # 엣지 (graph/graph.py와 동일)
    edges = [
        ("seraph", "filter"),
        ("filter", "augment"),
        ("augment", "rag"),
        ("rag", "scoring"),
        ("scoring", "report"),
        ("report", "END"),
    ]
    for s, t in edges:
        g.edge(s, t)

    out_dir = Path("outputs/graphs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "pipeline"
    g.render(str(out_path), cleanup=True)
    print(f"✅ Graphviz 시각화 완료: {out_path}.png")


def main():
    app = build_graph()  # LangGraph compiled graph
    ok = try_teddynote(app)
    if not ok:
        draw_with_graphviz()


if __name__ == "__main__":
    main()
