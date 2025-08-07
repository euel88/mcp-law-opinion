"""
K-Law Assistant - 통합 법률 검토 지원 시스템 (간소화 버전)
Enhanced Main Application with Simplified UI and Law Download Feature
Version 7.0 - Streamlined Interface
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
        'About': 'K-Law Assistant Pro v7.0 - AI 기반 통합 법률 검색 시스템'
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

# ========================= Enhanced Smart Search Tab =========================

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

# ========================= Enhanced AI Analysis Tab =========================

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

# ========================= Law Download Tab =========================

def render_law_download_tab():
    """법령 체계도 기반 일괄 다운로드 탭"""
    st.header("📥 법령 일괄 다운로드")
    
    clients = get_api_clients()
    
    if not clients.get('law_searcher'):
        st.error("법령 검색 모듈을 초기화할 수 없습니다.")
        return
    
    st.markdown("""
    ### 📋 법령 체계도 기반 다운로드
    
    법령과 관련된 하위 법령(시행령, 시행규칙, 감독규정 등)을 한 번에 다운로드할 수 있습니다.
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
    with st.expander("⚙️ 다운로드 옵션", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            include_types = st.multiselect(
                "포함할 법령 유형",
                ["법률", "시행령", "시행규칙", "행정규칙", "고시", "훈령", "예규"],
                default=["법률", "시행령", "시행규칙"],
                key="include_types"
            )
        
        with col2:
            format_option = st.selectbox(
                "다운로드 형식",
                ["Markdown (.md)", "Text (.txt)", "JSON (.json)"],
                key="format_option"
            )
            
            include_history = st.checkbox("법령 연혁 포함", value=False, key="include_history")
    
    # 체계도 조회 및 다운로드
    if search_btn and law_name:
        with st.spinner(f'"{law_name}" 법령 체계도 조회 중...'):
            try:
                law_searcher = clients['law_searcher']
                
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
                    
                    # 2. 관련 법령 체계도 조회
                    if st.button("📊 법령 체계도 조회", key="get_structure_btn"):
                        with st.spinner("법령 체계도 및 관련 법령 조회 중..."):
                            all_related_laws = []
                            
                            for selected_law in laws_to_download:
                                st.markdown(f"#### 📋 {selected_law['title']} 관련 법령")
                                
                                # 법령 체계도 조회
                                try:
                                    # 위임 법령 조회
                                    delegated = law_searcher.get_delegated_laws(
                                        law_id=selected_law['id']
                                    )
                                    
                                    # 법령 체계도 조회
                                    structure = law_searcher.get_law_structure_detail(
                                        law_id=selected_law['id']
                                    )
                                    
                                    # 관련 법령 수집
                                    related_laws = [selected_law['law']]  # 주 법령 포함
                                    
                                    # 하위 법령 검색 (시행령, 시행규칙 등)
                                    base_name = selected_law['title'].replace('법', '').strip()
                                    
                                    # 시행령 검색
                                    if "시행령" in include_types:
                                        decree_result = law_searcher.search_laws(
                                            query=f"{base_name} 시행령",
                                            display=5
                                        )
                                        if decree_result.get('results'):
                                            related_laws.extend(decree_result['results'])
                                    
                                    # 시행규칙 검색
                                    if "시행규칙" in include_types:
                                        rule_result = law_searcher.search_laws(
                                            query=f"{base_name} 시행규칙",
                                            display=5
                                        )
                                        if rule_result.get('results'):
                                            related_laws.extend(rule_result['results'])
                                    
                                    # 행정규칙 검색
                                    if "행정규칙" in include_types or "고시" in include_types:
                                        admin_result = clients.get('treaty_admin_searcher').search_admin_rules(
                                            query=base_name,
                                            display=10
                                        )
                                        if admin_result.get('rules'):
                                            related_laws.extend(admin_result['rules'])
                                    
                                    # 중복 제거
                                    unique_laws = []
                                    seen_ids = set()
                                    for law in related_laws:
                                        law_id = law.get('법령ID') or law.get('법령일련번호') or law.get('행정규칙ID')
                                        if law_id and law_id not in seen_ids:
                                            seen_ids.add(law_id)
                                            unique_laws.append(law)
                                    
                                    all_related_laws.extend(unique_laws)
                                    
                                    # 결과 표시
                                    st.success(f"✅ {len(unique_laws)}개 관련 법령 발견")
                                    
                                    # 관련 법령 목록
                                    with st.expander(f"관련 법령 목록 ({len(unique_laws)}개)"):
                                        for related_law in unique_laws:
                                            title = related_law.get('법령명한글') or related_law.get('행정규칙명', 'N/A')
                                            st.write(f"- {title}")
                                    
                                except Exception as e:
                                    st.error(f"체계도 조회 실패: {str(e)}")
                            
                            # 3. 다운로드 준비
                            if all_related_laws:
                                st.markdown("---")
                                st.markdown(f"### 💾 다운로드 준비 완료")
                                st.info(f"총 {len(all_related_laws)}개 법령이 다운로드 준비되었습니다.")
                                
                                # 다운로드 버튼
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    # Markdown 형식 다운로드
                                    if format_option == "Markdown (.md)":
                                        md_content = generate_laws_markdown(all_related_laws, law_searcher, include_history)
                                        st.download_button(
                                            "📥 Markdown 다운로드",
                                            data=md_content,
                                            file_name=f"{law_name}_laws_{datetime.now().strftime('%Y%m%d')}.md",
                                            mime="text/markdown",
                                            key="download_md",
                                            use_container_width=True
                                        )
                                
                                with col2:
                                    # ZIP 파일로 개별 다운로드
                                    zip_buffer = create_laws_zip(all_related_laws, law_searcher, format_option, include_history)
                                    st.download_button(
                                        "📦 ZIP 다운로드 (개별 파일)",
                                        data=zip_buffer,
                                        file_name=f"{law_name}_laws_{datetime.now().strftime('%Y%m%d')}.zip",
                                        mime="application/zip",
                                        key="download_zip",
                                        use_container_width=True
                                    )
                                
                                with col3:
                                    # JSON 형식 다운로드
                                    if st.button("📊 JSON 다운로드", key="download_json", use_container_width=True):
                                        json_content = json.dumps(all_related_laws, ensure_ascii=False, indent=2)
                                        st.download_button(
                                            "💾 JSON 파일 다운로드",
                                            data=json_content,
                                            file_name=f"{law_name}_laws_{datetime.now().strftime('%Y%m%d')}.json",
                                            mime="application/json",
                                            key="download_json_file"
                                        )
                                
                                # 다운로드 이력 저장
                                st.session_state.downloaded_laws.append({
                                    'law_name': law_name,
                                    'count': len(all_related_laws),
                                    'timestamp': datetime.now().isoformat()
                                })
                
            except Exception as e:
                st.error(f"법령 체계도 조회 중 오류 발생: {str(e)}")
                logger.exception(f"Law structure search error: {e}")

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

def generate_laws_markdown(laws: List[Dict], law_searcher, include_history: bool) -> str:
    """법령을 마크다운 형식으로 변환"""
    md_content = f"# 법령 모음\n\n"
    md_content += f"**생성일시:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    md_content += f"**총 법령 수:** {len(laws)}개\n\n"
    md_content += "---\n\n"
    
    for idx, law in enumerate(laws, 1):
        law_id = law.get('법령ID') or law.get('법령일련번호')
        law_name = law.get('법령명한글') or law.get('행정규칙명', 'N/A')
        
        md_content += f"## {idx}. {law_name}\n\n"
        md_content += f"- **공포일자:** {law.get('공포일자', 'N/A')}\n"
        md_content += f"- **시행일자:** {law.get('시행일자', 'N/A')}\n"
        md_content += f"- **소관부처:** {law.get('소관부처명', 'N/A')}\n\n"
        
        # 법령 본문 조회
        try:
            if law_id:
                detail = law_searcher.get_law_detail(law_id=law_id)
                if detail and 'error' not in detail:
                    # 본문 추가 (간략화)
                    content = detail.get('조문내용', detail.get('법령내용', ''))
                    if content:
                        md_content += "### 조문 내용\n\n"
                        md_content += content[:5000]  # 처음 5000자만
                        if len(content) > 5000:
                            md_content += "\n\n... (이하 생략)\n"
                    md_content += "\n\n"
        except Exception as e:
            logger.error(f"법령 상세 조회 실패: {e}")
        
        md_content += "---\n\n"
    
    return md_content

def create_laws_zip(laws: List[Dict], law_searcher, format_option: str, include_history: bool) -> bytes:
    """법령을 ZIP 파일로 압축"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for idx, law in enumerate(laws, 1):
            law_id = law.get('법령ID') or law.get('법령일련번호')
            law_name = law.get('법령명한글') or law.get('행정규칙명', 'N/A')
            
            # 파일명 정리 (특수문자 제거)
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', law_name)
            
            if format_option == "Markdown (.md)":
                file_ext = "md"
                content = f"# {law_name}\n\n"
                content += f"**공포일자:** {law.get('공포일자', 'N/A')}\n"
                content += f"**시행일자:** {law.get('시행일자', 'N/A')}\n\n"
                
                # 법령 본문 조회
                try:
                    if law_id:
                        detail = law_searcher.get_law_detail(law_id=law_id)
                        if detail and 'error' not in detail:
                            content += detail.get('조문내용', detail.get('법령내용', ''))
                except:
                    pass
                
            elif format_option == "Text (.txt)":
                file_ext = "txt"
                content = f"{law_name}\n"
                content += "=" * 50 + "\n"
                content += f"공포일자: {law.get('공포일자', 'N/A')}\n"
                content += f"시행일자: {law.get('시행일자', 'N/A')}\n\n"
                
            else:  # JSON
                file_ext = "json"
                content = json.dumps(law, ensure_ascii=False, indent=2)
            
            # ZIP에 파일 추가
            file_name = f"{idx:03d}_{safe_name}.{file_ext}"
            zip_file.writestr(file_name, content.encode('utf-8'))
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

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
    st.markdown("**AI 기반 통합 법률 검색 및 분석 시스템**")
    
    # API 키 확인
    if not st.session_state.api_keys.get('law_api_key'):
        st.warning("⚠️ 법제처 API 키가 설정되지 않았습니다. 사이드바에서 설정해주세요.")
    
    # 3개 탭으로 간소화
    tabs = st.tabs([
        "🔍 통합 스마트 검색",
        "🤖 AI 법률 분석",
        "📥 법령 다운로드"
    ])
    
    # Tab 1: 통합 스마트 검색
    with tabs[0]:
        render_unified_search_tab()
    
    # Tab 2: AI 법률 분석
    with tabs[1]:
        render_ai_analysis_tab()
    
    # Tab 3: 법령 다운로드
    with tabs[2]:
        render_law_download_tab()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error(f"애플리케이션 실행 중 오류가 발생했습니다: {str(e)}")
        st.info("페이지를 새로고침하거나 관리자에게 문의해주세요.")
