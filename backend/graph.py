# from langgraph.graph import StateGraph, END

# graph = StateGraph(DesignState)

# graph.add_node("requirements", requirements_node)
# graph.add_node("techstack", techstack_node)
# graph.add_node("architecture", architecture_node)
# graph.add_node("critic", critic_node)
# graph.add_node("assemble", assemble_node)

# graph.set_entry_point("requirements")
# graph.add_edge("requirements", "techstack")
# graph.add_edge("techstack", "architecture")
# graph.add_edge("architecture", "critic")

# def route_after_critic(state: DesignState) -> str:
#     if state["critic_verdict"]["verdict"] == "APPROVE":
#         return "assemble"
#     if state["revision_count"] >= 3:  # cap revisions
#         return "assemble"
#     return "architecture"

# graph.add_conditional_edges("critic", route_after_critic, {
#     "architecture": "architecture",
#     "assemble": "assemble",
# })
# graph.add_edge("assemble", END)

# app = graph.compile()