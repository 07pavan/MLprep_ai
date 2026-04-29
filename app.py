"""Main Streamlit Application"""
import streamlit as st
import pandas as pd
from agents import (
    OrchestratorAgent,
    DataProfilerAgent,
    AnalystAgent,
    VisualizerAgent,
    InsightsAgent
)
from utils import validate_csv_file, validate_dataframe
from config import settings
import plotly.graph_objects as go

# Page configuration
st.set_page_config(
    page_title="AI Data Analyst Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding: 1rem 0;
    }
    .sub-header {
        text-align: center;
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = None
if 'profile' not in st.session_state:
    st.session_state.profile = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'agents_initialized' not in st.session_state:
    st.session_state.agents_initialized = False

# Initialize agents
@st.cache_resource
def initialize_agents():
    """Initialize all agents (cached)"""
    return {
        'orchestrator': OrchestratorAgent(),
        'profiler': DataProfilerAgent(),
        'analyst': AnalystAgent(),
        'visualizer': VisualizerAgent(),
        'insights': InsightsAgent()
    }

# Header
st.markdown('<h1 class="main-header">🤖 AI Data Analyst Agent</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Upload your CSV and ask questions in natural language</p>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("📁 Data Upload")
    
    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=['csv'],
        help="Upload a CSV file (max 100MB)"
    )
    
    if uploaded_file is not None:
        is_valid, message = validate_csv_file(uploaded_file)
        
        if is_valid:
            try:
                df = pd.read_csv(uploaded_file)
                is_valid_df, df_message = validate_dataframe(df)
                
                if is_valid_df:
                    st.session_state.df = df
                    st.success(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
                    
                    if not st.session_state.agents_initialized:
                        with st.spinner("Initializing AI agents..."):
                            st.session_state.agents = initialize_agents()
                            st.session_state.agents_initialized = True
                    
                    if st.session_state.profile is None:
                        with st.spinner("Analyzing your data..."):
                            profiler = st.session_state.agents['profiler']
                            st.session_state.profile = profiler.profile_dataset(df)
                else:
                    st.error(f"❌ {df_message}")
            except Exception as e:
                st.error(f"❌ Error loading file: {str(e)}")
        else:
            st.error(f"❌ {message}")
    
    if st.session_state.df is not None:
        st.divider()
        st.subheader("📊 Dataset Info")
        
        profile = st.session_state.profile
        if profile:
            st.metric("Rows", f"{profile['basic_info']['rows']:,}")
            st.metric("Columns", f"{profile['basic_info']['columns']}")
            st.metric("Size", f"{profile['basic_info']['memory_mb']:.2f} MB")
            
            quality = st.session_state.agents['profiler'].get_data_quality_report(st.session_state.df)
            st.metric("Completeness", f"{quality['completeness_score']}%")
        
        if st.button("🔄 Reset Data", use_container_width=True):
            st.session_state.df = None
            st.session_state.profile = None
            st.session_state.chat_history = []
            st.rerun()

# Main content
if st.session_state.df is None:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("### 📤 Upload CSV\nStart by uploading your data file")
    
    with col2:
        st.info("### 💬 Ask Questions\nUse natural language queries")
    
    with col3:
        st.info("### 📊 Get Insights\nReceive analysis & visualizations")
    
    st.divider()
    
    st.subheader("Example Questions You Can Ask:")
    example_questions = [
        "Show me the first 10 rows",
        "What is the average sales amount?",
        "Show me the trend of revenue over time",
        "Which product category has the highest sales?",
        "Find any unusual patterns in the data",
        "Compare sales between different regions"
    ]
    
    cols = st.columns(2)
    for i, question in enumerate(example_questions):
        with cols[i % 2]:
            st.markdown(f"- {question}")

else:
    tab1, tab2, tab3 = st.tabs(["💬 Chat & Analysis", "📊 Data Overview", "🔍 Auto Insights"])
    
    with tab1:
        st.subheader("Ask Questions About Your Data")
        
        if st.session_state.profile:
            profiler = st.session_state.agents['profiler']
            suggestions = profiler.suggest_questions(st.session_state.df)
            
            st.write("**Suggested Questions:**")
            cols = st.columns(2)
            for i, suggestion in enumerate(suggestions[:6]):
                with cols[i % 2]:
                    if st.button(suggestion, key=f"suggestion_{i}", use_container_width=True):
                        st.session_state.pending_question = suggestion
                        st.rerun()
        
        st.divider()
        
        question = st.text_input(
            "Your Question:",
            placeholder="e.g., Show me the first 10 rows",
            key="question_input",
            value=st.session_state.get('pending_question', '')
        )
        
        if 'pending_question' in st.session_state:
            del st.session_state.pending_question
        
        col1, col2 = st.columns([3, 1])
        with col1:
            analyze_button = st.button("🚀 Analyze", type="primary", use_container_width=True)
        with col2:
            clear_button = st.button("🗑️ Clear History", use_container_width=True)
        
        if clear_button:
            st.session_state.chat_history = []
            st.rerun()
        
        if analyze_button and question:
            with st.spinner("🤖 AI agents are working..."):
                try:
                    orchestrator = st.session_state.agents['orchestrator']
                    analyst = st.session_state.agents['analyst']
                    visualizer = st.session_state.agents['visualizer']
                    insights_agent = st.session_state.agents['insights']
                    
                    plan = orchestrator.plan_execution(question, st.session_state.profile['raw_info'])
                    agents_to_use = plan['plan'].get('agents', ['analyst'])
                    
                    result_container = {
                        'question': question,
                        'analysis': None,
                        'visualization': None,
                        'insights': None
                    }
                    
                    if 'analyst' in agents_to_use or 'data_profiler' not in agents_to_use:
                        analysis_result = analyst.analyze(st.session_state.df, question)
                        result_container['analysis'] = analysis_result
                    
                    if 'visualizer' in agents_to_use:
                        viz_result = visualizer.create_visualization(
                            st.session_state.df,
                            question,
                            result_container['analysis'].get('result') if result_container['analysis'] else None
                        )
                        result_container['visualization'] = viz_result
                    
                    if 'insights' in agents_to_use:
                        insights_result = insights_agent.generate_insights(
                            st.session_state.df,
                            question,
                            result_container['analysis'].get('result') if result_container['analysis'] else None
                        )
                        result_container['insights'] = insights_result
                    
                    st.session_state.chat_history.append(result_container)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    with st.expander("🐛 Debug Info"):
                        st.code(traceback.format_exc())
        
        if st.session_state.chat_history:
            st.divider()
            st.subheader("📝 Analysis Results")
            
            for i, result in enumerate(reversed(st.session_state.chat_history)):
                with st.expander(f"❓ {result['question']}", expanded=(i == 0)):
                    
                    if result.get('analysis'):
                        analysis = result['analysis']
                        if analysis.get('success'):
                            st.success("✅ Analysis Complete")
                            
                            st.markdown("**📊 Result:**")
                            if isinstance(analysis.get('result'), pd.DataFrame):
                                st.dataframe(analysis['result'], use_container_width=True)
                            elif isinstance(analysis.get('result'), pd.Series):
                                st.dataframe(analysis['result'].to_frame(), use_container_width=True)
                            else:
                                st.write(analysis.get('result'))
                            
                            if analysis.get('code'):
                                st.divider()
                                show_code = st.checkbox("📝 Show Generated Code", key=f"code_{i}")
                                if show_code:
                                    st.code(analysis['code'], language='python')
                        else:
                            st.error("❌ Analysis Failed")
                            if analysis.get('error'):
                                st.error(f"Error: {analysis['error']}")
                    
                    if result.get('visualization'):
                        viz = result['visualization']
                        if viz.get('success') and viz.get('figure'):
                            st.divider()
                            st.markdown("**📈 Visualization:**")
                            st.plotly_chart(viz['figure'], use_container_width=True)
                    
                    if result.get('insights'):
                        insights = result['insights']
                        if insights.get('success'):
                            st.divider()
                            st.markdown("**💡 Insights:**")
                            st.info(insights['insights'])
    
    with tab2:
        st.subheader("📊 Dataset Overview")
        
        if st.session_state.profile:
            profile = st.session_state.profile
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Rows", f"{profile['basic_info']['rows']:,}")
            with col2:
                st.metric("Total Columns", profile['basic_info']['columns'])
            with col3:
                st.metric("Memory Usage", f"{profile['basic_info']['memory_mb']:.2f} MB")
            with col4:
                quality = st.session_state.agents['profiler'].get_data_quality_report(st.session_state.df)
                st.metric("Data Quality", f"{quality['completeness_score']:.1f}%")
            
            st.divider()
            st.subheader("📋 Column Information")
            
            col_info = []
            for col in st.session_state.df.columns:
                col_info.append({
                    "Column": col,
                    "Type": str(st.session_state.df[col].dtype),
                    "Non-Null": f"{st.session_state.df[col].count():,}",
                    "Missing": f"{st.session_state.df[col].isnull().sum():,}",
                    "Unique": f"{st.session_state.df[col].nunique():,}"
                })
            
            st.dataframe(pd.DataFrame(col_info), use_container_width=True)
            
            st.divider()
            st.subheader("👀 Data Preview")
            st.dataframe(st.session_state.df.head(10), use_container_width=True)
            
            st.subheader("📈 Summary Statistics")
            numeric_df = st.session_state.df.select_dtypes(include=['number'])
            if not numeric_df.empty:
                st.dataframe(numeric_df.describe(), use_container_width=True)
    
    with tab3:
        st.subheader("🔍 Automatically Discovered Insights")
        
        if st.button("🔍 Discover Patterns", type="primary", use_container_width=True):
            with st.spinner("🤖 Analyzing data for patterns..."):
                try:
                    insights_agent = st.session_state.agents['insights']
                    patterns = insights_agent.auto_discover_patterns(st.session_state.df)
                    
                    if patterns:
                        summary = insights_agent.summarize_patterns(patterns)
                        st.markdown(summary)
                        
                        st.divider()
                        for idx, pattern in enumerate(patterns):
                            with st.expander(f"Pattern {idx + 1}: {pattern['type'].upper()}", expanded=False):
                                st.json(pattern['details'])
                    else:
                        st.info("ℹ️ No significant patterns detected.")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("🤖 Powered by LangGraph & Groq")
with col2:
    st.caption("💡 AI Data Analyst Agent")
with col3:
    st.caption("🎓 College Project")