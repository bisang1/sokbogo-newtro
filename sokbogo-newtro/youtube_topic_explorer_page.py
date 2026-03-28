import streamlit as st
from youtube_topic_explorer import get_topic_trends


def render_topic_explorer(client, model):
    st.header("트렌드 탐색")

    if "selected_topic" not in st.session_state:
        st.session_state["selected_topic"] = None

    if "trend_results" not in st.session_state:
        st.session_state["trend_results"] = []

    # 이미 불러온 트렌드가 있으면 재사용
    if not st.session_state["trend_results"]:
        with st.spinner("트렌드 불러오는 중..."):
            st.session_state["trend_results"] = get_topic_trends(
                client=client,
                model=model,
            )

    trends = st.session_state["trend_results"]

    ranked_trends = sorted(
        trends,
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    st.subheader("🔥 트렌드 점수 TOP5")
    top5 = ranked_trends[:5]

    for idx, trend in enumerate(top5, 1):
        keyword = trend.get("keyword", "")
        score = trend.get("score", 0)
        reason = trend.get("reason", "")
        insight = trend.get("insight", "")
        health_angle = trend.get("health_angle", "")
        converted_topic = trend.get("converted_topic", "")
        topics = trend.get("topics", [])

        st.markdown(f"### {idx}. {keyword} ({score}점)")

        if reason:
            st.caption(f"이슈 이유: {reason}")

        if insight:
            st.caption(f"사람들이 궁금해하는 이유: {insight}")

        if health_angle:
            st.caption(f"건강 연결: {health_angle}")

        if converted_topic:
            st.success(f"추천 건강 주제: {converted_topic}")

        if topics:
            selected = st.selectbox(
                f"{keyword} 기반 쇼츠 주제",
                topics,
                key=f"topic_select_{idx}"
            )
        else:
            selected = converted_topic or keyword

        if st.button("이 주제 사용", key=f"use_topic_{idx}"):
            st.session_state["selected_topic"] = selected or converted_topic or keyword
            st.session_state["trend_reason"] = reason
            st.session_state["trend_insight"] = insight
            st.session_state["trend_health_angle"] = health_angle
            st.session_state["use_trend"] = True

            # 메인 생성 화면으로 이동
            st.session_state["channel"] = "속보고(장기-몸속-일상-희망)"

            # 다시 트렌드 탐색 반복하지 않도록 유지
            st.rerun()

        st.divider()

    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button("🔄 트렌드 새로고침", use_container_width=True):
            st.session_state["trend_results"] = []
            st.rerun()