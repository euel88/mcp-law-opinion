"""
K-Law Assistant - 통합 법률 검토 지원 시스템 (체계도 완전 다운로드 버전)
Enhanced Main Application with Complete Law Hierarchy Download
Version 8.0 - Full Hierarchy Download including Administrative Rules
"""

import os
import sys
import json
import time
import zipfile
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
from enum import Enum
import re
import base64

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
    page_title="K-Law Assistant Pro",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/your-repo',
        'Report a bug': 'https://github.com/your-repo/issues',
        'About': 'K-Law Assistant Pro v8.0 - AI 기반 통합 법률 검색 시스템'
    }
)

# Custom modules import with error handling
try:
    from common_api import LawAPIClient, OpenAIHelper
    from law_module import LawSearcher
    from committee_module import CommitteeDecisionSearcher
    from case_module import CaseSearcher, AdvancedCaseSearcher
    from treaty_admin_module import TreatyAdminSearcher
    from nlp_search_module import NaturalLanguageSearchProcessor, SmartSearchOrchestrator
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
        st.session_state.test_mode = False
        st.session_state.nlp_enabled = NLP_MODULE_LOADED
        st.session_state.smart_search_history = []
        st.session_state.downloaded_laws = []
        st.session_state.hierarchy_cache = {}  # 법령 체계도 캐시 추가
        logger.info("Session state initialized successfully")

# ========================= API Clients Initialization =========================

@st.cache_resource
def get_api_clients():
    """Initialize and cache all API clients including NLP processor"""
    try:
        law_api_key = st.session_state.api_keys.get('law_api_key', '')
        openai_api_key = st.session_state.api_keys.get('openai_api_key', '')

        logger.info(f"Initializing API clients...")
        
        if not law_api_key:
            st.warning("⚠️ 법제처 API 키가 설정되지 않았습니다. 사이드바에서 설정해주세요.")
            st.info("테스트를 위해서는 https://open.law.go.kr 에서 무료로 API 키를 발급받으실 수 있습니다.")
            return {}
        
        clients = {}
        
        # 기본 API 클라이언트
        try:
            clients['law_client'] = LawAPIClient(oc_key=law_api_key)
            clients['ai_helper'] = OpenAIHelper(api_key=openai_api_key) if openai_api_key else None
        except Exception as e:
            logger.error(f"Base client init failed: {e}")
            return {}
        
        # 각 검색 모듈 초기화
        try:
            clients['law_searcher'] = LawSearcher(oc_key=law_api_key)
            clients['case_searcher'] = CaseSearcher(api_client=clients.get('law_client'), ai_helper=clients.get('ai_helper'))
            clients['advanced_case_searcher'] = AdvancedCaseSearcher(api_client=clients.get('law_client'), ai_helper=clients.get('ai_helper'))
            clients['committee_searcher'] = CommitteeDecisionSearcher(api_client=clients.get('law_client'))
            clients['treaty_admin_searcher'] = TreatyAdminSearcher(oc_key=law_api_key)
        except Exception as e:
            logger.error(f"Searcher init failed: {e}")
        
        # NLP 프로세서 초기화
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
        st.error(f"API 클라이언트 초기화 실패: {str(e)}")
        return {}

# ========================= Enhanced Law Download Tab with Full Hierarchy =========================

def render_law_download_tab():
    """법령 체계도 기반 완전 일괄 다운로드 탭 (행정규칙 포함)"""
    st.header("📥 법령 일괄 다운로드 (체계도 기반)")
    
    clients = get_api_clients()
    
    if not clients.get('law_searcher'):
        st.error("법령 검색 모듈을 초기화할 수 없습니다.")
        return
    
    st.markdown("""
    ### 📋 법령 체계도 기반 완전 다운로드
    
    법령과 관련된 모든 하위 법령을 한 번에 다운로드할 수 있습니다:
    - **법률** → **시행령** → **시행규칙**
    - **행정규칙** (훈령, 예규, 고시, 지침)
    - **관련 자치법규** (조례, 규칙)
    - **위임 법령** 및 **별표서식**
    """)
    
    # 법령 검색
    col1, col2 = st.columns([4, 1])
    with col1:
        law_name = st.text_input(
            "법령명 입력",
            placeholder="예: 상호저축은행법, 도로교통법, 개인정보보호법",
            key="download_law_name"
        )
    
    with col2:
        st.write("")
        search_btn = st.button("🔍 체계도 조회", type="primary", use_container_width=True, key="search_structure_btn")
    
    # 다운로드 옵션
    with st.expander("⚙️ 다운로드 옵션", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**기본 법령**")
            include_law = st.checkbox("법률", value=True, key="include_law")
            include_decree = st.checkbox("시행령", value=True, key="include_decree")
            include_rule = st.checkbox("시행규칙", value=True, key="include_rule")
        
        with col2:
            st.markdown("**행정규칙**")
            include_directive = st.checkbox("훈령", value=True, key="include_directive")
            include_regulation = st.checkbox("예규", value=True, key="include_regulation")
            include_notice = st.checkbox("고시", value=True, key="include_notice")
            include_guideline = st.checkbox("지침", value=False, key="include_guideline")
        
        with col3:
            st.markdown("**기타**")
            include_local = st.checkbox("자치법규", value=False, key="include_local")
            include_attachments = st.checkbox("별표서식", value=False, key="include_attachments")
            include_history = st.checkbox("법령 연혁", value=False, key="include_history")
            include_delegated = st.checkbox("위임 법령", value=False, key="include_delegated")
    
    col1, col2 = st.columns(2)
    with col1:
        format_option = st.selectbox(
            "다운로드 형식",
            ["Markdown (.md)", "Text (.txt)", "JSON (.json)", "HTML (.html)"],
            key="format_option"
        )
    
    with col2:
        search_depth = st.selectbox(
            "검색 깊이",
            ["1단계 (직접 관련)", "2단계 (확장)", "3단계 (전체)"],
            key="search_depth"
        )
    
    # 체계도 조회 및 다운로드
    if search_btn and law_name:
        with st.spinner(f'"{law_name}" 법령 체계도 조회 중...'):
            try:
                law_searcher = clients['law_searcher']
                treaty_admin_searcher = clients.get('treaty_admin_searcher')
                
                # 1. 주 법령 검색
                main_law_result = law_searcher.search_laws(
                    query=law_name,
                    display=10
                )
                
                if main_law_result.get('totalCnt', 0) == 0:
                    st.warning(f"'{law_name}'에 대한 검색 결과가 없습니다.")
                    return
                
                # 검색 결과 표시
                st.markdown("### 🔍 검색된 법령")
                
                laws_to_download = []
                
                for idx, law in enumerate(main_law_result.get('results', [])[:5], 1):
                    law_id = law.get('법령ID') or law.get('법령일련번호')
                    law_title = law.get('법령명한글', 'N/A')
                    
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"{idx}. {law_title}")
                    with col2:
                        st.write(f"공포: {law.get('공포일자', 'N/A')}")
                    with col3:
                        if st.checkbox("선택", key=f"select_law_{idx}", value=idx==1):
                            laws_to_download.append({
                                'id': law_id,
                                'title': law_title,
                                'law': law
                            })
                
                if laws_to_download:
                    st.markdown("---")
                    
                    # 2. 관련 법령 체계도 조회 (개선된 버전)
                    if st.button("📊 전체 법령 체계도 조회", key="get_full_structure_btn"):
                        with st.spinner("전체 법령 체계도 및 관련 법령 조회 중..."):
                            all_related_laws = []
                            hierarchy_info = {}
                            
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            for selected_law in laws_to_download:
                                st.markdown(f"#### 📋 {selected_law['title']} 관련 법령 체계")
                                
                                # 체계도 정보 초기화
                                hierarchy_info[selected_law['title']] = {
                                    'main': selected_law['law'],
                                    'decree': [],
                                    'rule': [],
                                    'admin_rules': {
                                        'directive': [],  # 훈령
                                        'regulation': [],  # 예규
                                        'notice': [],      # 고시
                                        'guideline': []    # 지침
                                    },
                                    'local_laws': [],
                                    'attachments': [],
                                    'delegated': []
                                }
                                
                                # 주 법령 포함
                                related_laws = [selected_law['law']]
                                base_name = selected_law['title'].replace('법', '').strip()
                                
                                # 진행상황 업데이트
                                status_text.text("법령 체계도 조회 중...")
                                progress_bar.progress(0.1)
                                
                                # 법령 체계도 및 위임 법령 조회
                                try:
                                    if include_delegated:
                                        delegated = law_searcher.get_delegated_laws(law_id=selected_law['id'])
                                        if delegated and 'error' not in delegated:
                                            hierarchy_info[selected_law['title']]['delegated'].append(delegated)
                                    
                                    structure = law_searcher.get_law_structure_detail(law_id=selected_law['id'])
                                    if structure and 'error' not in structure:
                                        st.info("✅ 법령 체계도 조회 완료")
                                except Exception as e:
                                    logger.error(f"체계도 조회 실패: {e}")
                                
                                # 시행령 검색
                                if include_decree:
                                    status_text.text("시행령 검색 중...")
                                    progress_bar.progress(0.2)
                                    
                                    for search_term in [f"{base_name} 시행령", f"{base_name}법 시행령", f"{selected_law['title']} 시행령"]:
                                        decree_result = law_searcher.search_laws(
                                            query=search_term,
                                            display=10
                                        )
                                        if decree_result.get('results'):
                                            for decree in decree_result['results']:
                                                if '시행령' in decree.get('법령명한글', ''):
                                                    hierarchy_info[selected_law['title']]['decree'].append(decree)
                                                    related_laws.append(decree)
                                
                                # 시행규칙 검색
                                if include_rule:
                                    status_text.text("시행규칙 검색 중...")
                                    progress_bar.progress(0.3)
                                    
                                    for search_term in [f"{base_name} 시행규칙", f"{base_name}법 시행규칙", f"{selected_law['title']} 시행규칙"]:
                                        rule_result = law_searcher.search_laws(
                                            query=search_term,
                                            display=10
                                        )
                                        if rule_result.get('results'):
                                            for rule in rule_result['results']:
                                                if '시행규칙' in rule.get('법령명한글', ''):
                                                    hierarchy_info[selected_law['title']]['rule'].append(rule)
                                                    related_laws.append(rule)
                                
                                # 행정규칙 검색 (세분화)
                                if treaty_admin_searcher:
                                    # 훈령 검색
                                    if include_directive:
                                        status_text.text("훈령 검색 중...")
                                        progress_bar.progress(0.4)
                                        
                                        directive_result = treaty_admin_searcher.search_admin_rules(
                                            query=base_name,
                                            kind=1,  # 훈령
                                            display=20
                                        )
                                        if directive_result.get('totalCnt', 0) > 0:
                                            directives = directive_result.get('rules', directive_result.get('results', []))
                                            hierarchy_info[selected_law['title']]['admin_rules']['directive'].extend(directives)
                                            related_laws.extend(directives)
                                    
                                    # 예규 검색
                                    if include_regulation:
                                        status_text.text("예규 검색 중...")
                                        progress_bar.progress(0.5)
                                        
                                        regulation_result = treaty_admin_searcher.search_admin_rules(
                                            query=base_name,
                                            kind=2,  # 예규
                                            display=20
                                        )
                                        if regulation_result.get('totalCnt', 0) > 0:
                                            regulations = regulation_result.get('rules', regulation_result.get('results', []))
                                            hierarchy_info[selected_law['title']]['admin_rules']['regulation'].extend(regulations)
                                            related_laws.extend(regulations)
                                    
                                    # 고시 검색
                                    if include_notice:
                                        status_text.text("고시 검색 중...")
                                        progress_bar.progress(0.6)
                                        
                                        notice_result = treaty_admin_searcher.search_admin_rules(
                                            query=base_name,
                                            kind=3,  # 고시
                                            display=20
                                        )
                                        if notice_result.get('totalCnt', 0) > 0:
                                            notices = notice_result.get('rules', notice_result.get('results', []))
                                            hierarchy_info[selected_law['title']]['admin_rules']['notice'].extend(notices)
                                            related_laws.extend(notices)
                                    
                                    # 지침 검색
                                    if include_guideline:
                                        status_text.text("지침 검색 중...")
                                        progress_bar.progress(0.7)
                                        
                                        guideline_result = treaty_admin_searcher.search_admin_rules(
                                            query=base_name,
                                            kind=4,  # 지침
                                            display=20
                                        )
                                        if guideline_result.get('totalCnt', 0) > 0:
                                            guidelines = guideline_result.get('rules', guideline_result.get('results', []))
                                            hierarchy_info[selected_law['title']]['admin_rules']['guideline'].extend(guidelines)
                                            related_laws.extend(guidelines)
                                    
                                    # 자치법규 검색
                                    if include_local:
                                        status_text.text("자치법규 검색 중...")
                                        progress_bar.progress(0.8)
                                        
                                        local_result = treaty_admin_searcher.search_local_laws(
                                            query=base_name,
                                            display=20
                                        )
                                        if local_result.get('totalCnt', 0) > 0:
                                            local_laws = local_result.get('ordinances', local_result.get('results', []))
                                            hierarchy_info[selected_law['title']]['local_laws'].extend(local_laws)
                                            related_laws.extend(local_laws)
                                    
                                    # 별표서식 검색
                                    if include_attachments:
                                        status_text.text("별표서식 검색 중...")
                                        progress_bar.progress(0.9)
                                        
                                        # 법령 별표서식
                                        law_attach_result = treaty_admin_searcher.search_law_attachments(
                                            query=base_name,
                                            display=10
                                        )
                                        if law_attach_result.get('totalCnt', 0) > 0:
                                            attachments = law_attach_result.get('attachments', law_attach_result.get('results', []))
                                            hierarchy_info[selected_law['title']]['attachments'].extend(attachments)
                                            related_laws.extend(attachments)
                                        
                                        # 행정규칙 별표서식
                                        admin_attach_result = treaty_admin_searcher.search_admin_attachments(
                                            query=base_name,
                                            display=10
                                        )
                                        if admin_attach_result.get('totalCnt', 0) > 0:
                                            admin_attachments = admin_attach_result.get('attachments', admin_attach_result.get('results', []))
                                            hierarchy_info[selected_law['title']]['attachments'].extend(admin_attachments)
                                            related_laws.extend(admin_attachments)
                                
                                # 중복 제거
                                unique_laws = []
                                seen_ids = set()
                                for law in related_laws:
                                    law_id = (law.get('법령ID') or law.get('법령일련번호') or 
                                             law.get('행정규칙ID') or law.get('자치법규ID') or
                                             law.get('별표서식ID') or str(law.get('법령명한글', '')) + str(law.get('행정규칙명', '')))
                                    if law_id and law_id not in seen_ids:
                                        seen_ids.add(law_id)
                                        unique_laws.append(law)
                                
                                all_related_laws.extend(unique_laws)
                                
                                # 진행 완료
                                progress_bar.progress(1.0)
                                status_text.text("검색 완료!")
                                
                                # 체계도 표시
                                display_hierarchy_tree(hierarchy_info[selected_law['title']], selected_law['title'])
                            
                            # 3. 통계 및 다운로드 준비
                            if all_related_laws:
                                st.markdown("---")
                                st.markdown(f"### 💾 다운로드 준비 완료")
                                
                                # 통계 표시
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("총 법령 수", f"{len(all_related_laws)}개")
                                with col2:
                                    law_count = sum(1 for l in all_related_laws if '법률' in str(l.get('법령구분명', '')))
                                    st.metric("법률", f"{law_count}개")
                                with col3:
                                    decree_count = sum(1 for l in all_related_laws if '시행령' in str(l.get('법령명한글', '')))
                                    st.metric("시행령", f"{decree_count}개")
                                with col4:
                                    admin_count = sum(1 for l in all_related_laws if l.get('행정규칙명'))
                                    st.metric("행정규칙", f"{admin_count}개")
                                
                                # 다운로드 버튼
                                st.markdown("### 📥 다운로드")
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    # Markdown 형식 다운로드
                                    if format_option == "Markdown (.md)":
                                        md_content = generate_enhanced_laws_markdown(
                                            all_related_laws, 
                                            hierarchy_info,
                                            law_searcher, 
                                            include_history
                                        )
                                        st.download_button(
                                            "📄 Markdown 다운로드",
                                            data=md_content,
                                            file_name=f"{law_name}_complete_hierarchy_{datetime.now().strftime('%Y%m%d')}.md",
                                            mime="text/markdown",
                                            key="download_md",
                                            use_container_width=True
                                        )
                                
                                with col2:
                                    # ZIP 파일로 개별 다운로드
                                    zip_buffer = create_enhanced_laws_zip(
                                        all_related_laws,
                                        hierarchy_info,
                                        law_searcher,
                                        format_option,
                                        include_history
                                    )
                                    st.download_button(
                                        "📦 ZIP 다운로드 (개별 파일)",
                                        data=zip_buffer,
                                        file_name=f"{law_name}_complete_hierarchy_{datetime.now().strftime('%Y%m%d')}.zip",
                                        mime="application/zip",
                                        key="download_zip",
                                        use_container_width=True
                                    )
                                
                                with col3:
                                    # JSON 형식 다운로드
                                    json_data = {
                                        'metadata': {
                                            'search_query': law_name,
                                            'total_count': len(all_related_laws),
                                            'download_date': datetime.now().isoformat(),
                                            'hierarchy': hierarchy_info
                                        },
                                        'laws': all_related_laws
                                    }
                                    json_content = json.dumps(json_data, ensure_ascii=False, indent=2)
                                    st.download_button(
                                        "📊 JSON 다운로드",
                                        data=json_content,
                                        file_name=f"{law_name}_complete_hierarchy_{datetime.now().strftime('%Y%m%d')}.json",
                                        mime="application/json",
                                        key="download_json_file",
                                        use_container_width=True
                                    )
                                
                                # 다운로드 이력 저장
                                st.session_state.downloaded_laws.append({
                                    'law_name': law_name,
                                    'count': len(all_related_laws),
                                    'hierarchy': hierarchy_info,
                                    'timestamp': datetime.now().isoformat()
                                })
                                
                                # 체계도 캐시 저장
                                st.session_state.hierarchy_cache[law_name] = hierarchy_info
                
            except Exception as e:
                st.error(f"법령 체계도 조회 중 오류 발생: {str(e)}")
                logger.exception(f"Law structure search error: {e}")

def display_hierarchy_tree(hierarchy: Dict, law_name: str):
    """법령 체계도를 트리 형태로 표시"""
    with st.expander(f"📊 {law_name} 법령 체계도", expanded=True):
        # 주 법령
        st.markdown(f"**📚 주 법령**")
        st.write(f"└─ {hierarchy['main'].get('법령명한글', 'N/A')}")
        
        # 시행령
        if hierarchy['decree']:
            st.markdown(f"**📘 시행령 ({len(hierarchy['decree'])}개)**")
            for decree in hierarchy['decree']:
                st.write(f"  └─ {decree.get('법령명한글', 'N/A')}")
        
        # 시행규칙
        if hierarchy['rule']:
            st.markdown(f"**📗 시행규칙 ({len(hierarchy['rule'])}개)**")
            for rule in hierarchy['rule']:
                st.write(f"  └─ {rule.get('법령명한글', 'N/A')}")
        
        # 행정규칙
        admin_total = sum(len(v) for v in hierarchy['admin_rules'].values())
        if admin_total > 0:
            st.markdown(f"**📑 행정규칙 ({admin_total}개)**")
            
            if hierarchy['admin_rules']['directive']:
                st.write(f"  **훈령 ({len(hierarchy['admin_rules']['directive'])}개)**")
                for item in hierarchy['admin_rules']['directive'][:5]:
                    st.write(f"    └─ {item.get('행정규칙명', 'N/A')}")
                if len(hierarchy['admin_rules']['directive']) > 5:
                    st.write(f"    ... 외 {len(hierarchy['admin_rules']['directive'])-5}개")
            
            if hierarchy['admin_rules']['regulation']:
                st.write(f"  **예규 ({len(hierarchy['admin_rules']['regulation'])}개)**")
                for item in hierarchy['admin_rules']['regulation'][:5]:
                    st.write(f"    └─ {item.get('행정규칙명', 'N/A')}")
                if len(hierarchy['admin_rules']['regulation']) > 5:
                    st.write(f"    ... 외 {len(hierarchy['admin_rules']['regulation'])-5}개")
            
            if hierarchy['admin_rules']['notice']:
                st.write(f"  **고시 ({len(hierarchy['admin_rules']['notice'])}개)**")
                for item in hierarchy['admin_rules']['notice'][:5]:
                    st.write(f"    └─ {item.get('행정규칙명', 'N/A')}")
                if len(hierarchy['admin_rules']['notice']) > 5:
                    st.write(f"    ... 외 {len(hierarchy['admin_rules']['notice'])-5}개")
            
            if hierarchy['admin_rules']['guideline']:
                st.write(f"  **지침 ({len(hierarchy['admin_rules']['guideline'])}개)**")
                for item in hierarchy['admin_rules']['guideline'][:5]:
                    st.write(f"    └─ {item.get('행정규칙명', 'N/A')}")
                if len(hierarchy['admin_rules']['guideline']) > 5:
                    st.write(f"    ... 외 {len(hierarchy['admin_rules']['guideline'])-5}개")
        
        # 자치법규
        if hierarchy['local_laws']:
            st.markdown(f"**🏛️ 자치법규 ({len(hierarchy['local_laws'])}개)**")
            for local in hierarchy['local_laws'][:5]:
                st.write(f"  └─ {local.get('자치법규명', 'N/A')} ({local.get('지자체명', '')})")
            if len(hierarchy['local_laws']) > 5:
                st.write(f"  ... 외 {len(hierarchy['local_laws'])-5}개")
        
        # 별표서식
        if hierarchy['attachments']:
            st.markdown(f"**📎 별표서식 ({len(hierarchy['attachments'])}개)**")
            for attach in hierarchy['attachments'][:5]:
                name = attach.get('별표서식명', attach.get('별표명', 'N/A'))
                st.write(f"  └─ {name}")
            if len(hierarchy['attachments']) > 5:
                st.write(f"  ... 외 {len(hierarchy['attachments'])-5}개")

def generate_enhanced_laws_markdown(laws: List[Dict], hierarchy_info: Dict, law_searcher, include_history: bool) -> str:
    """법령을 체계도 기반으로 구조화된 마크다운으로 변환"""
    md_content = f"# 법령 체계도 기반 통합 문서\n\n"
    md_content += f"**생성일시:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    md_content += f"**총 법령 수:** {len(laws)}개\n\n"
    md_content += "---\n\n"
    
    # 체계도 요약
    if hierarchy_info:
        md_content += "## 📊 법령 체계도 요약\n\n"
        for main_law, hierarchy in hierarchy_info.items():
            md_content += f"### {main_law}\n\n"
            md_content += f"- **시행령:** {len(hierarchy.get('decree', []))}개\n"
            md_content += f"- **시행규칙:** {len(hierarchy.get('rule', []))}개\n"
            admin_total = sum(len(v) for v in hierarchy.get('admin_rules', {}).values())
            md_content += f"- **행정규칙:** {admin_total}개\n"
            md_content += f"  - 훈령: {len(hierarchy.get('admin_rules', {}).get('directive', []))}개\n"
            md_content += f"  - 예규: {len(hierarchy.get('admin_rules', {}).get('regulation', []))}개\n"
            md_content += f"  - 고시: {len(hierarchy.get('admin_rules', {}).get('notice', []))}개\n"
            md_content += f"  - 지침: {len(hierarchy.get('admin_rules', {}).get('guideline', []))}개\n"
            md_content += f"- **자치법규:** {len(hierarchy.get('local_laws', []))}개\n"
            md_content += f"- **별표서식:** {len(hierarchy.get('attachments', []))}개\n\n"
        md_content += "---\n\n"
    
    # 법령별 상세 내용
    md_content += "## 📚 법령 상세 내용\n\n"
    
    # 카테고리별로 정리
    categories = {
        '법률': [],
        '시행령': [],
        '시행규칙': [],
        '행정규칙': [],
        '자치법규': [],
        '기타': []
    }
    
    for law in laws:
        if law.get('법령구분명'):
            if '법률' in law['법령구분명']:
                categories['법률'].append(law)
            elif '시행령' in law.get('법령명한글', ''):
                categories['시행령'].append(law)
            elif '시행규칙' in law.get('법령명한글', ''):
                categories['시행규칙'].append(law)
            else:
                categories['기타'].append(law)
        elif law.get('행정규칙명'):
            categories['행정규칙'].append(law)
        elif law.get('자치법규명'):
            categories['자치법규'].append(law)
        else:
            categories['기타'].append(law)
    
    # 각 카테고리별로 출력
    for category_name, category_laws in categories.items():
        if category_laws:
            md_content += f"### 📋 {category_name} ({len(category_laws)}개)\n\n"
            
            for idx, law in enumerate(category_laws, 1):
                law_id = law.get('법령ID') or law.get('법령일련번호')
                law_name = law.get('법령명한글') or law.get('행정규칙명') or law.get('자치법규명', 'N/A')
                
                md_content += f"#### {idx}. {law_name}\n\n"
                
                # 메타데이터
                if law.get('공포일자'):
                    md_content += f"- **공포일자:** {law.get('공포일자')}\n"
                if law.get('시행일자'):
                    md_content += f"- **시행일자:** {law.get('시행일자')}\n"
                if law.get('발령일자'):
                    md_content += f"- **발령일자:** {law.get('발령일자')}\n"
                if law.get('소관부처명'):
                    md_content += f"- **소관부처:** {law.get('소관부처명')}\n"
                if law.get('지자체명'):
                    md_content += f"- **지자체:** {law.get('지자체명')}\n"
                
                md_content += "\n"
                
                # 본문 조회 (법령만)
                if law_id and category_name in ['법률', '시행령', '시행규칙']:
                    try:
                        detail = law_searcher.get_law_detail(law_id=law_id)
                        if detail and 'error' not in detail:
                            content = detail.get('조문내용', detail.get('법령내용', ''))
                            if content:
                                md_content += "##### 조문 내용\n\n"
                                md_content += content[:10000]  # 처음 10000자만
                                if len(content) > 10000:
                                    md_content += "\n\n... (이하 생략)\n"
                            md_content += "\n\n"
                    except Exception as e:
                        logger.error(f"법령 상세 조회 실패: {e}")
                
                md_content += "---\n\n"
    
    return md_content

def create_enhanced_laws_zip(laws: List[Dict], hierarchy_info: Dict, law_searcher, format_option: str, include_history: bool) -> bytes:
    """법령을 체계도 기반으로 구조화된 ZIP 파일로 압축"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # 폴더 구조 생성
        folders = {
            '01_법률': [],
            '02_시행령': [],
            '03_시행규칙': [],
            '04_행정규칙/훈령': [],
            '04_행정규칙/예규': [],
            '04_행정규칙/고시': [],
            '04_행정규칙/지침': [],
            '05_자치법규': [],
            '06_별표서식': [],
            '99_기타': []
        }
        
        # 법령 분류
        for law in laws:
            if law.get('법령구분명'):
                if '법률' in law['법령구분명']:
                    folders['01_법률'].append(law)
                elif '시행령' in law.get('법령명한글', ''):
                    folders['02_시행령'].append(law)
                elif '시행규칙' in law.get('법령명한글', ''):
                    folders['03_시행규칙'].append(law)
                else:
                    folders['99_기타'].append(law)
            elif law.get('행정규칙명'):
                rule_name = law.get('행정규칙명', '')
                if '훈령' in rule_name or law.get('행정규칙종류') == '훈령':
                    folders['04_행정규칙/훈령'].append(law)
                elif '예규' in rule_name or law.get('행정규칙종류') == '예규':
                    folders['04_행정규칙/예규'].append(law)
                elif '고시' in rule_name or law.get('행정규칙종류') == '고시':
                    folders['04_행정규칙/고시'].append(law)
                elif '지침' in rule_name or law.get('행정규칙종류') == '지침':
                    folders['04_행정규칙/지침'].append(law)
                else:
                    folders['04_행정규칙/훈령'].append(law)  # 기본값
            elif law.get('자치법규명'):
                folders['05_자치법규'].append(law)
            elif law.get('별표서식명') or law.get('별표명'):
                folders['06_별표서식'].append(law)
            else:
                folders['99_기타'].append(law)
        
        # 각 폴더별로 파일 생성
        for folder_path, folder_laws in folders.items():
            if folder_laws:
                for idx, law in enumerate(folder_laws, 1):
                    law_id = law.get('법령ID') or law.get('법령일련번호')
                    law_name = (law.get('법령명한글') or law.get('행정규칙명') or 
                               law.get('자치법규명') or law.get('별표서식명') or 'N/A')
                    
                    # 파일명 정리 (특수문자 제거)
                    safe_name = re.sub(r'[<>:"/\\|?*]', '_', law_name)[:100]  # 파일명 길이 제한
                    
                    if format_option == "Markdown (.md)":
                        file_ext = "md"
                        content = f"# {law_name}\n\n"
                        content += f"**공포일자:** {law.get('공포일자', law.get('발령일자', 'N/A'))}\n"
                        content += f"**시행일자:** {law.get('시행일자', 'N/A')}\n"
                        content += f"**소관부처:** {law.get('소관부처명', law.get('지자체명', 'N/A'))}\n\n"
                        
                        # 법령 본문 조회
                        if law_id and '행정규칙' not in folder_path and '자치법규' not in folder_path:
                            try:
                                detail = law_searcher.get_law_detail(law_id=law_id)
                                if detail and 'error' not in detail:
                                    content += "## 조문 내용\n\n"
                                    content += detail.get('조문내용', detail.get('법령내용', ''))
                            except:
                                pass
                    
                    elif format_option == "HTML (.html)":
                        file_ext = "html"
                        content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{law_name}</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; padding: 20px; }}
        h1 {{ color: #333; }}
        .metadata {{ background: #f5f5f5; padding: 10px; margin: 10px 0; }}
    </style>
</head>
<body>
    <h1>{law_name}</h1>
    <div class="metadata">
        <p><strong>공포일자:</strong> {law.get('공포일자', law.get('발령일자', 'N/A'))}</p>
        <p><strong>시행일자:</strong> {law.get('시행일자', 'N/A')}</p>
        <p><strong>소관부처:</strong> {law.get('소관부처명', law.get('지자체명', 'N/A'))}</p>
    </div>
"""
                        if law_id:
                            try:
                                detail = law_searcher.get_law_detail(law_id=law_id)
                                if detail and 'error' not in detail:
                                    content += f"<h2>조문 내용</h2>\n<pre>{detail.get('조문내용', '')}</pre>"
                            except:
                                pass
                        content += "</body></html>"
                    
                    elif format_option == "Text (.txt)":
                        file_ext = "txt"
                        content = f"{law_name}\n"
                        content += "=" * 50 + "\n"
                        content += f"공포일자: {law.get('공포일자', law.get('발령일자', 'N/A'))}\n"
                        content += f"시행일자: {law.get('시행일자', 'N/A')}\n"
                        content += f"소관부처: {law.get('소관부처명', law.get('지자체명', 'N/A'))}\n\n"
                    
                    else:  # JSON
                        file_ext = "json"
                        content = json.dumps(law, ensure_ascii=False, indent=2)
                    
                    # ZIP에 파일 추가
                    file_name = f"{folder_path}/{idx:03d}_{safe_name}.{file_ext}"
                    zip_file.writestr(file_name, content.encode('utf-8'))
        
        # 메타데이터 파일 추가
        metadata = {
            'generated_at': datetime.now().isoformat(),
            'total_files': len(laws),
            'hierarchy': hierarchy_info,
            'statistics': {
                folder: len(items) for folder, items in folders.items() if items
            }
        }
        zip_file.writestr('00_metadata.json', json.dumps(metadata, ensure_ascii=False, indent=2).encode('utf-8'))
        
        # README 파일 추가
        readme_content = f"""# 법령 체계도 기반 통합 다운로드

생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}
총 파일 수: {len(laws)}개

## 폴더 구조
- 01_법률: 기본 법률
- 02_시행령: 법률 시행령
- 03_시행규칙: 법률 시행규칙
- 04_행정규칙: 훈령, 예규, 고시, 지침
- 05_자치법규: 지방자치단체 조례, 규칙
- 06_별표서식: 법령 별표 및 서식
- 99_기타: 분류되지 않은 법령

## 파일 형식
- 형식: {format_option}
- 인코딩: UTF-8
"""
        zip_file.writestr('00_README.md', readme_content.encode('utf-8'))
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

# ========================= Other Functions (Unchanged) =========================

def render_unified_search_tab():
    """통합 스마트 검색 탭 - 모든 검색 기능 통합"""
    st.header("🔍 통합 스마트 검색")
    
    clients = get_api_clients()
    
    # 검색 안내
    with st.expander("💡 통합 검색 사용법", expanded=False):
        st.markdown("""
        ### 🎯 자연어 검색 예시
        - ✅ "음주운전 처벌 기준"
        - ✅ "부당해고 구제 방법"
        - ✅ "전세보증금 못 받을 때"
        - ✅ "개인정보 유출 손해배상"
        
        ### 📚 직접 검색 예시
        - 법령: "도로교통법", "근로기준법 제23조"
        - 판례: "대법원 2023다12345", "음주운전 판례"
        - 유권해석: "법제처 해석", "개인정보보호위원회 결정"
        - 위원회: "공정거래위원회 의결", "국가인권위원회"
        - 조약/행정규칙: "FTA", "시행규칙", "훈령"
        
        ### 🔍 검색 팁
        - 구체적인 상황을 설명하면 더 정확한 결과를 얻을 수 있습니다
        - 법령명이나 조문 번호를 알면 직접 입력하세요
        - 날짜 범위를 지정하면 최신 자료를 우선 검색합니다
        """)
    
    # 검색 입력 영역
    col1, col2 = st.columns([5, 1])
    with col1:
        search_query = st.text_area(
            "검색어 또는 질문을 입력하세요",
            placeholder="예: 음주운전 처벌 기준 / 근로기준법 / 대법원 판례 / 개인정보보호위원회 결정",
            height=100,
            key="unified_search_query"
        )
    
    with col2:
        st.write("")
        st.write("")
        search_btn = st.button("🔍 검색", type="primary", use_container_width=True, key="unified_search_btn")
    
    # 검색 옵션
    with st.expander("⚙️ 검색 옵션", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_targets = st.multiselect(
                "검색 대상",
                ["법령", "판례", "헌재결정", "유권해석", "위원회결정", "조약", "행정규칙", "자치법규"],
                default=["법령", "판례", "유권해석"],
                key="search_targets"
            )
        
        with col2:
            date_range = st.selectbox(
                "기간 설정",
                ["전체", "최근 1년", "최근 3년", "최근 5년", "직접 입력"],
                key="date_range_option"
            )
            
            if date_range == "직접 입력":
                start_date = st.date_input("시작일", key="start_date")
                end_date = st.date_input("종료일", key="end_date")
        
        with col3:
            sort_option = st.selectbox(
                "정렬 기준",
                ["관련도순", "최신순", "오래된순", "이름순"],
                key="sort_option"
            )
            
            search_in_content = st.checkbox("본문 검색 포함", value=False, key="content_search")
    
    # 빠른 검색 예시
    st.markdown("### 🚀 빠른 검색")
    
    # 주제별 예시
    example_categories = {
        "노동": ["부당해고", "임금체불", "산업재해", "퇴직금"],
        "부동산": ["전세보증금", "매매계약", "임대차보호", "재개발"],
        "교통": ["음주운전", "교통사고", "무면허운전", "신호위반"],
        "민사": ["손해배상", "계약위반", "소유권", "채권채무"],
        "형사": ["폭행", "사기", "절도", "명예훼손"],
        "가족": ["이혼", "양육권", "상속", "혼인"]
    }
    
    selected_category = st.selectbox("주제 선택", list(example_categories.keys()), key="category_select")
    
    cols = st.columns(4)
    for idx, example in enumerate(example_categories[selected_category]):
        with cols[idx % 4]:
            if st.button(example, key=f"ex_{selected_category}_{idx}", use_container_width=True):
                st.session_state.unified_search_query = example
                st.rerun()
    
    # 검색 실행
    if search_btn and search_query:
        with st.spinner('🔍 통합 검색 중... (법령, 판례, 유권해석 등)'):
            try:
                # NLP 분석 여부 결정
                is_natural_language = detect_query_type(search_query)
                
                if is_natural_language and st.session_state.get('nlp_enabled'):
                    # 자연어 처리
                    execute_smart_search(search_query, search_targets, clients)
                else:
                    # 키워드 기반 검색
                    execute_keyword_search(search_query, search_targets, clients)
                
                # 검색 이력 저장
                st.session_state.search_history.append({
                    'query': search_query,
                    'timestamp': datetime.now().isoformat(),
                    'type': 'unified_search',
                    'natural_language': is_natural_language
                })
                
            except Exception as e:
                st.error(f"검색 중 오류 발생: {str(e)}")
                logger.exception(f"Search error: {e}")

def render_ai_analysis_tab():
    """AI 법률 분석 탭 - 파일 업로드 및 분석 기능 통합"""
    st.header("🤖 AI 법률 분석")
    
    clients = get_api_clients()
    
    if not clients.get('ai_helper'):
        st.warning("⚠️ OpenAI API가 설정되지 않았습니다. 사이드바에서 API 키를 설정해주세요.")
        return
    
    # 분석 유형 선택
    analysis_type = st.selectbox(
        "분석 유형",
        ["법률 상담", "계약서 검토", "법률 문서 분석", "판례 분석", "법령 비교"],
        key="ai_analysis_type"
    )
    
    # 파일 업로드 영역
    uploaded_file = st.file_uploader(
        "문서 업로드 (선택사항)",
        type=['pdf', 'txt', 'docx', 'hwp'],
        help="계약서, 법률 문서 등을 업로드하세요",
        key="file_upload"
    )
    
    file_content = ""
    if uploaded_file:
        try:
            if uploaded_file.type == "text/plain":
                file_content = str(uploaded_file.read(), "utf-8")
            elif uploaded_file.type == "application/pdf":
                # PDF 처리 (PyPDF2 사용)
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                file_content = ""
                for page in pdf_reader.pages:
                    file_content += page.extract_text()
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                # DOCX 처리
                from docx import Document
                doc = Document(uploaded_file)
                file_content = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            
            st.success(f"✅ 파일 업로드 완료: {uploaded_file.name}")
            
            with st.expander("업로드된 문서 내용 미리보기"):
                st.text_area("문서 내용", file_content[:1000] + "..." if len(file_content) > 1000 else file_content, height=200)
                
        except Exception as e:
            st.error(f"파일 읽기 오류: {str(e)}")
    
    # 분석 대상 입력
    if analysis_type == "법률 상담":
        question = st.text_area(
            "법률 질문",
            placeholder="구체적인 상황과 질문을 입력하세요...",
            height=150,
            key="legal_question"
        )
        
        # 관련 자료 자동 검색 옵션
        auto_search = st.checkbox("관련 법령/판례 자동 검색", value=True, key="auto_search")
        
    elif analysis_type == "계약서 검토":
        if not file_content:
            contract_text = st.text_area(
                "계약서 내용",
                placeholder="검토할 계약서 내용을 입력하거나 파일을 업로드하세요...",
                height=300,
                key="contract_text"
            )
        else:
            contract_text = file_content
        
        # 검토 중점사항
        review_focus = st.multiselect(
            "검토 중점사항",
            ["독소조항", "불공정조항", "법률 위반", "리스크 평가", "누락사항", "개선제안"],
            default=["독소조항", "불공정조항", "리스크 평가"],
            key="review_focus"
        )
        
    elif analysis_type == "법률 문서 분석":
        if not file_content:
            document_text = st.text_area(
                "문서 내용",
                placeholder="분석할 법률 문서를 입력하거나 파일을 업로드하세요...",
                height=300,
                key="document_text"
            )
        else:
            document_text = file_content
        
        analysis_focus = st.multiselect(
            "분석 관점",
            ["요약", "핵심 쟁점", "법적 근거", "리스크", "대응 방안"],
            default=["요약", "핵심 쟁점"],
            key="analysis_focus"
        )
    
    # GPT 모델 선택
    col1, col2 = st.columns(2)
    with col1:
        model = st.selectbox(
            "AI 모델",
            ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
            format_func=lambda x: {
                "gpt-4o-mini": "GPT-4o Mini (빠름/경제적)",
                "gpt-4o": "GPT-4o (균형)",
                "gpt-4-turbo": "GPT-4 Turbo (정확)",
                "gpt-3.5-turbo": "GPT-3.5 Turbo (가장 경제적)"
            }[x],
            key="gpt_model"
        )
    
    with col2:
        temperature = st.slider(
            "창의성 수준",
            min_value=0.0,
            max_value=1.0,
            value=0.3,
            step=0.1,
            help="낮을수록 일관성 있고 정확한 답변, 높을수록 창의적인 답변",
            key="temperature"
        )
    
    # AI 분석 실행
    if st.button("🤖 AI 분석 시작", type="primary", key="ai_analyze_btn"):
        with st.spinner('AI가 분석 중입니다... (최대 1분 소요)'):
            try:
                ai_helper = clients['ai_helper']
                ai_helper.set_model(model)
                
                context = {}
                
                # 분석 유형별 처리
                if analysis_type == "법률 상담":
                    # 자동 검색 수행
                    if auto_search and question:
                        with st.spinner("관련 자료 검색 중..."):
                            context = perform_context_search(question, ["법령", "판례", "해석례"], clients)
                            if context:
                                st.success(f"✅ 관련 자료 {sum(len(v) for v in context.values())}건 검색 완료")
                    
                    # AI 분석
                    prompt = f"""
                    다음 법률 질문에 대해 전문적이고 실용적인 답변을 제공해주세요.
                    
                    질문: {question}
                    
                    답변 구조:
                    1. 핵심 답변 (3-5문장)
                    2. 법적 근거
                    3. 실무적 조언
                    4. 주의사항
                    """
                    
                    if uploaded_file:
                        prompt += f"\n\n참고 문서:\n{file_content[:3000]}"
                    
                    result = ai_helper.analyze_legal_text(prompt, context)
                    
                elif analysis_type == "계약서 검토":
                    prompt = f"""
                    다음 계약서를 전문가 관점에서 검토해주세요.
                    
                    검토 중점: {', '.join(review_focus)}
                    
                    계약서 내용:
                    {contract_text[:5000]}
                    
                    다음 형식으로 검토해주세요:
                    
                    ## 1. 검토 요약
                    ## 2. 발견된 문제점
                    ## 3. 리스크 평가
                    ## 4. 개선 제안
                    ## 5. 법적 검토 의견
                    """
                    
                    result = ai_helper.analyze_legal_text(prompt, {})
                    
                elif analysis_type == "법률 문서 분석":
                    prompt = f"""
                    다음 법률 문서를 분석해주세요.
                    
                    분석 관점: {', '.join(analysis_focus)}
                    
                    문서 내용:
                    {document_text[:5000]}
                    """
                    
                    result = ai_helper.analyze_legal_text(prompt, {})
                
                # 결과 표시
                st.markdown("### 📋 AI 분석 결과")
                st.markdown(result)
                
                # 결과 다운로드
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 결과 저장", key="save_result"):
                        st.session_state.search_history.append({
                            'query': analysis_type,
                            'timestamp': datetime.now().isoformat(),
                            'type': 'ai_analysis',
                            'result': result
                        })
                        st.success("분석 결과가 저장되었습니다.")
                
                with col2:
                    # 결과를 마크다운 파일로 다운로드
                    result_md = f"# AI 법률 분석 결과\n\n**분석 유형:** {analysis_type}\n**일시:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n**모델:** {model}\n\n---\n\n{result}"
                    st.download_button(
                        "📥 결과 다운로드 (MD)",
                        data=result_md,
                        file_name=f"ai_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                        mime="text/markdown",
                        key="download_result"
                    )
                
            except Exception as e:
                st.error(f"AI 분석 중 오류 발생: {str(e)}")
                logger.exception(f"AI analysis error: {e}")

# ========================= Helper Functions =========================

def detect_query_type(query: str) -> bool:
    """쿼리가 자연어인지 키워드인지 판별"""
    # 자연어 패턴
    natural_patterns = [
        r'어떻게|어떤|무엇|언제|누가|왜',
        r'해야|하나요|할까요|되나요|인가요',
        r'경우|때|상황|문제',
        r'도움|조언|방법|절차'
    ]
    
    # 키워드 패턴 (법령명, 판례번호 등)
    keyword_patterns = [
        r'^\S+법$',  # ~법으로 끝나는 단일 단어
        r'^\d{4}[다도허누]\d+',  # 판례번호
        r'^제\d+조',  # 조문 번호
    ]
    
    query_lower = query.lower()
    
    # 키워드 패턴 매칭
    for pattern in keyword_patterns:
        if re.search(pattern, query):
            return False
    
    # 자연어 패턴 매칭
    for pattern in natural_patterns:
        if re.search(pattern, query_lower):
            return True
    
    # 문장 길이로 판단 (20자 이상이면 자연어로 간주)
    return len(query) > 20

def execute_smart_search(query: str, targets: List[str], clients: Dict):
    """스마트 검색 실행 (NLP 기반)"""
    orchestrator = clients.get('smart_orchestrator')
    if not orchestrator:
        st.error("스마트 검색 모듈을 사용할 수 없습니다.")
        return
    
    # NLP 분석
    nlp_processor = clients['nlp_processor']
    analysis = nlp_processor.analyze_query(query)
    
    # 분석 결과 표시
    with st.expander("🧠 AI 쿼리 분석 결과", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("검색 의도", analysis.intent.value)
        with col2:
            st.metric("신뢰도", f"{analysis.confidence:.0%}")
        with col3:
            st.metric("키워드", len(analysis.keywords))
        
        if analysis.keywords:
            st.write("**추출된 키워드:**", ", ".join(analysis.keywords[:5]))
    
    # 통합 검색 실행
    search_results = orchestrator.execute_smart_search(query)
    
    # 결과 표시
    display_search_results(search_results, clients)

def execute_keyword_search(query: str, targets: List[str], clients: Dict):
    """키워드 기반 검색 실행"""
    all_results = {
        'query': query,
        'search_results': {},
        'total_count': 0
    }
    
    # 각 대상별 검색
    with st.spinner(f"검색 중... {', '.join(targets)}"):
        if "법령" in targets and clients.get('law_searcher'):
            result = clients['law_searcher'].search_laws(query, display=20)
            if result.get('totalCnt', 0) > 0:
                all_results['search_results']['laws'] = result
                all_results['total_count'] += result['totalCnt']
        
        if "판례" in targets and clients.get('case_searcher'):
            result = clients['case_searcher'].search_court_cases(query, display=20)
            if result.get('status') == 'success':
                all_results['search_results']['cases'] = result
                all_results['total_count'] += result.get('total_count', 0)
        
        if "헌재결정" in targets and clients.get('case_searcher'):
            result = clients['case_searcher'].search_constitutional_decisions(query, display=20)
            if result.get('status') == 'success':
                all_results['search_results']['constitutional'] = result
                all_results['total_count'] += result.get('total_count', 0)
        
        if "유권해석" in targets and clients.get('case_searcher'):
            result = clients['case_searcher'].search_legal_interpretations(query, display=20)
            if result.get('status') == 'success':
                all_results['search_results']['interpretations'] = result
                all_results['total_count'] += result.get('total_count', 0)
        
        if "위원회결정" in targets and clients.get('committee_searcher'):
            result = clients['committee_searcher'].search_all_committees(query, display_per_committee=5)
            if result.get('success'):
                all_results['search_results']['committees'] = result
                all_results['total_count'] += result.get('total_count', 0)
        
        if "조약" in targets and clients.get('treaty_admin_searcher'):
            result = clients['treaty_admin_searcher'].search_treaties(query, display=20)
            if result.get('totalCnt', 0) > 0:
                all_results['search_results']['treaties'] = result
                all_results['total_count'] += result['totalCnt']
        
        if "행정규칙" in targets and clients.get('treaty_admin_searcher'):
            result = clients['treaty_admin_searcher'].search_admin_rules(query, display=20)
            if result.get('totalCnt', 0) > 0:
                all_results['search_results']['admin_rules'] = result
                all_results['total_count'] += result['totalCnt']
        
        if "자치법규" in targets and clients.get('treaty_admin_searcher'):
            result = clients['treaty_admin_searcher'].search_local_laws(query, display=20)
            if result.get('totalCnt', 0) > 0:
                all_results['search_results']['local_laws'] = result
                all_results['total_count'] += result['totalCnt']
    
    # 결과 표시
    display_search_results(all_results, clients)

def display_search_results(results: Dict, clients: Dict):
    """검색 결과 통합 표시"""
    total_count = results.get('total_count', 0)
    
    if total_count == 0:
        st.warning("검색 결과가 없습니다. 다른 검색어를 시도해보세요.")
        return
    
    st.success(f"✅ 총 {total_count}건의 결과를 찾았습니다.")
    
    # 결과 유형별 탭 생성
    tab_names = []
    tab_contents = []
    
    search_results = results.get('search_results', {})
    
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
    
    # AI 종합 분석 탭 추가 (AI Helper가 있는 경우)
    if clients.get('ai_helper') and total_count > 0:
        tab_names.append("🤖 AI 종합분석")
        tab_contents.append('ai_analysis')
    
    if tab_names:
        tabs = st.tabs(tab_names)
        
        for idx, (tab, content_type) in enumerate(zip(tabs, tab_contents)):
            with tab:
                if content_type == 'laws':
                    display_laws_results(search_results['laws'])
                elif content_type == 'cases':
                    display_cases_results(search_results['cases'])
                elif content_type == 'constitutional':
                    display_constitutional_results(search_results['constitutional'])
                elif content_type == 'interpretations':
                    display_interpretations_results(search_results['interpretations'])
                elif content_type == 'committees':
                    display_committees_results(search_results['committees'])
                elif content_type == 'treaties':
                    display_treaties_results(search_results['treaties'])
                elif content_type == 'admin_rules':
                    display_admin_rules_results(search_results['admin_rules'])
                elif content_type == 'local_laws':
                    display_local_laws_results(search_results['local_laws'])
                elif content_type == 'ai_analysis':
                    display_ai_comprehensive_analysis(results, clients)

def display_laws_results(data: Dict):
    """법령 검색 결과 표시"""
    for idx, law in enumerate(data.get('results', [])[:10], 1):
        with st.expander(f"{idx}. {law.get('법령명한글', 'N/A')}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**공포일자:** {law.get('공포일자', 'N/A')}")
                st.write(f"**시행일자:** {law.get('시행일자', 'N/A')}")
            with col2:
                st.write(f"**소관부처:** {law.get('소관부처명', 'N/A')}")
                st.write(f"**법령구분:** {law.get('법령구분명', 'N/A')}")
            
            if law.get('법령상세링크'):
                st.markdown(f"[🔗 법령 상세보기]({law['법령상세링크']})")

def display_cases_results(data: Dict):
    """판례 검색 결과 표시"""
    for idx, case in enumerate(data.get('cases', [])[:10], 1):
        with st.expander(f"{idx}. {case.get('title', 'N/A')}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**법원:** {case.get('court', 'N/A')}")
                st.write(f"**사건번호:** {case.get('case_number', 'N/A')}")
            with col2:
                st.write(f"**선고일:** {case.get('date', 'N/A')}")
                st.write(f"**사건종류:** {case.get('type', 'N/A')}")
            
            if case.get('summary'):
                st.write("**판결요지:**")
                st.write(case['summary'][:500] + "..." if len(case.get('summary', '')) > 500 else case['summary'])

def display_constitutional_results(data: Dict):
    """헌재결정례 검색 결과 표시"""
    for idx, decision in enumerate(data.get('decisions', [])[:10], 1):
        with st.expander(f"{idx}. {decision.get('title', 'N/A')}"):
            st.write(f"**사건번호:** {decision.get('case_number', 'N/A')}")
            st.write(f"**종국일자:** {decision.get('date', 'N/A')}")

def display_interpretations_results(data: Dict):
    """유권해석 검색 결과 표시"""
    for idx, interp in enumerate(data.get('interpretations', [])[:10], 1):
        with st.expander(f"{idx}. {interp.get('title', 'N/A')}"):
            st.write(f"**질의기관:** {interp.get('requesting_agency', 'N/A')}")
            st.write(f"**회신기관:** {interp.get('responding_agency', 'N/A')}")
            st.write(f"**회신일자:** {interp.get('date', 'N/A')}")

def display_committees_results(data: Dict):
    """위원회 결정 검색 결과 표시"""
    for committee_code, committee_data in data.get('committees', {}).items():
        if committee_data.get('count', 0) > 0:
            st.subheader(f"📋 {committee_data['name']} ({committee_data['count']}건)")
            for idx, decision in enumerate(committee_data.get('decisions', [])[:5], 1):
                with st.expander(f"{idx}. {decision.get('title', 'N/A')}"):
                    st.write(f"**날짜:** {decision.get('date', 'N/A')}")
                    st.write(f"**번호:** {decision.get('number', 'N/A')}")

def display_treaties_results(data: Dict):
    """조약 검색 결과 표시"""
    for idx, treaty in enumerate(data.get('treaties', data.get('results', []))[:10], 1):
        with st.expander(f"{idx}. {treaty.get('조약명한글', treaty.get('조약명', 'N/A'))}"):
            st.write(f"**발효일자:** {treaty.get('발효일자', 'N/A')}")
            st.write(f"**체결일자:** {treaty.get('체결일자', 'N/A')}")

def display_admin_rules_results(data: Dict):
    """행정규칙 검색 결과 표시"""
    for idx, rule in enumerate(data.get('rules', data.get('results', []))[:10], 1):
        with st.expander(f"{idx}. {rule.get('행정규칙명', 'N/A')}"):
            st.write(f"**발령일자:** {rule.get('발령일자', 'N/A')}")
            st.write(f"**소관부처:** {rule.get('소관부처명', 'N/A')}")

def display_local_laws_results(data: Dict):
    """자치법규 검색 결과 표시"""
    for idx, law in enumerate(data.get('ordinances', data.get('results', []))[:10], 1):
        with st.expander(f"{idx}. {law.get('자치법규명', 'N/A')}"):
            st.write(f"**발령일자:** {law.get('발령일자', 'N/A')}")
            st.write(f"**지자체:** {law.get('지자체명', 'N/A')}")

def display_ai_comprehensive_analysis(results: Dict, clients: Dict):
    """AI 종합 분석 표시"""
    ai_helper = clients.get('ai_helper')
    if not ai_helper:
        st.warning("AI 분석을 사용할 수 없습니다.")
        return
    
    with st.spinner("AI가 검색 결과를 종합 분석 중입니다..."):
        # 컨텍스트 준비
        context = {
            'query': results.get('query', ''),
            'total_count': results.get('total_count', 0),
            'summary': {}
        }
        
        # 각 결과 유형별 요약
        search_results = results.get('search_results', {})
        for key, data in search_results.items():
            if key == 'laws':
                context['summary']['laws'] = f"{data.get('totalCnt', 0)}개 법령"
            elif key == 'cases':
                context['summary']['cases'] = f"{data.get('total_count', 0)}개 판례"
            elif key == 'interpretations':
                context['summary']['interpretations'] = f"{data.get('total_count', 0)}개 유권해석"
        
        prompt = f"""
        다음 법률 검색 결과를 종합적으로 분석하여 핵심 내용을 요약해주세요.
        
        검색어: {context['query']}
        총 검색 결과: {context['total_count']}건
        
        검색 결과 요약:
        {json.dumps(context['summary'], ensure_ascii=False, indent=2)}
        
        다음 형식으로 작성해주세요:
        1. 핵심 요약 (3-5문장)
        2. 주요 법령
        3. 관련 판례
        4. 실무 시사점
        5. 추가 검토사항
        """
        
        try:
            analysis = ai_helper.analyze_legal_text(prompt, context)
            st.markdown("### 🤖 AI 종합 분석")
            st.markdown(analysis)
        except Exception as e:
            st.error(f"AI 분석 중 오류: {str(e)}")

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
        
        if "해석례" in targets and clients.get('case_searcher'):
            result = clients['case_searcher'].search_legal_interpretations(query, display=5)
            if result.get('status') == 'success':
                context['interpretations'] = result.get('interpretations', [])
        
    except Exception as e:
        logger.error(f"Context search error: {str(e)}")
    
    return context

# ========================= Sidebar =========================

def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.title("⚖️ K-Law Assistant")
        
        # 상태 표시
        if st.session_state.get('nlp_enabled'):
            st.success("🧠 AI 분석 활성화")
        else:
            st.warning("📚 기본 모드")
        
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
            
            if st.button("💾 설정 저장", key="save_api_keys", use_container_width=True):
                st.session_state.api_keys['law_api_key'] = law_api_key
                st.session_state.api_keys['openai_api_key'] = openai_api_key
                st.cache_resource.clear()
                st.success("API 키가 저장되었습니다!")
                st.rerun()
        
        # GPT 모델 선택
        st.markdown("### 🤖 AI 설정")
        models = {
            'gpt-4o-mini': 'GPT-4o Mini',
            'gpt-4o': 'GPT-4o',
            'gpt-4-turbo': 'GPT-4 Turbo',
            'gpt-3.5-turbo': 'GPT-3.5 Turbo'
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
                if st.button(
                    f"🕐 {item['query'][:20]}...",
                    key=f"history_{idx}",
                    use_container_width=True
                ):
                    st.session_state.unified_search_query = item['query']
        
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
            ### 사용법
            1. **통합 검색**: 자연어 또는 키워드로 검색
            2. **AI 분석**: 문서 업로드 및 법률 분석
            3. **법령 다운로드**: 관련 법령 일괄 다운로드
               - 체계도 기반으로 모든 하위 법령 포함
               - 행정규칙 (훈령, 예규, 고시, 지침)
               - 자치법규, 별표서식 등
            
            ### 문의
            - 이메일: support@klaw.com
            - 전화: 02-1234-5678
            """)

# ========================= Main Application =========================

def main():
    """메인 애플리케이션"""
    
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
    st.markdown("**AI 기반 통합 법률 검색 및 분석 시스템 (체계도 완전 다운로드 지원)**")
    
    # API 키 확인
    if not st.session_state.api_keys.get('law_api_key'):
        st.warning("⚠️ 법제처 API 키가 설정되지 않았습니다. 사이드바에서 설정해주세요.")
    
    # 3개 탭으로 간소화
    tabs = st.tabs([
        "🔍 통합 스마트 검색",
        "🤖 AI 법률 분석",
        "📥 법령 체계도 다운로드"
    ])
    
    # Tab 1: 통합 스마트 검색
    with tabs[0]:
        render_unified_search_tab()
    
    # Tab 2: AI 법률 분석
    with tabs[1]:
        render_ai_analysis_tab()
    
    # Tab 3: 법령 다운로드 (개선된 버전)
    with tabs[2]:
        render_law_download_tab()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error(f"애플리케이션 실행 중 오류가 발생했습니다: {str(e)}")
        st.info("페이지를 새로고침하거나 관리자에게 문의해주세요.")
