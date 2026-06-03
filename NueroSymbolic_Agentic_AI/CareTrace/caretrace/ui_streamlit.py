"""
Streamlit UI for CareTrace.

Run:
  streamlit run caretrace/ui_streamlit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go
import networkx as nx

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from caretrace.orchestration.graph import run_turn
from caretrace.state import CareTraceState, default_case


def _init_state() -> CareTraceState:
    return {
        "messages": [],
        "case": default_case(),
        "kg_annotations": [],
        "turn": 0,
    }


def _reset() -> None:
    st.session_state.ct_state = _init_state()
    st.session_state.ct_chat = []


def _get_disposition_emoji(disposition: str) -> str:
    """Return emoji based on disposition."""
    emoji_map = {
        "ER_NOW": "🚨",
        "URGENT_SAME_DAY": "⚠️",
        "HOME_MANAGEMENT": "🏠",
        "OUT_OF_SCOPE": "❓",
    }
    return emoji_map.get(disposition, "❓")


def _create_kg_graph(kg_annotations: list) -> go.Figure:
    """Create a network graph visualization of KG concepts and relationships."""
    G = nx.DiGraph()

    if not kg_annotations:
        return go.Figure()

    # Add nodes for matched phrases, concepts, and ancestors
    for ann in kg_annotations:
        concept = ann.get("concept", {})
        mention = ann.get("mention", "")
        ancestors = ann.get("ancestors", [])

        concept_id = concept.get("id") or concept.get("conceptId") or ""
        concept_name = concept.get("term") or concept.get("pt") or "Unknown"

        # Add text mention node
        if mention:
            mention_node = f"Text: {mention}"
            G.add_node(mention_node, type="mention", color="#ff9999")

        # Add concept node
        concept_node = f"{concept_name}\n({concept_id})" if concept_id else concept_name
        G.add_node(concept_node, type="concept", color="#4dabf7")

        # Connect mention to concept
        if mention:
            G.add_edge(mention_node, concept_node)

        # Add ancestor nodes and IS_A relationships
        for ancestor in ancestors:
            anc_id = ancestor.get("id") or ancestor.get("conceptId") or ""
            anc_name = ancestor.get("term") or ancestor.get("pt") or "Unknown"
            ancestor_node = f"{anc_name}\n({anc_id})" if anc_id else anc_name

            G.add_node(ancestor_node, type="ancestor", color="#a8e6cf")
            G.add_edge(concept_node, ancestor_node)

    # Create hierarchical layout using sugiyama/layered approach
    try:
        # Find root nodes (nodes with no incoming edges)
        roots = [n for n in G.nodes() if G.in_degree(n) == 0]
        if not roots:
            roots = [next(iter(G.nodes()))] if G.nodes() else []

        pos = {}
        y_level = 0
        processed = set()
        current_level = roots

        # Assign positions level by level
        while current_level and len(processed) < len(G.nodes()):
            x_positions = {n: x for x, n in enumerate(current_level)}
            for node in current_level:
                x = x_positions[node] * 1.5 - len(current_level) * 0.75
                pos[node] = (x, -y_level)
                processed.add(node)

            # Get next level (children of current level nodes)
            next_level = []
            for node in current_level:
                children = list(G.successors(node))
                for child in children:
                    if child not in processed and child not in next_level:
                        next_level.append(child)

            current_level = next_level
            y_level += 1

        # Ensure all nodes are in pos
        for node in G.nodes():
            if node not in pos:
                pos[node] = (0, y_level)
    except Exception:
        # Fallback to spring layout if hierarchical fails
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    # Prepare edge traces with arrows
    edge_traces = []
    for edge in G.edges():
        if edge[0] in pos and edge[1] in pos:
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]

            edge_trace = go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=2, color='#666'),
                hoverinfo='none',
                showlegend=False
            )
            edge_traces.append(edge_trace)

    # Prepare node traces with size based on hierarchy level
    node_x = []
    node_y = []
    node_colors = []
    node_sizes = []
    node_text = []

    # Calculate depth for each node
    depths = {}
    for node in G.nodes():
        if G.in_degree(node) == 0:
            depths[node] = 0
        else:
            max_parent_depth = max(depths.get(parent, 0) for parent in G.predecessors(node))
            depths[node] = max_parent_depth + 1

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_data = G.nodes[node]
        node_colors.append(node_data.get('color', '#1f77b4'))
        depth = depths.get(node, 0)
        node_sizes.append(25 - (depth * 3))
        node_text.append(node)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=node_text,
        textposition="middle center",
        hoverinfo='text',
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=2, color='white')
        ),
        showlegend=False
    )

    # Create figure
    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20, l=5, r=5, t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='#f8f9fa',
        height=400,
    )

    return fig


def _display_traceability_right(state: CareTraceState) -> None:
    """Display explainability and traceability information in organized tabs."""
    decision = state.get("decision") or {}
    disposition = decision.get("disposition", "UNKNOWN")
    rule_ids = decision.get("rule_ids") or []
    med_flags = decision.get("med_flags") or []
    missing_required = decision.get("missing_required") or []
    kg_annotations = state.get("kg_annotations") or []

    # Style the traceability container with darker background
    st.markdown(
        """
        <style>
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column"] > [data-testid="stVerticalBlock"] {
            background-color: #e8eef5;
            padding: 1rem;
            border-radius: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Create tabs for organized display
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 Disposition", "🔍 Rules Fired", "⚕️ Med Flags", "🧬 KG Evidence"]
    )

    # Disposition Tab
    with tab1:
        st.markdown(f"### {_get_disposition_emoji(disposition)} {disposition}")
        status_colors = {
            "ER_NOW": "🔴",
            "URGENT_SAME_DAY": "🟡",
            "HOME_MANAGEMENT": "🟢",
            "OUT_OF_SCOPE": "⚪",
        }
        st.write(
            f"{status_colors.get(disposition, '⚪')} **Status:** {disposition}"
        )
        if missing_required:
            st.warning(f"⚠️ Missing {len(missing_required)} required fields")
            for field in missing_required:
                st.write(f"  • {field}")

    # Rules Fired Tab
    with tab2:
        if rule_ids:
            st.markdown("### Rules That Fired")
            for rule in rule_ids:
                st.write(f"✅ `{rule}`")
        else:
            st.info("No specific rules fired - decision based on overall assessment")

    # Medication Flags Tab
    with tab3:
        if med_flags:
            st.markdown("### Medication Safety Alerts")
            for flag in med_flags:
                st.warning(f"🚩 {flag}")
        else:
            st.success("No medication safety flags")

    # KG Evidence Tab
    with tab4:
        if kg_annotations:
            st.markdown("### Knowledge Graph Subgraph")
            fig = _create_kg_graph(kg_annotations)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("### Concept Details & Relationships")
            for ann in kg_annotations:
                concept = ann.get("concept", {})
                mention = ann.get("mention", "")
                ancestors = ann.get("ancestors", [])

                concept_id = concept.get("id") or concept.get("conceptId", "")
                concept_name = concept.get("term") or concept.get("pt") or "Unknown"

                st.write(f"**{concept_name}**")
                if mention:
                    st.caption(f'Matched from text: "{mention}"')
                if concept_id:
                    st.caption(f"ID: {concept_id}")

                if ancestors:
                    st.markdown("_Broader concepts (IS_A):_")
                    for ancestor in ancestors:
                        anc_name = ancestor.get("term") or ancestor.get("pt") or "Unknown"
                        anc_id = ancestor.get("id") or ancestor.get("conceptId", "")
                        if anc_id:
                            st.caption(f"  → {anc_name} ({anc_id})")
                        else:
                            st.caption(f"  → {anc_name}")

                st.divider()
        else:
            st.info("No KG concepts retrieved")


def main() -> None:
    st.set_page_config(page_title="CareTrace UI", page_icon="🩺", layout="wide")
    st.title("🩺 CareTrace - Pediatric Triage Assistant")
    st.markdown(
        "_Neurosymbolic AI-driven after-hours triage assistant: structure-aware, traceable, auditable, PyDatalog-powered_"
    )

    if "ct_state" not in st.session_state:
        st.session_state.ct_state = _init_state()
    if "ct_chat" not in st.session_state:
        st.session_state.ct_chat = []

    # Control panel
    if st.button("🔄 Reset Session", use_container_width=True):
        _reset()
        st.rerun()

    st.divider()

    # Chat history with side-by-side layout
    for i, turn in enumerate(st.session_state.ct_chat):
        with st.chat_message("user"):
            st.markdown(turn["user"])

        # Two-column layout for assistant response
        left_col, right_col = st.columns([1.5, 1])

        with left_col:
            with st.chat_message("assistant"):
                # Main explanation
                st.markdown(turn["assistant"])

        with right_col:
            st.markdown("### 📊 Traceability")
            _display_traceability_right(turn.get("state", {}))

    # Input
    user_text = st.chat_input("Describe your child's symptoms...")
    if not user_text:
        return

    # Display user message
    with st.chat_message("user"):
        st.markdown(user_text)

    # Process input
    state: CareTraceState = st.session_state.ct_state
    state["raw_user_text"] = user_text
    msgs = list(state.get("messages") or [])
    msgs.append({"role": "user", "content": user_text})
    state["messages"] = msgs

    with st.spinner("🤔 CareTrace is reasoning..."):
        new_state = run_turn(state)

    # Display assistant response with side-by-side layout
    assistant_text = new_state.get("assistant_reply") or "(no response)"

    left_col, right_col = st.columns([1.5, 1])

    with left_col:
        with st.chat_message("assistant"):
            st.markdown(assistant_text)

    with right_col:
        st.markdown("### 📊 Traceability")
        _display_traceability_right(new_state)

    st.session_state.ct_state = new_state
    st.session_state.ct_chat.append(
        {
            "user": user_text,
            "assistant": assistant_text,
            "state": new_state,
        }
    )


if __name__ == "__main__":
    main()
