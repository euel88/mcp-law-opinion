"""
K-Law Assistant - 통합 법률 검토 지원 시스템
Main Application with Streamlit UI (Fixed Version 4.0)
API 호출 및 데이터 처리 오류 수정
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

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG로 변경하여 더 많은 정보 확인
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="K-Law Assistant Pro",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom modules import
try:
    from common_api import LawAPIClient, OpenAIHelper
    from law_module import LawSearcher
    from committee_module import CommitteeDecisionSearcher
    from case_module import CaseSearcher, AdvancedCaseSearcher
    from treaty_admin_module import TreatyAdminSearcher
    MODULES_LOADED = True
except ImportError as e:
    MODULES_LOADED = False
    st.error(f"❌ 필수 모듈을 불러올 수 없습니다: {str(e)}")
    st.info("requirements.txt의 패키지를 모두 설치했는지 확인해주세요.")

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
        st.session_state.selected_model = 'o3'
        st.session_state.cache = {}
        st.session_state.api_clients = None
        st.session_state.selected_committees = []
        st.session_state.selected_ministries = []
        logger.info("Session state initialized successfully")

# ========================= API Clients Initialization =========================

@st.cache_resource
def get_api_clients():
    """Initialize and cache all API clients"""
    try:
        law_api_key = st.session_state.api_keys.get('law_api_key', '')
        openai_api_key = st.session_state.api_keys.get('openai_api_key', '')

        # API 키 검증 로깅 추가
        logger.info(f"Initializing API clients...")
        logger.info(f"Law API key exists: {bool(law_api_key)}")
        if law_api_key:
            logger.info(f"Law API key length: {len(law_api_key)}")
            logger.info(f"Law API key preview: {law_api_key[:4]}...{law_api_key[-4:]}")
            
        if not law_api_key:
            st.warning("⚠️ 법제처 API 키가 설정되지 않았습니다.")
            logger.warning("Law API key not found")
            return {}
        
        clients = {}
        
        # 기본 API 클라이언트
        clients['law_client'] = LawAPIClient(oc_key=law_api_key)
        clients['ai_helper'] = OpenAIHelper(api_key=openai_api_key) if openai_api_key else None
        
        # 각 검색 모듈 초기화
        try:
            clients['law_searcher'] = LawSearcher(oc_key=law_api_key)
            logger.info("LawSearcher initialized")
        except Exception as e:
            logger.error(f"LawSearcher init failed: {e}")
            
        try:
            clients['case_searcher'] = CaseSearcher(api_client=clients['law_client'], ai_helper=clients['ai_helper'])
            logger.info("CaseSearcher initialized")
        except Exception as e:
            logger.error(f"CaseSearcher init failed: {e}")
            
        try:
            clients['advanced_case_searcher'] = AdvancedCaseSearcher(api_client=clients['law_client'], ai_helper=clients['ai_helper'])
            logger.info("AdvancedCaseSearcher initialized")
        except Exception as e:
            logger.error(f"AdvancedCaseSearcher init failed: {e}")
            
        try:
            clients['committee_searcher'] = CommitteeDecisionSearcher(api_client=clients['law_client'])
            logger.info("CommitteeDecisionSearcher initialized")
        except Exception as e:
            logger.error(f"CommitteeDecisionSearcher init failed: {e}")
            
        try:
            clients['treaty_admin_searcher'] = TreatyAdminSearcher(oc_key=law_api_key)
            logger.info("TreatyAdminSearcher initialized")
        except Exception as e:
            logger.error(f"TreatyAdminSearcher init failed: {e}")
        
        logger.info(f"API clients initialized: {list(clients.keys())}")
        return clients
        
    except Exception as e:
        logger.error(f"API clients initialization failed: {str(e)}")
        st.error(f"API 클라이언트 초기화 실패: {str(e)}")
        return {}

# ========================= Sidebar UI =========================

def render_sidebar():
    """Enhanced sidebar with all features"""
    with st.sidebar:
        st.title("⚖️ K-Law Assistant Pro")
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
                "OpenAI API Key",
                value=st.session_state.api_keys.get('openai_api_key', ''),
                type="password",
                help="https://platform.openai.com 에서 발급",
                key="sidebar_openai_api_key"
            )
            
            if st.button("API 키 저장", key="save_api_keys"):
                st.session_state.api_keys['law_api_key'] = law_api_key
                st.session_state.api_keys['openai_api_key'] = openai_api_key
                st.cache_resource.clear()
                st.success("API 키가 저장되었습니다!")
                st.rerun()
        
        # GPT 모델 선택
        st.markdown("### 🤖 AI 모델")
        models = {
            'o3': 'o3 (최신)',
            'o3-mini': 'o3-mini',
            'o4-mini': 'o4-mini',
            'o3-pro': 'o3-pro'
        }
        
        st.session_state.selected_model = st.selectbox(
            "모델 선택",
            options=list(models.keys()),
            format_func=lambda x: models[x],
            index=list(models.keys()).index(st.session_state.selected_model),
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
        
        # 검색 이력
        if st.session_state.search_history:
            st.markdown("### 📜 최근 검색")
            for idx, item in enumerate(st.session_state.search_history[-5:][::-1]):
                if st.button(
                    f"🕐 {item['query'][:20]}...",
                    key=f"history_{idx}",
                    use_container_width=True
                ):
                    st.session_state.history_search = item['query']

# ========================= Tab 1: 법령 검색 (26개 API) =========================

def render_law_search_tab():
    """법령 검색 탭 - 26개 API 기능 모두 구현"""
    st.header("📚 법령 검색")
    
    clients = get_api_clients()
    if not clients.get('law_searcher'):
        st.error("법령 검색 모듈을 초기화할 수 없습니다. API 키를 확인해주세요.")
        return
    
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
                
                # 검색 유형별 처리
                if search_type == "현행법령":
                    results = law_searcher.search_laws(
                        query=query,
                        search_type=1 if search_scope == "법령명" else 2,
                        display=display,
                        sort={"법령명 오름차순": "lasc", "법령명 내림차순": "ldes",
                              "공포일자 오름차순": "dasc", "공포일자 내림차순": "ddes"}[sort_option]
                    )
                    logger.debug(f"현행법령 검색 결과: {results}")
                
                elif search_type == "시행일법령":
                    results = law_searcher.search_effective_laws(
                        query=query,
                        search_type=1 if search_scope == "법령명" else 2,
                        display=display
                    )
                
                elif search_type == "영문법령":
                    results = law_searcher.search_english_laws(
                        query=query,
                        search_type=1 if search_scope == "법령명" else 2,
                        display=display
                    )
                
                elif search_type == "법령연혁":
                    results = law_searcher.search_law_history(
                        query=query,
                        display=display
                    )
                
                elif search_type == "법령변경이력":
                    reg_dt = st.date_input("변경일자", datetime.now(), key="law_change_date")
                    if reg_dt:
                        results = law_searcher.search_law_change_history(
                            reg_dt=int(reg_dt.strftime('%Y%m%d')),
                            org=org if org else None,
                            display=display
                        )
                
                elif search_type == "조문별변경이력":
                    law_id = st.number_input("법령 ID", min_value=1, key="law_article_id")
                    jo = st.number_input("조번호", min_value=1, key="law_article_jo")
                    if law_id and jo:
                        results = law_searcher.get_article_change_history(
                            law_id=str(law_id),
                            jo=jo,
                            display=display
                        )
                
                elif search_type == "신구법비교":
                    results = law_searcher.search_old_new_laws(
                        query=query,
                        display=display
                    )
                
                elif search_type == "법령체계도":
                    results = law_searcher.search_law_structure(
                        query=query,
                        display=display
                    )
                
                elif search_type == "3단비교":
                    results = law_searcher.search_three_way_comparison(
                        query=query,
                        display=display
                    )
                
                elif search_type == "위임법령":
                    law_id = st.text_input("법령 ID 또는 MST", key="law_delegated_id")
                    if law_id:
                        results = law_searcher.get_delegated_laws(
                            law_id=law_id
                        )
                
                elif search_type == "법령-자치법규연계":
                    results = law_searcher.search_linked_ordinances(
                        query=query,
                        display=display
                    )
                
                elif search_type == "한눈보기":
                    results = law_searcher.search_oneview(
                        query=query,
                        display=display
                    )
                
                elif search_type == "법령명약칭":
                    results = law_searcher.search_law_abbreviations()
                
                elif search_type == "삭제데이터":
                    results = law_searcher.search_deleted_data(
                        display=display
                    )
                
                elif search_type == "조항호목조회":
                    law_id = st.text_input("법령 ID", key="law_article_detail_id")
                    jo = st.text_input("조번호 (6자리)", key="law_article_detail_jo")
                    if law_id and jo:
                        results = law_searcher.get_law_article_detail(
                            law_id=law_id,
                            jo=jo
                        )
                
                # 결과 표시
                if results:
                    if 'error' not in results:
                        total_count = results.get('totalCnt', 0)
                        st.success(f"✅ {total_count}건의 결과를 찾았습니다.")
                        
                        # 검색 이력 저장
                        if total_count > 0:
                            st.session_state.search_history.append({
                                'query': query,
                                'timestamp': datetime.now().isoformat(),
                                'type': search_type,
                                'count': total_count
                            })
                        
                        # 결과 표시
                        if 'results' in results and results['results']:
                            for idx, item in enumerate(results['results'][:10], 1):
                                with st.expander(f"{idx}. {item.get('법령명한글', item.get('법령명', item.get('title', 'N/A')))}"):
                                    # 기본 정보
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**공포일자:** {item.get('공포일자', 'N/A')}")
                                        st.write(f"**시행일자:** {item.get('시행일자', 'N/A')}")
                                    with col2:
                                        st.write(f"**소관부처:** {item.get('소관부처명', item.get('소관부처', 'N/A'))}")
                                        st.write(f"**법령구분:** {item.get('법령구분명', item.get('법령구분', 'N/A'))}")
                                    
                                    # 상세 조회 버튼
                                    if st.button(f"상세 조회", key=f"law_detail_{search_type}_{idx}"):
                                        detail = law_searcher.get_law_detail(
                                            law_id=item.get('법령ID', item.get('법령일련번호')),
                                            output_type="JSON"
                                        )
                                        st.json(detail)
                        else:
                            st.info("검색 결과가 없습니다. 다른 검색어를 시도해보세요.")
                    else:
                        st.error(f"오류: {results.get('error', '알 수 없는 오류')}")
                        logger.error(f"검색 오류: {results}")
                        
            except Exception as e:
                st.error(f"검색 중 오류 발생: {str(e)}")
                logger.exception(f"법령 검색 예외 발생: {e}")

# ========================= Tab 2: 판례/심판례 검색 =========================

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
                
                logger.info(f"판례 검색 시작: {case_type}, 검색어: {query}")
                
                if case_type == "법원 판례":
                    results = case_searcher.search_court_cases(
                        query=query,
                        court=court if court != "전체" else None,
                        court_name=court_name if court_name else None,
                        search_type=2 if search_in_content else 1,
                        display=display
                    )
                
                elif case_type == "헌재결정례":
                    results = case_searcher.search_constitutional_decisions(
                        query=query,
                        search_type=2 if search_in_content else 1,
                        display=display
                    )
                
                elif case_type == "법령해석례":
                    results = case_searcher.search_legal_interpretations(
                        query=query,
                        search_type=2 if search_in_content else 1,
                        display=display
                    )
                
                elif case_type == "행정심판례":
                    results = case_searcher.search_admin_tribunals(
                        query=query,
                        search_type=2 if search_in_content else 1,
                        display=display
                    )
                
                elif case_type == "통합검색":
                    results = case_searcher.search_all_precedents(
                        query=query,
                        limit_per_type=display // 4,
                        search_in_content=search_in_content
                    )
                
                logger.debug(f"판례 검색 결과: {results}")
                
                # 결과 표시
                if results and results.get('status') == 'success':
                    if case_type == "통합검색":
                        # 통합검색 결과 표시
                        st.success(f"✅ 총 {results['summary']['total']}건의 결과")
                        
                        for result_type, data in results['results'].items():
                            if data['items']:
                                st.subheader(f"{result_type.replace('_', ' ').title()}: {data['total']}건")
                                for idx, item in enumerate(data['items'][:5], 1):
                                    with st.expander(f"{idx}. {item.get('title', 'N/A')}"):
                                        display_case_item(item)
                    else:
                        # 개별 검색 결과 표시
                        total = results.get('total_count', 0)
                        st.success(f"✅ {total}건의 결과를 찾았습니다.")
                        
                        # 검색 이력 저장
                        if total > 0:
                            st.session_state.search_history.append({
                                'query': query,
                                'timestamp': datetime.now().isoformat(),
                                'type': case_type,
                                'count': total
                            })
                        
                        items = results.get('cases') or results.get('decisions') or \
                               results.get('interpretations') or results.get('tribunals', [])
                        
                        if items:
                            for idx, item in enumerate(items[:10], 1):
                                with st.expander(f"{idx}. {item.get('title', 'N/A')}"):
                                    display_case_item(item)
                        else:
                            st.info("검색 결과가 없습니다. 다른 검색어를 시도해보세요.")
                elif results:
                    st.error(f"검색 실패: {results.get('message', results.get('error', '알 수 없는 오류'))}")
                else:
                    st.info("검색 결과가 없습니다.")
                
            except Exception as e:
                st.error(f"검색 중 오류 발생: {str(e)}")
                logger.exception(f"판례 검색 예외 발생: {e}")

# ========================= Tab 3: 위원회 결정문 검색 =========================

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
    
    # 고급 옵션
    with st.expander("고급 검색 옵션"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_type = st.selectbox("검색 범위", ["제목", "본문"], key="committee_search_type")
            display = st.number_input("결과 개수", min_value=1, max_value=100, value=20, key="committee_display")
        
        with col2:
            sort = st.selectbox("정렬", ["최신순", "오래된순", "제목순"], key="committee_sort")
        
        with col3:
            date_from = st.date_input("시작일", key="committee_date_from")
            date_to = st.date_input("종료일", key="committee_date_to")
    
    # 검색 실행
    if st.button("🔍 검색", type="primary", key="committee_search_btn"):
        if not query and not selected_committees:
            st.warning("검색어를 입력하거나 위원회를 선택해주세요.")
            return
        
        with st.spinner('위원회 결정문 검색 중...'):
            try:
                # 선택된 위원회별로 검색
                all_results = {}
                total_count = 0
                
                logger.info(f"위원회 검색 시작: {selected_committees}, 검색어: {query}")
                
                for committee_code in selected_committees:
                    result = committee_searcher.search_by_committee(
                        committee_code=committee_code,
                        query=query,
                        search=2 if search_type == "본문" else 1,
                        display=display,
                        sort={'최신순': 'ddes', '오래된순': 'dasc', '제목순': 'lasc'}[sort]
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
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**위원회:** {decision.get('committee_name')}")
                                    st.write(f"**날짜:** {decision.get('date')}")
                                with col2:
                                    st.write(f"**번호:** {decision.get('number')}")
                                    if decision.get('decision'):
                                        st.write(f"**결정:** {decision['decision']}")
                                
                                # 상세 조회 버튼
                                if st.button(f"상세 조회", key=f"committee_detail_{committee_code}_{idx}"):
                                    detail = committee_searcher.get_decision_detail(
                                        committee_code=committee_code,
                                        decision_id=decision.get('id')
                                    )
                                    if detail['success']:
                                        st.json(detail['detail'])
                
            except Exception as e:
                st.error(f"검색 중 오류 발생: {str(e)}")
                logger.exception(f"위원회 검색 예외 발생: {e}")

# ========================= Tab 4: 조약/행정규칙/자치법규 =========================

def render_treaty_admin_tab():
    """조약, 행정규칙, 자치법규, 별표서식 등 검색"""
    st.header("📜 조약/행정규칙/자치법규")
    
    clients = get_api_clients()
    if not clients.get('treaty_admin_searcher'):
        st.error("조약/행정규칙 검색 모듈을 초기화할 수 없습니다. API 키를 확인해주세요.")
        return
    
    searcher = clients['treaty_admin_searcher']
    
    # 검색 유형 선택
    search_type = st.selectbox(
        "검색 유형",
        ["조약", "행정규칙", "자치법규", "법령 별표서식", "행정규칙 별표서식", 
         "자치법규 별표서식", "학칙", "공단규정", "공공기관규정", "법령용어", 
         "일상용어", "법령해석(부처별)", "특별행정심판재결례"],
        key="treaty_search_type"
    )
    
    # 검색어 입력
    query = st.text_input("검색어", placeholder="검색어를 입력하세요", key="treaty_query")
    
    # 유형별 추가 옵션
    if search_type == "조약":
        col1, col2 = st.columns(2)
        with col1:
            treaty_type = st.selectbox("조약 유형", ["전체", "양자조약", "다자조약"], key="treaty_type")
        with col2:
            nat_cd = st.text_input("국가코드", placeholder="예: US, JP, CN", key="treaty_nat_cd")
    
    elif search_type == "행정규칙" or search_type == "자치법규":
        col1, col2 = st.columns(2)
        with col1:
            org = st.text_input("기관", placeholder="기관명 또는 코드", key="treaty_org")
        with col2:
            if search_type == "행정규칙":
                kind = st.selectbox("종류", ["전체", "훈령", "예규", "고시", "지침"], key="admin_kind")
            else:
                kind = st.selectbox("종류", ["전체", "조례", "규칙", "훈령", "예규"], key="local_kind")
    
    elif "별표서식" in search_type:
        knd = st.selectbox("별표 종류", ["전체", "별표", "서식", "별지", "별도", "부록"], key="attachment_kind")
    
    elif search_type == "법령해석(부처별)":
        ministry = st.selectbox(
            "부처 선택",
            ["고용노동부", "국토교통부", "기획재정부", "해양수산부", 
             "행정안전부", "환경부", "관세청", "국세청"],
            key="ministry_select"
        )
        ministry_codes = {
            "고용노동부": "moelCgmExpc",
            "국토교통부": "molitCgmExpc",
            "기획재정부": "moefCgmExpc",
            "해양수산부": "mofCgmExpc",
            "행정안전부": "moisCgmExpc",
            "환경부": "meCgmExpc",
            "관세청": "kcsCgmExpc",
            "국세청": "ntsCgmExpc"
        }
    
    elif search_type == "특별행정심판재결례":
        tribunal = st.selectbox("심판원", ["조세심판원", "해양안전심판원"], key="tribunal_select")
    
    # 검색 실행
    if st.button("🔍 검색", type="primary", key="treaty_search_btn"):
        if not query:
            st.warning("검색어를 입력해주세요.")
            return
        
        with st.spinner(f'{search_type} 검색 중...'):
            try:
                results = None
                
                logger.info(f"조약/행정규칙 검색 시작: {search_type}, 검색어: {query}")
                
                # 검색 유형별 처리
                if search_type == "조약":
                    cls = None
                    if treaty_type == "양자조약":
                        cls = 1
                    elif treaty_type == "다자조약":
                        cls = 2
                    results = searcher.search_treaties(
                        query=query,
                        cls=cls,
                        nat_cd=nat_cd if nat_cd else None
                    )
                
                elif search_type == "행정규칙":
                    kind_code = {"훈령": 1, "예규": 2, "고시": 3, "지침": 4}.get(kind)
                    results = searcher.search_admin_rules(
                        query=query,
                        org=org if org else None,
                        kind=kind_code
                    )
                
                elif search_type == "자치법규":
                    kind_code = {"조례": 1, "규칙": 2, "훈령": 3, "예규": 4}.get(kind)
                    results = searcher.search_local_laws(
                        query=query,
                        org=org if org else None,
                        kind=kind_code
                    )
                
                elif "별표서식" in search_type:
                    knd_code = {"별표": 1, "서식": 2, "별지": 3, "별도": 4, "부록": 5}.get(knd)
                    
                    if search_type == "법령 별표서식":
                        results = searcher.search_law_attachments(query=query, knd=knd_code)
                    elif search_type == "행정규칙 별표서식":
                        results = searcher.search_admin_attachments(query=query, knd=knd_code)
                    elif search_type == "자치법규 별표서식":
                        results = searcher.search_ordin_attachments(query=query, knd=knd_code)
                
                elif search_type in ["학칙", "공단규정", "공공기관규정"]:
                    target_map = {"학칙": "school", "공단규정": "public", "공공기관규정": "pi"}
                    results = searcher.search_school_public_rules(
                        query=query,
                        target=target_map[search_type]
                    )
                
                elif search_type == "법령용어":
                    results = searcher.search_legal_terms(query=query)
                
                elif search_type == "일상용어":
                    results = searcher.search_daily_terms(query=query)
                
                elif search_type == "법령해석(부처별)":
                    results = searcher.search_ministry_interpretations(
                        query=query,
                        ministry=ministry_codes[ministry]
                    )
                
                elif search_type == "특별행정심판재결례":
                    tribunal_code = "ttSpecialDecc" if tribunal == "조세심판원" else "kmstSpecialDecc"
                    results = searcher.search_special_tribunals(
                        query=query,
                        tribunal=tribunal_code
                    )
                
                logger.debug(f"조약/행정규칙 검색 결과: {results}")
                
                # 결과 표시
                if results:
                    if 'error' not in results:
                        total = results.get('totalCnt', 0)
                        st.success(f"✅ {total}건의 결과를 찾았습니다.")
                        
                        # 결과 아이템 표시
                        items = results.get('treaties') or results.get('rules') or \
                               results.get('ordinances') or results.get('attachments') or \
                               results.get('terms') or results.get('interpretations') or \
                               results.get('decisions') or results.get('results', [])
                        
                        if items:
                            for idx, item in enumerate(items[:10], 1):
                                with st.expander(f"{idx}. {get_item_title(item, search_type)}"):
                                    display_treaty_admin_item(item, search_type)
                        else:
                            st.info("검색 결과가 없습니다. 다른 검색어를 시도해보세요.")
                    else:
                        st.error(f"오류: {results['error']}")
                        
            except Exception as e:
                st.error(f"검색 중 오류 발생: {str(e)}")
                logger.exception(f"조약/행정규칙 검색 예외 발생: {e}")

# ========================= Tab 5: AI 법률 분석 =========================

def render_ai_analysis_tab():
    """AI 법률 분석 탭"""
    st.header("🤖 AI 법률 분석")
    
    clients = get_api_clients()
    
    if not clients.get('ai_helper'):
        st.warning("⚠️ OpenAI API가 설정되지 않았습니다. 사이드바에서 API 키를 설정해주세요.")
        return
    
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
    
    elif analysis_type == "법률 의견서 작성":
        case_facts = st.text_area(
            "사실관계",
            placeholder="사실관계를 상세히 기술하세요...",
            height=200,
            key="ai_case_facts"
        )
        
        legal_issues = st.text_area(
            "법적 쟁점",
            placeholder="검토가 필요한 법적 쟁점을 입력하세요...",
            height=100,
            key="ai_legal_issues"
        )
    
    elif analysis_type == "판례 분석":
        case_info = st.text_area(
            "판례 정보",
            placeholder="판례 내용 또는 사건번호를 입력하세요...",
            height=200,
            key="ai_case_info"
        )
        
        analysis_focus = st.selectbox(
            "분석 관점",
            ["핵심 쟁점", "법리 해석", "판결 의미", "유사 판례 비교"],
            key="ai_analysis_focus"
        )
    
    elif analysis_type == "법령 비교":
        col1, col2 = st.columns(2)
        with col1:
            old_law = st.text_area(
                "구법",
                placeholder="구법 내용...",
                height=200,
                key="ai_old_law"
            )
        with col2:
            new_law = st.text_area(
                "신법",
                placeholder="신법 내용...",
                height=200,
                key="ai_new_law"
            )
    
    elif analysis_type == "위원회 결정 분석":
        decision_text = st.text_area(
            "위원회 결정문",
            placeholder="분석할 위원회 결정문을 입력하세요...",
            height=200,
            key="ai_decision_text"
        )
        
        committee = st.selectbox(
            "위원회",
            ["공정거래위원회", "개인정보보호위원회", "방송통신위원회", "기타"],
            key="ai_committee"
        )
    
    # AI 분석 실행
    if st.button("🤖 AI 분석 시작", type="primary", key="ai_analyze_btn"):
        with st.spinner('AI가 분석 중입니다...'):
            try:
                ai_helper = clients['ai_helper']
                ai_helper.set_model(st.session_state.selected_model)
                
                result = None
                
                if analysis_type == "법률 질문 답변":
                    # 관련 자료 검색
                    context = {}
                    if st.session_state.get('ai_auto_search'):
                        # 실제 검색 수행
                        context = perform_context_search(question, search_targets, clients)
                    
                    result = ai_helper.analyze_legal_text(question, context)
                
                elif analysis_type == "계약서 검토":
                    prompt = f"다음 계약서를 검토해주세요.\n중점사항: {', '.join(review_focus)}\n\n{contract}"
                    result = ai_helper.analyze_legal_text(prompt, {})
                
                elif analysis_type == "법률 의견서 작성":
                    context = {
                        'facts': case_facts,
                        'issues': legal_issues
                    }
                    result = ai_helper.generate_legal_document('opinion', context)
                
                elif analysis_type == "판례 분석":
                    prompt = f"다음 판례를 {analysis_focus} 관점에서 분석해주세요.\n\n{case_info}"
                    result = ai_helper.analyze_legal_text(prompt, {})
                
                elif analysis_type == "법령 비교":
                    result = ai_helper.compare_laws(old_law, new_law)
                
                elif analysis_type == "위원회 결정 분석":
                    decision_data = {
                        'committee_name': committee,
                        'content': decision_text
                    }
                    result = ai_helper.analyze_committee_decision(decision_data)
                
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
                            'result': result
                        })
                        st.success("분석 결과가 저장되었습니다.")
                
            except Exception as e:
                st.error(f"AI 분석 중 오류 발생: {str(e)}")
                logger.exception(f"AI 분석 예외 발생: {e}")

# ========================= Tab 6: 고급 기능 =========================

def render_advanced_features_tab():
    """고급 기능 탭"""
    st.header("🔧 고급 기능")
    
    clients = get_api_clients()
    
    # 기능 선택
    feature = st.selectbox(
        "기능 선택",
        ["법령 체계도", "3단 비교", "신구법 비교", "법령 연혁 조회",
         "조문별 변경이력", "위임법령 조회", "법령-자치법규 연계",
         "한눈보기", "통합 검색", "최근 법령 변경사항"],
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
                        # 체계도 시각화 (간단한 텍스트 표현)
                        for item in result.get('results', [])[:5]:
                            st.write(f"- {item.get('법령명한글', 'N/A')}")
    
    elif feature == "3단 비교":
        st.subheader("🔀 3단 비교")
        law_name = st.text_input("법령명", key="adv_3way_name")
        comparison_type = st.selectbox("비교 종류", ["인용조문", "위임조문"], key="adv_3way_type")
        
        if st.button("3단 비교 실행", key="adv_3way_btn"):
            if law_name and clients.get('law_searcher'):
                with st.spinner('3단 비교 중...'):
                    result = clients['law_searcher'].search_three_way_comparison(law_name)
                    if result and 'error' not in result:
                        st.success(f"✅ 비교 완료")
                        st.json(result)
    
    elif feature == "신구법 비교":
        st.subheader("📑 신구법 비교")
        law_name = st.text_input("법령명", key="adv_oldnew_name")
        
        if st.button("신구법 비교", key="adv_oldnew_btn"):
            if law_name and clients.get('law_searcher'):
                with st.spinner('신구법 비교 중...'):
                    result = clients['law_searcher'].search_old_new_laws(law_name)
                    if result and 'error' not in result:
                        st.success(f"✅ {result.get('totalCnt', 0)}건의 비교 결과")
                        for item in result.get('results', [])[:3]:
                            with st.expander(f"{item.get('법령명한글', 'N/A')}"):
                                st.write(f"구법: {item.get('구법', 'N/A')}")
                                st.write(f"신법: {item.get('신법', 'N/A')}")
    
    elif feature == "법령 연혁 조회":
        st.subheader("📜 법령 연혁")
        law_name = st.text_input("법령명", key="adv_history_name")
        
        if st.button("연혁 조회", key="adv_history_btn"):
            if law_name and clients.get('law_searcher'):
                with st.spinner('연혁 조회 중...'):
                    result = clients['law_searcher'].search_law_history(law_name)
                    if result and 'error' not in result:
                        st.success(f"✅ 연혁 조회 완료")
                        # 연혁 타임라인 표시
                        for item in result.get('results', [])[:10]:
                            st.write(f"📅 {item.get('공포일자', 'N/A')} - {item.get('제개정구분', 'N/A')}")
    
    elif feature == "최근 법령 변경사항":
        st.subheader("🆕 최근 법령 변경사항")
        date = st.date_input("조회 날짜", datetime.now(), key="adv_change_date")
        org = st.text_input("소관부처", placeholder="선택사항", key="adv_change_org")
        
        if st.button("변경사항 조회", key="adv_change_btn"):
            if clients.get('law_searcher'):
                with st.spinner('변경사항 조회 중...'):
                    result = clients['law_searcher'].search_law_change_history(
                        reg_dt=int(date.strftime('%Y%m%d')),
                        org=org if org else None
                    )
                    if result and 'error' not in result:
                        st.success(f"✅ {result.get('totalCnt', 0)}건의 변경사항")
                        for item in result.get('results', [])[:10]:
                            with st.expander(f"{item.get('법령명한글', 'N/A')}"):
                                st.write(f"변경일: {item.get('변경일자', 'N/A')}")
                                st.write(f"변경내용: {item.get('변경내용', 'N/A')}")

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
    
    if item.get('issues'):
        st.write("**판시사항:**")
        st.write(item['issues'][:300] + "..." if len(item.get('issues', '')) > 300 else item['issues'])
    
    if item.get('summary'):
        st.write("**판결요지:**")
        st.write(item['summary'][:300] + "..." if len(item.get('summary', '')) > 300 else item['summary'])

def get_item_title(item: Dict, search_type: str) -> str:
    """검색 결과 아이템의 제목 추출"""
    title_fields = {
        "조약": ["조약명", "조약명한글"],
        "행정규칙": ["행정규칙명", "제목"],
        "자치법규": ["자치법규명", "제목"],
        "법령용어": ["용어명", "법령용어명"],
        "일상용어": ["용어명", "일상용어명"]
    }
    
    for field in title_fields.get(search_type, ["제목", "명칭", "title"]):
        if field in item:
            return item[field]
    
    return str(item)[:50]

def display_treaty_admin_item(item: Dict, search_type: str):
    """조약/행정규칙 등 아이템 표시"""
    # 기본 정보 표시
    info_fields = {
        "조약": [("발효일자", "발효일자"), ("체결일자", "체결일자"), ("국가", "국가명")],
        "행정규칙": [("발령일자", "발령일자"), ("소관부처", "소관부처명"), ("종류", "행정규칙종류")],
        "자치법규": [("발령일자", "발령일자"), ("지자체", "지자체명"), ("종류", "자치법규종류")],
        "법령용어": [("정의", "정의"), ("출처", "출처법령")],
    }
    
    fields = info_fields.get(search_type, [])
    
    if fields:
        col1, col2 = st.columns(2)
        for i, (label, field) in enumerate(fields):
            with col1 if i % 2 == 0 else col2:
                if field in item:
                    st.write(f"**{label}:** {item[field]}")
    
    # 내용 표시
    if "내용" in item:
        st.write("**내용:**")
        content = item["내용"]
        st.write(content[:500] + "..." if len(content) > 500 else content)

def perform_context_search(query: str, targets: List[str], clients: Dict) -> Dict:
    """AI 분석을 위한 컨텍스트 검색 - 실제 데이터만 반환"""
    context = {}
    
    try:
        logger.info(f"Context search for: {query}, targets: {targets}")
        
        if "법령" in targets and clients.get('law_searcher'):
            result = clients['law_searcher'].search_laws(query, display=5)
            logger.debug(f"Law search result: {result}")
            # 실제 결과가 있을 때만 추가
            if result and result.get('totalCnt', 0) > 0 and result.get('results'):
                context['laws'] = result['results']
                logger.info(f"Found {len(result['results'])} laws")
        
        if "판례" in targets and clients.get('case_searcher'):
            result = clients['case_searcher'].search_court_cases(query, display=5)
            logger.debug(f"Case search result: {result}")
            # 실제 결과가 있을 때만 추가
            if result.get('status') == 'success' and result.get('total_count', 0) > 0:
                context['cases'] = result.get('cases', [])
                logger.info(f"Found {len(result.get('cases', []))} cases")
        
        if "해석례" in targets and clients.get('case_searcher'):
            result = clients['case_searcher'].search_legal_interpretations(query, display=5)
            # 실제 결과가 있을 때만 추가
            if result.get('status') == 'success' and result.get('total_count', 0) > 0:
                context['interpretations'] = result.get('interpretations', [])
                logger.info(f"Found {len(result.get('interpretations', []))} interpretations")
        
        if "위원회결정" in targets and clients.get('committee_searcher'):
            result = clients['committee_searcher'].search_all_committees(query, display_per_committee=3)
            # 실제 결과가 있을 때만 추가
            if result.get('success') and result.get('all_decisions'):
                context['committees'] = result.get('all_decisions', [])
                logger.info(f"Found {len(result.get('all_decisions', []))} committee decisions")
    
    except Exception as e:
        logger.error(f"Context search error: {str(e)}")
    
    # 컨텍스트가 비어있으면 명시적으로 표시
    if not context:
        context['no_results'] = True
        logger.warning("No context found for AI analysis")
    
    return context

# ========================= Main Application =========================

def main():
    """Main application with all features"""
    
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
    st.markdown("법령, 판례, 위원회 결정문, 조약 등 모든 법률자료를 통합 검색하고 AI 분석을 제공합니다.")
    
    # API 키 확인
    if not st.session_state.api_keys.get('law_api_key'):
        st.warning("⚠️ 법제처 API 키가 설정되지 않았습니다. 사이드바에서 설정해주세요.")
        st.info("테스트를 위해서는 https://open.law.go.kr 에서 API 키를 발급받아야 합니다.")
    
    # 탭 구성 - 모든 기능 포함
    tabs = st.tabs([
        "📚 법령검색",
        "⚖️ 판례/심판례",
        "🏛️ 위원회결정",
        "📜 조약/행정규칙",
        "🤖 AI 분석",
        "🔧 고급기능",
        "📊 통계",
        "ℹ️ 도움말"
    ])
    
    # Tab 1: 법령 검색 (26개 API)
    with tabs[0]:
        render_law_search_tab()
    
    # Tab 2: 판례/심판례 검색
    with tabs[1]:
        render_case_search_tab()
    
    # Tab 3: 위원회 결정문 검색
    with tabs[2]:
        render_committee_search_tab()
    
    # Tab 4: 조약/행정규칙/자치법규
    with tabs[3]:
        render_treaty_admin_tab()
    
    # Tab 5: AI 법률 분석
    with tabs[4]:
        render_ai_analysis_tab()
    
    # Tab 6: 고급 기능
    with tabs[5]:
        render_advanced_features_tab()
    
    # Tab 7: 통계
    with tabs[6]:
        st.header("📊 검색 통계")
        
        if st.session_state.search_history:
            # 검색 이력 통계
            history_df = pd.DataFrame(st.session_state.search_history)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 검색 수", len(history_df))
            with col2:
                if 'type' in history_df.columns:
                    ai_searches = len(history_df[history_df['type'] == 'ai_analysis'])
                    st.metric("AI 분석", ai_searches)
            with col3:
                if 'timestamp' in history_df.columns:
                    today_searches = len(history_df[pd.to_datetime(history_df['timestamp']).dt.date == datetime.now().date()])
                    st.metric("오늘 검색", today_searches)
            
            # 검색 이력 차트
            st.subheader("검색 추이")
            if 'timestamp' in history_df.columns:
                history_df['date'] = pd.to_datetime(history_df['timestamp']).dt.date
                daily_counts = history_df.groupby('date').size().reset_index(name='count')
                st.line_chart(daily_counts.set_index('date')['count'])
            
            # 최근 검색
            st.subheader("최근 검색 이력")
            display_cols = ['timestamp', 'query', 'type']
            display_cols = [col for col in display_cols if col in history_df.columns]
            if display_cols:
                st.dataframe(history_df[display_cols].tail(10))
        else:
            st.info("아직 검색 이력이 없습니다.")
    
    # Tab 8: 도움말
    with tabs[7]:
        st.header("ℹ️ 사용 가이드")
        
        with st.expander("📚 법령 검색 (26개 기능)"):
            st.markdown("""
            - **현행법령**: 현재 시행 중인 법령 검색
            - **시행일법령**: 특정 시행일 기준 법령 검색
            - **영문법령**: 영문 번역 법령 검색
            - **법령연혁**: 법령의 제·개정 이력 조회
            - **신구법비교**: 개정 전후 법령 비교
            - **3단비교**: 법령-시행령-시행규칙 비교
            - **법령체계도**: 법령 간 관계 시각화
            - **위임법령**: 위임 관계 법령 조회
            - **조항호목**: 특정 조항 상세 조회
            - **한눈보기**: 법령 요약 정보
            - 그 외 20개 이상의 세부 기능
            """)
        
        with st.expander("⚖️ 판례/심판례 검색"):
            st.markdown("""
            - **대법원/하급심 판례**: 법원 판례 검색
            - **헌재결정례**: 헌법재판소 결정 검색
            - **법령해석례**: 법제처 법령해석 검색
            - **행정심판례**: 행정심판 재결례 검색
            - **통합검색**: 모든 유형 동시 검색
            """)
        
        with st.expander("🏛️ 14개 위원회 결정문"):
            st.markdown("""
            - 개인정보보호위원회
            - 공정거래위원회
            - 국민권익위원회
            - 금융위원회
            - 노동위원회
            - 방송통신위원회
            - 중앙환경분쟁조정위원회
            - 국가인권위원회
            - 그 외 6개 위원회
            """)
        
        with st.expander("📜 조약/행정규칙/자치법규"):
            st.markdown("""
            - **조약**: 양자/다자 조약 검색
            - **행정규칙**: 훈령, 예규, 고시, 지침
            - **자치법규**: 조례, 규칙
            - **별표서식**: 법령/행정규칙/자치법규 별표
            - **학칙/공단규정**: 대학, 공공기관 규정
            - **법령용어**: 법령용어 사전
            - **부처별 법령해석**: 8개 부처 해석례
            """)
        
        with st.expander("🤖 AI 법률 분석"):
            st.markdown("""
            - **법률 질문 답변**: 자연어 질문에 대한 AI 답변
            - **계약서 검토**: 독소조항, 불공정조항 검토
            - **법률 의견서**: AI 기반 의견서 작성
            - **판례 분석**: 판례 요약 및 의미 분석
            - **법령 비교**: 신구법 비교 분석
            - **위원회 결정 분석**: 결정문 핵심 분석
            """)
        
        st.info("""
        💡 **Tip**: 
        - 복잡한 법률 문제는 o3-pro 모델을 사용하세요
        - 검색 결과는 자동으로 캐시되어 빠른 재검색이 가능합니다
        - AI 분석 시 관련 법령/판례를 자동으로 검색하여 정확도를 높입니다
        """)
        
        st.warning("""
        ⚠️ **주의사항**:
        - 본 시스템은 법률 정보 제공 목적이며, 법률자문이 아닙니다
        - 중요한 사안은 반드시 법률 전문가와 상담하세요
        - AI 분석 결과는 참고용으로만 활용하세요
        """)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error(f"애플리케이션 실행 중 오류가 발생했습니다: {str(e)}")
        st.info("페이지를 새로고침하거나 관리자에게 문의해주세요.")
