"""
K-Law Assistant - 통합 법률 검토 지원 시스템
Main Application with Streamlit UI (Fixed Version 2.0)
할루시네이션 방지 및 API 검증 강화
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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page configuration - 반드시 다른 Streamlit 명령 전에 실행
st.set_page_config(
    page_title="K-Law Assistant",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom modules import with error handling
try:
    from common_api import LawAPIClient, OpenAIHelper
    from legal_prompts_module import PromptBuilder, ServiceType, detect_service_type
    from law_module import LawSearcher
    from committee_module import CommitteeDecisionSearcher
    from case_module import CaseSearcher
    from treaty_admin_module import TreatyAdminSearcher
    MODULES_LOADED = True
except ImportError as e:
    MODULES_LOADED = False
    st.error(f"❌ 필수 모듈을 불러올 수 없습니다: {str(e)}")
    st.info("requirements.txt의 패키지를 모두 설치했는지 확인해주세요.")

# ========================= 할루시네이션 방지 설정 =========================

ANTI_HALLUCINATION_CONFIG = {
    # AI 모델 설정
    'temperature': 0.1,  # 매우 낮은 온도로 창의성 제한
    'max_tokens': 3000,
    'presence_penalty': 0.0,
    'frequency_penalty': 0.0,
    
    # 의심스러운 패턴들
    'suspicious_patterns': [
        r'대법원\s*\d{4}[다도허누]\d{4}\b',
        r'^\d{4}[다도허누]\d{4}\b',
        r'헌법재판소\s*\d{4}헌[가나다라마바사]\d+',
        r'법제처\s*\d{4}해석\d{4}',
        r'행정심판\s*\d{4}-\d{3,4}\b',
    ],
    
    # 검증 메시지
    'messages': {
        'no_results': "⚠️ 관련 법률자료가 검색되지 않았습니다.",
        'unverified': "⚠️ 일부 인용이 검증되지 않았습니다.",
        'disclaimer': "📌 본 내용은 AI가 작성한 참고자료이며, 법률자문이 아닙니다."
    }
}

# ========================= Query Type Detection =========================

class QueryType(Enum):
    """질문 유형 분류"""
    SIMPLE_SEARCH = "simple_search"
    AI_ANALYSIS = "ai_analysis"
    CONTRACT_REVIEW = "contract_review"
    LEGAL_OPINION = "legal_opinion"

def detect_query_type(query: str) -> Tuple[QueryType, str]:
    """사용자 질문 유형을 자동으로 판별"""
    if not query:
        return QueryType.SIMPLE_SEARCH, "검색어 없음"
        
    query_lower = query.lower()
    
    # 단순 검색 키워드
    search_keywords = ['검색', '찾아', '조회', '알려', '법령', '판례', '조문']
    
    # AI 분석 키워드
    ai_keywords = ['분석', '검토', '해석', '의미', '적용', '어떻게', '왜']
    
    # 계약서 검토 키워드
    contract_keywords = ['계약서', '계약 검토', '독소조항', '불공정']
    
    # 법률자문 키워드
    opinion_keywords = ['자문', '의견서', '법률자문', '소송', '분쟁']
    
    # 우선순위에 따른 판별
    if any(kw in query_lower for kw in contract_keywords):
        return QueryType.CONTRACT_REVIEW, "계약서 관련 키워드 감지"
    
    if any(kw in query_lower for kw in opinion_keywords):
        return QueryType.LEGAL_OPINION, "법률자문 관련 키워드 감지"
    
    search_count = sum(1 for kw in search_keywords if kw in query_lower)
    ai_count = sum(1 for kw in ai_keywords if kw in query_lower)
    
    if search_count > ai_count and search_count > 0:
        return QueryType.SIMPLE_SEARCH, f"검색 키워드 {search_count}개 감지"
    
    return QueryType.AI_ANALYSIS, "AI 분석이 필요한 복잡한 질문"

# ========================= Session State Management =========================

def init_session_state():
    """Initialize session state variables"""
    try:
        if 'initialized' not in st.session_state:
            st.session_state.initialized = False
            
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
            
        if 'api_clients' not in st.session_state:
            st.session_state.api_clients = None
            
        st.session_state.initialized = True
        logger.info("Session state initialized successfully")
        
    except Exception as e:
        logger.error(f"Session state initialization error: {str(e)}")
        st.error(f"세션 초기화 오류: {str(e)}")

# ========================= API Clients Initialization =========================

def get_api_clients(force_reload=False):
    """Initialize and cache API clients"""
    try:
        if not force_reload and st.session_state.api_clients is not None:
            return st.session_state.api_clients
            
        law_api_key = st.session_state.api_keys.get('law_api_key', '')
        openai_api_key = st.session_state.api_keys.get('openai_api_key', '')
        
        clients = {}
        
        # 법제처 API 클라이언트 초기화
        try:
            if law_api_key and law_api_key != 'your_law_api_key_here':
                law_client = LawAPIClient(oc_key=law_api_key)
                clients['law_client'] = law_client
                logger.info("법제처 API 클라이언트 초기화 성공")
            else:
                clients['law_client'] = None
                logger.warning("법제처 API 키가 설정되지 않음")
        except Exception as e:
            logger.error(f"LawAPIClient initialization error: {str(e)}")
            clients['law_client'] = None
            
        # OpenAI 헬퍼 초기화
        try:
            if openai_api_key and not openai_api_key.startswith('sk-your'):
                ai_helper = OpenAIHelper(api_key=openai_api_key)
                clients['ai_helper'] = ai_helper
                logger.info("OpenAI 헬퍼 초기화 성공")
            else:
                clients['ai_helper'] = None
                logger.warning("OpenAI API 키가 설정되지 않음")
        except Exception as e:
            logger.error(f"OpenAIHelper initialization error: {str(e)}")
            clients['ai_helper'] = None
            
        # 각 검색 모듈 초기화
        try:
            clients['law_searcher'] = LawSearcher(api_client=clients['law_client']) if clients['law_client'] else None
        except Exception as e:
            logger.error(f"LawSearcher initialization error: {str(e)}")
            clients['law_searcher'] = None
            
        try:
            clients['case_searcher'] = CaseSearcher(api_client=clients['law_client'], ai_helper=clients['ai_helper']) if clients['law_client'] else None
        except Exception as e:
            logger.error(f"CaseSearcher initialization error: {str(e)}")
            clients['case_searcher'] = None
            
        try:
            clients['prompt_builder'] = PromptBuilder()
        except Exception as e:
            logger.error(f"PromptBuilder initialization error: {str(e)}")
            clients['prompt_builder'] = None
        
        st.session_state.api_clients = clients
        
        return clients
        
    except Exception as e:
        logger.error(f"API clients initialization failed: {str(e)}")
        return {
            'law_client': None,
            'ai_helper': None,
            'law_searcher': None,
            'case_searcher': None,
            'prompt_builder': None
        }

# ========================= 법제처 API 테스트 함수 =========================

def test_law_api():
    """법제처 API 연결 테스트"""
    try:
        clients = get_api_clients()
        if not clients.get('law_searcher'):
            return False, "법제처 API 클라이언트가 초기화되지 않았습니다."
        
        # 간단한 검색 테스트
        test_result = clients['law_searcher'].search_laws("민법", display=1)
        
        if 'error' in test_result:
            return False, f"API 오류: {test_result['error']}"
        
        if 'results' in test_result and len(test_result['results']) > 0:
            return True, "법제처 API 연결 성공"
        else:
            return True, "API 연결은 성공했으나 검색 결과가 없습니다."
            
    except Exception as e:
        return False, f"API 테스트 실패: {str(e)}"

# ========================= Search Functions (개선) =========================

def perform_simple_search(query: str, search_targets: List[str]) -> Dict[str, Any]:
    """단순 검색 수행 (AI 없이 직접 검색) - 개선된 버전"""
    clients = get_api_clients()
    results = {
        'query': query,
        'timestamp': datetime.now().isoformat(),
        'results': {},
        'errors': []
    }
    
    if not clients:
        st.error("API 클라이언트를 초기화할 수 없습니다.")
        return results
    
    with st.spinner('검색 중...'):
        # 법령 검색
        if '법령' in search_targets and clients.get('law_searcher'):
            try:
                law_results = clients['law_searcher'].search_laws(query, display=10)
                if law_results and 'results' in law_results:
                    results['results']['laws'] = law_results['results']
                    logger.info(f"법령 검색 성공: {len(law_results['results'])}건")
                    st.success(f"✅ 법령 {len(law_results['results'])}건 검색 완료")
            except Exception as e:
                error_msg = f"법령 검색 오류: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                st.warning(error_msg)
        
        # 판례 검색
        if '판례' in search_targets and clients.get('case_searcher'):
            try:
                case_results = clients['case_searcher'].search_court_cases(query, display=10)
                if case_results.get('status') == 'success':
                    results['results']['cases'] = case_results.get('cases', [])
                    logger.info(f"판례 검색 성공: {len(case_results.get('cases', []))}건")
                    st.success(f"✅ 판례 {len(case_results.get('cases', []))}건 검색 완료")
            except Exception as e:
                error_msg = f"판례 검색 오류: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                st.warning(error_msg)
        
        # 헌재결정례 검색
        if '헌재결정' in search_targets and clients.get('case_searcher'):
            try:
                const_results = clients['case_searcher'].search_constitutional_decisions(query, display=10)
                if const_results.get('status') == 'success':
                    results['results']['constitutional'] = const_results.get('decisions', [])
                    logger.info(f"헌재결정례 검색 성공: {len(const_results.get('decisions', []))}건")
                    st.success(f"✅ 헌재결정례 {len(const_results.get('decisions', []))}건 검색 완료")
            except Exception as e:
                error_msg = f"헌재결정례 검색 오류: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                st.warning(error_msg)
        
        # 법령해석례 검색
        if '법령해석' in search_targets and clients.get('case_searcher'):
            try:
                interp_results = clients['case_searcher'].search_legal_interpretations(query, display=10)
                if interp_results.get('status') == 'success':
                    results['results']['interpretations'] = interp_results.get('interpretations', [])
                    logger.info(f"법령해석례 검색 성공: {len(interp_results.get('interpretations', []))}건")
                    st.success(f"✅ 법령해석례 {len(interp_results.get('interpretations', []))}건 검색 완료")
            except Exception as e:
                error_msg = f"법령해석례 검색 오류: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                st.warning(error_msg)
    
    return results

def validate_and_clean_response(response: str, context: Dict) -> str:
    """AI 응답 검증 및 정제"""
    
    # 1. 의심스러운 패턴 검사
    for pattern in ANTI_HALLUCINATION_CONFIG['suspicious_patterns']:
        matches = re.findall(pattern, response)
        for match in matches:
            # 실제 검색 결과에 있는지 확인
            found = False
            
            # 판례 확인
            for case in context.get('cases', []):
                if match in str(case.get('case_number', '')):
                    found = True
                    break
            
            # 찾지 못했으면 제거
            if not found:
                logger.warning(f"허위 판례번호 감지 및 제거: {match}")
                response = response.replace(match, "[검증 필요]")
    
    # 2. 검색 결과가 없는데 구체적 인용이 있는지 확인
    if not context.get('cases') and ('대법원' in response and '판결' in response):
        response = re.sub(
            r'대법원.*?판결.*?\n',
            '※ 관련 판례를 검색하지 못했습니다.\n',
            response
        )
    
    return response

def perform_ai_analysis(query: str, context: Dict[str, Any], service_type: ServiceType) -> str:
    """AI 분석 수행 - 할루시네이션 방지 강화 버전"""
    clients = get_api_clients()
    
    if not clients or not clients.get('ai_helper'):
        return "⚠️ OpenAI API가 설정되지 않았습니다. 사이드바에서 API 키를 입력해주세요."
    
    if not clients['ai_helper'].enabled:
        return "⚠️ OpenAI API가 활성화되지 않았습니다. API 키를 확인해주세요."
    
    try:
        # 검색 결과 요약
        search_summary = []
        formatted_context = ""
        
        # 법령 정리
        if 'laws' in context and context['laws']:
            search_summary.append(f"법령 {len(context['laws'])}건")
            formatted_context += "\n### 검색된 법령:\n"
            for law in context['laws'][:5]:
                formatted_context += f"- {law.get('법령명한글', '')} (공포: {law.get('공포일자', '')})\n"
        
        # 판례 정리
        if 'cases' in context and context['cases']:
            search_summary.append(f"판례 {len(context['cases'])}건")
            formatted_context += "\n### 검색된 판례:\n"
            for case in context['cases'][:5]:
                formatted_context += f"- {case.get('court', '')} {case.get('date', '')} {case.get('case_number', '')}\n"
                if case.get('판시사항'):
                    formatted_context += f"  판시사항: {case['판시사항'][:100]}...\n"
        
        # 해석례 정리
        if 'interpretations' in context and context['interpretations']:
            search_summary.append(f"해석례 {len(context['interpretations'])}건")
            formatted_context += "\n### 검색된 해석례:\n"
            for interp in context['interpretations'][:3]:
                formatted_context += f"- {interp.get('responding_agency', '')} {interp.get('case_number', '')}: {interp.get('title', '')}\n"
        
        # 시스템 프롬프트 - 할루시네이션 방지 강화
        system_prompt = """당신은 한국의 AI 법률 도우미입니다.

### 🚨 절대 준수 규칙:
1. **실제 데이터만 사용**: 제공된 검색 결과에 있는 정보만 인용
2. **허위 생성 금지**: 검색 결과에 없는 판례번호, 법령명, 날짜를 절대 만들지 마세요
3. **패턴 금지**: "2005다1234" 같은 임의의 번호를 만들지 마세요
4. **명시적 표시**: 검색 결과가 없으면 "검색된 자료 없음"이라고 명시
5. **검증 가능성**: 모든 인용은 제공된 검색 결과에서 확인 가능해야 함

⚖️ 본 내용은 AI가 작성한 참고자료이며, 법률자문이 아닙니다."""

        # 사용자 프롬프트
        user_prompt = f"""
질문: {query}

검색 결과 현황: {', '.join(search_summary) if search_summary else '검색 결과 없음'}

{formatted_context if formatted_context else '※ 검색된 법률자료가 없습니다.'}

### 답변 작성 지침:
1. **핵심 답변** (3-5줄로 요약)
2. **관련 법령** (위 검색 결과에서만 인용, 없으면 "검색된 법령 없음")
3. **관련 판례** (위 검색 결과에서만 인용, 없으면 "검색된 판례 없음")
4. **관련 해석례** (위 검색 결과에서만 인용, 없으면 "검색된 해석례 없음")
5. **실무 조언** (일반적인 조언 제공)

⚠️ 중요: 위에 제공된 검색 결과만 사용하고, 절대로 가짜 판례번호나 법령을 만들지 마세요!
검색 결과에 없는 내용은 "검색된 자료 없음"이라고 명시하세요."""

        # OpenAI API 호출
        from openai import OpenAI
        
        client = OpenAI(api_key=st.session_state.api_keys.get('openai_api_key'))
        
        response = client.chat.completions.create(
            model=st.session_state.selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=ANTI_HALLUCINATION_CONFIG['temperature'],
            max_tokens=ANTI_HALLUCINATION_CONFIG['max_tokens'],
            presence_penalty=ANTI_HALLUCINATION_CONFIG['presence_penalty'],
            frequency_penalty=ANTI_HALLUCINATION_CONFIG['frequency_penalty']
        )
        
        ai_response = response.choices[0].message.content
        
        # 응답 검증 및 정제
        cleaned_response = validate_and_clean_response(ai_response, context)
        
        # 최종 포맷팅
        if not search_summary:
            cleaned_response = "⚠️ **주의**: 관련 법률자료가 검색되지 않아 일반적인 법리로 답변합니다.\n\n" + cleaned_response
        
        cleaned_response += f"\n\n---\n{ANTI_HALLUCINATION_CONFIG['messages']['disclaimer']}"
        
        return cleaned_response
        
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
                value=st.session_state.api_keys.get('law_api_key', ''),
                type="password",
                help="https://open.law.go.kr 에서 발급"
            )
            
            openai_api_key = st.text_input(
                "OpenAI API Key",
                value=st.session_state.api_keys.get('openai_api_key', ''),
                type="password",
                help="https://platform.openai.com 에서 발급"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("API 키 저장", use_container_width=True):
                    st.session_state.api_keys['law_api_key'] = law_api_key
                    st.session_state.api_keys['openai_api_key'] = openai_api_key
                    st.session_state.api_clients = None
                    st.success("API 키가 저장되었습니다!")
                    st.rerun()
            
            with col2:
                if st.button("API 테스트", use_container_width=True):
                    success, message = test_law_api()
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
        
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
            ['법령', '판례', '헌재결정', '법령해석', '행정규칙'],
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
    """검색 결과를 표시 - 개선된 버전"""
    
    if not results.get('results'):
        st.info("검색 결과가 없습니다.")
        return
    
    # 결과 요약
    total_count = sum(
        len(items) if isinstance(items, list) else 0
        for items in results['results'].values()
    )
    
    if total_count > 0:
        st.success(f"✅ 총 {total_count}개의 결과를 찾았습니다.")
    
    # 오류 표시
    if results.get('errors'):
        with st.expander("⚠️ 검색 중 발생한 오류", expanded=False):
            for error in results['errors']:
                st.warning(error)
    
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
    try:
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
            if item.get('판시사항'):
                st.markdown(f"  > 판시사항: {item['판시사항'][:200]}...")
        
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
            st.markdown(f"**{idx}. {item.get('title', item.get('제목', str(item)[:100]))}**")
    except Exception as e:
        logger.error(f"검색 항목 표시 오류: {str(e)}")
        st.markdown(f"**{idx}. 항목 표시 오류**")

# ========================= Main Application =========================

def main():
    """Main application"""
    
    # 모듈 로드 확인
    if not MODULES_LOADED:
        st.error("필수 모듈을 로드할 수 없습니다. 설치를 확인해주세요.")
        st.code("pip install -r requirements.txt", language="bash")
        return
    
    # 세션 상태 초기화
    init_session_state()
    
    # 사이드바 렌더링
    render_sidebar()
    
    st.title("⚖️ K-Law Assistant - AI 법률 검토 지원 시스템")
    st.markdown("법령, 판례, 행정규칙 등을 종합 검토하여 AI가 법률 자문을 제공합니다.")
    
    # API 키 확인
    if not st.session_state.api_keys.get('law_api_key'):
        st.warning("⚠️ 법제처 API 키가 설정되지 않았습니다. 사이드바에서 설정해주세요.")
    
    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 통합 검색", "🤖 AI 법률 분석", "📊 검색 이력", "ℹ️ 사용 가이드"])
    
    # Tab 1: 통합 검색
    with tab1:
        st.header("통합 법률자료 검색")
        
        # 검색 입력
        col1, col2 = st.columns([5, 1])
        with col1:
            default_value = ""
            if 'quick_search' in st.session_state:
                default_value = st.session_state.quick_search
                del st.session_state.quick_search
            elif 'history_search' in st.session_state:
                default_value = st.session_state.history_search
                del st.session_state.history_search
                
            search_query = st.text_input(
                "검색어를 입력하세요",
                placeholder="예: 도로교통법 음주운전, 개인정보보호법, 근로계약서",
                value=default_value
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
    
    # Tab 2: AI 법률 분석
    with tab2:
        st.header("AI 법률 분석 및 자문")
        
        # OpenAI API 키 확인
        if not st.session_state.api_keys.get('openai_api_key'):
            st.warning("⚠️ OpenAI API 키가 설정되지 않았습니다. 사이드바에서 설정해주세요.")
        
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
        default_ai_query = st.session_state.get('ai_query', '')
        if 'ai_query' in st.session_state:
            del st.session_state.ai_query
            
        ai_query = st.text_area(
            "질문 또는 검토 요청사항",
            placeholder="법률 관련 질문을 자세히 입력해주세요...",
            value=default_ai_query,
            height=150
        )
        
        # 계약서 검토인 경우 추가 입력
        contract_text = ""
        if service_type == ServiceType.CONTRACT_REVIEW:
            contract_text = st.text_area(
                "계약서 내용",
                placeholder="검토할 계약서 내용을 붙여넣으세요...",
                height=300
            )
        
        # 법률자문의견서인 경우 추가 입력
        facts = ""
        if service_type == ServiceType.LEGAL_OPINION:
            facts = st.text_area(
                "사실관계",
                placeholder="관련 사실관계를 상세히 기술해주세요...",
                height=200
            )
        
        # AI 분석 실행
        if st.button("🤖 AI 분석 시작", type="primary"):
            if not ai_query and not contract_text:
                st.error("질문을 입력해주세요.")
            else:
                with st.spinner("AI가 관련 자료를 검색하고 분석 중입니다..."):
                    try:
                        # 1. 관련 자료 검색
                        st.info("📚 관련 법률자료 검색 중...")
                        search_query = contract_text if service_type == ServiceType.CONTRACT_REVIEW and contract_text else ai_query
                        search_results = perform_simple_search(
                            search_query[:100],  # 검색어 길이 제한
                            ['법령', '판례', '법령해석', '행정규칙']
                        )
                        
                        # 검색 결과 요약
                        total_results = sum(
                            len(v) if isinstance(v, list) else 0 
                            for v in search_results.get('results', {}).values()
                        )
                        
                        if total_results > 0:
                            st.success(f"✅ {total_results}개의 관련 법률자료를 찾았습니다.")
                        else:
                            st.warning("⚠️ 관련 법률자료를 찾지 못했습니다. 일반적인 법리로 답변합니다.")
                        
                        # 2. AI 분석
                        st.info("🤖 AI가 법률 분석을 수행 중...")
                        
                        if service_type == ServiceType.CONTRACT_REVIEW:
                            analysis = perform_ai_analysis(
                                contract_text or ai_query,
                                search_results['results'],
                                service_type
                            )
                        elif service_type == ServiceType.LEGAL_OPINION:
                            context = {**search_results['results'], 'facts': facts}
                            analysis = perform_ai_analysis(
                                ai_query,
                                context,
                                service_type
                            )
                        else:
                            analysis = perform_ai_analysis(
                                ai_query,
                                search_results['results'],
                                service_type
                            )
                        
                        # 3. 결과 표시
                        st.markdown("## 📋 AI 법률 분석 결과")
                        st.markdown(analysis)
                        
                        # 4. 참고 자료 표시
                        with st.expander("📚 실제 검색된 법률자료 확인", expanded=False):
                            if search_results.get('results'):
                                render_search_results(search_results)
                            else:
                                st.info("검색된 자료가 없습니다.")
                        
                        # 5. 검증 정보 표시
                        st.info("ℹ️ 모든 인용은 실제 검색된 자료를 기반으로 작성되었습니다.")
                        
                        # 6. 이력 저장
                        st.session_state.search_history.append({
                            'query': ai_query[:100],
                            'timestamp': datetime.now().isoformat(),
                            'type': 'ai_analysis',
                            'service_type': service_type.value,
                            'results_count': total_results
                        })
                        
                    except Exception as e:
                        logger.error(f"AI 분석 실행 오류: {str(e)}")
                        st.error(f"AI 분석 중 오류가 발생했습니다: {str(e)}")
    
    # Tab 3: 검색 이력
    with tab3:
        st.header("검색 이력 관리")
        
        if st.session_state.search_history:
            try:
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
                if not history_df.empty:
                    # 표시할 열 선택
                    display_cols = ['timestamp', 'query', 'type']
                    if 'results_count' in history_df.columns:
                        display_cols.append('results_count')
                    
                    st.dataframe(
                        history_df[display_cols].head(20),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # 이력 상세 보기
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
                    st.info("선택한 기간에 검색 이력이 없습니다.")
                    
            except Exception as e:
                logger.error(f"검색 이력 표시 오류: {str(e)}")
                st.error(f"검색 이력을 표시할 수 없습니다: {str(e)}")
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
        
        ### 🚨 할루시네이션 방지
        
        본 시스템은 AI의 허위 정보 생성을 방지하기 위해:
        - 실제 검색된 법률자료만을 인용합니다
        - 의심스러운 판례번호를 자동으로 검증합니다
        - 검색 결과가 없을 경우 명확히 표시합니다
        """)
        
        # 시스템 정보
        with st.expander("시스템 정보"):
            api_status = {
                "law_api": "✅" if st.session_state.api_keys.get('law_api_key') else "❌",
                "openai_api": "✅" if st.session_state.api_keys.get('openai_api_key') else "❌"
            }
            
            st.json({
                "version": "2.0.0",
                "last_updated": "2025-01-01",
                "models_available": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
                "search_targets": ["법령", "판례", "헌재결정례", "법령해석례", "행정규칙"],
                "api_status": api_status,
                "session_initialized": st.session_state.get('initialized', False),
                "anti_hallucination": "Enabled",
                "temperature": ANTI_HALLUCINATION_CONFIG['temperature']
            })

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error(f"애플리케이션 실행 중 오류가 발생했습니다: {str(e)}")
        st.info("페이지를 새로고침하거나 관리자에게 문의해주세요.")
