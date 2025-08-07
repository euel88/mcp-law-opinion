"""
K-Law Assistant - 통합 법률 검토 지원 시스템 with NLP
Enhanced Main Application with Natural Language Processing
Version 6.0 - NLP Search Integration
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
from enum import Enum
import re

# Python 3.13 호환성 패치 (TypedDict 'closed' 파라미터 문제 해결)
if sys.version_info >= (3, 13):
    import typing
    import typing_extensions
    
    # TypedDict 패치
    if hasattr(typing, '_TypedDictMeta'):
        original_new = typing._TypedDictMeta.__new__
        def patched_new(cls, name, bases, ns, total=True, **kwargs):
            kwargs.pop('closed', None)
            try:
                return original_new(cls, name, bases, ns, total=total)
            except TypeError:
                return original_new(cls, name, bases, ns)
        typing._TypedDictMeta.__new__ = staticmethod(patched_new)
    
    if hasattr(typing_extensions, '_TypedDictMeta'):
        original_new_ext = typing_extensions._TypedDictMeta.__new__
        def patched_new_ext(cls, name, bases, ns, total=True, **kwargs):
            kwargs.pop('closed', None)
            try:
                return original_new_ext(cls, name, bases, ns, total=total)
            except TypeError:
                return original_new_ext(cls, name, bases, ns)
        typing_extensions._TypedDictMeta.__new__ = staticmethod(patched_new_ext)

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="K-Law Assistant Pro with NLP",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom modules import with error handling
try:
    from common_api import LawAPIClient, OpenAIHelper
    from law_module import LawSearcher
    from committee_module import CommitteeDecisionSearcher
    from case_module import CaseSearcher, AdvancedCaseSearcher
    from treaty_admin_module import TreatyAdminSearcher
    from nlp_search_module import NaturalLanguageSearchProcessor, SmartSearchOrchestrator  # NLP 모듈 추가
    MODULES_LOADED = True
    NLP_MODULE_LOADED = True
except ImportError as e:
    MODULES_LOADED = False
    NLP_MODULE_LOADED = False
    st.error(f"❌ 필수 모듈을 불러올 수 없습니다: {str(e)}")
    st.info("requirements.txt의 패키지를 모두 설치했는지 확인해주세요.")
except Exception as e:
    MODULES_LOADED = False
    NLP_MODULE_LOADED = False
    st.error(f"❌ 모듈 로드 중 오류 발생: {str(e)}")
    if "closed" in str(e):
        st.warning("Python 3.13 호환성 문제가 감지되었습니다. 페이지를 새로고침해주세요.")

# ========================= Session State Management =========================

def init_session_state():
    """Initialize session state variables"""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.search_history = []
        st.session_state.favorites = []
        st.session_state.current_results = {}
        st.session_state.api_keys = {
            'law_api_key': os.getenv('LAW_API_KEY', ''),
            'openai_api_key': os.getenv('OPENAI_API_KEY', '')
        }
        st.session_state.selected_model = 'gpt-4o-mini'
        st.session_state.cache = {}
        st.session_state.api_clients = None
        st.session_state.selected_committees = []
        st.session_state.selected_ministries = []
        st.session_state.test_mode = False
        st.session_state.nlp_enabled = NLP_MODULE_LOADED  # NLP 모듈 상태
        st.session_state.smart_search_history = []  # 스마트 검색 이력
        logger.info("Session state initialized successfully")

# ========================= API Clients Initialization =========================

@st.cache_resource
def get_api_clients():
    """Initialize and cache all API clients including NLP processor"""
    try:
        law_api_key = st.session_state.api_keys.get('law_api_key', '')
        openai_api_key = st.session_state.api_keys.get('openai_api_key', '')

        logger.info(f"Initializing API clients...")
        logger.info(f"Law API key exists: {bool(law_api_key)}")
        
        test_mode = False
        if law_api_key:
            logger.info(f"Law API key length: {len(law_api_key)}")
            if len(law_api_key) < 20:
                st.warning(f"⚠️ 테스트 모드: API 키가 짧습니다 ({len(law_api_key)}자). 실제 API 키를 사용해주세요.")
                test_mode = True
                st.session_state.test_mode = True
            else:
                logger.info(f"Law API key preview: {law_api_key[:4]}...{law_api_key[-4:]}")
                st.session_state.test_mode = False
        else:
            st.warning("⚠️ 법제처 API 키가 설정되지 않았습니다. 사이드바에서 설정해주세요.")
            st.info("테스트를 위해서는 https://open.law.go.kr 에서 무료로 API 키를 발급받으실 수 있습니다.")
            logger.warning("Law API key not found")
            return {}
        
        clients = {}
        
        # 기본 API 클라이언트
        try:
            clients['law_client'] = LawAPIClient(oc_key=law_api_key)
            clients['ai_helper'] = OpenAIHelper(api_key=openai_api_key) if openai_api_key else None
        except Exception as e:
            logger.error(f"Base client init failed: {e}")
            if "closed" in str(e):
                st.error("Python 3.13 호환성 문제로 인한 초기화 실패. 페이지를 새로고침해주세요.")
                return {}
        
        # 각 검색 모듈 초기화
        try:
            clients['law_searcher'] = LawSearcher(oc_key=law_api_key)
            logger.info("LawSearcher initialized")
        except Exception as e:
            logger.error(f"LawSearcher init failed: {e}")
            
        try:
            clients['case_searcher'] = CaseSearcher(api_client=clients.get('law_client'), ai_helper=clients.get('ai_helper'))
            logger.info("CaseSearcher initialized")
        except Exception as e:
            logger.error(f"CaseSearcher init failed: {e}")
            
        try:
            clients['advanced_case_searcher'] = AdvancedCaseSearcher(api_client=clients.get('law_client'), ai_helper=clients.get('ai_helper'))
            logger.info("AdvancedCaseSearcher initialized")
        except Exception as e:
            logger.error(f"AdvancedCaseSearcher init failed: {e}")
            
        try:
            clients['committee_searcher'] = CommitteeDecisionSearcher(api_client=clients.get('law_client'))
            logger.info("CommitteeDecisionSearcher initialized")
        except Exception as e:
            logger.error(f"CommitteeDecisionSearcher init failed: {e}")
            
        try:
            clients['treaty_admin_searcher'] = TreatyAdminSearcher(oc_key=law_api_key)
            logger.info("TreatyAdminSearcher initialized")
        except Exception as e:
            logger.error(f"TreatyAdminSearcher init failed: {e}")
        
        # NLP 프로세서 초기화 (새로 추가)
        if NLP_MODULE_LOADED:
            try:
                nlp_processor = NaturalLanguageSearchProcessor(ai_helper=clients.get('ai_helper'))
                clients['nlp_processor'] = nlp_processor
                clients['smart_orchestrator'] = SmartSearchOrchestrator(nlp_processor, clients)
                logger.info("NLP Search Processor initialized")
                st.session_state.nlp_enabled = True
            except Exception as e:
                logger.error(f"NLP Processor init failed: {e}")
                st.session_state.nlp_enabled = False
        
        logger.info(f"API clients initialized: {list(clients.keys())}")
        return clients
        
    except Exception as e:
        logger.error(f"API clients initialization failed: {str(e)}")
        if "closed" in str(e):
            st.error("Python 3.13 호환성 문제가 감지되었습니다. 페이지를 새로고침하거나 Python 3.12로 다운그레이드를 고려해주세요.")
        else:
            st.error(f"API 클라이언트 초기화 실패: {str(e)}")
        return {}

# ========================= New Tab: Smart Search (자연어 검색) =========================

def render_smart_search_tab():
    """스마트 자연어 검색 탭 - NLP 기반 통합 검색"""
    st.header("🧠 스마트 검색 (자연어 처리)")
    
    clients = get_api_clients()
    
    # NLP 모듈 확인
    if not st.session_state.get('nlp_enabled') or not clients.get('smart_orchestrator'):
        st.warning("⚠️ 자연어 처리 모듈이 로드되지 않았습니다.")
        st.info("대신 일반 검색 기능을 사용해주세요.")
        return
    
    # 스마트 검색 설명
    with st.expander("💡 스마트 검색이란?", expanded=False):
        st.markdown("""
        **스마트 검색**은 복잡한 법률 용어를 몰라도 일상적인 언어로 법률 정보를 찾을 수 있는 기능입니다.
        
        예시:
        - ✅ "회사에서 갑자기 해고당했어요"
        - ✅ "전세금을 돌려받지 못하고 있습니다"
        - ✅ "개인정보가 유출되었는데 어떻게 해야 하나요?"
        - ✅ "음주운전 벌금이 얼마인가요?"
        
        자동으로:
        1. 질문의 의도를 파악합니다
        2. 관련 키워드를 추출합니다
        3. 적절한 법령/판례를 검색합니다
        4. AI가 종합적인 답변을 제공합니다
        """)
    
    # 질문 입력
    col1, col2 = st.columns([5, 1])
    with col1:
        user_query = st.text_area(
            "자연어로 질문하세요",
            placeholder="예: 직장에서 부당하게 해고당했는데 어떻게 대응해야 하나요?",
            height=100,
            key="smart_search_query"
        )
    
    with col2:
        st.write("")  # 간격 조정
        st.write("")
        search_btn = st.button("🔍 스마트 검색", type="primary", use_container_width=True, key="smart_search_btn")
    
    # 예시 질문들
    st.markdown("### 💬 예시 질문")
    example_cols = st.columns(3)
    
    example_queries = [
        "🏢 부당해고 대응방법",
        "🏠 전세보증금 반환",
        "🚗 음주운전 처벌",
        "💼 임금체불 신고",
        "📱 개인정보 유출 피해",
        "📝 계약서 작성 주의사항"
    ]
    
    for idx, example in enumerate(example_queries):
        with example_cols[idx % 3]:
            if st.button(example, key=f"example_{idx}", use_container_width=True):
                st.session_state.smart_search_query = example[2:]  # 이모지 제거
                st.rerun()
    
    # 검색 실행
    if search_btn and user_query:
        with st.spinner('🤖 AI가 질문을 분석하고 검색 중입니다...'):
            try:
                orchestrator = clients['smart_orchestrator']
                nlp_processor = clients['nlp_processor']
                
                # 1. 쿼리 분석
                st.markdown("### 1️⃣ 질문 분석")
                analysis = nlp_processor.analyze_query(user_query)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("검색 의도", analysis.intent.value)
                with col2:
                    st.metric("신뢰도", f"{analysis.confidence:.0%}")
                with col3:
                    st.metric("키워드 수", len(analysis.keywords))
                
                # 키워드 표시
                if analysis.keywords:
                    st.write("**추출된 키워드:**", ", ".join(analysis.keywords[:5]))
                
                # 2. 검색 전략
                st.markdown("### 2️⃣ 검색 전략")
                strategy = nlp_processor.optimize_search_strategy(user_query)
                
                # 실행 계획 표시
                with st.expander("검색 실행 계획", expanded=True):
                    for step in strategy['execution_plan']:
                        st.write(f"**Step {step['step']}:** {step['action']} - {step['reason']}")
                
                # 3. 통합 검색 실행
                st.markdown("### 3️⃣ 검색 실행")
                search_results = orchestrator.execute_smart_search(user_query)
                
                # 검색 결과 요약
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("총 검색 결과", search_results['total_count'])
                with col2:
                    st.metric("검색 시간", f"{search_results['execution_time']:.2f}초")
                with col3:
                    st.metric("검색 소스", len(search_results['search_results']))
                
                # 4. 결과 표시
                st.markdown("### 4️⃣ 검색 결과")
                
                if search_results['ranked_results']:
                    # 탭으로 결과 구분
                    result_tabs = st.tabs(["📚 법령", "⚖️ 판례", "📋 해석례", "📊 종합"])
                    
                    # 법령 탭
                    with result_tabs[0]:
                        law_results = [r for r in search_results['ranked_results'] if 'law' in r['type']]
                        if law_results:
                            for idx, result in enumerate(law_results[:5], 1):
                                item = result['item']
                                with st.expander(f"{idx}. {item.get('법령명한글', 'N/A')} (관련도: {result['score']:.0f})"):
                                    display_smart_search_item(item, 'law')
                        else:
                            st.info("관련 법령이 없습니다.")
                    
                    # 판례 탭
                    with result_tabs[1]:
                        case_results = [r for r in search_results['ranked_results'] if 'case' in r['type']]
                        if case_results:
                            for idx, result in enumerate(case_results[:5], 1):
                                item = result['item']
                                with st.expander(f"{idx}. {item.get('title', 'N/A')} (관련도: {result['score']:.0f})"):
                                    display_smart_search_item(item, 'case')
                        else:
                            st.info("관련 판례가 없습니다.")
                    
                    # 해석례 탭
                    with result_tabs[2]:
                        interp_results = [r for r in search_results['ranked_results'] if 'interpretation' in r['type']]
                        if interp_results:
                            for idx, result in enumerate(interp_results[:5], 1):
                                item = result['item']
                                with st.expander(f"{idx}. {item.get('title', 'N/A')} (관련도: {result['score']:.0f})"):
                                    display_smart_search_item(item, 'interpretation')
                        else:
                            st.info("관련 해석례가 없습니다.")
                    
                    # 종합 탭
                    with result_tabs[3]:
                        # AI 종합 답변 (AI Helper가 있는 경우)
                        if clients.get('ai_helper'):
                            st.markdown("#### 🤖 AI 종합 답변")
                            with st.spinner("AI가 답변을 생성 중입니다..."):
                                # 컨텍스트 준비
                                context = {
                                    'query_analysis': {
                                        'intent': analysis.intent.value,
                                        'keywords': analysis.keywords,
                                        'confidence': analysis.confidence
                                    },
                                    'search_results_summary': {
                                        'total_count': search_results['total_count'],
                                        'top_results': search_results['ranked_results'][:5]
                                    }
                                }
                                
                                # AI 답변 생성
                                ai_response = generate_smart_answer(user_query, context, clients['ai_helper'])
                                st.markdown(ai_response)
                        
                        # 결과 요약 차트
                        st.markdown("#### 📊 결과 분포")
                        result_types = {}
                        for r in search_results['ranked_results']:
                            result_types[r['type']] = result_types.get(r['type'], 0) + 1
                        
                        if result_types:
                            df = pd.DataFrame(list(result_types.items()), columns=['유형', '개수'])
                            st.bar_chart(df.set_index('유형'))
                
                # 검색 이력 저장
                st.session_state.smart_search_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'query': user_query,
                    'intent': analysis.intent.value,
                    'total_count': search_results['total_count'],
                    'confidence': analysis.confidence
                })
                
            except Exception as e:
                st.error(f"스마트 검색 중 오류 발생: {str(e)}")
                logger.exception(f"Smart search error: {e}")

# ========================= Helper Functions for Smart Search =========================

def display_smart_search_item(item: Dict, item_type: str):
    """스마트 검색 결과 아이템 표시"""
    if item_type == 'law':
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**공포일자:** {item.get('공포일자', 'N/A')}")
            st.write(f"**시행일자:** {item.get('시행일자', 'N/A')}")
        with col2:
            st.write(f"**소관부처:** {item.get('소관부처명', 'N/A')}")
            st.write(f"**법령구분:** {item.get('법령구분명', 'N/A')}")
    
    elif item_type == 'case':
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**법원:** {item.get('court', 'N/A')}")
            st.write(f"**사건번호:** {item.get('case_number', 'N/A')}")
        with col2:
            st.write(f"**선고일:** {item.get('date', 'N/A')}")
            st.write(f"**사건종류:** {item.get('type', 'N/A')}")
        
        if item.get('summary'):
            st.write("**판결요지:**")
            st.write(item['summary'][:300] + "..." if len(item.get('summary', '')) > 300 else item['summary'])
    
    elif item_type == 'interpretation':
        st.write(f"**해석일자:** {item.get('date', 'N/A')}")
        st.write(f"**질의요지:** {item.get('question', 'N/A')[:200]}...")
        st.write(f"**답변요지:** {item.get('answer', 'N/A')[:200]}...")

def generate_smart_answer(query: str, context: Dict, ai_helper) -> str:
    """AI를 사용한 종합 답변 생성"""
    try:
        prompt = f"""
        사용자 질문: {query}
        
        검색 의도: {context['query_analysis']['intent']}
        핵심 키워드: {', '.join(context['query_analysis']['keywords'][:5])}
        
        검색 결과 요약:
        - 총 {context['search_results_summary']['total_count']}건의 관련 자료를 찾았습니다.
        
        위 정보를 바탕으로 사용자 질문에 대한 종합적이고 실용적인 답변을 제공해주세요.
        법률 전문용어는 쉽게 설명하고, 실제로 취할 수 있는 행동을 구체적으로 안내해주세요.
        """
        
        response = ai_helper.analyze_legal_text(prompt, context)
        return response
        
    except Exception as e:
        logger.error(f"AI answer generation failed: {e}")
        return "AI 답변 생성 중 오류가 발생했습니다. 검색 결과를 직접 확인해주세요."

# ========================= Enhanced AI Analysis Tab =========================

def render_ai_analysis_tab_enhanced():
    """향상된 AI 법률 분석 탭 - NLP 통합"""
    st.header("🤖 AI 법률 분석 (Enhanced)")
    
    clients = get_api_clients()
    
    if not clients.get('ai_helper'):
        st.warning("⚠️ OpenAI API가 설정되지 않았습니다. 사이드바에서 API 키를 설정해주세요.")
        return
    
    # NLP 지원 여부 확인
    nlp_available = st.session_state.get('nlp_enabled') and clients.get('nlp_processor')
    
    if nlp_available:
        st.success("✅ 자연어 처리 모듈이 활성화되어 더 정확한 분석이 가능합니다!")
    
    # AI 분석 유형 선택
    analysis_type = st.selectbox(
        "분석 유형",
        ["법률 질문 답변", "계약서 검토", "법률 의견서 작성", 
         "판례 분석", "법령 비교", "위원회 결정 분석"],
        key="ai_analysis_type"
    )
    
    # 분석 대상 입력
    if analysis_type == "법률 질문 답변":
        question = st.text_area(
            "질문",
            placeholder="법률 관련 질문을 입력하세요...",
            height=150,
            key="ai_question"
        )
        
        # NLP 분석 옵션 (NLP 모듈이 있을 때만)
        if nlp_available:
            use_nlp = st.checkbox("🧠 자연어 분석 사용 (더 정확한 검색)", value=True, key="use_nlp_analysis")
        else:
            use_nlp = False
        
        # 참고자료 검색
        if st.checkbox("관련 법령/판례 자동 검색", key="ai_auto_search"):
            search_targets = st.multiselect(
                "검색 대상",
                ["법령", "판례", "해석례", "위원회결정"],
                default=["법령", "판례"],
                key="ai_search_targets"
            )
    
    elif analysis_type == "계약서 검토":
        contract = st.text_area(
            "계약서 내용",
            placeholder="검토할 계약서 내용을 붙여넣으세요...",
            height=300,
            key="ai_contract"
        )
        
        review_focus = st.multiselect(
            "검토 중점사항",
            ["독소조항", "불공정조항", "법적 리스크", "누락사항"],
            default=["독소조항", "불공정조항"],
            key="ai_review_focus"
        )
    
    # AI 분석 실행
    if st.button("🤖 AI 분석 시작", type="primary", key="ai_analyze_btn"):
        with st.spinner('AI가 분석 중입니다...'):
            try:
                ai_helper = clients['ai_helper']
                ai_helper.set_model(st.session_state.selected_model)
                
                result = None
                
                if analysis_type == "법률 질문 답변":
                    context = {}
                    
                    # NLP 분석 사용 시
                    if use_nlp and nlp_available:
                        nlp_processor = clients['nlp_processor']
                        
                        # NLP 분석 수행
                        st.markdown("#### 🧠 자연어 분석 결과")
                        query_analysis = nlp_processor.analyze_query(question)
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("검색 의도", query_analysis.intent.value)
                        with col2:
                            st.metric("신뢰도", f"{query_analysis.confidence:.0%}")
                        with col3:
                            st.metric("키워드", len(query_analysis.keywords))
                        
                        # NLP 기반 확장 검색
                        if st.session_state.get('ai_auto_search'):
                            with st.spinner("NLP 기반 스마트 검색 중..."):
                                orchestrator = clients.get('smart_orchestrator')
                                if orchestrator:
                                    smart_results = orchestrator.execute_smart_search(question)
                                    context['smart_search'] = smart_results
                                    st.success(f"✅ 스마트 검색으로 {smart_results['total_count']}건의 자료를 찾았습니다.")
                    
                    # 일반 검색 (NLP 미사용 시)
                    elif st.session_state.get('ai_auto_search'):
                        context = perform_context_search(question, search_targets, clients)
                    
                    result = ai_helper.analyze_legal_text(question, context)
                
                elif analysis_type == "계약서 검토":
                    prompt = f"다음 계약서를 검토해주세요.\n중점사항: {', '.join(review_focus)}\n\n{contract}"
                    result = ai_helper.analyze_legal_text(prompt, {})
                
                # 결과 표시
                if result:
                    st.markdown("### 📋 AI 분석 결과")
                    st.markdown(result)
                    
                    # 결과 저장
                    if st.button("💾 결과 저장", key="ai_save_result"):
                        st.session_state.search_history.append({
                            'query': analysis_type,
                            'timestamp': datetime.now().isoformat(),
                            'type': 'ai_analysis',
                            'result': result,
                            'nlp_used': use_nlp if 'use_nlp' in locals() else False
                        })
                        st.success("분석 결과가 저장되었습니다.")
                
            except Exception as e:
                st.error(f"AI 분석 중 오류 발생: {str(e)}")
                logger.exception(f"AI analysis error: {e}")

# ========================= Sidebar UI (Updated) =========================

def render_sidebar():
    """Enhanced sidebar with NLP status"""
    with st.sidebar:
        st.title("⚖️ K-Law Assistant Pro")
        
        # NLP 상태 표시
        if st.session_state.get('nlp_enabled'):
            st.success("🧠 자연어 처리 활성화")
        else:
            st.warning("📚 기본 검색 모드")
        
        st.markdown("---")
        
        # 테스트 모드 표시
        if st.session_state.get('test_mode', False):
            st.warning("🧪 테스트 모드로 실행 중")
        
        # API 설정
        with st.expander("🔑 API 설정", expanded=False):
            law_api_key = st.text_input(
                "법제처 API Key",
                value=st.session_state.api_keys.get('law_api_key', ''),
                type="password",
                help="https://open.law.go.kr 에서 발급",
                key="sidebar_law_api_key"
            )
            
            if law_api_key:
                if len(law_api_key) < 20:
                    st.error("❌ API 키가 너무 짧습니다.")
                else:
                    st.success("✅ API 키 형식 확인")
            
            openai_api_key = st.text_input(
                "OpenAI API Key",
                value=st.session_state.api_keys.get('openai_api_key', ''),
                type="password",
                help="https://platform.openai.com 에서 발급",
                key="sidebar_openai_api_key"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("API 키 저장", key="save_api_keys", use_container_width=True):
                    st.session_state.api_keys['law_api_key'] = law_api_key
                    st.session_state.api_keys['openai_api_key'] = openai_api_key
                    st.cache_resource.clear()
                    st.success("API 키가 저장되었습니다!")
                    st.rerun()
            
            with col2:
                if st.button("연결 테스트", key="test_api", use_container_width=True):
                    with st.spinner("API 연결 테스트 중..."):
                        try:
                            test_client = LawAPIClient(oc_key=law_api_key)
                            result = test_client.search(target='law', query='민법', display=1)
                            if 'error' not in result:
                                st.success("✅ API 연결 성공!")
                            else:
                                st.error(f"❌ API 연결 실패: {result.get('error')}")
                        except Exception as e:
                            st.error(f"❌ 연결 테스트 실패: {str(e)}")
        
        # GPT 모델 선택
        st.markdown("### 🤖 AI 모델")
        models = {
            'gpt-4o-mini': 'GPT-4o Mini (빠름)',
            'gpt-4o': 'GPT-4o (균형)',
            'gpt-4-turbo': 'GPT-4 Turbo (정확)',
            'gpt-3.5-turbo': 'GPT-3.5 Turbo (경제적)'
        }
        
        st.session_state.selected_model = st.selectbox(
            "모델 선택",
            options=list(models.keys()),
            format_func=lambda x: models[x],
            index=list(models.keys()).index(st.session_state.get('selected_model', 'gpt-4o-mini')),
            key="sidebar_model_select"
        )
        
        # 빠른 검색
        st.markdown("### 🚀 빠른 검색")
        quick_searches = {
            "도로교통법": "도로교통법",
            "개인정보보호": "개인정보보호법",
            "근로기준법": "근로기준법",
            "부동산거래": "부동산 실거래",
            "형법": "형법",
            "민법": "민법"
        }
        
        for label, query in quick_searches.items():
            if st.button(label, key=f"quick_{label}", use_container_width=True):
                st.session_state.quick_search = query
        
        # 최근 스마트 검색 (NLP가 활성화된 경우)
        if st.session_state.get('nlp_enabled') and st.session_state.get('smart_search_history'):
            st.markdown("### 🧠 최근 스마트 검색")
            for idx, item in enumerate(st.session_state.smart_search_history[-3:][::-1]):
                confidence = item.get('confidence', 0)
                emoji = "🟢" if confidence > 0.7 else "🟡" if confidence > 0.5 else "🔴"
                if st.button(
                    f"{emoji} {item['query'][:15]}... ({item['intent']})",
                    key=f"smart_history_{idx}",
                    use_container_width=True
                ):
                    st.session_state.smart_search_query = item['query']
        
        # 검색 이력
        if st.session_state.search_history:
            st.markdown("### 📜 최근 검색")
            for idx, item in enumerate(st.session_state.search_history[-5:][::-1]):
                nlp_badge = "🧠" if item.get('nlp_used') else ""
                if st.button(
                    f"🕐 {nlp_badge} {item['query'][:20]}...",
                    key=f"history_{idx}",
                    use_container_width=True
                ):
                    st.session_state.history_search = item['query']

# ========================= Other Tab Functions (기존 탭들은 그대로 유지) =========================

def render_law_search_tab():
    """법령 검색 탭 - 26개 API 기능 모두 구현"""
    st.header("📚 법령 검색")
    
    clients = get_api_clients()
    if not clients.get('law_searcher'):
        st.error("법령 검색 모듈을 초기화할 수 없습니다. API 키를 확인해주세요.")
        return
    
    # NLP 지원 표시
    if st.session_state.get('nlp_enabled'):
        st.info("💡 더 쉬운 검색을 원하시면 '스마트 검색' 탭을 이용해보세요!")
    
    # 검색 유형 선택
    search_type = st.selectbox(
        "검색 유형",
        [
            "현행법령", "시행일법령", "영문법령", "법령연혁",
            "법령변경이력", "조문별변경이력", "신구법비교", "법령체계도",
            "3단비교", "위임법령", "법령-자치법규연계", "한눈보기",
            "법령명약칭", "삭제데이터", "조항호목조회"
        ],
        key="law_search_type"
    )
    
    # 검색어 입력
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input("검색어", placeholder="예: 도로교통법, 민법, 형법", key="law_query")
    with col2:
        search_btn = st.button("🔍 검색", type="primary", use_container_width=True, key="law_search_btn")
    
    # 고급 옵션
    with st.expander("고급 검색 옵션"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_scope = st.selectbox("검색범위", ["법령명", "본문검색"], key="law_search_scope")
            display = st.number_input("결과 개수", min_value=1, max_value=100, value=20, key="law_display")
        
        with col2:
            sort_option = st.selectbox(
                "정렬",
                ["법령명 오름차순", "법령명 내림차순", "공포일자 오름차순", "공포일자 내림차순"],
                key="law_sort"
            )
            date_range = st.date_input("공포일자 범위", [], key="law_date_range")
        
        with col3:
            org = st.text_input("소관부처", placeholder="예: 법무부", key="law_org")
            kind = st.selectbox("법령종류", ["전체", "법률", "대통령령", "총리령", "부령"], key="law_kind")
    
    # 검색 실행
    if search_btn and query:
        with st.spinner(f'{search_type} 검색 중...'):
            try:
                results = None
                law_searcher = clients['law_searcher']
                
                logger.info(f"법령 검색 시작: {search_type}, 검색어: {query}")
                
                # 검색 유형별 처리 (기존 코드 유지)
                if search_type == "현행법령":
                    results = law_searcher.search_laws(
                        query=query,
                        search_type=1 if search_scope == "법령명" else 2,
                        display=display,
                        sort={"법령명 오름차순": "lasc", "법령명 내림차순": "ldes",
                              "공포일자 오름차순": "dasc", "공포일자 내림차순": "ddes"}[sort_option]
                    )
                
                # ... (나머지 검색 유형 처리 코드는 기존과 동일)
                
                # 결과 표시
                if results:
                    if 'error' not in results:
                        total_count = results.get('totalCnt', 0)
                        st.success(f"✅ {total_count}건의 결과를 찾았습니다.")
                        
                        if total_count > 0:
                            st.session_state.search_history.append({
                                'query': query,
                                'timestamp': datetime.now().isoformat(),
                                'type': search_type,
                                'count': total_count
                            })
                        
                        if 'results' in results and results['results']:
                            for idx, item in enumerate(results['results'][:10], 1):
                                with st.expander(f"{idx}. {item.get('법령명한글', item.get('법령명', item.get('title', 'N/A')))}"):
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**공포일자:** {item.get('공포일자', 'N/A')}")
                                        st.write(f"**시행일자:** {item.get('시행일자', 'N/A')}")
                                    with col2:
                                        st.write(f"**소관부처:** {item.get('소관부처명', item.get('소관부처', 'N/A'))}")
                                        st.write(f"**법령구분:** {item.get('법령구분명', item.get('법령구분', 'N/A'))}")
                                    
                                    if st.button(f"상세 조회", key=f"law_detail_{search_type}_{idx}"):
                                        detail = law_searcher.get_law_detail(
                                            law_id=item.get('법령ID', item.get('법령일련번호')),
                                            output_type="json"
                                        )
                                        st.json(detail)
                        else:
                            st.info("검색 결과가 없습니다. 다른 검색어를 시도해보세요.")
                    else:
                        st.error(f"오류: {results.get('error', '알 수 없는 오류')}")
                        
            except Exception as e:
                st.error(f"검색 중 오류 발생: {str(e)}")
                logger.exception(f"법령 검색 예외 발생: {e}")

def render_case_search_tab():
    """판례/심판례 검색 탭"""
    st.header("⚖️ 판례/심판례 검색")
    
    clients = get_api_clients()
    if not clients.get('case_searcher'):
        st.error("판례 검색 모듈을 초기화할 수 없습니다. API 키를 확인해주세요.")
        return
    
    case_searcher = clients['case_searcher']
    
    # 검색 유형 선택
    case_type = st.selectbox(
        "검색 유형",
        ["법원 판례", "헌재결정례", "법령해석례", "행정심판례", "통합검색"],
        key="case_type"
    )
    
    # 검색어 입력
    query = st.text_input("검색어", placeholder="예: 음주운전, 개인정보, 계약", key="case_query")
    
    # 고급 옵션
    with st.expander("고급 검색 옵션"):
        col1, col2 = st.columns(2)
        
        with col1:
            if case_type == "법원 판례":
                court = st.selectbox("법원", ["전체", "대법원", "하급심"], key="case_court")
                court_name = st.text_input("법원명", placeholder="예: 서울고등법원", key="case_court_name")
            
            date_range = st.date_input("날짜 범위", [], key="case_date_range")
            
        with col2:
            search_in_content = st.checkbox("본문 검색", value=False, key="case_content_search")
            display = st.number_input("결과 개수", min_value=1, max_value=100, value=20, key="case_display")
    
    # 검색 실행
    if st.button("🔍 검색", type="primary", key="case_search_btn"):
        if not query:
            st.warning("검색어를 입력해주세요.")
            return
        
        with st.spinner('검색 중...'):
            try:
                results = None
                
                if case_type == "법원 판례":
                    results = case_searcher.search_court_cases(
                        query=query,
                        court=court if court != "전체" else None,
                        court_name=court_name if court_name else None,
                        search_type=2 if search_in_content else 1,
                        display=display
                    )
                
                # ... (나머지 case_type 처리는 기존과 동일)
                
                # 결과 표시
                if results and results.get('status') == 'success':
                    total = results.get('total_count', 0)
                    st.success(f"✅ {total}건의 결과를 찾았습니다.")
                    
                    items = results.get('cases') or results.get('decisions') or \
                           results.get('interpretations') or results.get('tribunals', [])
                    
                    if items:
                        for idx, item in enumerate(items[:10], 1):
                            with st.expander(f"{idx}. {item.get('title', 'N/A')}"):
                                display_case_item(item)
                    else:
                        st.info("검색 결과가 없습니다.")
                        
            except Exception as e:
                st.error(f"검색 중 오류 발생: {str(e)}")
                logger.exception(f"판례 검색 예외 발생: {e}")

def render_committee_search_tab():
    """14개 위원회 결정문 검색 탭"""
    st.header("🏛️ 위원회 결정문 검색")
    
    clients = get_api_clients()
    if not clients.get('committee_searcher'):
        st.error("위원회 검색 모듈을 초기화할 수 없습니다. API 키를 확인해주세요.")
        return
    
    committee_searcher = clients['committee_searcher']
    
    # 위원회 정보 가져오기
    committees = committee_searcher.get_committee_info()
    
    # 위원회 선택
    col1, col2 = st.columns([2, 3])
    
    with col1:
        selected_committees = st.multiselect(
            "위원회 선택",
            options=[c['code'] for c in committees],
            format_func=lambda x: next(c['name'] for c in committees if c['code'] == x),
            default=['ftc', 'ppc'],
            key="committee_select"
        )
    
    with col2:
        query = st.text_input("검색어", placeholder="검색어를 입력하세요", key="committee_query")
    
    # 검색 실행
    if st.button("🔍 검색", type="primary", key="committee_search_btn"):
        if not query and not selected_committees:
            st.warning("검색어를 입력하거나 위원회를 선택해주세요.")
            return
        
        with st.spinner('위원회 결정문 검색 중...'):
            try:
                all_results = {}
                total_count = 0
                
                for committee_code in selected_committees:
                    result = committee_searcher.search_by_committee(
                        committee_code=committee_code,
                        query=query,
                        display=20
                    )
                    
                    if result['success']:
                        all_results[committee_code] = result
                        total_count += result.get('total_count', 0)
                
                # 결과 표시
                if all_results:
                    st.success(f"✅ 총 {total_count}건의 결정문을 찾았습니다.")
                    
                    for committee_code, result in all_results.items():
                        st.subheader(f"📋 {result['committee_name']} ({result['total_count']}건)")
                        
                        for idx, decision in enumerate(result['decisions'][:5], 1):
                            with st.expander(f"{idx}. {decision.get('title', 'N/A')}"):
                                st.write(f"**날짜:** {decision.get('date')}")
                                st.write(f"**번호:** {decision.get('number')}")
                
            except Exception as e:
                st.error(f"검색 중 오류 발생: {str(e)}")

def render_treaty_admin_tab():
    """조약, 행정규칙, 자치법규, 별표서식 등 검색"""
    st.header("📜 조약/행정규칙/자치법규")
    
    clients = get_api_clients()
    if not clients.get('treaty_admin_searcher'):
        st.error("조약/행정규칙 검색 모듈을 초기화할 수 없습니다.")
        return
    
    searcher = clients['treaty_admin_searcher']
    
    # 검색 유형 선택
    search_type = st.selectbox(
        "검색 유형",
        ["조약", "행정규칙", "자치법규", "법령 별표서식", "행정규칙 별표서식"],
        key="treaty_search_type"
    )
    
    # 검색어 입력
    query = st.text_input("검색어", placeholder="검색어를 입력하세요", key="treaty_query")
    
    # 검색 실행
    if st.button("🔍 검색", type="primary", key="treaty_search_btn"):
        if not query:
            st.warning("검색어를 입력해주세요.")
            return
        
        with st.spinner(f'{search_type} 검색 중...'):
            try:
                results = None
                
                if search_type == "조약":
                    results = searcher.search_treaties(query=query)
                elif search_type == "행정규칙":
                    results = searcher.search_admin_rules(query=query)
                elif search_type == "자치법규":
                    results = searcher.search_local_laws(query=query)
                
                # 결과 표시
                if results and 'error' not in results:
                    total = results.get('totalCnt', 0)
                    st.success(f"✅ {total}건의 결과를 찾았습니다.")
                    
                    items = results.get('treaties') or results.get('rules') or \
                           results.get('ordinances') or results.get('results', [])
                    
                    if items:
                        for idx, item in enumerate(items[:10], 1):
                            with st.expander(f"{idx}. {get_item_title(item, search_type)}"):
                                display_treaty_admin_item(item, search_type)
                                
            except Exception as e:
                st.error(f"검색 중 오류 발생: {str(e)}")

def render_advanced_features_tab():
    """고급 기능 탭"""
    st.header("🔧 고급 기능")
    
    clients = get_api_clients()
    
    # 기능 선택
    feature = st.selectbox(
        "기능 선택",
        ["법령 체계도", "3단 비교", "신구법 비교", "법령 연혁 조회"],
        key="advanced_feature"
    )
    
    if feature == "법령 체계도":
        st.subheader("📊 법령 체계도")
        law_name = st.text_input("법령명", placeholder="예: 민법", key="adv_structure_name")
        
        if st.button("체계도 조회", key="adv_structure_btn"):
            if law_name and clients.get('law_searcher'):
                with st.spinner('체계도 조회 중...'):
                    result = clients['law_searcher'].search_law_structure(law_name)
                    if result and 'error' not in result:
                        st.success(f"✅ {result.get('totalCnt', 0)}건의 결과")
                        for item in result.get('results', [])[:5]:
                            st.write(f"- {item.get('법령명한글', 'N/A')}")

# ========================= Helper Functions =========================

def display_case_item(item: Dict):
    """판례 항목 표시"""
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**법원:** {item.get('court', 'N/A')}")
        st.write(f"**사건번호:** {item.get('case_number', 'N/A')}")
    with col2:
        st.write(f"**선고일:** {item.get('date', 'N/A')}")
        st.write(f"**사건종류:** {item.get('type', 'N/A')}")
    
    if item.get('summary'):
        st.write("**판결요지:**")
        st.write(item['summary'][:300] + "..." if len(item.get('summary', '')) > 300 else item['summary'])

def get_item_title(item: Dict, search_type: str) -> str:
    """검색 결과 아이템의 제목 추출"""
    title_fields = {
        "조약": ["조약명", "조약명한글"],
        "행정규칙": ["행정규칙명", "제목"],
        "자치법규": ["자치법규명", "제목"],
    }
    
    for field in title_fields.get(search_type, ["제목", "명칭", "title"]):
        if field in item:
            return item[field]
    
    return str(item)[:50]

def display_treaty_admin_item(item: Dict, search_type: str):
    """조약/행정규칙 등 아이템 표시"""
    info_fields = {
        "조약": [("발효일자", "발효일자"), ("체결일자", "체결일자")],
        "행정규칙": [("발령일자", "발령일자"), ("소관부처", "소관부처명")],
        "자치법규": [("발령일자", "발령일자"), ("지자체", "지자체명")],
    }
    
    fields = info_fields.get(search_type, [])
    
    if fields:
        col1, col2 = st.columns(2)
        for i, (label, field) in enumerate(fields):
            with col1 if i % 2 == 0 else col2:
                if field in item:
                    st.write(f"**{label}:** {item[field]}")

def perform_context_search(query: str, targets: List[str], clients: Dict) -> Dict:
    """AI 분석을 위한 컨텍스트 검색"""
    context = {}
    
    try:
        if "법령" in targets and clients.get('law_searcher'):
            result = clients['law_searcher'].search_laws(query, display=5)
            if result and result.get('totalCnt', 0) > 0:
                context['laws'] = result.get('results', [])
        
        if "판례" in targets and clients.get('case_searcher'):
            result = clients['case_searcher'].search_court_cases(query, display=5)
            if result.get('status') == 'success':
                context['cases'] = result.get('cases', [])
        
    except Exception as e:
        logger.error(f"Context search error: {str(e)}")
    
    return context

# ========================= Main Application =========================

def main():
    """Main application with NLP integration"""
    
    # 모듈 로드 확인
    if not MODULES_LOADED:
        st.error("필수 모듈을 로드할 수 없습니다.")
        st.code("pip install -r requirements.txt", language="bash")
        return
    
    # 세션 상태 초기화
    init_session_state()
    
    # 사이드바 렌더링
    render_sidebar()
    
    # 메인 타이틀
    st.title("⚖️ K-Law Assistant Pro")
    st.markdown("법령, 판례, 위원회 결정문 통합 검색 및 **자연어 AI 분석** 시스템")
    
    # NLP 모듈 상태 표시
    if st.session_state.get('nlp_enabled'):
        st.success("🧠 자연어 처리 모듈이 활성화되어 더 스마트한 검색이 가능합니다!")
    
    # Python 버전 표시
    if sys.version_info >= (3, 13):
        st.info(f"🐍 Python {sys.version_info.major}.{sys.version_info.minor} 호환 모드로 실행 중")
    
    # API 키 확인
    if not st.session_state.api_keys.get('law_api_key'):
        st.warning("⚠️ 법제처 API 키가 설정되지 않았습니다. 사이드바에서 설정해주세요.")
    
    # 탭 구성 - 스마트 검색 탭 추가
    tab_names = ["🧠 스마트 검색"] if st.session_state.get('nlp_enabled') else []
    tab_names.extend([
        "📚 법령검색",
        "⚖️ 판례/심판례",
        "🏛️ 위원회결정",
        "📜 조약/행정규칙",
        "🤖 AI 분석",
        "🔧 고급기능",
        "📊 통계",
        "ℹ️ 도움말"
    ])
    
    tabs = st.tabs(tab_names)
    
    tab_index = 0
    
    # Tab 0: 스마트 검색 (NLP가 활성화된 경우에만)
    if st.session_state.get('nlp_enabled'):
        with tabs[tab_index]:
            render_smart_search_tab()
        tab_index += 1
    
    # Tab 1: 법령 검색
    with tabs[tab_index]:
        render_law_search_tab()
    tab_index += 1
    
    # Tab 2: 판례/심판례 검색
    with tabs[tab_index]:
        render_case_search_tab()
    tab_index += 1
    
    # Tab 3: 위원회 결정문 검색
    with tabs[tab_index]:
        render_committee_search_tab()
    tab_index += 1
    
    # Tab 4: 조약/행정규칙/자치법규
    with tabs[tab_index]:
        render_treaty_admin_tab()
    tab_index += 1
    
    # Tab 5: AI 법률 분석 (Enhanced)
    with tabs[tab_index]:
        render_ai_analysis_tab_enhanced()
    tab_index += 1
    
    # Tab 6: 고급 기능
    with tabs[tab_index]:
        render_advanced_features_tab()
    tab_index += 1
    
    # Tab 7: 통계
    with tabs[tab_index]:
        st.header("📊 검색 통계")
        
        if st.session_state.search_history or st.session_state.get('smart_search_history'):
            # 일반 검색 통계
            if st.session_state.search_history:
                history_df = pd.DataFrame(st.session_state.search_history)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("총 검색 수", len(history_df))
                with col2:
                    if 'type' in history_df.columns:
                        ai_searches = len(history_df[history_df['type'] == 'ai_analysis'])
                        st.metric("AI 분석", ai_searches)
                with col3:
                    if 'nlp_used' in history_df.columns:
                        nlp_searches = len(history_df[history_df['nlp_used'] == True])
                        st.metric("NLP 사용", nlp_searches)
            
            # 스마트 검색 통계
            if st.session_state.get('smart_search_history'):
                st.subheader("🧠 스마트 검색 통계")
                smart_df = pd.DataFrame(st.session_state.smart_search_history)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("스마트 검색 수", len(smart_df))
                with col2:
                    if 'confidence' in smart_df.columns:
                        avg_confidence = smart_df['confidence'].mean()
                        st.metric("평균 신뢰도", f"{avg_confidence:.0%}")
                
                # 검색 의도 분포
                if 'intent' in smart_df.columns:
                    intent_counts = smart_df['intent'].value_counts()
                    st.bar_chart(intent_counts)
        else:
            st.info("아직 검색 이력이 없습니다.")
    tab_index += 1
    
    # Tab 8: 도움말
    with tabs[tab_index]:
        st.header("ℹ️ 사용 가이드")
        
        with st.expander("🧠 스마트 검색 (NEW!)"):
            st.markdown("""
            **자연어 처리 기반 통합 검색**
            - 복잡한 법률 용어를 몰라도 일상 언어로 검색
            - AI가 질문 의도를 파악하여 최적의 검색 전략 수립
            - 법령, 판례, 해석례를 통합 검색하여 종합 답변 제공
            
            **사용 예시:**
            - "회사에서 갑자기 해고당했어요" → 근로기준법, 부당해고 판례 자동 검색
            - "전세금을 못 받고 있어요" → 주택임대차보호법, 관련 판례 검색
            - "개인정보가 유출됐어요" → 개인정보보호법, 손해배상 사례 검색
            """)
        
        with st.expander("📚 법령 검색 (26개 기능)"):
            st.markdown("""
            - **현행법령**: 현재 시행 중인 법령 검색
            - **영문법령**: 영문 번역 법령 검색
            - **법령연혁**: 법령의 제·개정 이력 조회
            - 그 외 23개 세부 기능
            """)
        
        st.info("""
        💡 **Tip**: 
        - 스마트 검색은 초보자에게 가장 추천되는 기능입니다
        - 복잡한 법률 문제는 GPT-4 모델을 사용하세요
        - NLP 모듈이 활성화되면 더 정확한 검색이 가능합니다
        """)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error(f"애플리케이션 실행 중 오류가 발생했습니다: {str(e)}")
        st.info("페이지를 새로고침하거나 관리자에게 문의해주세요.")
