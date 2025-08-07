"""
law_module.py - 법령 검색 모듈
법제처 Open API를 활용한 법령 검색 기능 구현
작성일: 2024
"""

import os
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import logging
from urllib.parse import quote

# common_api 모듈이 구현되어 있다고 가정
try:
    from common_api import LawAPIClient
except ImportError:
    # 개발 중 테스트를 위한 임시 클래스
    class LawAPIClient:
        def __init__(self, oc_key):
            self.oc_key = oc_key
            self.base_url = "http://www.law.go.kr/DRF"
        
        def search(self, target, query, **params):
            pass
        
        def get_detail(self, target, id, **params):
            pass

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LawSearcher:
    """
    법령 검색 및 조회를 위한 통합 클래스
    
    법제처 Open API의 모든 법령 관련 기능을 제공합니다.
    초보자도 쉽게 사용할 수 있도록 직관적인 메서드명과 상세한 문서화를 제공합니다.
    """
    
    # API 타겟 상수 정의
    TARGETS = {
        'LAW': 'law',                    # 현행법령
        'EFLAW': 'eflaw',                # 시행일법령
        'ELAW': 'elaw',                  # 영문법령
        'LAW_JOSUB': 'lawjosub',         # 조문별 조회
        'EFLAW_JOSUB': 'eflawjosub',     # 시행일법령 조문별
        'LS_HISTORY': 'lsHistory',       # 법령 연혁
        'LS_HST_INF': 'lsHstInf',       # 법령 변경이력
        'LS_JO_HST_INF': 'lsJoHstInf',  # 조문별 변경이력
        'OLD_AND_NEW': 'oldAndNew',      # 신구법 비교
        'LS_STMD': 'lsStmd',            # 법령 체계도
        'THD_CMP': 'thdCmp',            # 3단 비교
        'LS_DELEGATED': 'lsDelegated',   # 위임 법령
        'LNK_LS': 'lnkLs',              # 법령-자치법규 연계
        'LNK_LS_ORD_JO': 'lnkLsOrdJo',  # 법령별 조례 조문
        'LNK_DEP': 'lnkDep',            # 소관부처별 연계
        'DR_LAW': 'drlaw',              # 법령-자치법규 연계현황
        'LS_ABRV': 'lsAbrv',            # 법령명 약칭
        'DEL_HST': 'delHst',            # 삭제 데이터
        'ONEVIEW': 'oneview'            # 한눈보기
    }
    
    # 제개정 구분 코드
    REVISION_CODES = {
        '제정': '300201',
        '일부개정': '300202',
        '전부개정': '300203',
        '폐지': '300204',
        '폐지제정': '300205',
        '일괄개정': '300206',
        '일괄폐지': '300207',
        '기타': '300208',
        '타법개정': '300209',
        '타법폐지': '300210'
    }
    
    def __init__(self, api_client: Optional[LawAPIClient] = None, oc_key: Optional[str] = None):
        """
        법령 검색 모듈 초기화
        
        Args:
            api_client: LawAPIClient 인스턴스 (선택)
            oc_key: 법제처 API 키 (api_client가 없을 때 필수)
        """
        if api_client:
            self.client = api_client
        else:
            if not oc_key:
                oc_key = os.getenv('LAW_API_KEY')
            if not oc_key:
                raise ValueError("API 키가 필요합니다. LAW_API_KEY 환경변수를 설정하거나 oc_key를 제공하세요.")
            self.client = LawAPIClient(oc_key)
        
        logger.info("LawSearcher 모듈이 초기화되었습니다.")
    
    # ==================== 1. 현행법령 검색 ====================
    
    def search_laws(self, 
                    query: str = "",
                    search_type: int = 1,
                    display: int = 20,
                    page: int = 1,
                    sort: str = "lasc",
                    org: Optional[str] = None,
                    kind: Optional[str] = None,
                    date_range: Optional[Dict[str, str]] = None,
                    revision_type: Optional[str] = None) -> Dict[str, Any]:
        """
        현행법령을 검색합니다.
        
        Args:
            query: 검색어 (법령명)
            search_type: 검색범위 (1: 법령명, 2: 본문검색)
            display: 결과 개수 (최대 100)
            page: 페이지 번호
            sort: 정렬옵션 (lasc: 법령오름차순, ldes: 법령내림차순, dasc: 공포일자오름차순 등)
            org: 소관부처 코드
            kind: 법령종류 코드
            date_range: 날짜 범위 {'efYd': '20090101~20090130', 'ancYd': '20090101~20090130'}
            revision_type: 제개정 구분 (제정, 일부개정, 전부개정 등)
        
        Returns:
            검색 결과 딕셔너리
        
        Example:
            >>> searcher = LawSearcher()
            >>> results = searcher.search_laws("도로교통법")
            >>> print(f"검색 결과: {results['totalCnt']}건")
        """
        try:
            params = {
                'search': search_type,
                'display': min(display, 100),  # 최대 100개
                'page': page,
                'sort': sort
            }
            
            # 선택적 파라미터 추가
            if org:
                params['org'] = org
            if kind:
                params['knd'] = kind
            if date_range:
                if 'efYd' in date_range:
                    params['efYd'] = date_range['efYd']
                if 'ancYd' in date_range:
                    params['ancYd'] = date_range['ancYd']
            if revision_type and revision_type in self.REVISION_CODES:
                params['rrClsCd'] = self.REVISION_CODES[revision_type]
            
            logger.info(f"현행법령 검색 - 검색어: {query}, 페이지: {page}")
            
            result = self.client.search(
                target=self.TARGETS['LAW'],
                query=query,
                **params
            )
            
            return self._parse_search_result(result, '현행법령')
            
        except Exception as e:
            logger.error(f"현행법령 검색 실패: {str(e)}")
            return {'error': str(e), 'results': []}
    
    # ==================== 2. 법령 본문 조회 ====================
    
    def get_law_detail(self,
                      law_id: Optional[str] = None,
                      mst: Optional[str] = None,
                      jo_no: Optional[str] = None,
                      include_attachments: bool = False,
                      lang: str = "KO") -> Dict[str, Any]:
        """
        법령 상세 본문을 조회합니다.
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호 (law_id와 둘 중 하나 필수)
            jo_no: 조번호 (6자리, 예: '000200'은 2조)
            include_attachments: 별표/서식 포함 여부
            lang: 언어 (KO: 한글, ORI: 원문)
        
        Returns:
            법령 상세 정보 딕셔너리
        
        Example:
            >>> details = searcher.get_law_detail(law_id="001823")
            >>> print(details['법령명_한글'])
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {'LANG': lang}
            if jo_no:
                params['JO'] = jo_no
                
            if law_id:
                params['ID'] = law_id
            else:
                params['MST'] = mst
            
            logger.info(f"법령 상세 조회 - ID: {law_id or mst}")
            
            result = self.client.get_detail(
                target=self.TARGETS['LAW'],
                id=law_id or mst,
                **params
            )
            
            return self._parse_law_detail(result, include_attachments)
            
        except Exception as e:
            logger.error(f"법령 상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 3. 조문별 검색 ====================
    
    def search_articles(self,
                       law_id: Optional[str] = None,
                       mst: Optional[str] = None,
                       jo_no: str = None,
                       hang_no: Optional[str] = None,
                       ho_no: Optional[str] = None,
                       mok: Optional[str] = None) -> Dict[str, Any]:
        """
        특정 법령의 조문을 검색합니다.
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
            jo_no: 조번호 (6자리, 필수)
            hang_no: 항번호 (6자리)
            ho_no: 호번호 (6자리)
            mok: 목 (한글자)
        
        Returns:
            조문 정보 딕셔너리
        
        Example:
            >>> article = searcher.search_articles(law_id="001823", jo_no="000300")
            >>> print(article['조문내용'])
        """
        if not jo_no:
            raise ValueError("조번호(jo_no)는 필수입니다.")
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {'JO': jo_no}
            
            if hang_no:
                params['HANG'] = hang_no
            if ho_no:
                params['HO'] = ho_no
            if mok:
                params['MOK'] = quote(mok)  # 한글 인코딩
            
            if law_id:
                params['ID'] = law_id
            else:
                params['MST'] = mst
            
            logger.info(f"조문 검색 - 법령: {law_id or mst}, 조: {jo_no}")
            
            result = self.client.get_detail(
                target=self.TARGETS['LAW_JOSUB'],
                id=law_id or mst,
                **params
            )
            
            return self._parse_article_detail(result)
            
        except Exception as e:
            logger.error(f"조문 검색 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 4. 시행일 법령 검색 ====================
    
    def search_effective_laws(self,
                             query: str = "",
                             nw: Optional[List[int]] = None,
                             law_id: Optional[str] = None,
                             display: int = 20,
                             page: int = 1,
                             date: Optional[str] = None) -> Dict[str, Any]:
        """
        시행일 기준 법령을 검색합니다.
        
        Args:
            query: 검색어
            nw: 검색 범위 ([1]: 연혁, [2]: 시행예정, [3]: 현행)
            law_id: 특정 법령 ID로 검색
            display: 결과 개수
            page: 페이지
            date: 시행일자
        
        Returns:
            시행일 법령 검색 결과
        """
        try:
            params = {
                'display': min(display, 100),
                'page': page
            }
            
            if nw:
                params['nw'] = ','.join(map(str, nw))
            if law_id:
                params['LID'] = law_id
            if date:
                params['efYd'] = date
            
            logger.info(f"시행일 법령 검색 - 검색어: {query}")
            
            result = self.client.search(
                target=self.TARGETS['EFLAW'],
                query=query,
                **params
            )
            
            return self._parse_search_result(result, '시행일법령')
            
        except Exception as e:
            logger.error(f"시행일 법령 검색 실패: {str(e)}")
            return {'error': str(e), 'results': []}
    
    # ==================== 5. 법령 연혁 조회 ====================
    
    def get_law_history(self,
                       query: Optional[str] = None,
                       law_id: Optional[str] = None,
                       mst: Optional[str] = None,
                       display: int = 20,
                       page: int = 1) -> Dict[str, Any]:
        """
        법령의 제개정 연혁을 조회합니다.
        
        Args:
            query: 법령명 검색어
            law_id: 법령 ID (상세 조회시)
            mst: 법령 마스터 번호 (상세 조회시)
            display: 결과 개수
            page: 페이지
        
        Returns:
            법령 연혁 정보
        
        Example:
            >>> history = searcher.get_law_history(query="도로교통법")
            >>> for item in history['results']:
            >>>     print(f"{item['공포일자']}: {item['제개정구분명']}")
        """
        try:
            # 목록 조회
            if query and not law_id and not mst:
                params = {
                    'display': min(display, 100),
                    'page': page
                }
                
                logger.info(f"법령 연혁 목록 검색 - 검색어: {query}")
                
                result = self.client.search(
                    target=self.TARGETS['LS_HISTORY'],
                    query=query,
                    **params
                )
                
                return self._parse_search_result(result, '법령연혁')
            
            # 상세 조회
            elif law_id or mst:
                params = {}
                if law_id:
                    params['ID'] = law_id
                else:
                    params['MST'] = mst
                
                logger.info(f"법령 연혁 상세 조회 - ID: {law_id or mst}")
                
                result = self.client.get_detail(
                    target=self.TARGETS['LS_HISTORY'],
                    id=law_id or mst,
                    **params
                )
                
                return self._parse_history_detail(result)
            
            else:
                raise ValueError("query 또는 law_id/mst가 필요합니다.")
                
        except Exception as e:
            logger.error(f"법령 연혁 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 6. 신구법 비교 ====================
    
    def compare_old_new(self,
                       query: Optional[str] = None,
                       law_id: Optional[str] = None,
                       mst: Optional[str] = None) -> Dict[str, Any]:
        """
        법령의 신구 조문을 비교합니다.
        
        Args:
            query: 법령명 검색어 (목록 조회시)
            law_id: 법령 ID (상세 조회시)
            mst: 법령 마스터 번호 (상세 조회시)
        
        Returns:
            신구법 비교 정보
        
        Example:
            >>> comparison = searcher.compare_old_new(law_id="000170")
            >>> print(comparison['구조문'], comparison['신조문'])
        """
        try:
            # 목록 조회
            if query and not law_id and not mst:
                logger.info(f"신구법 목록 검색 - 검색어: {query}")
                
                result = self.client.search(
                    target=self.TARGETS['OLD_AND_NEW'],
                    query=query
                )
                
                return self._parse_search_result(result, '신구법')
            
            # 상세 조회
            elif law_id or mst:
                params = {}
                if law_id:
                    params['ID'] = law_id
                else:
                    params['MST'] = mst
                
                logger.info(f"신구법 상세 조회 - ID: {law_id or mst}")
                
                result = self.client.get_detail(
                    target=self.TARGETS['OLD_AND_NEW'],
                    id=law_id or mst,
                    **params
                )
                
                return self._parse_old_new_detail(result)
            
            else:
                raise ValueError("query 또는 law_id/mst가 필요합니다.")
                
        except Exception as e:
            logger.error(f"신구법 비교 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 7. 영문법령 검색 ====================
    
    def search_english_laws(self,
                           query: str = "",
                           display: int = 20,
                           page: int = 1) -> Dict[str, Any]:
        """
        영문 법령을 검색합니다.
        
        Args:
            query: 검색어 (한글 또는 영문)
            display: 결과 개수
            page: 페이지
        
        Returns:
            영문법령 검색 결과
        """
        try:
            params = {
                'display': min(display, 100),
                'page': page
            }
            
            logger.info(f"영문법령 검색 - 검색어: {query}")
            
            result = self.client.search(
                target=self.TARGETS['ELAW'],
                query=query,
                **params
            )
            
            return self._parse_search_result(result, '영문법령')
            
        except Exception as e:
            logger.error(f"영문법령 검색 실패: {str(e)}")
            return {'error': str(e), 'results': []}
    
    # ==================== 8. 법령 체계도 조회 ====================
    
    def get_law_structure(self,
                         query: Optional[str] = None,
                         law_id: Optional[str] = None,
                         mst: Optional[str] = None) -> Dict[str, Any]:
        """
        법령의 체계도(상하위 법령 관계)를 조회합니다.
        
        Args:
            query: 법령명 검색어
            law_id: 법령 ID
            mst: 법령 마스터 번호
        
        Returns:
            법령 체계도 정보
        """
        try:
            if query and not law_id and not mst:
                logger.info(f"법령 체계도 목록 검색 - 검색어: {query}")
                
                result = self.client.search(
                    target=self.TARGETS['LS_STMD'],
                    query=query
                )
                
                return self._parse_search_result(result, '법령체계도')
            
            elif law_id or mst:
                params = {}
                if law_id:
                    params['ID'] = law_id
                else:
                    params['MST'] = mst
                
                logger.info(f"법령 체계도 상세 조회 - ID: {law_id or mst}")
                
                result = self.client.get_detail(
                    target=self.TARGETS['LS_STMD'],
                    id=law_id or mst,
                    **params
                )
                
                return self._parse_structure_detail(result)
            
            else:
                raise ValueError("query 또는 law_id/mst가 필요합니다.")
                
        except Exception as e:
            logger.error(f"법령 체계도 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 9. 3단 비교 조회 ====================
    
    def get_three_way_comparison(self,
                                 query: Optional[str] = None,
                                 law_id: Optional[str] = None,
                                 mst: Optional[str] = None,
                                 kind: int = 1) -> Dict[str, Any]:
        """
        법령의 3단 비교(법률-시행령-시행규칙)를 조회합니다.
        
        Args:
            query: 법령명 검색어
            law_id: 법령 ID
            mst: 법령 마스터 번호
            kind: 비교 종류 (1: 인용조문, 2: 위임조문)
        
        Returns:
            3단 비교 정보
        """
        try:
            if query and not law_id and not mst:
                logger.info(f"3단 비교 목록 검색 - 검색어: {query}")
                
                result = self.client.search(
                    target=self.TARGETS['THD_CMP'],
                    query=query
                )
                
                return self._parse_search_result(result, '3단비교')
            
            elif law_id or mst:
                params = {'knd': kind}
                if law_id:
                    params['ID'] = law_id
                else:
                    params['MST'] = mst
                
                logger.info(f"3단 비교 상세 조회 - ID: {law_id or mst}, 종류: {kind}")
                
                result = self.client.get_detail(
                    target=self.TARGETS['THD_CMP'],
                    id=law_id or mst,
                    **params
                )
                
                return self._parse_three_way_detail(result, kind)
            
            else:
                raise ValueError("query 또는 law_id/mst가 필요합니다.")
                
        except Exception as e:
            logger.error(f"3단 비교 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 10. 위임 법령 조회 ====================
    
    def get_delegated_laws(self,
                          law_id: Optional[str] = None,
                          mst: Optional[str] = None) -> Dict[str, Any]:
        """
        특정 법령이 위임한 하위 법령을 조회합니다.
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
        
        Returns:
            위임 법령 정보
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {}
            if law_id:
                params['ID'] = law_id
            else:
                params['MST'] = mst
            
            logger.info(f"위임 법령 조회 - ID: {law_id or mst}")
            
            result = self.client.get_detail(
                target=self.TARGETS['LS_DELEGATED'],
                id=law_id or mst,
                **params
            )
            
            return self._parse_delegated_detail(result)
            
        except Exception as e:
            logger.error(f"위임 법령 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 11. 조문 변경 이력 조회 ====================
    
    def get_article_history(self,
                           law_id: str,
                           jo_no: str,
                           reg_date: Optional[str] = None,
                           date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        특정 조문의 변경 이력을 조회합니다.
        
        Args:
            law_id: 법령 ID
            jo_no: 조번호 (6자리)
            reg_date: 특정 날짜의 변경 이력
            date_range: 기간 검색 {'from': '20150201', 'to': '20150228'}
        
        Returns:
            조문 변경 이력
        """
        try:
            # 날짜별 조회
            if reg_date or date_range:
                params = {}
                if reg_date:
                    params['regDt'] = reg_date
                if date_range:
                    if 'from' in date_range:
                        params['fromRegDt'] = date_range['from']
                    if 'to' in date_range:
                        params['toRegDt'] = date_range['to']
                if law_id:
                    params['ID'] = law_id
                if jo_no:
                    params['JO'] = jo_no
                
                logger.info(f"조문 변경 이력 날짜별 조회 - 법령: {law_id}, 조: {jo_no}")
                
                result = self.client.search(
                    target=self.TARGETS['LS_JO_HST_INF'],
                    query="",
                    **params
                )
                
                return self._parse_article_history(result)
            
            # 조문별 조회
            else:
                params = {
                    'ID': law_id,
                    'JO': jo_no
                }
                
                logger.info(f"조문 변경 이력 조회 - 법령: {law_id}, 조: {jo_no}")
                
                result = self.client.get_detail(
                    target=self.TARGETS['LS_JO_HST_INF'],
                    id=law_id,
                    **params
                )
                
                return self._parse_article_history_detail(result)
                
        except Exception as e:
            logger.error(f"조문 변경 이력 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 12. 법령 약칭 조회 ====================
    
    def get_law_abbreviations(self,
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        법령명 약칭 목록을 조회합니다.
        
        Args:
            start_date: 등록일 시작 (YYYYMMDD)
            end_date: 등록일 종료 (YYYYMMDD)
        
        Returns:
            법령 약칭 목록
        """
        try:
            params = {}
            if start_date:
                params['stdDt'] = start_date
            if end_date:
                params['endDt'] = end_date
            
            logger.info("법령 약칭 조회")
            
            result = self.client.search(
                target=self.TARGETS['LS_ABRV'],
                query="",
                **params
            )
            
            return self._parse_abbreviations(result)
            
        except Exception as e:
            logger.error(f"법령 약칭 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 13. 한눈보기 조회 ====================
    
    def get_oneview(self,
                   query: Optional[str] = None,
                   mst: Optional[str] = None,
                   jo_no: Optional[str] = None) -> Dict[str, Any]:
        """
        법령 한눈보기 정보를 조회합니다.
        
        Args:
            query: 법령명 검색어
            mst: 법령 마스터 번호
            jo_no: 조번호
        
        Returns:
            한눈보기 정보
        """
        try:
            if query and not mst:
                logger.info(f"한눈보기 목록 검색 - 검색어: {query}")
                
                result = self.client.search(
                    target=self.TARGETS['ONEVIEW'],
                    query=query
                )
                
                return self._parse_search_result(result, '한눈보기')
            
            elif mst:
                params = {'MST': mst}
                if jo_no:
                    params['JO'] = jo_no
                
                logger.info(f"한눈보기 상세 조회 - MST: {mst}")
                
                result = self.client.get_detail(
                    target=self.TARGETS['ONEVIEW'],
                    id=mst,
                    **params
                )
                
                return self._parse_oneview_detail(result)
            
            else:
                raise ValueError("query 또는 mst가 필요합니다.")
                
        except Exception as e:
            logger.error(f"한눈보기 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 파싱 헬퍼 메서드들 ====================
    
    def _parse_search_result(self, result: Any, result_type: str) -> Dict[str, Any]:
        """검색 결과를 파싱하여 정규화된 형태로 반환"""
        try:
            if isinstance(result, str):
                # XML 파싱
                root = ET.fromstring(result)
                total_cnt = root.findtext('.//totalCnt', '0')
                
                items = []
                for item in root.findall('.//law') or root.findall('.//item'):
                    items.append({
                        '법령일련번호': self._safe_get(item, '법령일련번호'),
                        '법령명한글': self._safe_get(item, '법령명한글'),
                        '법령ID': self._safe_get(item, '법령ID'),
                        '공포일자': self._safe_get(item, '공포일자'),
                        '공포번호': self._safe_get(item, '공포번호'),
                        '제개정구분명': self._safe_get(item, '제개정구분명'),
                        '소관부처명': self._safe_get(item, '소관부처명'),
                        '시행일자': self._safe_get(item, '시행일자'),
                        '법령상세링크': self._safe_get(item, '법령상세링크')
                    })
                
                return {
                    'type': result_type,
                    'totalCnt': int(total_cnt),
                    'results': items
                }
            
            elif isinstance(result, dict):
                # JSON 형태로 이미 파싱된 경우
                return {
                    'type': result_type,
                    'totalCnt': result.get('totalCnt', 0),
                    'results': result.get('laws', result.get('items', []))
                }
            
            else:
                return {'type': result_type, 'totalCnt': 0, 'results': []}
                
        except Exception as e:
            logger.error(f"검색 결과 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}', 'results': []}
    
    def _parse_law_detail(self, result: Any, include_attachments: bool) -> Dict[str, Any]:
        """법령 상세 정보를 파싱"""
        try:
            if isinstance(result, str):
                root = ET.fromstring(result)
                
                detail = {
                    '법령ID': self._safe_get(root, './/법령ID'),
                    '법령명_한글': self._safe_get(root, './/법령명_한글'),
                    '법령명_한자': self._safe_get(root, './/법령명_한자'),
                    '공포일자': self._safe_get(root, './/공포일자'),
                    '공포번호': self._safe_get(root, './/공포번호'),
                    '시행일자': self._safe_get(root, './/시행일자'),
                    '소관부처': self._safe_get(root, './/소관부처'),
                    '제개정구분': self._safe_get(root, './/제개정구분'),
                    '조문': []
                }
                
                # 조문 파싱
                for jo in root.findall('.//조문'):
                    article = {
                        '조문번호': self._safe_get(jo, '조문번호'),
                        '조문제목': self._safe_get(jo, '조문제목'),
                        '조문내용': self._safe_get(jo, '조문내용'),
                        '항': []
                    }
                    
                    for hang in jo.findall('.//항'):
                        article['항'].append({
                            '항번호': self._safe_get(hang, '항번호'),
                            '항내용': self._safe_get(hang, '항내용')
                        })
                    
                    detail['조문'].append(article)
                
                # 별표 파싱 (선택적)
                if include_attachments:
                    detail['별표'] = []
                    for table in root.findall('.//별표'):
                        detail['별표'].append({
                            '별표번호': self._safe_get(table, '별표번호'),
                            '별표제목': self._safe_get(table, '별표제목'),
                            '별표내용': self._safe_get(table, '별표내용')
                        })
                
                return detail
            
            else:
                return result  # 이미 파싱된 경우
                
        except Exception as e:
            logger.error(f"법령 상세 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}'}
    
    def _parse_article_detail(self, result: Any) -> Dict[str, Any]:
        """조문 상세 정보를 파싱"""
        try:
            if isinstance(result, str):
                root = ET.fromstring(result)
                
                return {
                    '법령명_한글': self._safe_get(root, './/법령명_한글'),
                    '조문번호': self._safe_get(root, './/조문번호'),
                    '조문제목': self._safe_get(root, './/조문제목'),
                    '조문내용': self._safe_get(root, './/조문내용'),
                    '항내용': self._safe_get(root, './/항내용'),
                    '호내용': self._safe_get(root, './/호내용'),
                    '목내용': self._safe_get(root, './/목내용')
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"조문 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}'}
    
    def _parse_history_detail(self, result: Any) -> Dict[str, Any]:
        """법령 연혁 상세를 파싱"""
        try:
            if isinstance(result, str):
                # HTML 형태의 연혁 정보 처리
                return {
                    'type': '법령연혁',
                    'html': result  # HTML은 그대로 반환
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"연혁 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}'}
    
    def _parse_old_new_detail(self, result: Any) -> Dict[str, Any]:
        """신구법 비교 상세를 파싱"""
        try:
            if isinstance(result, str):
                root = ET.fromstring(result)
                
                return {
                    '법령명': self._safe_get(root, './/법령명'),
                    '구조문': self._safe_get(root, './/구조문'),
                    '신조문': self._safe_get(root, './/신조문'),
                    '시행일자': self._safe_get(root, './/시행일자')
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"신구법 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}'}
    
    def _parse_structure_detail(self, result: Any) -> Dict[str, Any]:
        """법령 체계도를 파싱"""
        try:
            if isinstance(result, str):
                root = ET.fromstring(result)
                
                return {
                    '법령명': self._safe_get(root, './/법령명'),
                    '법률': self._safe_get(root, './/법률'),
                    '시행령': self._safe_get(root, './/시행령'),
                    '시행규칙': self._safe_get(root, './/시행규칙'),
                    '상위법': self._safe_get(root, './/상위법'),
                    '하위법': self._safe_get(root, './/하위법')
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"체계도 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}'}
    
    def _parse_three_way_detail(self, result: Any, kind: int) -> Dict[str, Any]:
        """3단 비교 상세를 파싱"""
        try:
            if isinstance(result, str):
                root = ET.fromstring(result)
                
                if kind == 1:  # 인용조문
                    return {
                        '법령명': self._safe_get(root, './/법령명'),
                        '시행령명': self._safe_get(root, './/시행령명'),
                        '시행규칙명': self._safe_get(root, './/시행규칙명'),
                        '법률조문': self._safe_get(root, './/법률조문'),
                        '시행령조문': self._safe_get(root, './/시행령조문'),
                        '시행규칙조문': self._safe_get(root, './/시행규칙조문')
                    }
                else:  # 위임조문
                    return {
                        '기준법령명': self._safe_get(root, './/기준법령명'),
                        '법률조문': self._safe_get(root, './/법률조문'),
                        '시행령조문': self._safe_get(root, './/시행령조문'),
                        '시행규칙조문': self._safe_get(root, './/시행규칙조문')
                    }
            else:
                return result
                
        except Exception as e:
            logger.error(f"3단 비교 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}'}
    
    def _parse_delegated_detail(self, result: Any) -> Dict[str, Any]:
        """위임 법령 상세를 파싱"""
        try:
            if isinstance(result, str):
                root = ET.fromstring(result)
                
                delegated = []
                for item in root.findall('.//위임법령'):
                    delegated.append({
                        '위임구분': self._safe_get(item, '위임구분'),
                        '위임법령제목': self._safe_get(item, '위임법령제목'),
                        '위임법령조문번호': self._safe_get(item, '위임법령조문번호'),
                        '위임법령조문제목': self._safe_get(item, '위임법령조문제목')
                    })
                
                return {
                    '법령명': self._safe_get(root, './/법령명'),
                    '위임법령목록': delegated
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"위임 법령 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}'}
    
    def _parse_article_history(self, result: Any) -> Dict[str, Any]:
        """조문 변경 이력을 파싱"""
        try:
            if isinstance(result, str):
                root = ET.fromstring(result)
                
                history = []
                for item in root.findall('.//조문변경'):
                    history.append({
                        '조문번호': self._safe_get(item, '조문번호'),
                        '변경사유': self._safe_get(item, '변경사유'),
                        '조문개정일': self._safe_get(item, '조문개정일'),
                        '조문시행일': self._safe_get(item, '조문시행일')
                    })
                
                return {
                    '법령명': self._safe_get(root, './/법령명한글'),
                    '조문변경이력': history
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"조문 이력 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}'}
    
    def _parse_article_history_detail(self, result: Any) -> Dict[str, Any]:
        """조문별 변경 이력 상세를 파싱"""
        return self._parse_article_history(result)
    
    def _parse_abbreviations(self, result: Any) -> Dict[str, Any]:
        """법령 약칭을 파싱"""
        try:
            if isinstance(result, str):
                root = ET.fromstring(result)
                
                items = []
                for item in root.findall('.//약칭'):
                    items.append({
                        '법령명한글': self._safe_get(item, '법령명한글'),
                        '법령약칭명': self._safe_get(item, '법령약칭명'),
                        '등록일': self._safe_get(item, '등록일')
                    })
                
                return {
                    'type': '법령약칭',
                    'results': items
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"약칭 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}'}
    
    def _parse_oneview_detail(self, result: Any) -> Dict[str, Any]:
        """한눈보기 상세를 파싱"""
        try:
            if isinstance(result, str):
                root = ET.fromstring(result)
                
                return {
                    '법령명': self._safe_get(root, './/법령명'),
                    '조번호': self._safe_get(root, './/조번호'),
                    '조제목': self._safe_get(root, './/조제목'),
                    '콘텐츠제목': self._safe_get(root, './/콘텐츠제목'),
                    '링크URL': self._safe_get(root, './/링크URL')
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"한눈보기 파싱 실패: {str(e)}")
            return {'error': f'파싱 실패: {str(e)}'}
    
    def _safe_get(self, element: Any, path: str, default: str = '') -> str:
        """XML 요소에서 안전하게 텍스트 추출"""
        try:
            if hasattr(element, 'findtext'):
                return element.findtext(path, default)
            elif hasattr(element, 'find'):
                elem = element.find(path)
                return elem.text if elem is not None and elem.text else default
            else:
                return default
        except:
            return default
    
    # ==================== 통합 검색 메서드 ====================
    
    def search_all(self, query: str, search_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        모든 유형의 법령을 통합 검색합니다.
        
        Args:
            query: 검색어
            search_types: 검색할 유형 리스트 ['현행법령', '영문법령', '시행일법령']
        
        Returns:
            통합 검색 결과
        """
        if not search_types:
            search_types = ['현행법령', '시행일법령']
        
        results = {}
        
        try:
            if '현행법령' in search_types:
                results['현행법령'] = self.search_laws(query, display=10)
            
            if '시행일법령' in search_types:
                results['시행일법령'] = self.search_effective_laws(query, display=10)
            
            if '영문법령' in search_types:
                results['영문법령'] = self.search_english_laws(query, display=10)
            
            if '법령연혁' in search_types:
                results['법령연혁'] = self.get_law_history(query=query, display=10)
            
            return {
                'query': query,
                'search_types': search_types,
                'results': results,
                'total_count': sum(r.get('totalCnt', 0) for r in results.values() if isinstance(r, dict))
            }
            
        except Exception as e:
            logger.error(f"통합 검색 실패: {str(e)}")
            return {'error': str(e), 'results': {}}


# ==================== 테스트 코드 ====================

if __name__ == "__main__":
    """
    모듈 테스트 코드
    실행: python law_module.py
    """
    
    # 테스트용 API 키 (실제 사용시 환경변수로 설정)
    # export LAW_API_KEY=your_api_key
    
    print("=" * 50)
    print("법령 검색 모듈 테스트")
    print("=" * 50)
    
    try:
        # LawSearcher 초기화
        searcher = LawSearcher()
        
        # 1. 현행법령 검색 테스트
        print("\n1. 현행법령 검색 테스트")
        print("-" * 30)
        result = searcher.search_laws("도로교통법", display=5)
        if 'error' not in result:
            print(f"검색 결과: {result['totalCnt']}건")
            for idx, law in enumerate(result['results'][:3], 1):
                print(f"  {idx}. {law.get('법령명한글', 'N/A')} ({law.get('공포일자', 'N/A')})")
        else:
            print(f"오류: {result['error']}")
        
        # 2. 법령 상세 조회 테스트
        print("\n2. 법령 상세 조회 테스트")
        print("-" * 30)
        if result.get('results'):
            first_law = result['results'][0]
            law_id = first_law.get('법령ID')
            if law_id:
                detail = searcher.get_law_detail(law_id=law_id)
                if 'error' not in detail:
                    print(f"법령명: {detail.get('법령명_한글', 'N/A')}")
                    print(f"시행일자: {detail.get('시행일자', 'N/A')}")
                    print(f"조문 수: {len(detail.get('조문', []))}")
                else:
                    print(f"오류: {detail['error']}")
        
        # 3. 영문법령 검색 테스트
        print("\n3. 영문법령 검색 테스트")
        print("-" * 30)
        eng_result = searcher.search_english_laws("traffic", display=3)
        if 'error' not in eng_result:
            print(f"검색 결과: {eng_result['totalCnt']}건")
        else:
            print(f"오류: {eng_result['error']}")
        
        # 4. 통합 검색 테스트
        print("\n4. 통합 검색 테스트")
        print("-" * 30)
        integrated = searcher.search_all("교통", ['현행법령', '시행일법령'])
        if 'error' not in integrated:
            print(f"전체 검색 결과: {integrated['total_count']}건")
            for search_type, result in integrated['results'].items():
                if isinstance(result, dict):
                    print(f"  - {search_type}: {result.get('totalCnt', 0)}건")
        else:
            print(f"오류: {integrated['error']}")
        
        print("\n" + "=" * 50)
        print("테스트 완료!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n테스트 중 오류 발생: {str(e)}")
        print("API 키를 확인하거나 common_api.py 모듈이 있는지 확인하세요.")
