"""
case_module.py - 판례/심판례 검색 모듈 (Python 3.13 호환 수정판)

이 모듈은 법제처 API를 사용하여 다양한 유형의 판례와 심판례를 검색하고 조회합니다.
지원하는 판례 유형: 판례(대법원/하급심), 헌재결정례, 법령해석례, 행정심판례

개발 가이드의 모든 API 파라미터와 기능을 완벽하게 구현한 버전입니다.
Python 3.13 호환성 문제 해결 - Enum 제거, TypedDict 제거
"""

from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
import logging
from common_api import LawAPIClient, OpenAIHelper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Python 3.13 호환성을 위해 Enum 대신 딕셔너리 상수 사용
class CourtType:
    """법원 종류 상수 클래스"""
    SUPREME = {'code': '400201', 'label': '대법원'}
    LOWER = {'code': '400202', 'label': '하위법원'}


class DecisionType:
    """재결 구분 상수 클래스 (행정심판)"""
    DISMISSAL = {'code': '440201', 'label': '기각'}
    REJECTION = {'code': '440202', 'label': '각하'}
    ACCEPTANCE = {'code': '440203', 'label': '인용'}
    PARTIAL_ACCEPTANCE = {'code': '440204', 'label': '일부인용'}
    WITHDRAWAL = {'code': '440205', 'label': '취하'}
    MEDIATION = {'code': '440206', 'label': '조정'}
    OTHER = {'code': '440207', 'label': '기타'}


class CaseSearcher:
    """판례 및 심판례 검색 클래스 (완전판)"""
    
    # 법원 종류 코드
    COURT_CODES = {
        '대법원': '400201',
        '하위법원': '400202',
        '하급심': '400202'
    }
    
    # 재결 구분 코드 (행정심판)
    DECISION_CODES = {
        '기각': '440201',
        '각하': '440202',
        '인용': '440203',
        '일부인용': '440204',
        '취하': '440205',
        '조정': '440206',
        '기타': '440207'
    }
    
    # 재판부 구분 코드 (헌재)
    TRIBUNAL_CODES = {
        '전원재판부': '430201',
        '지정재판부': '430202'
    }
    
    # 정렬 옵션 (각 API별로 다름)
    SORT_OPTIONS = {
        # 공통
        'name_asc': 'lasc',    # 사건명/법령명 오름차순
        'name_desc': 'ldes',   # 사건명/법령명 내림차순
        'date_asc': 'dasc',    # 날짜 오름차순
        'date_desc': 'ddes',   # 날짜 내림차순
        'number_asc': 'nasc',  # 번호 오름차순
        'number_desc': 'ndes', # 번호 내림차순
        # 헌재결정례 전용
        'end_date_asc': 'efasc',   # 종국일자 오름차순
        'end_date_desc': 'efdes',  # 종국일자 내림차순
    }
    
    # 데이터 출처명 (판례 전용)
    DATA_SOURCES = {
        'tax': '국세법령정보시스템',
        'labor': '근로복지공단산재판례',
        'supreme': '대법원'
    }
    
    def __init__(self, api_client: LawAPIClient = None, ai_helper: OpenAIHelper = None):
        """
        초기화 메서드
        
        Args:
            api_client: LawAPIClient 인스턴스 (없으면 새로 생성)
            ai_helper: OpenAIHelper 인스턴스 (선택사항)
        """
        self.api_client = api_client or LawAPIClient()
        self.ai_helper = ai_helper
    
    # ========== 판례 검색 (대법원/하급심) ==========
    
    def search_court_cases(
        self, 
        query: str = "",
        court: Optional[str] = None,
        court_name: Optional[str] = None,
        date: Optional[str] = None,
        date_range: Optional[Tuple[str, str]] = None,
        search_type: int = 1,
        display: int = 20,
        page: int = 1,
        sort: str = 'date_desc',
        case_number: Optional[str] = None,
        reference_law: Optional[str] = None,
        data_source: Optional[str] = None,
        gana: Optional[str] = None,
        popup: bool = False
    ) -> Dict[str, Any]:
        """
        법원 판례 검색 (수정된 버전)
        """
        try:
            # 기본 파라미터 설정
            params = {
                'search': search_type,
                'display': min(display, 100),
                'page': page,
                'sort': self.SORT_OPTIONS.get(sort, 'ddes'),
                'type': 'json'
            }
            
            # 선택적 파라미터 추가 (None이 아닌 경우만)
            if court and court in self.COURT_CODES:
                params['org'] = self.COURT_CODES[court]
            if court_name:
                params['curt'] = court_name
            if date:
                params['date'] = self._format_date_for_api(date)
            if date_range and len(date_range) == 2:
                params['prncYd'] = f"{self._format_date_for_api(date_range[0])}~{self._format_date_for_api(date_range[1])}"
            if case_number:
                params['nb'] = case_number
            if reference_law:
                params['JO'] = reference_law
            if data_source and data_source in self.DATA_SOURCES:
                params['datSrcNm'] = self.DATA_SOURCES[data_source]
            if gana:
                params['gana'] = gana
            if popup:
                params['popYn'] = 'Y'
            
            # API 호출 (한 번만!)
            result = self.api_client.search(
                target='prec',
                query=query if query else '*',
                **params
            )
            
            # 디버깅용 로그
            logger.debug(f"판례 검색 요청 - query: {query}, params: {params}")
            logger.debug(f"판례 검색 응답 - keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
            
            # 에러 체크
            if isinstance(result, dict) and 'error' in result:
                logger.error(f"판례 검색 API 오류: {result['error']}")
                return {
                    'status': 'error',
                    'message': result['error'],
                    'total_count': 0,
                    'cases': []
                }
            
            # 정상 결과 처리
            if isinstance(result, dict):
                # prec 키 또는 results 키에서 판례 추출
                cases = result.get('prec', result.get('results', []))
                
                return {
                    'status': 'success',
                    'total_count': result.get('totalCnt', 0),
                    'page': page,
                    'cases': self._normalize_court_cases(cases) if isinstance(cases, list) else [],
                    'query': query,
                    'search_params': params
                }
            
            return {
                'status': 'error',
                'message': 'Invalid response format',
                'total_count': 0,
                'cases': []
            }
            
        except Exception as e:
            logger.error(f"법원 판례 검색 중 오류: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'total_count': 0,
                'cases': []
            }
    
    def get_court_case_detail(
        self, 
        case_id: Optional[int] = None,
        case_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        법원 판례 상세 조회
        
        Args:
            case_id: 판례 일련번호 (ID)
            case_name: 판례명 (LM)
            
        Returns:
            판례 상세 정보
        """
        try:
            params = {}
            
            if case_id:
                params['ID'] = case_id
            
            if case_name:
                params['LM'] = case_name
            
            if not params:
                return {
                    'status': 'error',
                    'message': '판례 일련번호(ID) 또는 판례명(LM)이 필요합니다.'
                }
            
            result = self.api_client.get_detail(
                target='prec',
                type='json',
                **params
            )
            
            if isinstance(result, dict) and 'error' not in result:
                return {
                    'status': 'success',
                    'case': self._normalize_court_case_detail(result)
                }
            
            return {
                'status': 'error',
                'message': result.get('error', 'Unknown error')
            }
            
        except Exception as e:
            logger.error(f"판례 상세 조회 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== 헌재결정례 검색 ==========
    
    def search_constitutional_decisions(
        self,
        query: str = "",
        date: Optional[str] = None,
        date_range: Optional[Tuple[str, str]] = None,
        search_type: int = 1,
        display: int = 20,
        page: int = 1,
        sort: str = 'name_asc',
        case_number: Optional[int] = None,
        gana: Optional[str] = None,
        popup: bool = False
    ) -> Dict[str, Any]:
        """
        헌법재판소 결정례 검색 (완전판)
        
        Args:
            query: 검색어
            date: 특정 종국일자 (YYYYMMDD)
            date_range: 종국일자 범위 튜플 (시작일, 종료일) YYYYMMDD 형식
            search_type: 1=헌재결정례명 검색, 2=본문 검색
            display: 결과 개수 (기본 20, 최대 100)
            page: 페이지 번호 (기본 1)
            sort: 정렬 옵션 (기본 name_asc)
                - name_asc/desc: 사건명 오름/내림차순
                - date_asc/desc: 선고일자 오름/내림차순
                - number_asc/desc: 사건번호 오름/내림차순
                - end_date_asc/desc: 종국일자 오름/내림차순
            case_number: 사건번호
            gana: 사전식 검색 (ga, na, da 등)
            popup: 상세화면 팝업창 여부
            
        Returns:
            검색 결과 딕셔너리
        """
        try:
            # 기본 파라미터
            params = {}
            
            # 선택적 파라미터 추가
            if date:
                params['date'] = self._format_date_for_api(date)
            if date_range and len(date_range) == 2:
                params['edYd'] = f"{self._format_date_for_api(date_range[0])}~{self._format_date_for_api(date_range[1])}"
            if case_number:
                params['nb'] = case_number
            if gana:
                params['gana'] = gana
            if popup:
                params['popYn'] = 'Y'
            
            # API 호출
            result = self.api_client.search(
                target='detc',
                query=query if query else '*',
                search=search_type,
                display=min(display, 100),
                page=page,
                sort=self.SORT_OPTIONS.get(sort, 'lasc'),
                type='json',
                **params
            )
            
            # 에러 체크
            if isinstance(result, dict) and 'error' in result:
                logger.error(f"헌재결정례 검색 API 오류: {result['error']}")
                return {
                    'status': 'error',
                    'message': result['error'],
                    'total_count': 0,
                    'decisions': []
                }
            
            # 정상 결과 처리
            if isinstance(result, dict):
                decisions = result.get('detc', result.get('results', []))  # 'detc' 키에서 결정례 추출
                
                return {
                    'status': 'success',
                    'total_count': result.get('totalCnt', 0),
                    'page': page,
                    'decisions': self._normalize_constitutional_decisions(decisions) if isinstance(decisions, list) else [],
                    'query': query,
                    'search_params': params
                }
            
            return {
                'status': 'error',
                'message': 'Invalid response format',
                'total_count': 0,
                'decisions': []
            }
            
        except Exception as e:
            logger.error(f"헌재결정례 검색 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e), 'total_count': 0, 'decisions': []}
    
    def get_constitutional_decision_detail(
        self,
        decision_id: Optional[int] = None,
        decision_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        헌재결정례 상세 조회
        
        Args:
            decision_id: 헌재결정례 일련번호 (ID)
            decision_name: 헌재결정례명 (LM)
            
        Returns:
            헌재결정례 상세 정보
        """
        try:
            params = {}
            
            if decision_id:
                params['ID'] = decision_id
            
            if decision_name:
                params['LM'] = decision_name
            
            if not params:
                return {
                    'status': 'error',
                    'message': '헌재결정례 일련번호(ID) 또는 헌재결정례명(LM)이 필요합니다.'
                }
            
            result = self.api_client.get_detail(
                target='detc',
                type='json',
                **params
            )
            
            if isinstance(result, dict) and 'error' not in result:
                return {
                    'status': 'success',
                    'decision': self._normalize_constitutional_decision_detail(result)
                }
            
            return {
                'status': 'error',
                'message': result.get('error', 'Unknown error')
            }
            
        except Exception as e:
            logger.error(f"헌재결정례 상세 조회 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== 법령해석례 검색 ==========
    
    def search_legal_interpretations(
        self,
        query: str = "",
        requesting_agency: Optional[str] = None,
        responding_agency: Optional[str] = None,
        case_number: Optional[str] = None,
        registration_date_range: Optional[Tuple[str, str]] = None,
        interpretation_date_range: Optional[Tuple[str, str]] = None,
        search_type: int = 1,
        display: int = 20,
        page: int = 1,
        sort: str = 'name_asc',
        gana: Optional[str] = None,
        popup: bool = False
    ) -> Dict[str, Any]:
        """
        법령해석례 검색 (완전판)
        
        Args:
            query: 검색어
            requesting_agency: 질의기관 (inq)
            responding_agency: 회신기관 (rpl)
            case_number: 안건번호 (예: "13-0217" -> "130217")
            registration_date_range: 등록일자 범위 튜플 (시작일, 종료일) YYYYMMDD 형식
            interpretation_date_range: 해석일자 범위 튜플 (시작일, 종료일) YYYYMMDD 형식
            search_type: 1=법령해석례명 검색, 2=본문 검색
            display: 결과 개수 (기본 20, 최대 100)
            page: 페이지 번호 (기본 1)
            sort: 정렬 옵션 (기본 name_asc)
                - name_asc/desc: 법령해석례명 오름/내림차순
                - date_asc/desc: 해석일자 오름/내림차순
                - number_asc/desc: 안건번호 오름/내림차순
            gana: 사전식 검색 (ga, na, da 등)
            popup: 상세화면 팝업창 여부
            
        Returns:
            검색 결과 딕셔너리
        """
        try:
            # 선택적 파라미터
            params = {}
            
            if requesting_agency:
                params['inq'] = requesting_agency
            if responding_agency:
                params['rpl'] = responding_agency
            if case_number:
                params['itmno'] = case_number.replace('-', '')  # 하이픈 제거
            if registration_date_range and len(registration_date_range) == 2:
                params['regYd'] = f"{self._format_date_for_api(registration_date_range[0])}~{self._format_date_for_api(registration_date_range[1])}"
            if interpretation_date_range and len(interpretation_date_range) == 2:
                params['explYd'] = f"{self._format_date_for_api(interpretation_date_range[0])}~{self._format_date_for_api(interpretation_date_range[1])}"
            if gana:
                params['gana'] = gana
            if popup:
                params['popYn'] = 'Y'
            
            # API 호출
            result = self.api_client.search(
                target='expc',
                query=query if query else '*',
                search=search_type,
                display=min(display, 100),
                page=page,
                sort=self.SORT_OPTIONS.get(sort, 'lasc'),
                type='json',
                **params
            )
            
            # 에러 체크
            if isinstance(result, dict) and 'error' in result:
                logger.error(f"법령해석례 검색 API 오류: {result['error']}")
                return {
                    'status': 'error',
                    'message': result['error'],
                    'total_count': 0,
                    'interpretations': []
                }
            
            # 정상 결과 처리
            if isinstance(result, dict):
                interpretations = result.get('expc', result.get('results', []))  # 'expc' 키에서 해석례 추출
                
                return {
                    'status': 'success',
                    'total_count': result.get('totalCnt', 0),
                    'page': page,
                    'interpretations': self._normalize_legal_interpretations(interpretations) if isinstance(interpretations, list) else [],
                    'query': query,
                    'search_params': params
                }
            
            return {
                'status': 'error',
                'message': 'Invalid response format',
                'total_count': 0,
                'interpretations': []
            }
            
        except Exception as e:
            logger.error(f"법령해석례 검색 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e), 'total_count': 0, 'interpretations': []}
    
    def get_legal_interpretation_detail(
        self,
        interpretation_id: Optional[int] = None,
        interpretation_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        법령해석례 상세 조회
        
        Args:
            interpretation_id: 법령해석례 일련번호 (ID)
            interpretation_name: 법령해석례명 (LM)
            
        Returns:
            법령해석례 상세 정보
        """
        try:
            params = {}
            
            if interpretation_id:
                params['ID'] = interpretation_id
            
            if interpretation_name:
                params['LM'] = interpretation_name
            
            if not params:
                return {
                    'status': 'error',
                    'message': '법령해석례 일련번호(ID) 또는 법령해석례명(LM)이 필요합니다.'
                }
            
            result = self.api_client.get_detail(
                target='expc',
                type='json',
                **params
            )
            
            if isinstance(result, dict) and 'error' not in result:
                return {
                    'status': 'success',
                    'interpretation': self._normalize_legal_interpretation_detail(result)
                }
            
            return {
                'status': 'error',
                'message': result.get('error', 'Unknown error')
            }
            
        except Exception as e:
            logger.error(f"법령해석례 상세 조회 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== 행정심판례 검색 ==========
    
    def search_admin_tribunals(
        self,
        query: str = "",
        decision_type: Optional[str] = None,
        decision_date: Optional[str] = None,
        decision_date_range: Optional[Tuple[str, str]] = None,
        disposition_date_range: Optional[Tuple[str, str]] = None,
        search_type: int = 1,
        display: int = 20,
        page: int = 1,
        sort: str = 'name_asc',
        gana: Optional[str] = None,
        popup: bool = False
    ) -> Dict[str, Any]:
        """
        행정심판례 검색 (완전판)
        
        Args:
            query: 검색어
            decision_type: 재결례 유형 (기각, 각하, 인용, 일부인용, 취하, 조정, 기타)
            decision_date: 특정 의결일자 (YYYYMMDD)
            decision_date_range: 의결일자 범위 튜플 (시작일, 종료일) YYYYMMDD 형식
            disposition_date_range: 처분일자 범위 튜플 (시작일, 종료일) YYYYMMDD 형식
            search_type: 1=행정심판례명 검색, 2=본문 검색
            display: 결과 개수 (기본 20, 최대 100)
            page: 페이지 번호 (기본 1)
            sort: 정렬 옵션 (기본 name_asc)
                - name_asc/desc: 재결례명 오름/내림차순
                - date_asc/desc: 의결일자 오름/내림차순
                - number_asc/desc: 사건번호 오름/내림차순
            gana: 사전식 검색 (ga, na, da 등)
            popup: 상세화면 팝업창 여부
            
        Returns:
            검색 결과 딕셔너리
        """
        try:
            # 선택적 파라미터
            params = {}
            
            if decision_type and decision_type in self.DECISION_CODES:
                params['cls'] = self.DECISION_CODES[decision_type]
            if decision_date:
                params['date'] = self._format_date_for_api(decision_date)
            if decision_date_range and len(decision_date_range) == 2:
                params['rslYd'] = f"{self._format_date_for_api(decision_date_range[0])}~{self._format_date_for_api(decision_date_range[1])}"
            if disposition_date_range and len(disposition_date_range) == 2:
                params['dpaYd'] = f"{self._format_date_for_api(disposition_date_range[0])}~{self._format_date_for_api(disposition_date_range[1])}"
            if gana:
                params['gana'] = gana
            if popup:
                params['popYn'] = 'Y'
            
            # API 호출
            result = self.api_client.search(
                target='decc',
                query=query if query else '*',
                search=search_type,
                display=min(display, 100),
                page=page,
                sort=self.SORT_OPTIONS.get(sort, 'lasc'),
                type='json',
                **params
            )
            
            # 에러 체크
            if isinstance(result, dict) and 'error' in result:
                logger.error(f"행정심판례 검색 API 오류: {result['error']}")
                return {
                    'status': 'error',
                    'message': result['error'],
                    'total_count': 0,
                    'tribunals': []
                }
            
            # 정상 결과 처리
            if isinstance(result, dict):
                tribunals = result.get('decc', result.get('results', []))  # 'decc' 키에서 심판례 추출
                
                return {
                    'status': 'success',
                    'total_count': result.get('totalCnt', 0),
                    'page': page,
                    'tribunals': self._normalize_admin_tribunals(tribunals) if isinstance(tribunals, list) else [],
                    'query': query,
                    'search_params': params
                }
            
            return {
                'status': 'error',
                'message': 'Invalid response format',
                'total_count': 0,
                'tribunals': []
            }
            
        except Exception as e:
            logger.error(f"행정심판례 검색 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e), 'total_count': 0, 'tribunals': []}
    
    def get_admin_tribunal_detail(
        self,
        tribunal_id: Optional[int] = None,
        tribunal_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        행정심판례 상세 조회
        
        Args:
            tribunal_id: 행정심판례 일련번호 (ID)
            tribunal_name: 행정심판례명 (LM)
            
        Returns:
            행정심판례 상세 정보
        """
        try:
            params = {}
            
            if tribunal_id:
                params['ID'] = tribunal_id
            
            if tribunal_name:
                params['LM'] = tribunal_name
            
            if not params:
                return {
                    'status': 'error',
                    'message': '행정심판례 일련번호(ID) 또는 행정심판례명(LM)이 필요합니다.'
                }
            
            result = self.api_client.get_detail(
                target='decc',
                type='json',
                **params
            )
            
            if isinstance(result, dict) and 'error' not in result:
                return {
                    'status': 'success',
                    'tribunal': self._normalize_admin_tribunal_detail(result)
                }
            
            return {
                'status': 'error',
                'message': result.get('error', 'Unknown error')
            }
            
        except Exception as e:
            logger.error(f"행정심판례 상세 조회 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== 통합 검색 ==========
    
    def search_all_precedents(
        self,
        query: str,
        include_types: Optional[List[str]] = None,
        limit_per_type: int = 10,
        search_in_content: bool = False
    ) -> Dict[str, Any]:
        """
        모든 유형의 판례/심판례 통합 검색
        
        Args:
            query: 검색어
            include_types: 포함할 유형 리스트 ['court', 'constitutional', 'interpretation', 'admin']
                          None이면 모든 유형 검색
            limit_per_type: 각 유형별 최대 결과 수 (기본 10)
            search_in_content: True면 본문 검색, False면 제목 검색 (기본 False)
            
        Returns:
            통합 검색 결과
        """
        try:
            # 기본값: 모든 유형 검색
            if include_types is None:
                include_types = ['court', 'constitutional', 'interpretation', 'admin']
            
            search_type = 2 if search_in_content else 1
            
            results = {
                'status': 'success',
                'query': query,
                'search_type': 'content' if search_in_content else 'title',
                'results': {},
                'summary': {}
            }
            
            # 각 유형별 검색 수행
            if 'court' in include_types:
                court_result = self.search_court_cases(
                    query=query,
                    search_type=search_type,
                    display=limit_per_type
                )
                if court_result.get('status') == 'success':
                    results['results']['court_cases'] = {
                        'total': court_result.get('total_count', 0),
                        'items': court_result.get('cases', [])
                    }
            
            if 'constitutional' in include_types:
                const_result = self.search_constitutional_decisions(
                    query=query,
                    search_type=search_type,
                    display=limit_per_type
                )
                if const_result.get('status') == 'success':
                    results['results']['constitutional_decisions'] = {
                        'total': const_result.get('total_count', 0),
                        'items': const_result.get('decisions', [])
                    }
            
            if 'interpretation' in include_types:
                interp_result = self.search_legal_interpretations(
                    query=query,
                    search_type=search_type,
                    display=limit_per_type
                )
                if interp_result.get('status') == 'success':
                    results['results']['legal_interpretations'] = {
                        'total': interp_result.get('total_count', 0),
                        'items': interp_result.get('interpretations', [])
                    }
            
            if 'admin' in include_types:
                admin_result = self.search_admin_tribunals(
                    query=query,
                    search_type=search_type,
                    display=limit_per_type
                )
                if admin_result.get('status') == 'success':
                    results['results']['admin_tribunals'] = {
                        'total': admin_result.get('total_count', 0),
                        'items': admin_result.get('tribunals', [])
                    }
            
            # 요약 통계
            total_count = 0
            for result_type, result_data in results['results'].items():
                count = result_data.get('total', 0)
                total_count += count
                results['summary'][result_type] = count
            
            results['summary']['total'] = total_count
            
            return results
            
        except Exception as e:
            logger.error(f"통합 판례 검색 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def get_case_detail(self, case_type: str, case_id: int) -> Dict[str, Any]:
        """
        판례 유형별 상세 조회 (통합 인터페이스)
        
        Args:
            case_type: 판례 유형 ('court', 'constitutional', 'interpretation', 'admin')
            case_id: 판례 일련번호
            
        Returns:
            판례 상세 정보
        """
        try:
            if case_type == 'court':
                return self.get_court_case_detail(case_id=case_id)
            elif case_type == 'constitutional':
                return self.get_constitutional_decision_detail(decision_id=case_id)
            elif case_type == 'interpretation':
                return self.get_legal_interpretation_detail(interpretation_id=case_id)
            elif case_type == 'admin':
                return self.get_admin_tribunal_detail(tribunal_id=case_id)
            else:
                return {
                    'status': 'error',
                    'message': f"지원하지 않는 판례 유형: {case_type}"
                }
                
        except Exception as e:
            logger.error(f"판례 상세 조회 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== AI 분석 기능 ==========
    
    def analyze_case_with_ai(
        self,
        case_type: str,
        case_id: int,
        analysis_type: str = 'summary',
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        AI를 활용한 판례 분석
        
        Args:
            case_type: 판례 유형
            case_id: 판례 일련번호
            analysis_type: 분석 유형
                - 'summary': 요약
                - 'key_points': 핵심 쟁점
                - 'implications': 법적 의미
                - 'comparison': 유사 판례 비교
                - 'custom': 사용자 정의 분석
            custom_prompt: 사용자 정의 프롬프트 (analysis_type이 'custom'일 때 사용)
            
        Returns:
            AI 분석 결과
        """
        if not self.ai_helper:
            return {
                'status': 'error',
                'message': 'AI 분석 기능을 사용하려면 OpenAIHelper가 필요합니다.'
            }
        
        try:
            # 판례 상세 정보 조회
            detail_result = self.get_case_detail(case_type, case_id)
            
            if detail_result.get('status') != 'success':
                return detail_result
            
            # 판례 내용 추출
            case_data = detail_result.get('case') or \
                       detail_result.get('decision') or \
                       detail_result.get('interpretation') or \
                       detail_result.get('tribunal', {})
            
            # 분석 프롬프트 생성
            prompts = {
                'summary': "다음 판례를 핵심만 간단히 3-5문장으로 요약해주세요.",
                'key_points': "다음 판례의 핵심 쟁점과 법원의 판단을 번호를 매겨 정리해주세요.",
                'implications': "다음 판례가 갖는 법적 의미와 향후 유사 사건에 미칠 영향을 분석해주세요.",
                'comparison': "다음 판례와 유사한 선례가 있다면 비교 분석해주세요.",
                'custom': custom_prompt or "다음 판례를 분석해주세요."
            }
            
            prompt = prompts.get(analysis_type, prompts['summary'])
            full_prompt = f"{prompt}\n\n판례 정보:\n{self._format_case_for_ai(case_data)}"
            
            analysis = self.ai_helper.analyze_legal_text(
                query=full_prompt,
                context=str(case_data)
            )
            
            return {
                'status': 'success',
                'case_id': case_id,
                'case_type': case_type,
                'analysis_type': analysis_type,
                'analysis': analysis,
                'case_summary': {
                    'title': case_data.get('title') or case_data.get('사건명'),
                    'date': case_data.get('date') or case_data.get('선고일자'),
                    'court': case_data.get('court') or case_data.get('법원명')
                }
            }
            
        except Exception as e:
            logger.error(f"AI 판례 분석 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def compare_cases_with_ai(
        self,
        case1: Dict[str, Any],
        case2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        두 판례를 AI로 비교 분석
        
        Args:
            case1: 첫 번째 판례 정보 {'type': str, 'id': int}
            case2: 두 번째 판례 정보 {'type': str, 'id': int}
            
        Returns:
            비교 분석 결과
        """
        if not self.ai_helper:
            return {
                'status': 'error',
                'message': 'AI 분석 기능을 사용하려면 OpenAIHelper가 필요합니다.'
            }
        
        try:
            # 두 판례 정보 조회
            detail1 = self.get_case_detail(case1['type'], case1['id'])
            detail2 = self.get_case_detail(case2['type'], case2['id'])
            
            if detail1.get('status') != 'success' or detail2.get('status') != 'success':
                return {
                    'status': 'error',
                    'message': '판례 정보를 조회할 수 없습니다.'
                }
            
            # 판례 데이터 추출
            data1 = detail1.get('case') or detail1.get('decision') or \
                   detail1.get('interpretation') or detail1.get('tribunal', {})
            data2 = detail2.get('case') or detail2.get('decision') or \
                   detail2.get('interpretation') or detail2.get('tribunal', {})
            
            prompt = f"""
            다음 두 판례를 비교 분석해주세요:
            
            [판례 1]
            {self._format_case_for_ai(data1)}
            
            [판례 2]
            {self._format_case_for_ai(data2)}
            
            다음 관점에서 비교해주세요:
            1. 핵심 쟁점의 유사점과 차이점
            2. 법원의 판단 기준 비교
            3. 판결 결과의 차이와 그 이유
            4. 법리 발전 측면에서의 의미
            """
            
            comparison = self.ai_helper.analyze_legal_text(
                query=prompt,
                context=f"판례1: {str(data1)}\n\n판례2: {str(data2)}"
            )
            
            return {
                'status': 'success',
                'case1': {
                    'id': case1['id'],
                    'type': case1['type'],
                    'title': data1.get('title') or data1.get('사건명')
                },
                'case2': {
                    'id': case2['id'],
                    'type': case2['type'],
                    'title': data2.get('title') or data2.get('사건명')
                },
                'comparison': comparison
            }
            
        except Exception as e:
            logger.error(f"판례 비교 분석 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== 헬퍼 메서드 (결과 정규화) ==========
    
    def _normalize_court_cases(self, cases: List[Dict]) -> List[Dict]:
        """법원 판례 검색 결과 정규화"""
        normalized = []
        for case in cases:
            normalized.append({
                'id': case.get('판례일련번호'),
                'title': case.get('사건명'),
                'case_number': case.get('사건번호'),
                'court': case.get('법원명'),
                'court_type': case.get('법원종류코드'),
                'date': case.get('선고일자'),
                'type': case.get('사건종류명'),
                'type_code': case.get('사건종류코드'),
                'judgment_type': case.get('판결유형'),
                'judgment': case.get('선고'),
                'data_source': case.get('데이터출처명'),
                'url': case.get('판례상세링크')
            })
        return normalized
    
    def _normalize_court_case_detail(self, case: Dict) -> Dict:
        """법원 판례 상세 정보 정규화"""
        return {
            'id': case.get('판례정보일련번호'),
            'title': case.get('사건명'),
            'case_number': case.get('사건번호'),
            'court': case.get('법원명'),
            'court_type_code': case.get('법원종류코드'),
            'date': case.get('선고일자'),
            'judgment': case.get('선고'),
            'type': case.get('사건종류명'),
            'type_code': case.get('사건종류코드'),
            'judgment_type': case.get('판결유형'),
            'issues': case.get('판시사항'),
            'summary': case.get('판결요지'),
            'reference_laws': case.get('참조조문'),
            'reference_cases': case.get('참조판례'),
            'content': case.get('판례내용')
        }
    
    def _normalize_constitutional_decisions(self, decisions: List[Dict]) -> List[Dict]:
        """헌재결정례 검색 결과 정규화"""
        normalized = []
        for decision in decisions:
            normalized.append({
                'id': decision.get('헌재결정례일련번호'),
                'title': decision.get('사건명'),
                'case_number': decision.get('사건번호'),
                'date': decision.get('종국일자'),
                'url': decision.get('헌재결정례상세링크')
            })
        return normalized
    
    def _normalize_constitutional_decision_detail(self, decision: Dict) -> Dict:
        """헌재결정례 상세 정보 정규화"""
        return {
            'id': decision.get('헌재결정례일련번호'),
            'title': decision.get('사건명'),
            'case_number': decision.get('사건번호'),
            'date': decision.get('종국일자'),
            'type': decision.get('사건종류명'),
            'type_code': decision.get('사건종류코드'),
            'court_type': decision.get('재판부구분코드'),  # 전원재판부/지정재판부
            'issues': decision.get('판시사항'),
            'summary': decision.get('결정요지'),
            'content': decision.get('전문'),
            'reference_laws': decision.get('참조조문'),
            'reference_cases': decision.get('참조판례'),
            'target_provisions': decision.get('심판대상조문')
        }
    
    def _normalize_legal_interpretations(self, interpretations: List[Dict]) -> List[Dict]:
        """법령해석례 검색 결과 정규화"""
        normalized = []
        for interp in interpretations:
            normalized.append({
                'id': interp.get('법령해석례일련번호'),
                'title': interp.get('안건명'),
                'case_number': interp.get('안건번호'),
                'requesting_agency': interp.get('질의기관명'),
                'requesting_agency_code': interp.get('질의기관코드'),
                'responding_agency': interp.get('회신기관명'),
                'responding_agency_code': interp.get('회신기관코드'),
                'date': interp.get('회신일자'),
                'url': interp.get('법령해석례상세링크')
            })
        return normalized
    
    def _normalize_legal_interpretation_detail(self, interpretation: Dict) -> Dict:
        """법령해석례 상세 정보 정규화"""
        return {
            'id': interpretation.get('법령해석례일련번호'),
            'title': interpretation.get('안건명'),
            'case_number': interpretation.get('안건번호'),
            'interpretation_date': interpretation.get('해석일자'),
            'interpretation_agency': interpretation.get('해석기관명'),
            'interpretation_agency_code': interpretation.get('해석기관코드'),
            'requesting_agency': interpretation.get('질의기관명'),
            'requesting_agency_code': interpretation.get('질의기관코드'),
            'management_agency_code': interpretation.get('관리기관코드'),
            'registration_date': interpretation.get('등록일시'),
            'question': interpretation.get('질의요지'),
            'answer': interpretation.get('회답'),
            'reasoning': interpretation.get('이유')
        }
    
    def _normalize_admin_tribunals(self, tribunals: List[Dict]) -> List[Dict]:
        """행정심판례 검색 결과 정규화"""
        normalized = []
        for tribunal in tribunals:
            normalized.append({
                'id': tribunal.get('행정심판재결례일련번호'),
                'title': tribunal.get('사건명'),
                'case_number': tribunal.get('사건번호'),
                'disposition_date': tribunal.get('처분일자'),
                'decision_date': tribunal.get('의결일자'),
                'disposition_agency': tribunal.get('처분청'),
                'tribunal_agency': tribunal.get('재결청'),
                'decision_type': tribunal.get('재결구분명'),
                'decision_type_code': tribunal.get('재결구분코드'),
                'url': tribunal.get('행정심판례상세링크')
            })
        return normalized
    
    def _normalize_admin_tribunal_detail(self, tribunal: Dict) -> Dict:
        """행정심판례 상세 정보 정규화"""
        return {
            'id': tribunal.get('행정심판례일련번호'),
            'title': tribunal.get('사건명'),
            'case_number': tribunal.get('사건번호'),
            'disposition_date': tribunal.get('처분일자'),
            'decision_date': tribunal.get('의결일자'),
            'disposition_agency': tribunal.get('처분청'),
            'tribunal_agency': tribunal.get('재결청'),
            'decision_type': tribunal.get('재결례유형명'),
            'decision_type_code': tribunal.get('재결례유형코드'),
            'order': tribunal.get('주문'),
            'claim': tribunal.get('청구취지'),
            'reasoning': tribunal.get('이유'),
            'summary': tribunal.get('재결요지')
        }
    
    # ========== 유틸리티 메서드 ==========
    
    def _format_date_for_api(self, date: Union[str, datetime]) -> str:
        """
        날짜를 API 형식(YYYYMMDD)으로 변환
        
        Args:
            date: 날짜 문자열 또는 datetime 객체
            
        Returns:
            YYYYMMDD 형식의 문자열
        """
        if isinstance(date, datetime):
            return date.strftime('%Y%m%d')
        elif isinstance(date, str):
            # 이미 YYYYMMDD 형식인 경우
            if len(date) == 8 and date.isdigit():
                return date
            
            # 다양한 형식 처리
            date = date.strip()
            
            # 구분자 제거
            for sep in ['-', '/', '.', '년', '월', '일', ' ']:
                date = date.replace(sep, '')
            
            # 8자리 숫자로 변환
            if len(date) == 8 and date.isdigit():
                return date
        
        raise ValueError(f"날짜 형식을 변환할 수 없습니다: {date}")
    
    def _format_case_for_ai(self, case_data: Dict) -> str:
        """AI 분석을 위해 판례 데이터를 포맷팅"""
        formatted = []
        
        # 기본 정보
        if case_data.get('title'):
            formatted.append(f"사건명: {case_data['title']}")
        if case_data.get('case_number'):
            formatted.append(f"사건번호: {case_data['case_number']}")
        if case_data.get('court'):
            formatted.append(f"법원: {case_data['court']}")
        if case_data.get('date'):
            formatted.append(f"선고일: {case_data['date']}")
        
        # 핵심 내용
        if case_data.get('issues'):
            formatted.append(f"\n판시사항:\n{case_data['issues']}")
        if case_data.get('summary'):
            formatted.append(f"\n판결요지:\n{case_data['summary']}")
        if case_data.get('reasoning'):
            formatted.append(f"\n이유:\n{case_data['reasoning']}")
        
        # 전문 (길이 제한)
        if case_data.get('content'):
            content = case_data['content']
            if len(content) > 3000:
                content = content[:3000] + "...(이하 생략)"
            formatted.append(f"\n판례 내용:\n{content}")
        
        return '\n'.join(formatted)
    
    def get_available_courts(self) -> List[str]:
        """사용 가능한 법원 목록 반환"""
        return list(self.COURT_CODES.keys())
    
    def get_available_decision_types(self) -> List[str]:
        """사용 가능한 재결 구분 목록 반환"""
        return list(self.DECISION_CODES.keys())
    
    def get_available_sort_options(self) -> Dict[str, str]:
        """사용 가능한 정렬 옵션 반환"""
        return {
            'name_asc': '이름 오름차순',
            'name_desc': '이름 내림차순',
            'date_asc': '날짜 오름차순',
            'date_desc': '날짜 내림차순',
            'number_asc': '번호 오름차순',
            'number_desc': '번호 내림차순',
            'end_date_asc': '종국일자 오름차순 (헌재 전용)',
            'end_date_desc': '종국일자 내림차순 (헌재 전용)'
        }
    
    def get_data_sources(self) -> Dict[str, str]:
        """사용 가능한 데이터 출처 반환"""
        return self.DATA_SOURCES.copy()


# ========== 고급 검색 클래스 ==========

class AdvancedCaseSearcher(CaseSearcher):
    """고급 검색 기능을 제공하는 확장 클래스"""
    
    def search_by_keywords(
        self,
        keywords: List[str],
        operator: str = 'AND',
        case_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        여러 키워드로 복합 검색
        
        Args:
            keywords: 검색 키워드 리스트
            operator: 'AND' 또는 'OR' 연산자
            case_types: 검색할 판례 유형 리스트
            
        Returns:
            검색 결과
        """
        if operator == 'AND':
            query = ' '.join(keywords)
        else:  # OR
            query = ' OR '.join(keywords)
        
        return self.search_all_precedents(
            query=query,
            include_types=case_types
        )
    
    def search_by_date_range(
        self,
        start_date: str,
        end_date: str,
        case_type: str = 'court'
    ) -> Dict[str, Any]:
        """
        날짜 범위로 판례 검색
        
        Args:
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            case_type: 판례 유형
            
        Returns:
            검색 결과
        """
        if case_type == 'court':
            return self.search_court_cases(
                date_range=(start_date, end_date)
            )
        elif case_type == 'constitutional':
            return self.search_constitutional_decisions(
                date_range=(start_date, end_date)
            )
        elif case_type == 'interpretation':
            return self.search_legal_interpretations(
                interpretation_date_range=(start_date, end_date)
            )
        elif case_type == 'admin':
            return self.search_admin_tribunals(
                decision_date_range=(start_date, end_date)
            )
        else:
            return {'status': 'error', 'message': f"지원하지 않는 유형: {case_type}"}
    
    def get_recent_cases(
        self,
        days: int = 30,
        case_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        최근 n일 이내의 판례 조회
        
        Args:
            days: 조회할 일수
            case_types: 조회할 판례 유형
            
        Returns:
            최근 판례 목록
        """
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')
        
        results = {}
        
        if not case_types:
            case_types = ['court', 'constitutional', 'interpretation', 'admin']
        
        for case_type in case_types:
            result = self.search_by_date_range(start_str, end_str, case_type)
            if result.get('status') == 'success':
                results[case_type] = result
        
        return {
            'status': 'success',
            'period': f"{start_str} ~ {end_str}",
            'days': days,
            'results': results
        }


# ========== 테스트 코드 ==========

if __name__ == "__main__":
    # 테스트를 위한 예제 코드
    import os
    from dotenv import load_dotenv
    
    # 환경변수 로드
    load_dotenv()
    
    # CaseSearcher 인스턴스 생성
    searcher = CaseSearcher()
    
    print("="*50)
    print("법제처 API - 판례/심판례 검색 모듈 테스트")
    print("="*50)
    
    # 1. 법원 판례 검색 테스트 (모든 파라미터 활용)
    print("\n[1] 법원 판례 검색 - 도로교통법 관련 대법원 판례")
    court_results = searcher.search_court_cases(
        query="도로교통법",
        court="대법원",
        search_type=1,  # 제목 검색
        display=5,
        sort='date_desc',
        gana='da'  # 'ㄷ'으로 시작하는 판례
    )
    
    if court_results.get('status') == 'success':
        print(f"✓ 검색 성공: 총 {court_results.get('total_count')}건")
        for idx, case in enumerate(court_results.get('cases', [])[:3], 1):
            print(f"  {idx}. {case.get('title')}")
            print(f"     - 법원: {case.get('court')}")
            print(f"     - 날짜: {case.get('date')}")
            print(f"     - 사건번호: {case.get('case_number')}")
    else:
        print(f"✗ 검색 실패: {court_results.get('message')}")
    
    # 2. 헌재결정례 검색 테스트
    print("\n[2] 헌재결정례 검색 - 기본권 관련")
    const_results = searcher.search_constitutional_decisions(
        query="기본권",
        sort='end_date_desc',  # 종국일자 내림차순
        display=5
    )
    
    if const_results.get('status') == 'success':
        print(f"✓ 검색 성공: 총 {const_results.get('total_count')}건")
        for idx, decision in enumerate(const_results.get('decisions', [])[:3], 1):
            print(f"  {idx}. {decision.get('title')}")
            print(f"     - 사건번호: {decision.get('case_number')}")
            print(f"     - 종국일자: {decision.get('date')}")
    else:
        print(f"✗ 검색 실패: {const_results.get('message')}")
    
    # 3. 법령해석례 검색 테스트
    print("\n[3] 법령해석례 검색 - 건축법 관련")
    interp_results = searcher.search_legal_interpretations(
        query="건축법",
        sort='date_desc',
        display=5
    )
    
    if interp_results.get('status') == 'success':
        print(f"✓ 검색 성공: 총 {interp_results.get('total_count')}건")
        for idx, interp in enumerate(interp_results.get('interpretations', [])[:3], 1):
            print(f"  {idx}. {interp.get('title')}")
            print(f"     - 질의기관: {interp.get('requesting_agency')}")
            print(f"     - 회신기관: {interp.get('responding_agency')}")
            print(f"     - 회신일자: {interp.get('date')}")
    else:
        print(f"✗ 검색 실패: {interp_results.get('message')}")
    
    # 4. 행정심판례 검색 테스트
    print("\n[4] 행정심판례 검색 - 영업정지 관련 인용 사례")
    admin_results = searcher.search_admin_tribunals(
        query="영업정지",
        decision_type="인용",  # 인용된 사례만
        sort='date_desc',
        display=5
    )
    
    if admin_results.get('status') == 'success':
        print(f"✓ 검색 성공: 총 {admin_results.get('total_count')}건")
        for idx, tribunal in enumerate(admin_results.get('tribunals', [])[:3], 1):
            print(f"  {idx}. {tribunal.get('title')}")
            print(f"     - 재결구분: {tribunal.get('decision_type')}")
            print(f"     - 처분청: {tribunal.get('disposition_agency')}")
            print(f"     - 의결일자: {tribunal.get('decision_date')}")
    else:
        print(f"✗ 검색 실패: {admin_results.get('message')}")
    
    # 5. 통합 검색 테스트
    print("\n[5] 통합 판례 검색 - '개인정보' 키워드")
    all_results = searcher.search_all_precedents(
        query="개인정보",
        limit_per_type=3,
        search_in_content=False  # 제목만 검색
    )
    
    if all_results.get('status') == 'success':
        print(f"✓ 검색 성공")
        print(f"  전체 결과: {all_results['summary']['total']}건")
        for result_type, count in all_results['summary'].items():
            if result_type != 'total':
                print(f"  - {result_type}: {count}건")
    else:
        print(f"✗ 검색 실패: {all_results.get('message')}")
    
    # 6. 고급 검색 테스트
    print("\n[6] 고급 검색 - 최근 30일 판례")
    advanced_searcher = AdvancedCaseSearcher()
    recent_results = advanced_searcher.get_recent_cases(days=30, case_types=['court'])
    
    if recent_results.get('status') == 'success':
        print(f"✓ 최근 30일 판례 검색 성공")
        print(f"  기간: {recent_results['period']}")
        for case_type, result in recent_results['results'].items():
            if result.get('status') == 'success':
                count = result.get('total_count', 0)
                print(f"  - {case_type}: {count}건")
    
    print("\n" + "="*50)
    print("테스트 완료!")
    print("="*50)
