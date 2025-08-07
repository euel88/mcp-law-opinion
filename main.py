"""
K-Law Assistant - 통합 법률 검토 지원 시스템
Main Application with Streamlit UI
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
from enum import Enum

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Custom modules
from common_api import LawAPIClient, OpenAIHelper
from legal_prompts_module import PromptBuilder, ServiceType, detect_service_type
from law_module import LawSearcher
from committee_module import CommitteeDecisionSearcher
from case_module import CaseSearcher
from treaty_admin_module import TreatyAdminSearcher

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="K-Law Assistant",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================= Query Type Detection =========================

class QueryType(Enum):
    """질문 유형 분류"""
    SIMPLE_SEARCH = "simple_search"  # 단순 검색 (법령/판례/해석 등)
    AI_ANALYSIS = "ai_analysis"      # AI 분석 필요
    CONTRACT_REVIEW = "contract_review"  # 계약서 검토
    LEGAL_OPINION = "legal_opinion"    # 법률자문의견서

def detect_query_type(query: str) -> Tuple[QueryType, str]:
    """
    사용자 질문 유형을 자동으로 판별
    
    Returns:
        (QueryType, reason): 질문 유형과 판별 이유
    """
    query_lower = query.lower()
    
    # 단순 검색 키워드
    search_keywords = [
        '검색', '찾아', '조회', '알려', '법령', '판례', '조문', '제.*조',
        '법률', '시행령', '시행규칙', '고시', '훈령', '예규', '조례',
        '대법원', '헌재', '헌법재판소', '행정심판', '위원회'
    ]
    
    # AI 분석 키워드
    ai_keywords = [
        '분석', '검토', '해석', '의미', '적용', '해당', '가능',
        '어떻게', '왜', '설명', '비교', '차이', '유리', '불리',
        '위험', '리스크', '대응', '전략', '조언', '추천'
    ]
    
    # 계약서 검토 키워드
    contract_keywords = [
        '계약서', '계약 검토', '독소조항', '불공정', '조항',
        '계약 위험', '수정', '협상'
    ]
    
    # 법률자문 키워드
    opinion_keywords = [
        '자문', '의견서', '법률자문', '법적 검토', '소송',
        '분쟁', '대응방안', '법적 조치'
    ]
    
    # 우선순위에 따른 판별
    if any(kw in query_lower for kw in contract_keywords):
        return QueryType.CONTRACT_REVIEW, "계약서 관련 키워드 감지"
    
    if any(kw in query_lower for kw in opinion_keywords):
        return QueryType.LEGAL_OPINION, "법률자문 관련 키워드 감지"
    
    # 검색 키워드가 많고 AI 키워드가 적으면 단순 검색
    search_count = sum(1 for kw in search_keywords if kw in query_lower)
    ai_count = sum(1 for kw in ai_keywords if kw in query_lower)
    
    if search_count > ai_count and search_count > 0:
        return QueryType.SIMPLE_SEARCH, f"검색 키워드 {search_count}개 감지"
    
    # 기본값: AI 분석
    return QueryType.AI_ANALYSIS, "AI 분석이 필요한 복잡한 질문"

# ========================= Session State Management =========================

def init_session_state():
    """Initialize session state variables"""
    if 'search_history' not in st.session_state:
        st.session_state.search_history = []
    
    if 'favorites' not in st.session_state:
        st.session_state.favorites = []
    
    if 'current_results' not in st.session_state:
        st.session_state.current_results = {}
    
    if 'api_keys' not in st.session_state:
        st.session_state.api_keys = {
            'law_api_key': os.getenv('LAW_API_KEY', ''),
            'openai_api_key': os.getenv('OPENAI_API_KEY', '')
        }
    
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = 'gpt-4o-mini'
    
    if 'cache' not in st.session_state:
        st.session_state.cache = {}

# ========================= API Clients Initialization =========================

@st.cache_resource
def get_api_clients():
    """Initialize and cache API clients"""
    law_api_key = st.session_state.api_keys['law_api_key']
    openai_api_key = st.session_state.api_keys['openai_api_key']
    
    law_client = LawAPIClient(oc_key=law_api_key) if law_api_key else None
    ai_helper = OpenAIHelper(api_key=openai_api_key) if openai_api_key else None
    
    return {
        'law_client': law_client,
        'ai_helper': ai_helper,
        'law_searcher': LawSearcher(api_client=law_client) if law_client else None,
        'committee_searcher': CommitteeDecisionSearcher(api_client=law_client) if law_client else None,
        'case_searcher': CaseSearcher(api_client=law_client, ai_helper=ai_helper) if law_client else None,
        'treaty_searcher': TreatyAdminSearcher(oc_key=law_api_key) if law_api_key else None,
        'prompt_builder': PromptBuilder()
    }

# ========================= Search Functions =========================

def perform_simple_search(query: str, search_targets: List[str]) -> Dict[str, Any]:
    """
    단순 검색 수행 (AI 없이 직접 검색)
    """
    clients = get_api_clients()
    results = {
        'query': query,
        'timestamp': datetime.now().isoformat(),
        'results': {}
    }
    
    with st.spinner('검색 중...'):
        # 법령 검색
        if '법령' in search_targets and clients['law_searcher']:
            try:
                law_results = clients['law_searcher'].search_laws(query, display=10)
                if law_results and 'results' in law_results:
                    results['results']['laws'] = law_results['results']
            except Exception as e:
                st.error(f"법령 검색 오류: {str(e)}")
        
        # 판례 검색
        if '판례' in search_targets and clients['case_searcher']:
            try:
                case_results = clients['case_searcher'].search_court_cases(query, display=10)
                if case_results.get('status') == 'success':
                    results['results']['cases'] = case_results.get('cases', [])
            except Exception as e:
                st.error(f"판례 검색 오류: {str(e)}")
        
        # 헌재결정례 검색
        if '헌재결정' in search_targets and clients['case_searcher']:
            try:
                const_results = clients['case_searcher'].search_constitutional_decisions(query, display=10)
                if const_results.get('status') == 'success':
                    results['results']['constitutional'] = const_results.get('decisions', [])
            except Exception as e:
                st.error(f"헌재결정례 검색 오류: {str(e)}")
        
        # 법령해석례 검색
        if '법령해석' in search_targets and clients['case_searcher']:
            try:
                interp_results = clients['case_searcher'].search_legal_interpretations(query, display=10)
                if interp_results.get('status') == 'success':
                    results['results']['interpretations'] = interp_results.get('interpretations', [])
            except Exception as e:
                st.error(f"법령해석례 검색 오류: {str(e)}")
        
        # 행정규칙 검색
        if '행정규칙' in search_targets and clients['treaty_searcher']:
            try:
                admin_results = clients['treaty_searcher'].search_admin_rules(query, display=10)
                if 'error' not in admin_results:
                    results['results']['admin_rules'] = admin_results.get('rules', [])
            except Exception as e:
                st.error(f"행정규칙 검색 오류: {str(e)}")
    
    return results

def perform_ai_analysis(query: str, context: Dict[str, Any], service_type: ServiceType) -> str:
    """
    AI 분석 수행
    """
    clients = get_api_clients()
    
    if not clients['ai_helper'] or not clients['ai_helper'].enabled:
        return "⚠️ OpenAI API가 설정되지 않았습니다. 사이드바에서 API 키를 입력해주세요."
    
    # 프롬프트 생성
    system_prompt, user_prompt = clients['prompt_builder'].build_prompt(
        service_type=service_type,
        query=query,
        context=context
    )
    
    # OpenAI API 호출 (선택된 모델 사용)
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=st.session_state.api_keys['openai_api_key'])
        
        response = client.chat.completions.create(
            model=st.session_state.selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=3000
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"AI 분석 오류: {str(e)}")
        return f"⚠️ AI 분석 중 오류가 발생했습니다: {str(e)}"

# ========================= UI Components =========================

def render_sidebar():
    """Render sidebar with settings and options"""
    with st.sidebar:
        st.title("⚖️ K-Law Assistant")
        st.markdown("---")
        
        # API 설정
        with st.expander("🔑 API 설정", expanded=False):
            law_api_key = st.text_input(
                "법제처 API Key",
                value=st.session_state.api_keys['law_api_key'],
                type="password",
                help="https://open.law.go.kr 에서 발급"
            )
            
            openai_api_key = st.text_input(
                "OpenAI API Key",
                value=st.session_state.api_keys['openai_api_key'],
                type="password",
                help="https://platform.openai.com 에서 발급"
            )
            
            if st.button("API 키 저장"):
                st.session_state.api_keys['law_api_key'] = law_api_key
                st.session_state.api_keys['openai_api_key'] = openai_api_key
                st.success("API 키가 저장되었습니다!")
                st.rerun()
        
        # GPT 모델 선택
        st.markdown("### 🤖 AI 모델 선택")
        models = {
            'gpt-4o': 'GPT-4o (최신, 고성능)',
            'gpt-4o-mini': 'GPT-4o Mini (빠름, 경제적)',
            'gpt-4-turbo': 'GPT-4 Turbo',
            'gpt-3.5-turbo': 'GPT-3.5 Turbo (기본)'
        }
        
        selected_model = st.selectbox(
            "모델 선택",
            options=list(models.keys()),
            format_func=lambda x: models[x],
            index=list(models.keys()).index(st.session_state.selected_model),
            help="복잡한 법률 분석은 GPT-4o를 추천합니다"
        )
        st.session_state.selected_model = selected_model
        
        # 검색 대상 선택
        st.markdown("### 🔍 검색 대상")
        search_targets = st.multiselect(
            "검색할 자료 유형",
            ['법령', '판례', '헌재결정', '법령해석', '행정규칙', '자치법규', '위원회결정'],
            default=['법령', '판례']
        )
        st.session_state.search_targets = search_targets
        
        # 빠른 검색
        st.markdown("### 🚀 빠른 검색")
        quick_searches = {
            "도로교통법 음주운전": "도로교통법 음주운전",
            "개인정보보호법": "개인정보보호법",
            "부동산 계약": "부동산 매매계약",
            "근로기준법 연차": "근로기준법 연차휴가"
        }
        
        for label, query in quick_searches.items():
            if st.button(label, key=f"quick_{label}", use_container_width=True):
                st.session_state.quick_search = query
        
        # 검색 이력
        st.markdown("### 📜 최근 검색")
        if st.session_state.search_history:
            for idx, item in enumerate(st.session_state.search_history[-5:][::-1]):
                if st.button(
                    f"🕐 {item['query'][:30]}...",
                    key=f"history_{idx}",
                    use_container_width=True
                ):
                    st.session_state.history_search = item['query']

def render_search_results(results: Dict[str, Any]):
    """검색 결과를 표시"""
    
    if not results.get('results'):
        st.info("검색 결과가 없습니다.")
        return
    
    # 결과 요약
    total_count = sum(
        len(items) if isinstance(items, list) else 0
        for items in results['results'].values()
    )
    
    st.success(f"✅ 총 {total_count}개의 결과를 찾았습니다.")
    
    # 각 유형별 결과 표시
    for result_type, items in results['results'].items():
        if items:
            with st.expander(f"📚 {get_result_type_label(result_type)} ({len(items)}건)", expanded=True):
                for idx, item in enumerate(items[:5], 1):
                    display_search_item(result_type, item, idx)
                
                if len(items) > 5:
                    st.info(f"... 외 {len(items) - 5}건 더 있습니다.")

def get_result_type_label(result_type: str) -> str:
    """결과 유형에 대한 한글 레이블 반환"""
    labels = {
        'laws': '법령',
        'cases': '판례',
        'constitutional': '헌재결정례',
        'interpretations': '법령해석례',
        'admin_rules': '행정규칙',
        'committees': '위원회결정',
        'tribunals': '행정심판례'
    }
    return labels.get(result_type, result_type)

def display_search_item(result_type: str, item: Dict, idx: int):
    """개별 검색 결과 항목 표시"""
    if result_type == 'laws':
        st.markdown(f"""
        **{idx}. {item.get('법령명한글', 'N/A')}**
        - 공포일자: {item.get('공포일자', 'N/A')}
        - 시행일자: {item.get('시행일자', 'N/A')}
        - 소관부처: {item.get('소관부처명', 'N/A')}
        """)
    
    elif result_type == 'cases':
        st.markdown(f"""
        **{idx}. {item.get('title', item.get('사건명', 'N/A'))}**
        - 법원: {item.get('court', item.get('법원명', 'N/A'))}
        - 사건번호: {item.get('case_number', item.get('사건번호', 'N/A'))}
        - 선고일자: {item.get('date', item.get('선고일자', 'N/A'))}
        """)
    
    elif result_type == 'constitutional':
        st.markdown(f"""
        **{idx}. {item.get('title', item.get('사건명', 'N/A'))}**
        - 사건번호: {item.get('case_number', item.get('사건번호', 'N/A'))}
        - 종국일자: {item.get('date', item.get('종국일자', 'N/A'))}
        """)
    
    elif result_type == 'interpretations':
        st.markdown(f"""
        **{idx}. {item.get('title', item.get('안건명', 'N/A'))}**
        - 해석기관: {item.get('responding_agency', item.get('해석기관명', 'N/A'))}
        - 안건번호: {item.get('case_number', item.get('안건번호', 'N/A'))}
        - 회신일자: {item.get('date', item.get('회신일자', 'N/A'))}
        """)
    
    else:
        # 기본 표시
        st.markdown(f"**{idx}. {item.get('title', item.get('제목', str(item)[:100]))}**")

# ========================= Main Application =========================

def main():
    """Main application"""
    init_session_state()
    render_sidebar()
    
    st.title("⚖️ K-Law Assistant - AI 법률 검토 지원 시스템")
    st.markdown("법령, 판례, 행정규칙 등을 종합 검토하여 AI가 법률 자문을 제공합니다.")
    
    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 통합 검색", "🤖 AI 법률 분석", "📊 검색 이력", "ℹ️ 사용 가이드"])
    
    # Tab 1: 통합 검색
    with tab1:
        st.header("통합 법률자료 검색")
        
        # 검색 입력
        col1, col2 = st.columns([5, 1])
        with col1:
            search_query = st.text_input(
                "검색어를 입력하세요",
                placeholder="예: 도로교통법 음주운전, 개인정보보호법, 근로계약서",
                value=st.session_state.get('quick_search', '') or st.session_state.get('history_search', '')
            )
        
        with col2:
            search_button = st.button("🔍 검색", type="primary", use_container_width=True)
        
        # 질문 유형 자동 판별
        if search_query and search_button:
            query_type, reason = detect_query_type(search_query)
            
            # 질문 유형 표시
            col1, col2 = st.columns([1, 3])
            with col1:
                if query_type == QueryType.SIMPLE_SEARCH:
                    st.info(f"📋 단순 검색\n{reason}")
                else:
                    st.warning(f"🤖 AI 분석 필요\n{reason}")
            
            with col2:
                if query_type == QueryType.SIMPLE_SEARCH:
                    # 단순 검색 수행
                    results = perform_simple_search(
                        search_query,
                        st.session_state.get('search_targets', ['법령', '판례'])
                    )
                    
                    # 결과 저장
                    st.session_state.current_results = results
                    
                    # 검색 이력 추가
                    st.session_state.search_history.append({
                        'query': search_query,
                        'timestamp': datetime.now().isoformat(),
                        'type': 'simple_search',
                        'results_count': sum(len(v) for v in results['results'].values() if isinstance(v, list))
                    })
                    
                    # 결과 표시
                    render_search_results(results)
                    
                else:
                    st.info("🤖 AI 분석이 필요한 질문입니다. 'AI 법률 분석' 탭으로 이동해주세요.")
                    if st.button("AI 분석 탭으로 이동"):
                        st.session_state.ai_query = search_query
                        st.rerun()
        
        # 빠른 검색 초기화
        if 'quick_search' in st.session_state:
            del st.session_state.quick_search
        if 'history_search' in st.session_state:
            del st.session_state.history_search
    
    # Tab 2: AI 법률 분석
    with tab2:
        st.header("AI 법률 분석 및 자문")
        
        # 서비스 유형 선택
        service_type = st.selectbox(
            "서비스 유형",
            options=[
                ServiceType.LEGAL_INFO,
                ServiceType.CONTRACT_REVIEW,
                ServiceType.LEGAL_OPINION
            ],
            format_func=lambda x: {
                ServiceType.LEGAL_INFO: "법률 정보 제공",
                ServiceType.CONTRACT_REVIEW: "계약서 검토",
                ServiceType.LEGAL_OPINION: "법률자문의견서"
            }[x]
        )
        
        # 질문 입력
        ai_query = st.text_area(
            "질문 또는 검토 요청사항",
            placeholder="법률 관련 질문을 자세히 입력해주세요...",
            value=st.session_state.get('ai_query', ''),
            height=150
        )
        
        # 계약서 검토인 경우 추가 입력
        if service_type == ServiceType.CONTRACT_REVIEW:
            contract_text = st.text_area(
                "계약서 내용",
                placeholder="검토할 계약서 내용을 붙여넣으세요...",
                height=300
            )
        
        # 법률자문의견서인 경우 추가 입력
        if service_type == ServiceType.LEGAL_OPINION:
            facts = st.text_area(
                "사실관계",
                placeholder="관련 사실관계를 상세히 기술해주세요...",
                height=200
            )
        
        # AI 분석 실행
        if st.button("🤖 AI 분석 시작", type="primary"):
            if not ai_query:
                st.error("질문을 입력해주세요.")
            else:
                with st.spinner("AI가 관련 자료를 검색하고 분석 중입니다..."):
                    # 1. 관련 자료 검색
                    search_results = perform_simple_search(
                        ai_query,
                        ['법령', '판례', '법령해석', '행정규칙']
                    )
                    
                    # 2. AI 분석
                    if service_type == ServiceType.CONTRACT_REVIEW:
                        analysis = perform_ai_analysis(
                            contract_text if 'contract_text' in locals() else ai_query,
                            search_results['results'],
                            service_type
                        )
                    elif service_type == ServiceType.LEGAL_OPINION:
                        analysis = perform_ai_analysis(
                            ai_query,
                            {**search_results['results'], 'facts': facts if 'facts' in locals() else ''},
                            service_type
                        )
                    else:
                        analysis = perform_ai_analysis(
                            ai_query,
                            search_results['results'],
                            service_type
                        )
                    
                    # 3. 결과 표시
                    st.markdown("### 📋 AI 분석 결과")
                    st.markdown(analysis)
                    
                    # 4. 참고 자료 표시
                    with st.expander("📚 참고 법률자료", expanded=False):
                        render_search_results(search_results)
                    
                    # 5. 이력 저장
                    st.session_state.search_history.append({
                        'query': ai_query,
                        'timestamp': datetime.now().isoformat(),
                        'type': 'ai_analysis',
                        'service_type': service_type.value
                    })
        
        # AI 질문 초기화
        if 'ai_query' in st.session_state:
            del st.session_state.ai_query
    
    # Tab 3: 검색 이력
    with tab3:
        st.header("검색 이력 관리")
        
        if st.session_state.search_history:
            # 이력을 DataFrame으로 변환
            history_df = pd.DataFrame(st.session_state.search_history)
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
            history_df = history_df.sort_values('timestamp', ascending=False)
            
            # 필터링 옵션
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_type = st.selectbox(
                    "검색 유형",
                    ["전체", "단순 검색", "AI 분석"],
                    key="filter_type"
                )
            
            with col2:
                date_range = st.date_input(
                    "기간",
                    value=(datetime.now() - timedelta(days=7), datetime.now()),
                    key="date_range"
                )
            
            with col3:
                if st.button("🗑️ 이력 삭제", use_container_width=True):
                    st.session_state.search_history = []
                    st.rerun()
            
            # 필터링 적용
            if filter_type == "단순 검색":
                history_df = history_df[history_df['type'] == 'simple_search']
            elif filter_type == "AI 분석":
                history_df = history_df[history_df['type'] == 'ai_analysis']
            
            # 이력 표시
            st.dataframe(
                history_df[['timestamp', 'query', 'type']].head(20),
                use_container_width=True,
                hide_index=True
            )
            
            # 이력 상세 보기
            if len(history_df) > 0:
                st.markdown("### 상세 보기")
                selected_idx = st.selectbox(
                    "검색 이력 선택",
                    range(len(history_df)),
                    format_func=lambda x: f"{history_df.iloc[x]['timestamp'].strftime('%Y-%m-%d %H:%M')} - {history_df.iloc[x]['query'][:50]}"
                )
                
                if selected_idx is not None:
                    selected = history_df.iloc[selected_idx]
                    st.json(selected.to_dict())
        else:
            st.info("검색 이력이 없습니다.")
    
    # Tab 4: 사용 가이드
    with tab4:
        st.header("사용 가이드")
        
        st.markdown("""
        ### 🎯 주요 기능
        
        1. **통합 검색**: 법령, 판례, 헌재결정례, 법령해석례 등을 한 번에 검색
        2. **AI 법률 분석**: GPT를 활용한 심층적인 법률 분석 및 자문
        3. **계약서 검토**: 독소조항 발견 및 수정 제안
        4. **법률자문의견서**: 전문적인 법률 의견서 작성
        
        ### 💡 사용 팁
        
        - **단순 검색 vs AI 분석**: 시스템이 자동으로 질문 유형을 판별합니다
        - **모델 선택**: 복잡한 법률 문제는 GPT-4o를 사용하세요
        - **검색 대상**: 사이드바에서 검색할 자료 유형을 선택할 수 있습니다
        - **빠른 검색**: 자주 사용하는 검색어를 사이드바에서 클릭하세요
        
        ### 🔑 API 키 설정
        
        1. **법제처 API 키**: https://open.law.go.kr 에서 무료 발급
        2. **OpenAI API 키**: https://platform.openai.com 에서 발급
        
        ### ⚖️ 면책 고지
        
        본 시스템은 AI가 작성한 참고자료를 제공하며, 법률자문이 아닙니다.
        구체적인 사안에 대해서는 반드시 변호사 등 전문가의 검토가 필요합니다.
        """)
        
        # 시스템 정보
        with st.expander("시스템 정보"):
            st.json({
                "version": "1.0.0",
                "last_updated": "2025-01-01",
                "models_available": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
                "search_targets": ["법령", "판례", "헌재결정례", "법령해석례", "행정규칙", "자치법규", "위원회결정"],
                "api_status": {
                    "law_api": "✅" if st.session_state.api_keys['law_api_key'] else "❌",
                    "openai_api": "✅" if st.session_state.api_keys['openai_api_key'] else "❌"
                }
            })

if __name__ == "__main__":
    main()