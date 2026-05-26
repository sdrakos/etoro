"""
related_companies.py — Build a network graph of related/peer companies.

Based on Massive.com's "Related Companies API" tutorial.
Outputs JSON for visualization (vis-network) + optional Mermaid diagram.

Usage:
    # Single ticker → see immediate peers
    python related_companies.py --tickers NVDA

    # Multiple roots → build extended network
    python related_companies.py --tickers AAPL MSFT NVDA GOOGL META --depth 2

    # Output for visualization
    python related_companies.py --tickers AAPL --output data.json
    # Then open visualization.html (bundled)

Requirements:
    pip install massive
    export MASSIVE_API_KEY="your_key"
"""

import json
import argparse
from massive import RESTClient


def build_network(seed_tickers, depth=1):
    """
    BFS from seed tickers up to specified depth.
    Returns (nodes, edges) for graph visualization.
    """
    client = RESTClient()
    nodes = []
    edges = []
    id_map = {}
    current_id = 1
    visited = set()
    queue = [(t, 0) for t in seed_tickers]

    def add_node(ticker):
        nonlocal current_id
        if ticker not in id_map:
            id_map[ticker] = current_id
            nodes.append({"id": current_id, "label": ticker})
            current_id += 1
        return id_map[ticker]

    while queue:
        ticker, level = queue.pop(0)
        if ticker in visited or level > depth:
            continue
        visited.add(ticker)
        add_node(ticker)

        try:
            related = client.get_related_companies(ticker)
        except Exception as e:
            print(f"  Error fetching {ticker}: {e}")
            continue

        for company in related:
            rt = company.ticker
            add_node(rt)
            edges.append({"from": id_map[ticker], "to": id_map[rt]})
            if level < depth:
                queue.append((rt, level + 1))

    return nodes, edges


def to_mermaid(nodes, edges):
    """Generate Mermaid diagram for quick visualization in Notion/GitHub."""
    label_by_id = {n["id"]: n["label"] for n in nodes}
    lines = ["graph LR"]
    seen_edges = set()
    for e in edges:
        key = (e["from"], e["to"])
        rev_key = (e["to"], e["from"])
        if key in seen_edges or rev_key in seen_edges:
            continue
        seen_edges.add(key)
        lines.append(f"  {label_by_id[e['from']]} --- {label_by_id[e['to']]}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Build related-companies network graph")
    parser.add_argument("--tickers", nargs="+", required=True,
                        help="Seed tickers (e.g. AAPL MSFT NVDA)")
    parser.add_argument("--depth", type=int, default=1,
                        help="BFS depth (1=direct peers, 2=peers of peers, ...)")
    parser.add_argument("--output", default="related_data.json",
                        help="Output JSON file")
    parser.add_argument("--mermaid", action="store_true",
                        help="Also output Mermaid diagram to stdout")

    args = parser.parse_args()

    print(f"Building network from {args.tickers} at depth {args.depth}")
    nodes, edges = build_network(args.tickers, depth=args.depth)

    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {len(edges)}")

    with open(args.output, "w") as f:
        json.dump({"nodes": nodes, "edges": edges}, f, indent=2)
    print(f"  Saved → {args.output}")

    if args.mermaid:
        print("\n--- Mermaid diagram ---")
        print(to_mermaid(nodes, edges))

    print("\nFor interactive visualization, paste nodes+edges into vis-network HTML template:")
    print("  https://visjs.github.io/vis-network/examples/")


if __name__ == "__main__":
    main()
