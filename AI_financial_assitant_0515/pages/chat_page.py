import streamlit as st
import uuid
from database.connection import get_session
from ai.orchestrator import answer_question

SUGGESTED_QUESTIONS = [
    "What is the overall budget execution rate?",
    "Which chapters show abnormal consumption?",
    "Are there old outstanding commitments?",
    "Which suppliers concentrate the most spending?",
    "How many mandates have been rejected and why?",
    "What are the priority alerts I should address?",
    "Which budget lines may be insufficient before year-end?",
    "Generate a brief budget execution summary for management.",
]

CONFIDENCE_COLORS = {"high": "🟢", "medium": "🟡", "low": "🔴", "none": "⚫"}


def render(la_id: int, fy_id: int, la_name: str, year: int):
    st.title(f"AI Financial Assistant — {la_name} — {year}")
    st.caption(
        "Ask questions about your financial data. Answers are sourced from imported data only — "
        "the assistant will refuse to invent figures."
    )

    # Session ID for conversation logging
    if "chat_session_id" not in st.session_state:
        st.session_state.chat_session_id = str(uuid.uuid4())

    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Suggested questions
    st.subheader("Suggested Questions")
    cols = st.columns(2)
    for i, q in enumerate(SUGGESTED_QUESTIONS):
        if cols[i % 2].button(q, key=f"sq_{i}", use_container_width=True):
            st.session_state.pending_question = q

    st.divider()

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and "meta" in msg:
                meta = msg["meta"]
                conf_icon = CONFIDENCE_COLORS.get(meta.get("confidence", "none"), "⚫")
                st.caption(
                    f"{conf_icon} Confidence: **{meta.get('confidence', 'unknown')}** | "
                    f"Intent: `{meta.get('intent', '?')}` | "
                    f"Sources: {', '.join(meta.get('sources', [])) or 'none'}"
                )

    # Input
    pending = st.session_state.pop("pending_question", None)
    user_input = st.chat_input("Ask a financial question...") or pending

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Analysing data and generating answer..."):
                session = get_session()
                result = answer_question(
                    question=user_input,
                    la_id=la_id,
                    fy_id=fy_id,
                    session=session,
                    session_id=st.session_state.chat_session_id,
                )
                session.close()

            st.markdown(result["answer"])
            conf_icon = CONFIDENCE_COLORS.get(result.get("confidence", "none"), "⚫")
            st.caption(
                f"{conf_icon} Confidence: **{result.get('confidence', 'unknown')}** | "
                f"Intent: `{result.get('intent', '?')}` | "
                f"Sources: {', '.join(result.get('sources', [])) or 'none'}"
            )

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "meta": result,
        })

    # Clear history
    if st.session_state.messages and st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.chat_session_id = str(uuid.uuid4())
        st.rerun()
