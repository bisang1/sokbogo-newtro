import streamlit as st
from youtube_topic_explorer import get_topic_trends


def render_topic_explorer():

    st.header("트렌드 탐색")

    trends = get_topic_trends()

    if "selected_topic" not in st.session_state:
        st.session_state.selected_topic = ""

    for i, trend in enumerate(trends):

        with st.container():

            st.subheader(trend["keyword"])

            topic = st.radio(
                "주제 선택",
                trend["topics"],
                key=f"topic_{i}"
            )

            if st.button("이 주제 사용", key=f"btn_{i}"):

                st.session_state.selected_topic = topic

                st.success(f"선택된 주제: {topic}")

            st.divider()

    st.subheader("현재 선택된 주제")

    if st.session_state.selected_topic:
        st.code(st.session_state.selected_topic)