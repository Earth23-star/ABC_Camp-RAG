"""YES24 IT / Mobile Bestseller Analysis (EDA) and Recommendation Streamlit App

Loads book data from data/yes24_it_mobile_bestsellers.csv, provides various
statistics and charts, and offers a keyword based book search feature.
"""

import os
import re
import json
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq

# 1. Page configuration
st.set_page_config(
    page_title="YES24 IT / Mobile Bestseller Analysis",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for improved UI (premium look)
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

# 2. Data loading function
@st.cache_data
def load_data(file_path: str) -> pd.DataFrame:
    """Load CSV file and perform basic preprocessing for analysis.

    - Extract year/month from Publish Date
    - Handle missing values for Rating, Sale Price, Original Price
    - Convert Discount Rate to numeric

    Args:
        file_path: Path to the CSV file to load.

    Returns:
        Preprocessed pandas DataFrame.
    """
    if not os.path.exists(file_path):
        return pd.DataFrame()
        
    df = pd.read_csv(file_path)
    
    # 1. Parse Publish Date (e.g. "2026-05" -> 2026, 5)
    def parse_year_month(date_str):
        if not isinstance(date_str, str):
            return None, None
        match = re.search(r'(\d{4})\s*(\d{2})', date_str)
        if match:
            return int(match.group(1)), int(match.group(2))
        # also handle "2026.05" style dates
        match_alt = re.search(r'(\d{4})[-.](\d{2})', date_str)
        if match_alt:
            return int(match_alt.group(1)), int(match_alt.group(2))
        return None, None

    if 'Publish Date' in df.columns:
        parsed = df['Publish Date'].apply(parse_year_month)
        df['Publish Year'] = [p[0] for p in parsed]
        df['Publish Month'] = [p[1] for p in parsed]
        # build a proper datetime column for trend analysis
        df['Publish YearMonth'] = pd.to_datetime(
            df.apply(
                lambda row: f"{int(row['Publish Year'])}-{int(row['Publish Month']):02d}-01" 
                if pd.notna(row['Publish Year']) and pd.notna(row['Publish Month']) 
                else None, 
                axis=1
            )
        )
        
    # 2. Convert Discount Rate (e.g. "10%" -> 10)
    if 'Discount Rate' in df.columns:
        df['Discount Rate Numeric'] = df['Discount Rate'].astype(str).str.replace('%', '', regex=False)
        df['Discount Rate Numeric'] = pd.to_numeric(df['Discount Rate Numeric'], errors='coerce').fillna(0)
        
    # 3. Fill missing Description
    if 'Description' in df.columns:
        df['Description'] = df['Description'].fillna("No detailed description available.")
    else:
        df['Description'] = "No detailed description available."
        
    return df

# Data file path setting (resolve relative to repo root so it works
# regardless of the Streamlit working directory)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "yes24_it_mobile_bestsellers.csv")
df_raw = load_data(DATA_PATH)

# Data load check
if df_raw.empty:
    st.error("Could not load the data file. Please check that 'data/yes24_it_mobile_bestsellers.csv' exists.")
    st.info("Run the scraper/migration script first to generate the data file.")
    st.stop()

# 3. Sidebar settings
with st.sidebar:
    st.markdown("### ⚙️ **App Settings**")
    st.write("This app analyzes YES24 IT/Mobile bestseller data and provides book recommendations.")
    st.markdown("---")
    
    # Filter feature
    st.markdown("🔍 **Publisher Filter (multi-select)**")
    publishers = sorted(df_raw['Publisher'].dropna().unique())
    selected_publishers = st.multiselect("Select publishers (empty = all)", publishers)
    
    st.markdown("🔍 **Author Filter (search)**")
    author_query = st.text_input("Enter author name (partial match)", "")
    
    st.markdown("---")
    st.markdown("📊 **Data Overview**")
    st.markdown(f"- **Total books**: `{len(df_raw)}`")
    st.markdown(f"- **Average sale price**: `{int(df_raw['Sale Price'].mean()):,}` KRW")
    st.markdown(f"- **Average rating**: `{df_raw['Rating'].mean():.2f} / 10.0`")

# Filtering logic
df_filtered = df_raw.copy()
if selected_publishers:
    df_filtered = df_filtered[df_filtered['Publisher'].isin(selected_publishers)]
if author_query:
    df_filtered = df_filtered[df_filtered['Author'].astype(str).str.contains(author_query, case=False, na=False)]

# 4. Main content introduction
st.markdown('<div class="main-title">YES24 IT / Mobile Bestseller Analysis</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Explore YES24 IT/Mobile bestseller data through EDA and AI-powered book search.</div>', unsafe_allow_html=True)

# Create tabs
tab_eda, tab_search, tab_chat = st.tabs(["📊 Data Analysis (EDA)", "🔎 Book Search", "🤖 Book Recommendation Chatbot"])

# ==========================================
# Tab 1: Data Analysis (EDA)
# ==========================================
with tab_eda:
    st.markdown("### 📈 **IT / Mobile Bestseller Core Trend Analysis**")
    
    # 4.1 Core KPI cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Books</div>
            <div class="metric-value">{len(df_filtered):,}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Average Rating</div>
            <div class="metric-value">{df_filtered['Rating'].mean():.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Avg Sale Price</div>
            <div class="metric-value">{int(df_filtered['Sale Price'].mean()):,} KRW</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Max Sale Index</div>
            <div class="metric-value">{int(df_filtered['Sale Index'].max()):,}</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # 4.2 Visualization layout
    vis_col1, vis_col2 = st.columns(2)
    
    # Chart 1: Price distribution (Original vs Sale Price BoxPlot)
    with vis_col1:
        st.markdown("#### 📦 **Book Price Distribution Analysis**")
        price_melted = df_filtered.melt(
            id_vars=['Title'], 
            value_vars=['Original Price', 'Sale Price'], 
            var_name='Price Type', 
            value_name='Price'
        )
        price_melted['Price Type'] = price_melted['Price Type'].map({
            'Original Price': 'Original', 
            'Sale Price': 'Sale'
        })
        
        fig_price = px.box(
            price_melted, 
            x='Price Type', 
            y='Price', 
            color='Price Type',
            points="all",
            color_discrete_map={'Original': '#95a5a6', 'Sale': '#6c5ce7'},
            title="Original vs Sale Price Distribution"
        )
        fig_price.update_layout(
            xaxis_title="Price Type", 
            yaxis_title="Price (KRW)", 
            showlegend=False,
            template="plotly_white"
        )
        st.plotly_chart(fig_price, use_container_width=True)

    # Chart 2: Discount rate distribution
    with vis_col2:
        st.markdown("#### 📉 **Discount Rate Statistics**")
        discount_counts = df_filtered['Discount Rate'].value_counts().reset_index()
        discount_counts.columns = ['Discount Rate', 'Book Count']
        
        fig_discount = px.pie(
            discount_counts,
            values='Book Count',
            names='Discount Rate',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel,
            title="Book Share by Discount Rate"
        )
        fig_discount.update_traces(textposition='inside', textinfo='percent+label')
        fig_discount.update_layout(template="plotly_white")
        st.plotly_chart(fig_discount, use_container_width=True)
        
    st.markdown("---")
    vis_col3, vis_col4 = st.columns(2)
    
    # Chart 3: Top 10 publishers by book count
    with vis_col3:
        st.markdown("#### 🏢 **Top 10 Publishers**")
        pub_counts = df_filtered['Publisher'].value_counts().head(10).reset_index()
        pub_counts.columns = ['Publisher', 'Book Count']
        
        fig_pub = px.bar(
            pub_counts,
            y='Publisher',
            x='Book Count',
            orientation='h',
            text='Book Count',
            color='Book Count',
            color_continuous_scale='Purples',
            title="Top 10 Publishers by Registered Book Count"
        )
        fig_pub.update_layout(
            yaxis={'categoryorder': 'total ascending'},
            xaxis_title="Book Count",
            yaxis_title="Publisher Name",
            template="plotly_white",
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_pub, use_container_width=True)
        
    # Chart 4: Rating vs Sale Index correlation
    with vis_col4:
        st.markdown("#### ⭐ **Rating vs Sale Index (Correlation)**")
        fig_scatter = px.scatter(
            df_filtered,
            x='Rating',
            y='Sale Index',
            color='Review Count',
            size='Review Count',
            hover_name='Title',
            hover_data=['Author', 'Publisher', 'Sale Price'],
            color_continuous_scale='Viridis',
            title="Rating vs Sale Index Scatter"
        )
        fig_scatter.update_layout(
            xaxis_title="Rating (0-10)",
            yaxis_title="Sale Index",
            template="plotly_white"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("---")
    
    # Chart 5: Publisher trend (book count by publish month)
    st.markdown("#### 📅 **Publisher Trend Analysis**")
    if 'Publish YearMonth' in df_filtered.columns:
        trend_df = df_filtered.groupby('Publish YearMonth').size().reset_index(name='Book Count')
        trend_df = trend_df.sort_values('Publish YearMonth')
        
        fig_trend = px.line(
            trend_df,
            x='Publish YearMonth',
            y='Book Count',
            markers=True,
            line_shape='spline',
            color_discrete_sequence=['#20bf6b'],
            title="Registered Book Count Trend by Publish Month"
        )
        fig_trend.update_layout(
            xaxis_title="Publish Year-Month",
            yaxis_title="Book Count",
            template="plotly_white"
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Trend analysis is unavailable due to a date parsing issue.")

# ==========================================
# Tab 2: Book Search
# ==========================================
with tab_search:
    st.markdown("### 🔎 **Book Search**")
    st.write("Search books by **title** or **description** (content).")
    
    # Search input components
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        query = st.text_input("Enter keyword to search (e.g. machine learning, coding)", "", key="search_query")
    with search_col2:
        sort_by = st.selectbox(
            "Sort By",
            ["Rank (Ascending)", "Sale Index (Descending)", "Rating (Descending)", "Review Count (Descending)", "Price (Ascending)", "Price (Descending)"]
        )
        
    st.markdown("---")
    
    # Search filter logic
    if query:
        search_filter = (
            df_filtered['Title'].astype(str).str.contains(query, case=False, na=False) |
            df_filtered['Description'].astype(str).str.contains(query, case=False, na=False)
        )
        search_results = df_filtered[search_filter]
    else:
        search_results = df_filtered.copy()
        
    # Sort logic
    if sort_by == "Rank (Ascending)":
        search_results = search_results.sort_values('Rank', ascending=True)
    elif sort_by == "Sale Index (Descending)":
        search_results = search_results.sort_values('Sale Index', ascending=False)
    elif sort_by == "Rating (Descending)":
        search_results = search_results.sort_values('Rating', ascending=False)
    elif sort_by == "Review Count (Descending)":
        search_results = search_results.sort_values('Review Count', ascending=False)
    elif sort_by == "Price (Ascending)":
        search_results = search_results.sort_values('Sale Price', ascending=True)
    elif sort_by == "Price (Descending)":
        search_results = search_results.sort_values('Sale Price', ascending=False)
        
    # Result count
    st.markdown(f"Found **{len(search_results)}** books matching the search condition.")
    
    # Result book cards
    if search_results.empty:
        st.warning("No books found. Please try a different keyword.")
    else:
        for idx, row in search_results.iterrows():
            # Rating stars text
            stars = "⭐" * int(round(row['Rating']/2)) if pd.notna(row['Rating']) else ""
            rating_text = f"{row['Rating']:.1f}" if pd.notna(row['Rating']) and row['Rating'] > 0 else "No rating"
            
            # Card structure
            with st.container():
                st.markdown(f"""
                <div class="book-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                        <span style="background-color: #6c5ce7; color: white; padding: 0.2rem 0.6rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600;">Rank {int(row['Rank'])}</span>
                        <span style="color: #fdcb6e; font-weight: 600;">{stars} ({rating_text})</span>
                    </div>
                    <h4 style="margin: 0.3rem 0; color: #2d3436; font-size: 1.25rem;">{row['Title']}</h4>
                    <p style="margin: 0.2rem 0; color: #636e72; font-size: 0.9rem;">
                        Author: <strong>{row['Author']}</strong> | Publisher: <strong>{row['Publisher']}</strong> | Published: <strong>{row['Publish Date']}</strong>
                    </p>
                    <div style="margin: 0.5rem 0; display: flex; gap: 1rem; align-items: center;">
                        <span style="font-size: 1.1rem; font-weight: 700; color: #d63031;">{int(row['Sale Price']):,} KRW</span>
                        <span style="font-size: 0.9rem; text-decoration: line-through; color: #b2bec3;">{int(row['Original Price']):,} KRW</span>
                        <span style="font-size: 0.85rem; background-color: #ffeaa7; color: #d63031; padding: 0.1rem 0.4rem; border-radius: 4px; font-weight: 600;">{row['Discount Rate']} off</span>
                        <span style="font-size: 0.85rem; color: #74b9ff;">Sale Index {int(row['Sale Index']):,}</span>
                        <span style="font-size: 0.85rem; color: #a8e6cf;">Reviews {int(row['Review Count'])}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Detail info (Description) expander
                with st.expander("View Book Description"):
                    st.write(row['Description'])
                    st.markdown(f"[Open YES24 Detail Page]({row['Detail Link']})")
                
                st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

# ==========================================
# Tab 3: Book Recommendation Chatbot (RAG - ChromaDB + Groq)
# ==========================================
with tab_chat:
    st.markdown("### 🤖 **AI Book Recommendation Chatbot (RAG)**")
    st.write("Finds books related to your query from the ChromaDB vector store (1000 books) and recommends them via AI.")

    with st.expander("🔑 Set Groq API Key", expanded=not st.session_state.get("groq_api_key")):
        api_key = st.text_input(
            "Enter your Groq API Key",
            type="password",
            value=st.session_state.get("groq_api_key", ""),
            key="groq_api_key_input",
            help="Get your key from https://console.groq.com/keys"
        )
        if api_key:
            st.session_state.groq_api_key = api_key
        if not st.session_state.get("groq_api_key"):
            st.warning("Please enter your Groq API Key.")

    if "embedding_ready" not in st.session_state:
        st.session_state.embedding_ready = False

    with st.expander("Vector DB Management", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("Build Vector Index (first time only)"):
                with st.spinner("Building ChromaDB index..."):
                    from embedding_store import EmbeddingStore
                    store = EmbeddingStore()
                    count = store.build_index(df_raw)
                    st.session_state.embedding_store = store
                    st.session_state.embedding_ready = True
                    st.success(f"Indexed {count} books!")
        with col2:
            st.markdown("Status: " + ("Ready" if st.session_state.embedding_ready else "Not ready"))

    st.markdown("---")

    if st.button("🗑️ Reset Chat"):
        st.session_state.chat_messages = []
        st.rerun()

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Describe the book you are looking for"):
        if not st.session_state.get("groq_api_key"):
            st.error("Please enter your Groq API Key first.")
            st.stop()
        if not st.session_state.get("embedding_ready"):
            st.error("Please click 'Build Vector Index' first.")
            st.stop()

        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        store = st.session_state.embedding_store
        results = store.search(prompt, top_k=5)

        if results:
            lines = []
            for r in results:
                link = f"[YES24 Book Link]({r['detail_link']})" if r.get("detail_link") else "No link"
                lines.append(
                    f"- Title: {r['title']} | Author: {r['author']} | Publisher: {r['publisher']} "
                    f"| Price: {r['sale_price']:,} KRW | Rating: {r['rating']}/10 | Link: {link}\n"
                    f"  Content: {r['document'][:200]}"
                )
            context = "Vector search results:\n\n" + "\n\n".join(lines)
        else:
            context = "No search results found."

        system_prompt = f"""You are a YES24 IT/Mobile book recommendation expert.
Based on the books found in ChromaDB, recommend the most relevant books to the user.

{context}

**Rules:**
1. Recommend books related to the user's question based on the retrieved content.
2. Include title, author, publisher, sale price, rating, and recommendation reason, and provide the link in [YES24 Book Link](URL) format.
3. If there are no related books, say "I could not find a book matching your condition in the current database."
4. If the question is not about books, say "I can only answer book-related questions."
5. Please answer in Korean.
"""

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
            reply = f"API call error: {str(e)}"

        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)
