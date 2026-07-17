"""YES24 IT 모바일 베스트셀러 탐색적 데이터 분석(EDA) 및 도서 검색 Streamlit 대시보드.

이 모듈은 data/yes24_it_mobile_bestsellers.csv 데이터를 불러와
다양한 통계 지표와 시각화 차트를 제공하고, 도서 제목 및 상세 소개 글 기반의 키워드 검색 엔진을 제공합니다.
"""

import os
import re
import json
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq

# 1. 페이지 설정 및 프리미엄 스타일 정의
st.set_page_config(
    page_title="YES24 IT 모바일 베스트셀러 대시보드",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS 적용으로 디자인 개선 (프리미엄 룩앤필)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Noto Sans KR', sans-serif;
    }
    
    .main-title {
        background: linear-gradient(135deg, #6c5ce7, #a8df65);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    
    .sub-title {
        color: #555555;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 1.5rem;
        border-left: 5px solid #6c5ce7;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
    }
    
    .metric-title {
        font-size: 0.9rem;
        color: #666666;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #2d3436;
        margin-top: 0.5rem;
    }
    
    .book-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .book-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 15px rgba(108, 92, 231, 0.1);
        border-color: #6c5ce7;
    }
</style>
""", unsafe_allow_html=True)

# 2. 데이터 로드 및 전처리 함수
@st.cache_data
def load_data(file_path: str) -> pd.DataFrame:
    """CSV 데이터를 로드하고 분석에 용이하게 정제한다.

    - Publish Date에서 연도 및 월 추출
    - Rating, Sale Price, Original Price 등의 결측 처리
    - Discount Rate를 수치형으로 정제

    Args:
        file_path: 불러올 CSV 파일 경로.

    Returns:
        정제된 pandas DataFrame.
    """
    if not os.path.exists(file_path):
        return pd.DataFrame()
        
    df = pd.read_csv(file_path)
    
    # 1. Publish Date 파싱 (예: "2026년 05월" -> 2026, 5)
    def parse_year_month(date_str):
        if not isinstance(date_str, str):
            return None, None
        match = re.search(r'(\d{4})년\s*(\d{2})월', date_str)
        if match:
            return int(match.group(1)), int(match.group(2))
        # "2026.05" 혹은 유사 형식 파싱 시도
        match_alt = re.search(r'(\d{4})[-.](\d{2})', date_str)
        if match_alt:
            return int(match_alt.group(1)), int(match_alt.group(2))
        return None, None

    if 'Publish Date' in df.columns:
        parsed = df['Publish Date'].apply(parse_year_month)
        df['Publish Year'] = [p[0] for p in parsed]
        df['Publish Month'] = [p[1] for p in parsed]
        # 시계열용 가상 날짜 컬럼 생성 (월초 기준)
        df['Publish YearMonth'] = pd.to_datetime(
            df.apply(
                lambda row: f"{int(row['Publish Year'])}-{int(row['Publish Month']):02d}-01" 
                if pd.notna(row['Publish Year']) and pd.notna(row['Publish Month']) 
                else None, 
                axis=1
            )
        )
        
    # 2. Discount Rate 수치 변환 (예: "10%" -> 10)
    if 'Discount Rate' in df.columns:
        df['Discount Rate Numeric'] = df['Discount Rate'].astype(str).str.replace('%', '', regex=False)
        df['Discount Rate Numeric'] = pd.to_numeric(df['Discount Rate Numeric'], errors='coerce').fillna(0)
        
    # 3. Description 빈 값 채우기
    if 'Description' in df.columns:
        df['Description'] = df['Description'].fillna("등록된 책 소개 정보가 없습니다.")
    else:
        df['Description'] = "등록된 책 소개 정보가 없습니다."
        
    return df

# 데이터 파일 경로 설정
DATA_PATH = os.path.join("data", "yes24_it_mobile_bestsellers.csv")
df_raw = load_data(DATA_PATH)

# 데이터 로드 검증
if df_raw.empty:
    st.error("⚠️ 데이터를 불러올 수 없습니다. 'data/yes24_it_mobile_bestsellers.csv' 파일이 존재하는지 확인해 주세요.")
    st.info("💡 스크래퍼를 실행해 데이터를 먼저 수집하거나 마이그레이션 스크립트를 완료해 주세요.")
    st.stop()

# 3. 사이드바 디자인
with st.sidebar:
    st.markdown("### 📊 **대시보드 설정**")
    st.write("YES24 IT/모바일 베스트셀러 데이터를 바탕으로 작성된 탐색적 분석 대시보드입니다.")
    st.markdown("---")
    
    # 필터 기능 제공
    st.markdown("🔍 **출판사 필터 (다중 선택)**")
    publishers = sorted(df_raw['Publisher'].dropna().unique())
    selected_publishers = st.multiselect("출판사를 선택하세요 (미선택 시 전체 조회)", publishers)
    
    st.markdown("👤 **저자 필터 (검색 포함)**")
    author_query = st.text_input("저자 이름을 입력하세요 (포함 검색)", "")
    
    st.markdown("---")
    st.markdown("📌 **데이터 개요**")
    st.markdown(f"- **총 수집 도서 수**: `{len(df_raw)}` 권")
    st.markdown(f"- **평균 판매 가격**: `{int(df_raw['Sale Price'].mean()):,}원`")
    st.markdown(f"- **평균 도서 평점**: `★ {df_raw['Rating'].mean():.2f} / 10.0`")

# 필터링 적용
df_filtered = df_raw.copy()
if selected_publishers:
    df_filtered = df_filtered[df_filtered['Publisher'].isin(selected_publishers)]
if author_query:
    df_filtered = df_filtered[df_filtered['Author'].astype(str).str.contains(author_query, case=False, na=False)]

# 4. 본문 메인 타이틀 및 소개
st.markdown('<div class="main-title">YES24 IT/모바일 베스트셀러 대시보드</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">수집된 IT 모바일 도서 베스트셀러를 바탕으로 한 탐색적 데이터 분석(EDA) 및 키워드 기반 도서 상세 검색 서비스입니다.</div>', unsafe_allow_html=True)

# 탭 나누기
tab_eda, tab_search, tab_chat = st.tabs(["📊 탐색적 데이터 분석 (EDA)", "🔍 도서 키워드 검색 엔진", "💬 도서 추천 챗봇"])

# ==========================================
# Tab 1: 탐색적 데이터 분석 (EDA)
# ==========================================
with tab_eda:
    st.markdown("### 📈 **IT/모바일 베스트셀러 핵심 트렌드 분석**")
    
    # 4.1 핵심 KPI 카드 영역
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">전체 도서 수</div>
            <div class="metric-value">{len(df_filtered):,}권</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">평균 평점</div>
            <div class="metric-value">★ {df_filtered['Rating'].mean():.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">평균 판매가</div>
            <div class="metric-value">{int(df_filtered['Sale Price'].mean()):,}원</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">최고 판매지수</div>
            <div class="metric-value">{int(df_filtered['Sale Index'].max()):,}</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # 4.2 시각화 그리드 배치
    vis_col1, vis_col2 = st.columns(2)
    
    # 시각화 1: 가격대 분석 (정가 vs 판매가 BoxPlot)
    with vis_col1:
        st.markdown("#### 💵 **도서 가격대 분포 분석**")
        price_melted = df_filtered.melt(
            id_vars=['Title'], 
            value_vars=['Original Price', 'Sale Price'], 
            var_name='Price Type', 
            value_name='Price'
        )
        price_melted['Price Type'] = price_melted['Price Type'].map({
            'Original Price': '정가', 
            'Sale Price': '판매가'
        })
        
        fig_price = px.box(
            price_melted, 
            x='Price Type', 
            y='Price', 
            color='Price Type',
            points="all",
            color_discrete_map={'정가': '#95a5a6', '판매가': '#6c5ce7'},
            title="도서 정가와 판매가 분포 비교"
        )
        fig_price.update_layout(
            xaxis_title="가격 구분", 
            yaxis_title="가격 (원)", 
            showlegend=False,
            template="plotly_white"
        )
        st.plotly_chart(fig_price, use_container_width=True)

    # 시각화 2: 할인율 비중 분석
    with vis_col2:
        st.markdown("#### 🏷️ **할인율(Discount Rate) 통계**")
        discount_counts = df_filtered['Discount Rate'].value_counts().reset_index()
        discount_counts.columns = ['할인율', '도서 수']
        
        fig_discount = px.pie(
            discount_counts,
            values='도서 수',
            names='할인율',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel,
            title="할인율별 도서 비중"
        )
        fig_discount.update_traces(textposition='inside', textinfo='percent+label')
        fig_discount.update_layout(template="plotly_white")
        st.plotly_chart(fig_discount, use_container_width=True)
        
    st.markdown("---")
    vis_col3, vis_col4 = st.columns(2)
    
    # 시각화 3: 출판사별 베스트셀러 점유율 TOP 10
    with vis_col3:
        st.markdown("#### 🏢 **주요 출판사 TOP 10**")
        pub_counts = df_filtered['Publisher'].value_counts().head(10).reset_index()
        pub_counts.columns = ['출판사', '도서 수']
        
        fig_pub = px.bar(
            pub_counts,
            y='출판사',
            x='도서 수',
            orientation='h',
            text='도서 수',
            color='도서 수',
            color_continuous_scale='Purples',
            title="베스트셀러 등록 도서가 가장 많은 출판사 TOP 10"
        )
        fig_pub.update_layout(
            yaxis={'categoryorder': 'total ascending'},
            xaxis_title="등록 도서 수 (권)",
            yaxis_title="출판사명",
            template="plotly_white",
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_pub, use_container_width=True)
        
    # 시각화 4: 평점 vs 판매지수 상관관계 산점도
    with vis_col4:
        st.markdown("#### 📈 **평점과 판매지수(Sale Index) 상관관계**")
        fig_scatter = px.scatter(
            df_filtered,
            x='Rating',
            y='Sale Index',
            color='Review Count',
            size='Review Count',
            hover_name='Title',
            hover_data=['Author', 'Publisher', 'Sale Price'],
            color_continuous_scale='Viridis',
            title="평점과 판매지수, 그리고 리뷰 수의 관계"
        )
        fig_scatter.update_layout(
            xaxis_title="평점 (점)",
            yaxis_title="판매지수 (Sale Index)",
            template="plotly_white"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("---")
    
    # 시각화 5: 출판 트렌드 (월별 출판 권수 변화)
    st.markdown("#### 📅 **출판 시기별 트렌드 분석**")
    if 'Publish YearMonth' in df_filtered.columns:
        trend_df = df_filtered.groupby('Publish YearMonth').size().reset_index(name='도서 수')
        # 최근 24개월(혹은 데이터 범위 내) 필터링
        trend_df = trend_df.sort_values('Publish YearMonth')
        
        fig_trend = px.line(
            trend_df,
            x='Publish YearMonth',
            y='도서 수',
            markers=True,
            line_shape='spline',
            color_discrete_sequence=['#20bf6b'],
            title="출판 월별 베스트셀러 등록 도서 추이"
        )
        fig_trend.update_layout(
            xaxis_title="출판 연월",
            yaxis_title="베스트셀러 등록 수 (권)",
            template="plotly_white"
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("출판일 형식 문제로 인해 시기별 트렌드를 시각화할 수 없습니다.")

# ==========================================
# Tab 2: 도서 키워드 검색 엔진
# ==========================================
with tab_search:
    st.markdown("### 🔍 **통합 도서 검색 서비스**")
    st.write("책의 **제목**과 상세 **내용(소개글)** 전반에서 검색하려는 키워드를 입력해 보세요.")
    
    # 검색 입력 컴포넌트
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        query = st.text_input("검색할 키워드를 입력하세요 (예: 파이썬, 클로드, 머신러닝, 코딩)", "", key="search_query")
    with search_col2:
        sort_by = st.selectbox(
            "정렬 기준",
            ["순위순 (오름차순)", "판매지수순 (내림차순)", "평점순 (내림차순)", "리뷰 많은 순 (내림차순)", "가격 낮은 순", "가격 높은 순"]
        )
        
    st.markdown("---")
    
    # 키워드 필터링 로직
    if query:
        # 제목 혹은 내용에서 해당 키워드 매칭
        # 대소문자 구분 없음
        search_filter = (
            df_filtered['Title'].astype(str).str.contains(query, case=False, na=False) |
            df_filtered['Description'].astype(str).str.contains(query, case=False, na=False)
        )
        search_results = df_filtered[search_filter]
    else:
        search_results = df_filtered.copy()
        
    # 정렬 방식 적용
    if sort_by == "순위순 (오름차순)":
        search_results = search_results.sort_values('Rank', ascending=True)
    elif sort_by == "판매지수순 (내림차순)":
        search_results = search_results.sort_values('Sale Index', ascending=False)
    elif sort_by == "평점순 (내림차순)":
        search_results = search_results.sort_values('Rating', ascending=False)
    elif sort_by == "리뷰 많은 순 (내림차순)":
        search_results = search_results.sort_values('Review Count', ascending=False)
    elif sort_by == "가격 낮은 순":
        search_results = search_results.sort_values('Sale Price', ascending=True)
    elif sort_by == "가격 높은 순":
        search_results = search_results.sort_values('Sale Price', ascending=False)
        
    # 검색 결과 개수 출력
    st.markdown(f"💡 검색 조건에 부합하는 도서가 총 **{len(search_results)}** 권 검색되었습니다.")
    
    # 검색 결과 도서 카드 렌더링
    if search_results.empty:
        st.warning("일치하는 도서가 없습니다. 다른 검색어로 시도해 주세요.")
    else:
        for idx, row in search_results.iterrows():
            # 평점 별점 문자열 생성
            stars = "★" * int(round(row['Rating']/2)) if pd.notna(row['Rating']) else ""
            rating_text = f"★ {row['Rating']:.1f}" if pd.notna(row['Rating']) and row['Rating'] > 0 else "평점 없음"
            
            # 카드 구조 렌더링
            with st.container():
                st.markdown(f"""
                <div class="book-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                        <span style="background-color: #6c5ce7; color: white; padding: 0.2rem 0.6rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600;">베스트셀러 {int(row['Rank'])}위</span>
                        <span style="color: #fdcb6e; font-weight: 600;">{stars} ({rating_text})</span>
                    </div>
                    <h4 style="margin: 0.3rem 0; color: #2d3436; font-size: 1.25rem;">{row['Title']}</h4>
                    <p style="margin: 0.2rem 0; color: #636e72; font-size: 0.9rem;">
                        저자: <strong>{row['Author']}</strong> | 출판사: <strong>{row['Publisher']}</strong> | 출판일: <strong>{row['Publish Date']}</strong>
                    </p>
                    <div style="margin: 0.5rem 0; display: flex; gap: 1rem; align-items: center;">
                        <span style="font-size: 1.1rem; font-weight: 700; color: #d63031;">{int(row['Sale Price']):,}원</span>
                        <span style="font-size: 0.9rem; text-decoration: line-through; color: #b2bec3;">{int(row['Original Price']):,}원</span>
                        <span style="font-size: 0.85rem; background-color: #ffeaa7; color: #d63031; padding: 0.1rem 0.4rem; border-radius: 4px; font-weight: 600;">{row['Discount Rate']} 할인</span>
                        <span style="font-size: 0.85rem; color: #74b9ff;">판매지수: {int(row['Sale Index']):,}</span>
                        <span style="font-size: 0.85rem; color: #a8e6cf;">리뷰 수: {int(row['Review Count'])}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 책 상세 정보 (Description) 및 링크
                with st.expander("📖 책 소개 및 상세 내용 보기"):
                    st.write(row['Description'])
                    st.markdown(f"[🔗 YES24 상세페이지로 이동하기]({row['Detail Link']})")
                
                st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

# ==========================================
# Tab 3: 도서 추천 챗봇 (RAG - ChromaDB + Groq)
# ==========================================
with tab_chat:
    st.markdown("### 💬 **AI 도서 추천 챗봇 (RAG)**")
    st.write("ChromaDB 벡터 검색으로 전체 1000권에서 관련 도서를 찾아 AI가 추천합니다.")

    with st.expander("🔑 Groq API Key 설정", expanded=not st.session_state.get("groq_api_key")):
        api_key = st.text_input(
            "Groq API Key를 입력하세요",
            type="password",
            value=st.session_state.get("groq_api_key", ""),
            key="groq_api_key_input",
            help="https://console.groq.com/keys 에서 발급받을 수 있습니다."
        )
        if api_key:
            st.session_state.groq_api_key = api_key
        if not st.session_state.get("groq_api_key"):
            st.warning("Groq API Key를 입력해 주세요.")

    if "embedding_ready" not in st.session_state:
        st.session_state.embedding_ready = False

    with st.expander("벡터DB 관리", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("임베딩 인덱스 구축 (처음 1회)"):
                with st.spinner("ChromaDB 임베딩 저장 중..."):
                    from embedding_store import EmbeddingStore
                    store = EmbeddingStore()
                    count = store.build_index(df_raw)
                    st.session_state.embedding_store = store
                    st.session_state.embedding_ready = True
                    st.success(f"{count}권 저장 완료!")
        with col2:
            st.markdown("상태: " + ("준비됨" if st.session_state.embedding_ready else "미구축"))

    st.markdown("---")

    if st.button("대화 초기화"):
        st.session_state.chat_messages = []
        st.rerun()

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("찾고 싶은 도서를 설명해 주세요"):
        if not st.session_state.get("groq_api_key"):
            st.error("Groq API Key를 먼저 입력해 주세요.")
            st.stop()
        if not st.session_state.get("embedding_ready"):
            st.error("먼저 '임베딩 인덱스 구축' 버튼을 눌러 주세요.")
            st.stop()

        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        store = st.session_state.embedding_store
        results = store.search(prompt, top_k=5)

        if results:
            lines = []
            for r in results:
                link = f"[YES24에서 보기]({r['detail_link']})" if r.get("detail_link") else "링크없음"
                lines.append(
                    f"- 제목: {r['title']} | 저자: {r['author']} | 출판사: {r['publisher']} "
                    f"| 가격: {r['sale_price']:,}원 | 평점: {r['rating']}/10 | 링크: {link}\n"
                    f"  관련내용: {r['document'][:200]}"
                )
            context = "벡터 검색 결과:\n\n" + "\n\n".join(lines)
        else:
            context = "검색 결과가 없습니다."

        system_prompt = f"""당신은 YES24 IT/모바일 베스트셀러 도서 추천 전문가입니다.
아래는 ChromaDB로 찾은 관련 도서입니다:

{context}

**규칙:**
1. 위 정보에서 사용자 질문과 가장 관련 있는 도서를 추천하세요.
2. 책 제목, 저자, 출판사, 판매가, 평점, 추천 이유를 포함하고 링크는 [YES24에서 보기](URL) 형식으로 주세요.
3. 관련 도서가 없으면 "현재 보유한 데이터에서 조건에 맞는 도서를 찾을 수 없습니다."라고 답변하세요.
4. 도서 외 질문에는 "도서 관련 질문만 받을 수 있습니다."라고 답변하세요.
5. 답변은 한국어로 해주세요."""

        try:
            client = Groq(api_key=st.session_state.groq_api_key)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *[{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_messages]
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            reply = response.choices[0].message.content
        except Exception as e:
            reply = f"API 호출 오류: {str(e)}"

        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)
