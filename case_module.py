"""
case_module.py - 판례/심판례 검색 모듈

이 모듈은 법제처 API를 사용하여 다양한 유형의 판례와 심판례를 검색하고 조회합니다.
지원하는 판례 유형: 판례(대법원/하급심), 헌재결정례, 법령해석례, 행정심판례
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import logging
from common_api import LawAPIClient, OpenAIHelper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CaseSearcher:
    """판례 및 심판례 검색 클래스"""
    
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
    
    # 정렬 옵션
    SORT_OPTIONS = {
        'name_asc': 'lasc',    # 사건명 오름차순
        'name_desc': 'ldes',   # 사건명 내림차순
        'date_asc': 'dasc',    # 날짜 오름차순
        'date_desc': 'ddes',   # 날짜 내림차순 (기본값)
        'number_asc': 'nasc',  # 번호 오름차순
        'number_desc': 'ndes'  # 번호 내림차순
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
        query: str,
        court: Optional[str] = None,
        date_range: Optional[tuple] = None,
        search_type: int = 1,
        display: int = 20,
        page: int = 1,
        sort: str = 'date_desc',
        case_number: Optional[str] = None,
        reference_law: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        법원 판례 검색
        
        Args:
            query: 검색어
            court: 법원 종류 ('대법원', '하위법원') 또는 법원명
            date_range: 선고일자 범위 튜플 (시작일, 종료일) YYYYMMDD 형식
            search_type: 1=판례명 검색, 2=본문 검색
            display: 결과 개수 (최대 100)
            page: 페이지 번호
            sort: 정렬 옵션
            case_number: 사건번호
            reference_law: 참조법령명
            
        Returns:
            검색 결과 딕셔너리
        """
        try:
            params = {
                'search': search_type,
                'query': query,
                'display': min(display, 100),
                'page': page,
                'sort': self.SORT_OPTIONS.get(sort, 'ddes')
            }
            
            # 법원 종류/이름 처리
            if court:
                if court in self.COURT_CODES:
                    params['org'] = self.COURT_CODES[court]
                else:
                    params['curt'] = court
            
            # 날짜 범위 처리
            if date_range and len(date_range) == 2:
                params['prncYd'] = f"{date_range[0]}~{date_range[1]}"
            
            # 사건번호 검색
            if case_number:
                params['nb'] = case_number
            
            # 참조법령 검색
            if reference_law:
                params['JO'] = reference_law
            
            # API 호출
            result = self.api_client.search('prec', **params)
            
            # 결과 정규화
            if result.get('status') == 'success':
                cases = self._normalize_court_cases(result.get('data', []))
                return {
                    'status': 'success',
                    'total_count': result.get('totalCnt', 0),
                    'page': page,
                    'cases': cases,
                    'query': query
                }
            
            return result
            
        except Exception as e:
            logger.error(f"법원 판례 검색 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def get_court_case_detail(self, case_id: int) -> Dict[str, Any]:
        """
        법원 판례 상세 조회
        
        Args:
            case_id: 판례 일련번호
            
        Returns:
            판례 상세 정보
        """
        try:
            result = self.api_client.get_detail('prec', case_id)
            
            if result.get('status') == 'success':
                return {
                    'status': 'success',
                    'case': self._normalize_court_case_detail(result.get('data', {}))
                }
            
            return result
            
        except Exception as e:
            logger.error(f"판례 상세 조회 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== 헌재결정례 검색 ==========
    
    def search_constitutional_decisions(
        self,
        query: str = "",
        date_range: Optional[tuple] = None,
        search_type: int = 1,
        display: int = 20,
        page: int = 1,
        sort: str = 'date_desc',
        case_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        헌법재판소 결정례 검색
        
        Args:
            query: 검색어
            date_range: 종국일자 범위 튜플 (시작일, 종료일) YYYYMMDD 형식
            search_type: 1=헌재결정례명 검색, 2=본문 검색
            display: 결과 개수
            page: 페이지 번호
            sort: 정렬 옵션
            case_number: 사건번호
            
        Returns:
            검색 결과 딕셔너리
        """
        try:
            params = {
                'search': search_type,
                'query': query,
                'display': min(display, 100),
                'page': page,
                'sort': self.SORT_OPTIONS.get(sort, 'ddes')
            }
            
            # 날짜 범위 처리
            if date_range and len(date_range) == 2:
                params['edYd'] = f"{date_range[0]}~{date_range[1]}"
            
            # 사건번호 검색
            if case_number:
                params['nb'] = case_number
            
            # API 호출
            result = self.api_client.search('detc', **params)
            
            # 결과 정규화
            if result.get('status') == 'success':
                decisions = self._normalize_constitutional_decisions(result.get('data', []))
                return {
                    'status': 'success',
                    'total_count': result.get('totalCnt', 0),
                    'page': page,
                    'decisions': decisions,
                    'query': query
                }
            
            return result
            
        except Exception as e:
            logger.error(f"헌재결정례 검색 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def get_constitutional_decision_detail(self, decision_id: int) -> Dict[str, Any]:
        """
        헌재결정례 상세 조회
        
        Args:
            decision_id: 헌재결정례 일련번호
            
        Returns:
            헌재결정례 상세 정보
        """
        try:
            result = self.api_client.get_detail('detc', decision_id)
            
            if result.get('status') == 'success':
                return {
                    'status': 'success',
                    'decision': self._normalize_constitutional_decision_detail(result.get('data', {}))
                }
            
            return result
            
        except Exception as e:
            logger.error(f"헌재결정례 상세 조회 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== 법령해석례 검색 ==========
    
    def search_legal_interpretations(
        self,
        query: str = "",
        agency: Optional[str] = None,
        requesting_agency: Optional[str] = None,
        date_range: Optional[tuple] = None,
        search_type: int = 1,
        display: int = 20,
        page: int = 1,
        sort: str = 'date_desc',
        case_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        법령해석례 검색
        
        Args:
            query: 검색어
            agency: 회신기관
            requesting_agency: 질의기관
            date_range: 해석일자 범위 튜플 (시작일, 종료일) YYYYMMDD 형식
            search_type: 1=법령해석례명 검색, 2=본문 검색
            display: 결과 개수
            page: 페이지 번호
            sort: 정렬 옵션
            case_number: 안건번호 (예: 13-0217 -> 130217)
            
        Returns:
            검색 결과 딕셔너리
        """
        try:
            params = {
                'search': search_type,
                'query': query,
                'display': min(display, 100),
                'page': page,
                'sort': self.SORT_OPTIONS.get(sort, 'ddes')
            }
            
            # 회신기관
            if agency:
                params['rpl'] = agency
            
            # 질의기관
            if requesting_agency:
                params['inq'] = requesting_agency
            
            # 날짜 범위 처리 (해석일자)
            if date_range and len(date_range) == 2:
                params['explYd'] = f"{date_range[0]}~{date_range[1]}"
            
            # 안건번호 검색 (하이픈 제거)
            if case_number:
                params['itmno'] = case_number.replace('-', '')
            
            # API 호출
            result = self.api_client.search('expc', **params)
            
            # 결과 정규화
            if result.get('status') == 'success':
                interpretations = self._normalize_legal_interpretations(result.get('data', []))
                return {
                    'status': 'success',
                    'total_count': result.get('totalCnt', 0),
                    'page': page,
                    'interpretations': interpretations,
                    'query': query
                }
            
            return result
            
        except Exception as e:
            logger.error(f"법령해석례 검색 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def get_legal_interpretation_detail(self, interpretation_id: int) -> Dict[str, Any]:
        """
        법령해석례 상세 조회
        
        Args:
            interpretation_id: 법령해석례 일련번호
            
        Returns:
            법령해석례 상세 정보
        """
        try:
            result = self.api_client.get_detail('expc', interpretation_id)
            
            if result.get('status') == 'success':
                return {
                    'status': 'success',
                    'interpretation': self._normalize_legal_interpretation_detail(result.get('data', {}))
                }
            
            return result
            
        except Exception as e:
            logger.error(f"법령해석례 상세 조회 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== 행정심판례 검색 ==========
    
    def search_admin_tribunals(
        self,
        query: str = "",
        tribunal_type: Optional[str] = None,
        date_range: Optional[tuple] = None,
        search_type: int = 1,
        display: int = 20,
        page: int = 1,
        sort: str = 'date_desc',
        decision_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        행정심판례 검색
        
        Args:
            query: 검색어
            tribunal_type: 재결례 유형 (기각, 각하, 인용 등)
            date_range: 의결일자 범위 튜플 (시작일, 종료일) YYYYMMDD 형식
            search_type: 1=행정심판례명 검색, 2=본문 검색
            display: 결과 개수
            page: 페이지 번호
            sort: 정렬 옵션
            decision_type: 재결 구분 (기각, 각하, 인용, 일부인용, 취하, 조정, 기타)
            
        Returns:
            검색 결과 딕셔너리
        """
        try:
            params = {
                'search': search_type,
                'query': query,
                'display': min(display, 100),
                'page': page,
                'sort': self.SORT_OPTIONS.get(sort, 'ddes')
            }
            
            # 재결 구분 처리
            if decision_type and decision_type in self.DECISION_CODES:
                params['cls'] = self.DECISION_CODES[decision_type]
            
            # 날짜 범위 처리 (의결일자)
            if date_range and len(date_range) == 2:
                params['rslYd'] = f"{date_range[0]}~{date_range[1]}"
            
            # API 호출
            result = self.api_client.search('decc', **params)
            
            # 결과 정규화
            if result.get('status') == 'success':
                tribunals = self._normalize_admin_tribunals(result.get('data', []))
                return {
                    'status': 'success',
                    'total_count': result.get('totalCnt', 0),
                    'page': page,
                    'tribunals': tribunals,
                    'query': query
                }
            
            return result
            
        except Exception as e:
            logger.error(f"행정심판례 검색 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def get_admin_tribunal_detail(self, tribunal_id: int) -> Dict[str, Any]:
        """
        행정심판례 상세 조회
        
        Args:
            tribunal_id: 행정심판례 일련번호
            
        Returns:
            행정심판례 상세 정보
        """
        try:
            result = self.api_client.get_detail('decc', tribunal_id)
            
            if result.get('status') == 'success':
                return {
                    'status': 'success',
                    'tribunal': self._normalize_admin_tribunal_detail(result.get('data', {}))
                }
            
            return result
            
        except Exception as e:
            logger.error(f"행정심판례 상세 조회 중 오류: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== 통합 검색 ==========
    
    def search_all_precedents(
        self,
        query: str,
        include_types: Optional[List[str]] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        모든 유형의 판례/심판례 통합 검색
        
        Args:
            query: 검색어
            include_types: 포함할 유형 리스트 ['court', 'constitutional', 'interpretation', 'admin']
                          None이면 모든 유형 검색
            limit: 각 유형별 최대 결과 수
            
        Returns:
            통합 검색 결과
        """
        try:
            # 기본값: 모든 유형 검색
            if include_types is None:
                include_types = ['court', 'constitutional', 'interpretation', 'admin']
            
            results = {
                'status': 'success',
                'query': query,
                'results': {}
            }
            
            # 각 유형별 검색 수행
            if 'court' in include_types:
                court_result = self.search_court_cases(query, display=limit)
                if court_result.get('status') == 'success':
                    results['results']['court_cases'] = {
                        'total': court_result.get('total_count', 0),
                        'items': court_result.get('cases', [])[:limit]
                    }
            
            if 'constitutional' in include_types:
                const_result = self.search_constitutional_decisions(query, display=limit)
                if const_result.get('status') == 'success':
                    results['results']['constitutional_decisions'] = {
                        'total': const_result.get('total_count', 0),
                        'items': const_result.get('decisions', [])[:limit]
                    }
            
            if 'interpretation' in include_types:
                interp_result = self.search_legal_interpretations(query, display=limit)
                if interp_result.get('status') == 'success':
                    results['results']['legal_interpretations'] = {
                        'total': interp_result.get('total_count', 0),
                        'items': interp_result.get('interpretations', [])[:limit]
                    }
            
            if 'admin' in include_types:
                admin_result = self.search_admin_tribunals(query, display=limit)
                if admin_result.get('status') == 'success':
                    results['results']['admin_tribunals'] = {
                        'total': admin_result.get('total_count', 0),
                        'items': admin_result.get('tribunals', [])[:limit]
                    }
            
            # 전체 결과 수 계산
            total_count = sum(
                res.get('total', 0) 
                for res in results['results'].values()
            )
            results['total_count'] = total_count
            
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
                return self.get_court_case_detail(case_id)
            elif case_type == 'constitutional':
                return self.get_constitutional_decision_detail(case_id)
            elif case_type == 'interpretation':
                return self.get_legal_interpretation_detail(case_id)
            elif case_type == 'admin':
                return self.get_admin_tribunal_detail(case_id)
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
        analysis_type: str = 'summary'
    ) -> Dict[str, Any]:
        """
        AI를 활용한 판례 분석
        
        Args:
            case_type: 판례 유형
            case_id: 판례 일련번호
            analysis_type: 분석 유형 ('summary', 'key_points', 'implications')
            
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
            
            # AI 분석 수행
            if analysis_type == 'summary':
                prompt = f"다음 판례를 3-5문장으로 요약해주세요:\n{case_data}"
            elif analysis_type == 'key_points':
                prompt = f"다음 판례의 핵심 쟁점과 판단을 정리해주세요:\n{case_data}"
            elif analysis_type == 'implications':
                prompt = f"다음 판례의 법적 의미와 향후 영향을 분석해주세요:\n{case_data}"
            else:
                prompt = f"다음 판례를 분석해주세요:\n{case_data}"
            
            analysis = self.ai_helper.analyze_legal_text(prompt, str(case_data))
            
            return {
                'status': 'success',
                'case_id': case_id,
                'case_type': case_type,
                'analysis_type': analysis_type,
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"AI 판례 분석 중 오류: {str(e)}")
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
                'date': case.get('선고일자'),
                'type': case.get('사건종류명'),
                'judgment_type': case.get('판결유형'),
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
            'date': case.get('선고일자'),
            'type': case.get('사건종류명'),
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
            'court_type': decision.get('재판부구분코드'),
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
                'responding_agency': interp.get('회신기관명'),
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
            'date': interpretation.get('해석일자'),
            'requesting_agency': interpretation.get('질의기관명'),
            'responding_agency': interpretation.get('해석기관명'),
            'question': interpretation.get('질의요지'),
            'answer': interpretation.get('회답'),
            'reasoning': interpretation.get('이유'),
            'registration_date': interpretation.get('등록일시')
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
            'order': tribunal.get('주문'),
            'claim': tribunal.get('청구취지'),
            'reasoning': tribunal.get('이유'),
            'summary': tribunal.get('재결요지')
        }
    
    # ========== 유틸리티 메서드 ==========
    
    def format_date_for_api(self, date: Union[str, datetime]) -> str:
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
            # 여러 형식 처리
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y년%m월%d일']:
                try:
                    dt = datetime.strptime(date, fmt)
                    return dt.strftime('%Y%m%d')
                except ValueError:
                    continue
            # 이미 YYYYMMDD 형식인 경우
            if len(date) == 8 and date.isdigit():
                return date
        
        raise ValueError(f"날짜 형식을 변환할 수 없습니다: {date}")
    
    def get_available_courts(self) -> List[str]:
        """사용 가능한 법원 목록 반환"""
        return list(self.COURT_CODES.keys())
    
    def get_available_decision_types(self) -> List[str]:
        """사용 가능한 재결 구분 목록 반환"""
        return list(self.DECISION_CODES.keys())


# ========== 테스트 코드 ==========
if __name__ == "__main__":
    # 테스트를 위한 예제 코드
    import os
    from dotenv import load_dotenv
    
    # 환경변수 로드
    load_dotenv()
    
    # CaseSearcher 인스턴스 생성
    searcher = CaseSearcher()
    
    # 1. 법원 판례 검색 테스트
    print("=== 법원 판례 검색 ===")
    court_results = searcher.search_court_cases(
        query="도로교통법",
        court="대법원",
        display=5
    )
    if court_results.get('status') == 'success':
        print(f"검색 결과: {court_results.get('total_count')}건")
        for case in court_results.get('cases', [])[:3]:
            print(f"- {case.get('title')} ({case.get('date')})")
    
    # 2. 헌재결정례 검색 테스트
    print("\n=== 헌재결정례 검색 ===")
    const_results = searcher.search_constitutional_decisions(
        query="기본권",
        display=5
    )
    if const_results.get('status') == 'success':
        print(f"검색 결과: {const_results.get('total_count')}건")
        for decision in const_results.get('decisions', [])[:3]:
            print(f"- {decision.get('title')} ({decision.get('date')})")
    
    # 3. 법령해석례 검색 테스트
    print("\n=== 법령해석례 검색 ===")
    interp_results = searcher.search_legal_interpretations(
        query="건축법",
        display=5
    )
    if interp_results.get('status') == 'success':
        print(f"검색 결과: {interp_results.get('total_count')}건")
        for interp in interp_results.get('interpretations', [])[:3]:
            print(f"- {interp.get('title')} ({interp.get('responding_agency')})")
    
    # 4. 행정심판례 검색 테스트
    print("\n=== 행정심판례 검색 ===")
    admin_results = searcher.search_admin_tribunals(
        query="영업정지",
        display=5
    )
    if admin_results.get('status') == 'success':
        print(f"검색 결과: {admin_results.get('total_count')}건")
        for tribunal in admin_results.get('tribunals', [])[:3]:
            print(f"- {tribunal.get('title')} ({tribunal.get('decision_type')})")
    
    # 5. 통합 검색 테스트
    print("\n=== 통합 판례 검색 ===")
    all_results = searcher.search_all_precedents(
        query="개인정보",
        limit=3
    )
    if all_results.get('status') == 'success':
        print(f"전체 검색 결과: {all_results.get('total_count')}건")
        for result_type, results in all_results.get('results', {}).items():
            print(f"\n{result_type}: {results.get('total')}건")
            for item in results.get('items', [])[:2]:
                print(f"  - {item.get('title', item.get('case_number', 'N/A'))}")
    
    print("\n테스트 완료!")
