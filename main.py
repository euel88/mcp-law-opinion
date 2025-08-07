"""
K-Law Assistant - 통합 법률 검토 지원 시스템 (모듈화 버전)
Modularized Main Application
Version 12.0 - Clean Architecture with Separated Modules
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Python 3.13 호환성 패치
if sys.version_info >= (3, 13):
    import typing
    import typing_extensions
    
    if hasattr(typing, '_TypedDictMeta'):
        original_new = typing._TypedDictMeta.__new__
        def patched_new(cls, name, bases, ns, total=True, **kwargs):
            kwargs.pop('closed', None)
            try:
                return original_new(cls, name, bases, ns, total=total)
            except TypeError:
                return original_new(cls, name, bases, ns)
        typing._TypedDictMeta.__new__ = staticmethod(patched_new)

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===========================
# 페이지 설정
# ===========================
st.set_page_config(
    page_title="K-Law Assistant Pro",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/your-repo',
        'Report a bug': 'https://github.com/your-repo/issues',
        'About': 'K-Law Assistant Pro v12.0 - AI 기반 통합 법률 검색 시스템'
    }
)

# ===========================
# 모듈 임포트
# ===========================
MODULES_LOADED = False
NLP_MODULE_LOADED = False

try:
    # 기본 모듈
    from common_api import LawAPIClient, OpenAIHelper
    from law_module import LawSearcher
    from committee_module import CommitteeDecisionSearcher
    from case_module import CaseSearcher, AdvancedCaseSearcher
    from treaty_admin_module import TreatyAdminSearcher
    
    # 법령 체계도 전문 모듈 (신규)
    from law_hierarchy_module import (
        LawHierarchyManager, SearchConfig, LawHierarchy,
        LawNameProcessor, AdminRules
    )
    
    MODULES_LOADED = True
    logger.info("필수 모듈 로드 완료")
    
    # NLP 모듈 (선택적)
    try:
        from nlp_search_module import NaturalLanguageSearchProcessor, SmartSearchOrchestrator
        NLP_MODULE_LOADED = True
        logger.info("NLP 모듈 로드 완료")
    except ImportError:
        logger.warning("NLP 모듈을 사용할 수 없습니다. 기본 검색만 사용 가능합니다.")
        
except ImportError as e:
    st.error(f"❌ 필수 모듈을 불러올 수 없습니다: {str(e)}")
    st.info("requirements.txt의 패키지를 모두 설치했는지 확인해주세요.")
    logger.error(f"모듈 임포트 실패: {e}")

# ===========================
# 세션 상태 관리
# ===========================
def init_session_state():
    """세션 상태 초기화"""
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
        st.session_state.nlp_enabled = NLP_MODULE_LOADED
        st.session_state.downloaded_laws = []
        st.session_state.hierarchy_manager = None
        st.session_state.debug_mode = False
        logger.info("세션 상태 초기화 완료")

# ===========================
# API 클라이언트 초기화
# ===========================
@st.cache_resource
def get_api_clients():
    """API 클라이언트 초기화 및 캐싱"""
    try:
        law_api_key = st.session_state.api_keys.get('law_api_key', '')
        openai_api_key = st.session_state.api_keys.get('openai_api_key', '')
        
        if not law_api_key:
            st.warning("⚠️ 법제처 API 키가 설정되지 않았습니다.")
            st.info("https://open.law.go.kr 에서 무료로 API 키를 발급받으실 수 있습니다.")
            return {}
        
        clients = {}
        
        # 기본 API 클라이언트
        clients['law_client'] = LawAPIClient(oc_key=law_api_key)
        clients['law_searcher'] = LawSearcher(oc_key=law_api_key)
        
        # AI Helper (선택적)
        if openai_api_key:
            clients['ai_helper'] = OpenAIHelper(api_key=openai_api_key)
        
        # 각 검색 모듈
        clients['case_searcher'] = CaseSearcher(
            api_client=clients['law_client'],
            ai_helper=clients.get('ai_helper')
        )
        clients['advanced_case_searcher'] = AdvancedCaseSearcher(
            api_client=clients['law_client'],
            ai_helper=clients.get('ai_helper')
        )
        clients['committee_searcher'] = CommitteeDecisionSearcher(
            api_client=clients['law_client']
        )
        clients['treaty_admin_searcher'] = TreatyAdminSearcher(oc_key=law_api_key)
        
        # 법령 체계도 관리자
        clients['hierarchy_manager'] = LawHierarchyManager(
            law_client=clients['law_client'],
            law_searcher=clients['law_searcher']
        )
        
        # NLP 프로세서 (선택적)
        if NLP_MODULE_LOADED and clients.get('ai_helper'):
            try:
                nlp_processor = NaturalLanguageSearchProcessor(
                    ai_helper=clients['ai_helper']
                )
                clients['nlp_processor'] = nlp_processor
                clients['smart_orchestrator'] = SmartSearchOrchestrator(
                    nlp_processor, clients
                )
                st.session_state.nlp_enabled = True
            except Exception as e:
                logger.warning(f"NLP 프로세서 초기화 실패: {e}")
        
        logger.info(f"API 클라이언트 초기화 완료: {list(clients.keys())}")
        return clients
        
    except Exception as e:
        logger.error(f"API 클라이언트 초기화 실패: {e}")
        st.error(f"API 클라이언트 초기화 실패: {str(e)}")
        return {}

# ===========================
# 사이드바 렌더링
# ===========================
def render_sidebar():
    """사이드바 UI"""
    with st.sidebar:
        st.title("⚖️ K-Law Assistant")
        
        # 상태 표시
        status_col1, status_col2 = st.columns(2)
        with status_col1:
            if st.session_state.get('nlp_enabled'):
                st.success("🧠 AI 활성화")
            else:
                st.warning("📚 기본 모드")
        
        with status_col2:
            if st.session_state.get('debug_mode'):
                st.info("🔧 디버그 ON")
        
        st.markdown("---")
        
        # API 설정
        with st.expander("🔑 API 설정", expanded=False):
            law_api_key = st.text_input(
                "법제처 API Key",
                value=st.session_state.api_keys.get('law_api_key', ''),
                type="password",
                help="https://open.law.go.kr 에서 발급",
                key="sidebar_law_api_key"
            )
            
            openai_api_key = st.text_input(
                "OpenAI API Key (선택)",
                value=st.session_state.api_keys.get('openai_api_key', ''),
                type="password",
                help="AI 기능 사용 시 필요",
                key="sidebar_openai_api_key"
            )
            
            if st.button("💾 설정 저장", key="save_api_keys", use_container_width=True):
                st.session_state.api_keys['law_api_key'] = law_api_key
                st.session_state.api_keys['openai_api_key'] = openai_api_key
                st.cache_resource.clear()
                st.success("API 키가 저장되었습니다!")
                st.rerun()
        
        # AI 모델 선택 (OpenAI API가 있을 때만)
        if st.session_state.api_keys.get('openai_api_key'):
            st.markdown("### 🤖 AI 설정")
            models = {
                'gpt-4o-mini': 'GPT-4o Mini (빠름)',
                'gpt-4o': 'GPT-4o (균형)',
                'gpt-4-turbo': 'GPT-4 Turbo (정확)',
                'gpt-3.5-turbo': 'GPT-3.5 Turbo (경제적)'
            }
            
            st.session_state.selected_model = st.selectbox(
                "AI 모델",
                options=list(models.keys()),
                format_func=lambda x: models[x],
                index=0,
                key="sidebar_model_select"
            )
        
        # 검색 이력
        if st.session_state.search_history:
            st.markdown("### 📜 최근 검색")
            for idx, item in enumerate(st.session_state.search_history[-5:][::-1]):
                query_text = item['query'][:30] + "..." if len(item['query']) > 30 else item['query']
                if st.button(f"🕐 {query_text}", key=f"history_{idx}", use_container_width=True):
                    st.session_state.current_query = item['query']
                    st.rerun()
        
        # 통계
        st.markdown("### 📊 사용 통계")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("총 검색", len(st.session_state.search_history))
        with col2:
            st.metric("다운로드", len(st.session_state.downloaded_laws))
        
        # 도움말
        with st.expander("ℹ️ 도움말"):
            st.markdown("""
            ### 주요 기능
            1. **통합 검색**: 법령, 판례, 유권해석 통합 검색
            2. **법령 체계도**: 관련 법령 일괄 다운로드
            3. **AI 분석**: 법률 문서 분석 (OpenAI API 필요)
            
            ### 문의
            - GitHub: https://github.com/your-repo
            - Email: support@klaw.com
            """)

# ===========================
# 통합 검색 탭
# ===========================
def render_unified_search_tab():
    """통합 스마트 검색 탭"""
    st.header("🔍 통합 스마트 검색")
    
    clients = get_api_clients()
    if not clients:
        return
    
    # 검색 안내
    with st.expander("💡 검색 사용법", expanded=False):
        st.markdown("""
        ### 자연어 검색 예시
        - "음주운전 처벌 기준"
        - "부당해고 구제 방법"
        - "전세보증금 못 받을 때"
        
        ### 직접 검색 예시
        - 법령: "도로교통법", "근로기준법 제23조"
        - 판례: "대법원 2023다12345"
        - 유권해석: "법제처 해석"
        """)
    
    # 검색 입력
    col1, col2 = st.columns([5, 1])
    with col1:
        search_query = st.text_area(
            "검색어 또는 질문을 입력하세요",
            placeholder="예: 음주운전 처벌 기준 / 근로기준법 / 대법원 판례",
            height=100,
            key="unified_search_query",
            value=st.session_state.get('current_query', '')
        )
    
    with col2:
        st.write("")
        st.write("")
        search_btn = st.button("🔍 검색", type="primary", use_container_width=True)
    
    # 검색 옵션
    with st.expander("⚙️ 검색 옵션", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_targets = st.multiselect(
                "검색 대상",
                ["법령", "판례", "헌재결정", "유권해석", "위원회결정", "조약", "행정규칙", "자치법규"],
                default=["법령", "판례"],
                key="search_targets"
            )
        
        with col2:
            date_range = st.selectbox(
                "기간 설정",
                ["전체", "최근 1년", "최근 3년", "최근 5년"],
                key="date_range"
            )
        
        with col3:
            sort_option = st.selectbox(
                "정렬 기준",
                ["관련도순", "최신순", "오래된순"],
                key="sort_option"
            )
    
    # 빠른 검색 예시
    st.markdown("### 🚀 빠른 검색")
    
    example_categories = {
        "노동": ["부당해고", "임금체불", "산업재해", "퇴직금"],
        "부동산": ["전세보증금", "매매계약", "임대차보호", "재개발"],
        "교통": ["음주운전", "교통사고", "무면허운전", "신호위반"],
        "민사": ["손해배상", "계약위반", "소유권", "채권채무"]
    }
    
    selected_category = st.selectbox("주제 선택", list(example_categories.keys()), key="category_select")
    
    cols = st.columns(4)
    for idx, example in enumerate(example_categories[selected_category]):
        with cols[idx % 4]:
            if st.button(example, key=f"ex_{idx}", use_container_width=True):
                st.session_state.current_query = example
                st.rerun()
    
    # 검색 실행
    if search_btn and search_query:
        execute_search(search_query, search_targets, clients)

def execute_search(query: str, targets: List[str], clients: Dict):
    """검색 실행"""
    with st.spinner('검색 중...'):
        try:
            all_results = {
                'query': query,
                'search_results': {},
                'total_count': 0
            }
            
            # 법령 검색
            if "법령" in targets and clients.get('law_searcher'):
                result = clients['law_searcher'].search_laws(query, display=20)
                if result.get('totalCnt', 0) > 0:
                    all_results['search_results']['laws'] = result
                    all_results['total_count'] += result['totalCnt']
            
            # 판례 검색
            if "판례" in targets and clients.get('case_searcher'):
                result = clients['case_searcher'].search_court_cases(query, display=20)
                if result.get('status') == 'success':
                    all_results['search_results']['cases'] = result
                    all_results['total_count'] += result.get('total_count', 0)
            
            # 헌재결정 검색
            if "헌재결정" in targets and clients.get('case_searcher'):
                result = clients['case_searcher'].search_constitutional_decisions(query, display=20)
                if result.get('status') == 'success':
                    all_results['search_results']['constitutional'] = result
                    all_results['total_count'] += result.get('total_count', 0)
            
            # 유권해석 검색
            if "유권해석" in targets and clients.get('case_searcher'):
                result = clients['case_searcher'].search_legal_interpretations(query, display=20)
                if result.get('status') == 'success':
                    all_results['search_results']['interpretations'] = result
                    all_results['total_count'] += result.get('total_count', 0)
            
            # 위원회결정 검색
            if "위원회결정" in targets and clients.get('committee_searcher'):
                result = clients['committee_searcher'].search_all_committees(query, display_per_committee=5)
                if result.get('success'):
                    all_results['search_results']['committees'] = result
                    all_results['total_count'] += result.get('total_count', 0)
            
            # 조약 검색
            if "조약" in targets and clients.get('treaty_admin_searcher'):
                result = clients['treaty_admin_searcher'].search_treaties(query, display=20)
                if result.get('totalCnt', 0) > 0:
                    all_results['search_results']['treaties'] = result
                    all_results['total_count'] += result['totalCnt']
            
            # 행정규칙 검색
            if "행정규칙" in targets and clients.get('treaty_admin_searcher'):
                result = clients['treaty_admin_searcher'].search_admin_rules(query, display=20)
                if result.get('totalCnt', 0) > 0:
                    all_results['search_results']['admin_rules'] = result
                    all_results['total_count'] += result['totalCnt']
            
            # 자치법규 검색
            if "자치법규" in targets and clients.get('treaty_admin_searcher'):
                result = clients['treaty_admin_searcher'].search_local_laws(query, display=20)
                if result.get('totalCnt', 0) > 0:
                    all_results['search_results']['local_laws'] = result
                    all_results['total_count'] += result['totalCnt']
            
            # 결과 표시
            display_search_results(all_results)
            
            # 검색 이력 저장
            st.session_state.search_history.append({
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'type': 'unified_search'
            })
            
        except Exception as e:
            st.error(f"검색 중 오류 발생: {str(e)}")
            logger.exception(f"Search error: {e}")

def display_search_results(results: Dict):
    """검색 결과 표시"""
    total_count = results.get('total_count', 0)
    
    if total_count == 0:
        st.warning("검색 결과가 없습니다.")
        return
    
    st.success(f"✅ 총 {total_count}건의 결과를 찾았습니다.")
    
    # 결과 유형별 탭 생성
    search_results = results.get('search_results', {})
    tab_names = []
    tab_contents = []
    
    if 'laws' in search_results:
        tab_names.append(f"📚 법령 ({search_results['laws'].get('totalCnt', 0)})")
        tab_contents.append('laws')
    
    if 'cases' in search_results:
        tab_names.append(f"⚖️ 판례 ({search_results['cases'].get('total_count', 0)})")
        tab_contents.append('cases')
    
    if 'constitutional' in search_results:
        tab_names.append(f"🏛️ 헌재결정 ({search_results['constitutional'].get('total_count', 0)})")
        tab_contents.append('constitutional')
    
    if 'interpretations' in search_results:
        tab_names.append(f"📋 유권해석 ({search_results['interpretations'].get('total_count', 0)})")
        tab_contents.append('interpretations')
    
    if 'committees' in search_results:
        tab_names.append(f"🏢 위원회 ({search_results['committees'].get('total_count', 0)})")
        tab_contents.append('committees')
    
    if 'treaties' in search_results:
        tab_names.append(f"📜 조약 ({search_results['treaties'].get('totalCnt', 0)})")
        tab_contents.append('treaties')
    
    if 'admin_rules' in search_results:
        tab_names.append(f"📑 행정규칙 ({search_results['admin_rules'].get('totalCnt', 0)})")
        tab_contents.append('admin_rules')
    
    if 'local_laws' in search_results:
        tab_names.append(f"🏛️ 자치법규 ({search_results['local_laws'].get('totalCnt', 0)})")
        tab_contents.append('local_laws')
    
    if tab_names:
        tabs = st.tabs(tab_names)
        
        for idx, (tab, content_type) in enumerate(zip(tabs, tab_contents)):
            with tab:
                if content_type == 'laws':
                    for i, law in enumerate(search_results['laws'].get('results', [])[:10], 1):
                        with st.expander(f"{i}. {law.get('법령명한글', 'N/A')}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**공포일자:** {law.get('공포일자', 'N/A')}")
                                st.write(f"**시행일자:** {law.get('시행일자', 'N/A')}")
                            with col2:
                                st.write(f"**소관부처:** {law.get('소관부처명', 'N/A')}")
                                st.write(f"**법령구분:** {law.get('법령구분명', 'N/A')}")
                
                elif content_type == 'cases':
                    for i, case in enumerate(search_results['cases'].get('cases', [])[:10], 1):
                        with st.expander(f"{i}. {case.get('title', 'N/A')}"):
                            st.write(f"**법원:** {case.get('court', 'N/A')}")
                            st.write(f"**사건번호:** {case.get('case_number', 'N/A')}")
                            st.write(f"**선고일:** {case.get('date', 'N/A')}")
                
                # 다른 컨텐츠 타입들도 유사하게 처리...

# ===========================
# 법령 체계도 다운로드 탭
# ===========================
def render_law_hierarchy_tab():
    """법령 체계도 기반 다운로드 탭"""
    st.header("📥 법령 체계도 다운로드")
    
    clients = get_api_clients()
    if not clients:
        return
    
    hierarchy_manager = clients.get('hierarchy_manager')
    if not hierarchy_manager:
        st.error("법령 체계도 관리자를 초기화할 수 없습니다.")
        return
    
    st.markdown("""
    ### 📋 법령 체계도 기반 완전 다운로드
    
    법령과 관련된 **모든** 하위 법령을 한 번에 다운로드:
    - 시행령, 시행규칙
    - 행정규칙 (훈령, 예규, 고시, 지침, 규정)
    - 자치법규, 별표서식, 위임법령
    """)
    
    # 디버그 모드
    st.session_state.debug_mode = st.checkbox(
        "🔧 디버그 모드", 
        value=False, 
        help="검색 과정의 상세 정보를 표시합니다"
    )
    
    # 법령 검색
    col1, col2 = st.columns([4, 1])
    with col1:
        law_name = st.text_input(
            "법령명 입력",
            placeholder="예: 자본시장과 금융투자업에 관한 법률, 도로교통법",
            key="download_law_name"
        )
    
    with col2:
        st.write("")
        search_btn = st.button("🔍 체계도 조회", type="primary", use_container_width=True)
    
    # 다운로드 옵션
    with st.expander("⚙️ 다운로드 옵션", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**기본 법령**")
            include_decree = st.checkbox("시행령", value=True, key="inc_decree")
            include_rule = st.checkbox("시행규칙", value=True, key="inc_rule")
            include_delegated = st.checkbox("위임법령", value=True, key="inc_delegated")
        
        with col2:
            st.markdown("**행정규칙**")
            include_admin = st.checkbox("행정규칙 전체", value=True, key="inc_admin")
            include_admin_attach = st.checkbox("행정규칙 별표서식", value=True, key="inc_admin_attach")
        
        with col3:
            st.markdown("**기타**")
            include_local = st.checkbox("자치법규", value=True, key="inc_local")
            include_attachments = st.checkbox("법령 별표서식", value=True, key="inc_attach")
    
    col1, col2 = st.columns(2)
    with col1:
        format_option = st.selectbox(
            "다운로드 형식",
            ["markdown", "json", "text"],
            format_func=lambda x: {
                "markdown": "Markdown (.md)",
                "json": "JSON (.json)",
                "text": "Text (.txt)"
            }[x],
            key="format_option"
        )
    
    with col2:
        search_depth = st.selectbox(
            "검색 깊이",
            ["표준", "확장", "최대"],
            index=2,
            key="search_depth"
        )
    
    # 체계도 조회
    if search_btn and law_name:
        with st.spinner(f'"{law_name}" 법령 체계도 조회 중...'):
            try:
                law_searcher = clients['law_searcher']
                
                # 주 법령 검색
                main_law_result = law_searcher.search_laws(query=law_name, display=10)
                
                if main_law_result.get('totalCnt', 0) == 0:
                    st.warning(f"'{law_name}'에 대한 검색 결과가 없습니다.")
                    return
                
                # 검색 결과 표시
                st.markdown("### 🔍 검색된 법령")
                
                laws_to_process = []
                for idx, law in enumerate(main_law_result.get('results', [])[:5], 1):
                    law_id = law.get('법령ID') or law.get('법령일련번호')
                    law_title = law.get('법령명한글', 'N/A')
                    
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"{idx}. {law_title}")
                    with col2:
                        st.write(f"공포: {law.get('공포일자', 'N/A')}")
                    with col3:
                        if st.checkbox("선택", key=f"sel_{idx}", value=idx==1):
                            laws_to_process.append(law)
                
                if laws_to_process:
                    st.markdown("---")
                    
                    # 체계도 조회 버튼
                    if st.button("📊 전체 체계도 조회", key="get_hierarchy"):
                        # 검색 설정
                        config = SearchConfig(
                            include_decree=include_decree,
                            include_rule=include_rule,
                            include_admin_rules=include_admin,
                            include_local=include_local,
                            include_attachments=include_attachments,
                            include_admin_attachments=include_admin_attach,
                            include_delegated=include_delegated,
                            search_depth=search_depth,
                            debug_mode=st.session_state.debug_mode
                        )
                        
                        # 진행률 표시
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # 각 법령에 대해 체계도 검색
                        hierarchy_manager.clear()  # 이전 결과 초기화
                        
                        for i, law in enumerate(laws_to_process):
                            status_text.text(f"검색 중: {law.get('법령명한글', 'N/A')}")
                            progress_bar.progress((i + 1) / len(laws_to_process))
                            
                            # 체계도 검색
                            hierarchy = hierarchy_manager.search_law_hierarchy(law, config)
                            
                            # 결과 표시
                            display_hierarchy_summary(hierarchy, law.get('법령명한글', 'N/A'))
                        
                        status_text.text("검색 완료!")
                        progress_bar.progress(1.0)
                        
                        # 전체 통계
                        total_stats = hierarchy_manager.get_statistics()
                        st.markdown("### 📊 전체 통계")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("총 법령", total_stats['total'])
                        with col2:
                            st.metric("시행령", total_stats['decree'])
                        with col3:
                            st.metric("시행규칙", total_stats['rule'])
                        with col4:
                            st.metric("행정규칙", total_stats['admin'])
                        
                        # 다운로드 버튼
                        st.markdown("### 📥 다운로드")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            # Markdown 다운로드
                            md_content = hierarchy_manager.export_markdown()
                            st.download_button(
                                "📄 Markdown 다운로드",
                                data=md_content,
                                file_name=f"law_hierarchy_{datetime.now().strftime('%Y%m%d')}.md",
                                mime="text/markdown",
                                use_container_width=True
                            )
                        
                        with col2:
                            # ZIP 다운로드
                            zip_data = hierarchy_manager.export_zip(format_type=format_option)
                            st.download_button(
                                "📦 ZIP 다운로드",
                                data=zip_data,
                                file_name=f"law_hierarchy_{datetime.now().strftime('%Y%m%d')}.zip",
                                mime="application/zip",
                                use_container_width=True
                            )
                        
                        with col3:
                            # JSON 다운로드
                            json_data = {
                                'metadata': {
                                    'generated_at': datetime.now().isoformat(),
                                    'statistics': total_stats
                                },
                                'hierarchies': {
                                    name: {
                                        'statistics': h.get_statistics(),
                                        'laws_count': len(h.get_all_laws())
                                    }
                                    for name, h in hierarchy_manager.hierarchies.items()
                                }
                            }
                            st.download_button(
                                "📊 JSON 다운로드",
                                data=json.dumps(json_data, ensure_ascii=False, indent=2),
                                file_name=f"law_hierarchy_{datetime.now().strftime('%Y%m%d')}.json",
                                mime="application/json",
                                use_container_width=True
                            )
                        
                        # 다운로드 이력 저장
                        st.session_state.downloaded_laws.append({
                            'law_name': law_name,
                            'count': total_stats['total'],
                            'timestamp': datetime.now().isoformat()
                        })
                        
            except Exception as e:
                st.error(f"체계도 조회 중 오류 발생: {str(e)}")
                logger.exception(f"Hierarchy search error: {e}")

def display_hierarchy_summary(hierarchy: LawHierarchy, law_name: str):
    """법령 체계도 요약 표시"""
    with st.expander(f"📊 {law_name} 체계도", expanded=True):
        stats = hierarchy.get_statistics()
        
        # 통계 표시
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("시행령", stats['decree'])
        with col2:
            st.metric("시행규칙", stats['rule'])
        with col3:
            st.metric("행정규칙", stats['admin'])
        with col4:
            st.metric("자치법규", stats['local'])
        
        # 상세 내역 (일부만 표시)
        if hierarchy.decree:
            st.write(f"**시행령 ({len(hierarchy.decree)}개)**")
            for decree in hierarchy.decree[:3]:
                st.write(f"  - {decree.get('법령명한글', 'N/A')}")
            if len(hierarchy.decree) > 3:
                st.write(f"  ... 외 {len(hierarchy.decree)-3}개")
        
        if hierarchy.rule:
            st.write(f"**시행규칙 ({len(hierarchy.rule)}개)**")
            for rule in hierarchy.rule[:3]:
                st.write(f"  - {rule.get('법령명한글', 'N/A')}")
            if len(hierarchy.rule) > 3:
                st.write(f"  ... 외 {len(hierarchy.rule)-3}개")
        
        admin_total = hierarchy.admin_rules.total_count()
        if admin_total > 0:
            st.write(f"**행정규칙 ({admin_total}개)**")
            # 카테고리별 표시
            if hierarchy.admin_rules.directive:
                st.write(f"  훈령: {len(hierarchy.admin_rules.directive)}개")
            if hierarchy.admin_rules.regulation:
                st.write(f"  예규: {len(hierarchy.admin_rules.regulation)}개")
            if hierarchy.admin_rules.notice:
                st.write(f"  고시: {len(hierarchy.admin_rules.notice)}개")

# ===========================
# AI 분석 탭
# ===========================
def render_ai_analysis_tab():
    """AI 법률 분석 탭"""
    st.header("🤖 AI 법률 분석")
    
    clients = get_api_clients()
    
    if not clients.get('ai_helper'):
        st.warning("⚠️ OpenAI API가 설정되지 않았습니다.")
        st.info("사이드바에서 OpenAI API 키를 설정해주세요.")
        return
    
    analysis_type = st.selectbox(
        "분석 유형",
        ["법률 상담", "계약서 검토", "법률 문서 분석"],
        key="ai_analysis_type"
    )
    
    # 파일 업로드
    uploaded_file = st.file_uploader(
        "문서 업로드 (선택)",
        type=['pdf', 'txt', 'docx'],
        help="분석할 문서를 업로드하세요",
        key="file_upload"
    )
    
    # 분석 대상 입력
    if analysis_type == "법률 상담":
        question = st.text_area(
            "법률 질문",
            placeholder="구체적인 상황과 질문을 입력하세요...",
            height=150,
            key="legal_question"
        )
        
        auto_search = st.checkbox("관련 법령/판례 자동 검색", value=True)
        
    elif analysis_type == "계약서 검토":
        contract_text = st.text_area(
            "계약서 내용",
            placeholder="검토할 계약서 내용을 입력하세요...",
            height=300,
            key="contract_text"
        )
        
        review_focus = st.multiselect(
            "검토 중점사항",
            ["독소조항", "불공정조항", "법률 위반", "리스크 평가"],
            default=["독소조항", "불공정조항"],
            key="review_focus"
        )
    
    elif analysis_type == "법률 문서 분석":
        document_text = st.text_area(
            "문서 내용",
            placeholder="분석할 법률 문서를 입력하세요...",
            height=300,
            key="document_text"
        )
        
        analysis_focus = st.multiselect(
            "분석 관점",
            ["요약", "핵심 쟁점", "법적 근거", "리스크"],
            default=["요약", "핵심 쟁점"],
            key="analysis_focus"
        )
    
    # AI 분석 실행
    if st.button("🤖 AI 분석 시작", type="primary", key="ai_analyze"):
        with st.spinner('AI가 분석 중입니다...'):
            try:
                ai_helper = clients['ai_helper']
                ai_helper.set_model(st.session_state.selected_model)
                
                # 분석 수행 (각 유형별 처리)
                if analysis_type == "법률 상담" and 'question' in locals():
                    prompt = f"""
                    다음 법률 질문에 대해 전문적인 답변을 제공해주세요.
                    
                    질문: {question}
                    
                    답변 구조:
                    1. 핵심 답변
                    2. 법적 근거
                    3. 실무적 조언
                    4. 주의사항
                    """
                    
                    result = ai_helper.analyze_legal_text(prompt, {})
                    
                    # 결과 표시
                    st.markdown("### 📋 AI 분석 결과")
                    st.markdown(result)
                    
                    # 결과 저장
                    st.session_state.search_history.append({
                        'query': question,
                        'timestamp': datetime.now().isoformat(),
                        'type': 'ai_analysis',
                        'result': result
                    })
                    
            except Exception as e:
                st.error(f"AI 분석 중 오류: {str(e)}")
                logger.exception(f"AI analysis error: {e}")

# ===========================
# 메인 애플리케이션
# ===========================
def main():
    """메인 애플리케이션"""
    
    # 모듈 로드 확인
    if not MODULES_LOADED:
        st.error("필수 모듈을 로드할 수 없습니다.")
        st.code("pip install -r requirements.txt", language="bash")
        return
    
    # 세션 상태 초기화
    init_session_state()
    
    # 사이드바
    render_sidebar()
    
    # 메인 타이틀
    st.title("⚖️ K-Law Assistant Pro")
    st.markdown("**AI 기반 통합 법률 검색 및 분석 시스템**")
    
    # API 키 확인
    if not st.session_state.api_keys.get('law_api_key'):
        st.warning("⚠️ 법제처 API 키가 설정되지 않았습니다.")
        st.info("사이드바에서 API 키를 설정해주세요.")
    
    # 메인 탭
    tabs = st.tabs([
        "🔍 통합 검색",
        "📥 법령 체계도",
        "🤖 AI 분석"
    ])
    
    with tabs[0]:
        render_unified_search_tab()
    
    with tabs[1]:
        render_law_hierarchy_tab()
    
    with tabs[2]:
        render_ai_analysis_tab()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error(f"애플리케이션 실행 중 오류가 발생했습니다: {str(e)}")
        st.info("페이지를 새로고침하거나 관리자에게 문의해주세요.")
