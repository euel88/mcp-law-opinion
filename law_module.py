"""
law_module.py - 법제처 Open API 통합 모듈
모든 법령 검색 기능을 포함한 완전한 구현
작성일: 2024
버전: 2.1 (API 호출 수정 버전)
"""

import os
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import logging
import requests
from urllib.parse import quote, urlencode

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LawAPIClient:
    """
    법제처 Open API 클라이언트
    실제 HTTP 요청을 처리하는 저수준 클래스
    """
    
    BASE_URL = "https://www.law.go.kr/DRF"
    
    def __init__(self, oc_key: str):
        """
        API 클라이언트 초기화
        
        Args:
            oc_key: 법제처 API 인증키 (사용자 이메일 ID)
        """
        self.oc_key = oc_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def search(self, target: str, **params) -> Dict:
        """
        검색 API 호출
        
        Args:
            target: 검색 대상 (law, prec, detc 등)
            **params: 추가 파라미터
        
        Returns:
            API 응답 (JSON 딕셔너리)
        """
        url = f"{self.BASE_URL}/lawSearch.do"
        
        # 필수 파라미터 설정
        params['OC'] = self.oc_key
        params['target'] = target
        
        # type 파라미터가 없으면 JSON 기본값 설정
        if 'type' not in params:
            params['type'] = 'json'
        
        # query가 없으면 기본값 설정
        if 'query' not in params:
            params['query'] = '*'
        
        logger.debug(f"API 호출: {url}")
        logger.debug(f"파라미터: {params}")
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Content-Type 확인
            content_type = response.headers.get('Content-Type', '')
            
            if params['type'].lower() == 'json' or 'json' in content_type.lower():
                try:
                    return response.json()
                except json.JSONDecodeError:
                    # JSON 파싱 실패시 에러 반환
                    logger.error(f"JSON 파싱 실패: {response.text[:200]}")
                    return {"error": "JSON parsing failed", "totalCnt": 0}
            else:
                return response.text
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API 요청 실패: {str(e)}")
            return {"error": str(e), "totalCnt": 0}
    
    def get_detail(self, target: str, **params) -> Dict:
        """
        상세 조회 API 호출
        
        Args:
            target: 조회 대상 (law, prec, detc 등)
            **params: 추가 파라미터
        
        Returns:
            API 응답
        """
        url = f"{self.BASE_URL}/lawService.do"
        
        params['OC'] = self.oc_key
        params['target'] = target
        
        if 'type' not in params:
            params['type'] = 'json'
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            if params['type'].lower() == 'json':
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"error": "JSON parsing failed"}
            else:
                return response.text
                
        except requests.exceptions.RequestException as e:
            logger.error(f"상세 조회 실패: {str(e)}")
            return {"error": str(e)}


class LawSearcher:
    """
    법제처 Open API를 활용한 법령 검색 통합 모듈
    
    개발 가이드의 모든 26개 API 기능을 구현합니다.
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
    
    # 정렬 옵션
    SORT_OPTIONS = {
        '법령오름차순': 'lasc',
        '법령내림차순': 'ldes',
        '공포일자오름차순': 'dasc',
        '공포일자내림차순': 'ddes',
        '공포번호오름차순': 'nasc',
        '공포번호내림차순': 'ndes',
        '시행일자오름차순': 'efasc',
        '시행일자내림차순': 'efdes'
    }
    
    def __init__(self, oc_key: Optional[str] = None):
        """
        법령 검색 모듈 초기화
        
        Args:
            oc_key: 법제처 API 키 (없으면 환경변수에서 읽음)
        
        Raises:
            ValueError: API 키가 없는 경우
        """
        if not oc_key:
            oc_key = os.getenv('LAW_API_KEY', 'test')  # 테스트시 'test' 사용
        
        if not oc_key:
            raise ValueError("API 키가 필요합니다. LAW_API_KEY 환경변수를 설정하거나 oc_key를 제공하세요.")
        
        self.client = LawAPIClient(oc_key)
        logger.info(f"LawSearcher 모듈이 초기화되었습니다. (API Key: {oc_key[:4]}...)")
    
    # ==================== 1. 법령 목록 조회 API ====================
    
    def search_laws(self, 
                    query: str = "",
                    search_type: int = 1,
                    output_type: str = "json",
                    display: int = 20,
                    page: int = 1,
                    sort: str = "lasc",
                    date: Optional[int] = None,
                    ef_yd: Optional[str] = None,
                    anc_yd: Optional[str] = None,
                    anc_no: Optional[str] = None,
                    rr_cls_cd: Optional[str] = None,
                    nb: Optional[int] = None,
                    org: Optional[str] = None,
                    knd: Optional[str] = None,
                    ls_chap_no: Optional[str] = None,
                    gana: Optional[str] = None,
                    pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        현행법령을 검색합니다. (API #1)
        
        Args:
            query: 검색어 (법령명)
            search_type: 검색범위 (1: 법령명, 2: 본문검색)
            output_type: 출력형태 (html/xml/json)
            display: 검색 결과 개수 (최대 100)
            page: 페이지 번호
            sort: 정렬옵션
            date: 공포일자 검색
            ef_yd: 시행일자 범위 검색 (예: '20090101~20090130')
            anc_yd: 공포일자 범위 검색
            anc_no: 공포번호 범위 검색
            rr_cls_cd: 제개정 구분 코드
            nb: 공포번호 검색
            org: 소관부처 코드
            knd: 법령종류 코드
            ls_chap_no: 법령분류 (01-제1편 ~ 44-제44편)
            gana: 사전식 검색 (ga, na, da 등)
            pop_yn: 팝업창 여부 ('Y')
        
        Returns:
            검색 결과 딕셔너리
        
        Example:
            >>> searcher = LawSearcher()
            >>> results = searcher.search_laws("자동차관리법")
            >>> print(f"검색 결과: {results['totalCnt']}건")
        """
        try:
            params = {
                'search': search_type,
                'query': query if query else '*',
                'display': min(display, 100),
                'page': page,
                'sort': sort,
                'type': output_type.lower()
            }
            
            # 선택적 파라미터 추가
            if date: params['date'] = date
            if ef_yd: params['efYd'] = ef_yd
            if anc_yd: params['ancYd'] = anc_yd
            if anc_no: params['ancNo'] = anc_no
            if rr_cls_cd: params['rrClsCd'] = rr_cls_cd
            if nb: params['nb'] = nb
            if org: params['org'] = org
            if knd: params['knd'] = knd
            if ls_chap_no: params['lsChapNo'] = ls_chap_no
            if gana: params['gana'] = gana
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"현행법령 검색 - 검색어: {query}, 페이지: {page}")
            
            # API 호출 (수정된 방식)
            result = self.client.search(target=self.TARGETS['LAW'], **params)
            
            # 에러 체크
            if isinstance(result, dict) and 'error' in result:
                logger.error(f"API 오류: {result['error']}")
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            # 정상 응답 처리
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('law', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"현행법령 검색 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 2. 법령 본문 조회 API ====================
    
    def get_law_detail(self,
                      law_id: Optional[str] = None,
                      mst: Optional[str] = None,
                      output_type: str = "json",
                      lm: Optional[str] = None,
                      ld: Optional[int] = None,
                      ln: Optional[int] = None,
                      jo: Optional[int] = None,
                      lang: str = "KO") -> Dict[str, Any]:
        """
        법령 상세 본문을 조회합니다. (API #2)
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호 (law_id와 둘 중 하나 필수)
            output_type: 출력형태 (html/xml/json)
            lm: 법령명
            ld: 공포일자
            ln: 공포번호
            jo: 조번호 (6자리, 예: 000200은 2조)
            lang: 언어 (KO: 한글, ORI: 원문)
        
        Returns:
            법령 상세 정보
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {
                'type': output_type.lower(),
                'LANG': lang
            }
            
            if law_id: params['ID'] = law_id
            if mst: params['MST'] = mst
            if lm: params['LM'] = lm
            if ld: params['LD'] = ld
            if ln: params['LN'] = ln
            if jo: params['JO'] = jo
            
            logger.info(f"법령 상세 조회 - ID: {law_id or mst}")
            
            result = self.client.get_detail(target=self.TARGETS['LAW'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"법령 상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 3. 시행일 법령 목록 조회 API ====================
    
    def search_effective_laws(self,
                             query: str = "",
                             output_type: str = "json",
                             search_type: int = 1,
                             nw: Optional[str] = None,
                             lid: Optional[str] = None,
                             display: int = 20,
                             page: int = 1,
                             sort: str = "lasc",
                             ef_yd: Optional[str] = None,
                             date: Optional[str] = None,
                             anc_yd: Optional[str] = None,
                             anc_no: Optional[str] = None,
                             rr_cls_cd: Optional[str] = None,
                             nb: Optional[int] = None,
                             org: Optional[str] = None,
                             knd: Optional[str] = None,
                             gana: Optional[str] = None,
                             pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        시행일 법령 목록을 조회합니다. (API #3)
        
        Args:
            query: 검색어
            output_type: 출력형태
            search_type: 검색범위 (1: 법령명, 2: 본문검색)
            nw: 검색 범위 (1: 연혁, 2: 시행예정, 3: 현행, 쉼표로 구분)
            lid: 법령 ID
            기타 파라미터는 search_laws와 동일
        
        Returns:
            시행일 법령 검색 결과
        """
        try:
            params = {
                'search': search_type,
                'query': query if query else '*',
                'display': min(display, 100),
                'page': page,
                'sort': sort,
                'type': output_type.lower()
            }
            
            if nw: params['nw'] = nw
            if lid: params['LID'] = lid
            if ef_yd: params['efYd'] = ef_yd
            if date: params['date'] = date
            if anc_yd: params['ancYd'] = anc_yd
            if anc_no: params['ancNo'] = anc_no
            if rr_cls_cd: params['rrClsCd'] = rr_cls_cd
            if nb: params['nb'] = nb
            if org: params['org'] = org
            if knd: params['knd'] = knd
            if gana: params['gana'] = gana
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"시행일 법령 검색 - 검색어: {query}")
            
            result = self.client.search(target=self.TARGETS['EFLAW'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('eflaw', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"시행일 법령 검색 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 4. 시행일 법령 본문 조회 API ====================
    
    def get_effective_law_detail(self,
                                law_id: Optional[str] = None,
                                mst: Optional[str] = None,
                                ef_yd: int = None,
                                output_type: str = "json",
                                jo: Optional[int] = None,
                                chr_cls_cd: Optional[str] = None) -> Dict[str, Any]:
        """
        시행일 법령 본문을 조회합니다. (API #4)
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
            ef_yd: 시행일자 (MST 사용시 필수)
            output_type: 출력형태
            jo: 조번호
            chr_cls_cd: 원문/한글 여부 (010202: 한글, 010201: 원문)
        
        Returns:
            시행일 법령 상세 정보
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {
                'type': output_type.lower()
            }
            
            if law_id: params['ID'] = law_id
            if mst: 
                params['MST'] = mst
                if ef_yd: params['efYd'] = ef_yd
            if jo: params['JO'] = jo
            if chr_cls_cd: params['chrClsCd'] = chr_cls_cd
            
            logger.info(f"시행일 법령 상세 조회 - ID: {law_id or mst}")
            
            result = self.client.get_detail(target=self.TARGETS['EFLAW'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"시행일 법령 상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 5. 법령 연혁 목록 조회 API ====================
    
    def search_law_history(self,
                          query: str = "",
                          output_type: str = "html",
                          display: int = 20,
                          page: int = 1,
                          sort: str = "lasc",
                          ef_yd: Optional[str] = None,
                          date: Optional[str] = None,
                          anc_yd: Optional[str] = None,
                          anc_no: Optional[str] = None,
                          rr_cls_cd: Optional[str] = None,
                          org: Optional[str] = None,
                          knd: Optional[str] = None,
                          ls_chap_no: Optional[str] = None,
                          gana: Optional[str] = None,
                          pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        법령 연혁 목록을 조회합니다. (API #5)
        
        Args:
            query: 검색어
            output_type: 출력형태 (HTML만 지원)
            기타 파라미터는 search_laws와 동일
        
        Returns:
            법령 연혁 목록
        """
        try:
            params = {
                'query': query if query else '*',
                'display': min(display, 100),
                'page': page,
                'sort': sort,
                'type': output_type.lower()
            }
            
            if ef_yd: params['efYd'] = ef_yd
            if date: params['date'] = date
            if anc_yd: params['ancYd'] = anc_yd
            if anc_no: params['ancNo'] = anc_no
            if rr_cls_cd: params['rrClsCd'] = rr_cls_cd
            if org: params['org'] = org
            if knd: params['knd'] = knd
            if ls_chap_no: params['lsChapNo'] = ls_chap_no
            if gana: params['gana'] = gana
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"법령 연혁 목록 검색 - 검색어: {query}")
            
            result = self.client.search(target=self.TARGETS['LS_HISTORY'], **params)
            return self._parse_response(result, 'history_search')
            
        except Exception as e:
            logger.error(f"법령 연혁 목록 검색 실패: {str(e)}")
            return {'error': str(e), 'results': []}
    
    # ==================== 6. 법령 연혁 본문 조회 API ====================
    
    def get_law_history_detail(self,
                              law_id: Optional[str] = None,
                              mst: Optional[str] = None,
                              output_type: str = "html",
                              lm: Optional[str] = None,
                              ld: Optional[int] = None,
                              ln: Optional[int] = None,
                              chr_cls_cd: Optional[str] = None) -> Dict[str, Any]:
        """
        법령 연혁 본문을 조회합니다. (API #6)
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
            output_type: 출력형태 (HTML만 지원)
            lm: 법령명
            ld: 공포일자
            ln: 공포번호
            chr_cls_cd: 원문/한글 여부
        
        Returns:
            법령 연혁 상세
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {
                'type': output_type.lower()
            }
            
            if law_id: params['ID'] = law_id
            if mst: params['MST'] = mst
            if lm: params['LM'] = lm
            if ld: params['LD'] = ld
            if ln: params['LN'] = ln
            if chr_cls_cd: params['chrClsCd'] = chr_cls_cd
            
            logger.info(f"법령 연혁 상세 조회 - ID: {law_id or mst}")
            
            result = self.client.get_detail(target=self.TARGETS['LS_HISTORY'], **params)
            return self._parse_response(result, 'history_detail')
            
        except Exception as e:
            logger.error(f"법령 연혁 상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 7. 현행법령 본문 조항호목 조회 API ====================
    
    def get_law_article_detail(self,
                              law_id: Optional[str] = None,
                              mst: Optional[str] = None,
                              jo: str = None,
                              hang: Optional[str] = None,
                              ho: Optional[str] = None,
                              mok: Optional[str] = None,
                              output_type: str = "json") -> Dict[str, Any]:
        """
        현행법령의 조항호목을 조회합니다. (API #7)
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
            jo: 조번호 (6자리, 필수) 예: '000300' (제3조)
            hang: 항번호 (6자리) 예: '000100' (제1항)
            ho: 호번호 (6자리) 예: '000200' (제2호)
            mok: 목 (한글자) 예: '가', '나', '다'
            output_type: 출력형태
        
        Returns:
            조항호목 상세
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        if not jo:
            raise ValueError("조번호(jo)는 필수입니다.")
        
        try:
            params = {
                'JO': jo,
                'type': output_type.lower()
            }
            
            if law_id: params['ID'] = law_id
            if mst: params['MST'] = mst
            if hang: params['HANG'] = hang
            if ho: params['HO'] = ho
            if mok: params['MOK'] = quote(mok)  # 한글 인코딩
            
            logger.info(f"조항호목 조회 - 법령: {law_id or mst}, 조: {jo}")
            
            result = self.client.get_detail(target=self.TARGETS['LAW_JOSUB'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"조항호목 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 8. 시행일법령 본문 조항호목 조회 API ====================
    
    def get_effective_law_article_detail(self,
                                        law_id: Optional[str] = None,
                                        mst: Optional[str] = None,
                                        ef_yd: int = None,
                                        jo: str = None,
                                        hang: Optional[str] = None,
                                        ho: Optional[str] = None,
                                        mok: Optional[str] = None,
                                        output_type: str = "json") -> Dict[str, Any]:
        """
        시행일법령의 조항호목을 조회합니다. (API #8)
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
            ef_yd: 시행일자 (MST 사용시 필수)
            jo: 조번호 (필수)
            hang: 항번호
            ho: 호번호
            mok: 목
            output_type: 출력형태
        
        Returns:
            시행일법령 조항호목 상세
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        if not jo:
            raise ValueError("조번호(jo)는 필수입니다.")
        
        try:
            params = {
                'JO': jo,
                'type': output_type.lower()
            }
            
            if law_id: params['ID'] = law_id
            if mst: 
                params['MST'] = mst
                if ef_yd: params['efYd'] = ef_yd
            if hang: params['HANG'] = hang
            if ho: params['HO'] = ho
            if mok: params['MOK'] = quote(mok)
            
            logger.info(f"시행일법령 조항호목 조회 - 법령: {law_id or mst}, 조: {jo}")
            
            result = self.client.get_detail(target=self.TARGETS['EFLAW_JOSUB'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"시행일법령 조항호목 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 9. 영문법령 목록 조회 API ====================
    
    def search_english_laws(self,
                           query: str = "*",
                           search_type: int = 1,
                           output_type: str = "json",
                           display: int = 20,
                           page: int = 1,
                           sort: str = "lasc",
                           date: Optional[int] = None,
                           ef_yd: Optional[str] = None,
                           anc_yd: Optional[str] = None,
                           anc_no: Optional[str] = None,
                           rr_cls_cd: Optional[str] = None,
                           nb: Optional[int] = None,
                           org: Optional[str] = None,
                           knd: Optional[str] = None,
                           gana: Optional[str] = None,
                           pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        영문법령을 검색합니다. (API #9)
        
        Args:
            query: 검색어 (기본값 '*' - 전체)
            search_type: 검색범위
            output_type: 출력형태
            기타 파라미터는 search_laws와 동일
        
        Returns:
            영문법령 검색 결과
        """
        try:
            params = {
                'search': search_type,
                'query': query,
                'display': min(display, 100),
                'page': page,
                'sort': sort,
                'type': output_type.lower()
            }
            
            if date: params['date'] = date
            if ef_yd: params['efYd'] = ef_yd
            if anc_yd: params['ancYd'] = anc_yd
            if anc_no: params['ancNo'] = anc_no
            if rr_cls_cd: params['rrClsCd'] = rr_cls_cd
            if nb: params['nb'] = nb
            if org: params['org'] = org
            if knd: params['knd'] = knd
            if gana: params['gana'] = gana
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"영문법령 검색 - 검색어: {query}")
            
            result = self.client.search(target=self.TARGETS['ELAW'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('elaw', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"영문법령 검색 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 10. 영문법령 본문 조회 API ====================
    
    def get_english_law_detail(self,
                              law_id: Optional[str] = None,
                              mst: Optional[str] = None,
                              output_type: str = "json",
                              lm: Optional[str] = None,
                              ld: Optional[int] = None,
                              ln: Optional[int] = None) -> Dict[str, Any]:
        """
        영문법령 본문을 조회합니다. (API #10)
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
            output_type: 출력형태
            lm: 법령명
            ld: 공포일자
            ln: 공포번호
        
        Returns:
            영문법령 상세
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {
                'type': output_type.lower()
            }
            
            if law_id: params['ID'] = law_id
            if mst: params['MST'] = mst
            if lm: params['LM'] = lm
            if ld: params['LD'] = ld
            if ln: params['LN'] = ln
            
            logger.info(f"영문법령 상세 조회 - ID: {law_id or mst}")
            
            result = self.client.get_detail(target=self.TARGETS['ELAW'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"영문법령 상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 11. 법령 변경이력 목록 조회 API ====================
    
    def search_law_change_history(self,
                                 reg_dt: int = None,
                                 org: Optional[str] = None,
                                 output_type: str = "json",
                                 display: int = 20,
                                 page: int = 1,
                                 pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        법령 변경이력 목록을 조회합니다. (API #11)
        
        Args:
            reg_dt: 법령 변경일 (YYYYMMDD, 필수)
            org: 소관부처 코드
            output_type: 출력형태
            display: 결과 개수
            page: 페이지
            pop_yn: 팝업창 여부
        
        Returns:
            법령 변경이력 목록
        """
        if not reg_dt:
            raise ValueError("reg_dt(법령 변경일)는 필수입니다.")
        
        try:
            params = {
                'regDt': reg_dt,
                'display': min(display, 100),
                'page': page,
                'type': output_type.lower()
            }
            
            if org: params['org'] = org
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"법령 변경이력 조회 - 날짜: {reg_dt}")
            
            result = self.client.search(target=self.TARGETS['LS_HST_INF'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('lsHstInf', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"법령 변경이력 조회 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 12. 일자별 조문 개정 이력 목록 조회 API ====================
    
    def search_article_revision_history(self,
                                       reg_dt: Optional[int] = None,
                                       from_reg_dt: Optional[int] = None,
                                       to_reg_dt: Optional[int] = None,
                                       law_id: Optional[int] = None,
                                       jo: Optional[int] = None,
                                       org: Optional[str] = None,
                                       output_type: str = "json",
                                       page: int = 1) -> Dict[str, Any]:
        """
        일자별 조문 개정 이력을 조회합니다. (API #12)
        
        Args:
            reg_dt: 조문 개정일 (YYYYMMDD)
            from_reg_dt: 조회기간 시작일
            to_reg_dt: 조회기간 종료일
            law_id: 법령 ID
            jo: 조문번호 (6자리)
            org: 소관부처 코드
            output_type: 출력형태
            page: 페이지
        
        Returns:
            조문 개정 이력
        """
        try:
            params = {
                'page': page,
                'type': output_type.lower()
            }
            
            if reg_dt: params['regDt'] = reg_dt
            if from_reg_dt: params['fromRegDt'] = from_reg_dt
            if to_reg_dt: params['toRegDt'] = to_reg_dt
            if law_id: params['ID'] = law_id
            if jo: params['JO'] = jo
            if org: params['org'] = org
            
            logger.info(f"조문 개정 이력 조회 - 법령: {law_id}, 조: {jo}")
            
            result = self.client.search(target=self.TARGETS['LS_JO_HST_INF'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('lsJoHstInf', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"조문 개정 이력 조회 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 13. 조문별 변경 이력 목록 조회 API ====================
    
    def get_article_change_history(self,
                                  law_id: str,
                                  jo: int,
                                  output_type: str = "json",
                                  display: int = 20,
                                  page: int = 1) -> Dict[str, Any]:
        """
        조문별 변경 이력을 조회합니다. (API #13)
        
        Args:
            law_id: 법령 ID (필수)
            jo: 조번호 (6자리, 필수)
            output_type: 출력형태
            display: 결과 개수
            page: 페이지
        
        Returns:
            조문별 변경 이력
        """
        try:
            params = {
                'ID': law_id,
                'JO': jo,
                'display': min(display, 100),
                'page': page,
                'type': output_type.lower()
            }
            
            logger.info(f"조문별 변경 이력 조회 - 법령: {law_id}, 조: {jo}")
            
            result = self.client.get_detail(target=self.TARGETS['LS_JO_HST_INF'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"조문별 변경 이력 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 14. 법령 자치법규 연계 목록 조회 API ====================
    
    def search_linked_ordinances(self,
                                query: str = "",
                                output_type: str = "json",
                                display: int = 20,
                                page: int = 1,
                                sort: str = "lasc",
                                pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        법령-자치법규 연계 목록을 조회합니다. (API #14)
        
        Args:
            query: 검색어
            output_type: 출력형태
            display: 결과 개수
            page: 페이지
            sort: 정렬옵션
            pop_yn: 팝업창 여부
        
        Returns:
            연계 법령 목록
        """
        try:
            params = {
                'query': query if query else '*',
                'display': min(display, 100),
                'page': page,
                'sort': sort,
                'type': output_type.lower()
            }
            
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"법령-자치법규 연계 검색 - 검색어: {query}")
            
            result = self.client.search(target=self.TARGETS['LNK_LS'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('lnkLs', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"연계 법령 검색 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 15. 연계 법령별 조례 조문 목록 조회 API ====================
    
    def search_ordinance_articles(self,
                                 query: str = "",
                                 knd: Optional[str] = None,
                                 jo: Optional[int] = None,
                                 jobr: Optional[int] = None,
                                 output_type: str = "json",
                                 display: int = 20,
                                 page: int = 1,
                                 sort: str = "lasc",
                                 pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        연계 법령별 조례 조문 목록을 조회합니다. (API #15)
        
        Args:
            query: 검색어
            knd: 법령종류 코드
            jo: 조번호 (4자리)
            jobr: 조가지번호 (2자리)
            output_type: 출력형태
            display: 결과 개수
            page: 페이지
            sort: 정렬옵션
            pop_yn: 팝업창 여부
        
        Returns:
            조례 조문 목록
        """
        try:
            params = {
                'query': query if query else '*',
                'display': min(display, 100),
                'page': page,
                'sort': sort,
                'type': output_type.lower()
            }
            
            if knd: params['knd'] = knd
            if jo: params['JO'] = jo
            if jobr: params['JOBR'] = jobr
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"조례 조문 검색 - 검색어: {query}")
            
            result = self.client.search(target=self.TARGETS['LNK_LS_ORD_JO'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('lnkLsOrdJo', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"조례 조문 검색 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 16. 연계 법령 소관부처별 목록 조회 API ====================
    
    def search_linked_by_department(self,
                                   org: str,
                                   output_type: str = "json",
                                   display: int = 20,
                                   page: int = 1,
                                   sort: str = "lasc",
                                   pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        소관부처별 연계 법령을 조회합니다. (API #16)
        
        Args:
            org: 소관부처 코드 (필수)
            output_type: 출력형태
            display: 결과 개수
            page: 페이지
            sort: 정렬옵션
            pop_yn: 팝업창 여부
        
        Returns:
            소관부처별 연계 법령
        """
        try:
            params = {
                'org': org,
                'display': min(display, 100),
                'page': page,
                'sort': sort,
                'type': output_type.lower()
            }
            
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"소관부처별 연계 법령 조회 - 부처: {org}")
            
            result = self.client.search(target=self.TARGETS['LNK_DEP'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('lnkDep', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"소관부처별 연계 법령 조회 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 17. 법령-자치법규 연계현황 조회 API ====================
    
    def get_ordinance_link_status(self, output_type: str = "html") -> Dict[str, Any]:
        """
        법령-자치법규 연계현황을 조회합니다. (API #17)
        
        Args:
            output_type: 출력형태 (HTML만 지원)
        
        Returns:
            연계현황
        """
        try:
            params = {
                'type': output_type.lower()
            }
            
            logger.info("법령-자치법규 연계현황 조회")
            
            result = self.client.search(target=self.TARGETS['DR_LAW'], **params)
            return self._parse_response(result, 'link_status')
            
        except Exception as e:
            logger.error(f"연계현황 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 18. 위임 법령 조회 API ====================
    
    def get_delegated_laws(self,
                          law_id: Optional[str] = None,
                          mst: Optional[str] = None,
                          output_type: str = "json") -> Dict[str, Any]:
        """
        위임 법령을 조회합니다. (API #18)
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
            output_type: 출력형태
        
        Returns:
            위임 법령 정보
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {
                'type': output_type.lower()
            }
            
            if law_id: params['ID'] = law_id
            if mst: params['MST'] = mst
            
            logger.info(f"위임 법령 조회 - ID: {law_id or mst}")
            
            result = self.client.get_detail(target=self.TARGETS['LS_DELEGATED'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"위임 법령 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 19. 법령 체계도 목록 조회 API ====================
    
    def search_law_structure(self,
                            query: str = "",
                            output_type: str = "json",
                            display: int = 20,
                            page: int = 1,
                            sort: str = "lasc",
                            ef_yd: Optional[str] = None,
                            anc_yd: Optional[str] = None,
                            date: Optional[int] = None,
                            nb: Optional[int] = None,
                            anc_no: Optional[str] = None,
                            rr_cls_cd: Optional[str] = None,
                            org: Optional[str] = None,
                            knd: Optional[str] = None,
                            gana: Optional[str] = None,
                            pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        법령 체계도 목록을 조회합니다. (API #19)
        
        Args:
            query: 검색어
            output_type: 출력형태
            기타 파라미터는 search_laws와 동일
        
        Returns:
            법령 체계도 목록
        """
        try:
            params = {
                'query': query if query else '*',
                'display': min(display, 100),
                'page': page,
                'sort': sort,
                'type': output_type.lower()
            }
            
            if ef_yd: params['efYd'] = ef_yd
            if anc_yd: params['ancYd'] = anc_yd
            if date: params['date'] = date
            if nb: params['nb'] = nb
            if anc_no: params['ancNo'] = anc_no
            if rr_cls_cd: params['rrClsCd'] = rr_cls_cd
            if org: params['org'] = org
            if knd: params['knd'] = knd
            if gana: params['gana'] = gana
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"법령 체계도 목록 검색 - 검색어: {query}")
            
            result = self.client.search(target=self.TARGETS['LS_STMD'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('lsStmd', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"법령 체계도 목록 검색 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 20. 법령 체계도 본문 조회 API ====================
    
    def get_law_structure_detail(self,
                                law_id: Optional[str] = None,
                                mst: Optional[str] = None,
                                output_type: str = "json",
                                lm: Optional[str] = None,
                                ld: Optional[int] = None,
                                ln: Optional[int] = None) -> Dict[str, Any]:
        """
        법령 체계도 본문을 조회합니다. (API #20)
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
            output_type: 출력형태
            lm: 법령명
            ld: 공포일자
            ln: 공포번호
        
        Returns:
            법령 체계도 상세
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {
                'type': output_type.lower()
            }
            
            if law_id: params['ID'] = law_id
            if mst: params['MST'] = mst
            if lm: params['LM'] = lm
            if ld: params['LD'] = ld
            if ln: params['LN'] = ln
            
            logger.info(f"법령 체계도 상세 조회 - ID: {law_id or mst}")
            
            result = self.client.get_detail(target=self.TARGETS['LS_STMD'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"법령 체계도 상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 21. 신구법 목록 조회 API ====================
    
    def search_old_new_laws(self,
                           query: str = "",
                           output_type: str = "json",
                           display: int = 20,
                           page: int = 1,
                           sort: str = "lasc",
                           ef_yd: Optional[str] = None,
                           anc_yd: Optional[str] = None,
                           date: Optional[int] = None,
                           nb: Optional[int] = None,
                           anc_no: Optional[str] = None,
                           rr_cls_cd: Optional[str] = None,
                           org: Optional[str] = None,
                           knd: Optional[str] = None,
                           gana: Optional[str] = None,
                           pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        신구법 목록을 조회합니다. (API #21)
        
        Args:
            query: 검색어
            output_type: 출력형태
            기타 파라미터는 search_laws와 동일
        
        Returns:
            신구법 목록
        """
        try:
            params = {
                'query': query if query else '*',
                'display': min(display, 100),
                'page': page,
                'sort': sort,
                'type': output_type.lower()
            }
            
            if ef_yd: params['efYd'] = ef_yd
            if anc_yd: params['ancYd'] = anc_yd
            if date: params['date'] = date
            if nb: params['nb'] = nb
            if anc_no: params['ancNo'] = anc_no
            if rr_cls_cd: params['rrClsCd'] = rr_cls_cd
            if org: params['org'] = org
            if knd: params['knd'] = knd
            if gana: params['gana'] = gana
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"신구법 목록 검색 - 검색어: {query}")
            
            result = self.client.search(target=self.TARGETS['OLD_AND_NEW'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('oldAndNew', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"신구법 목록 검색 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 22. 신구법 본문 조회 API ====================
    
    def get_old_new_law_detail(self,
                              law_id: Optional[str] = None,
                              mst: Optional[str] = None,
                              output_type: str = "json",
                              lm: Optional[str] = None,
                              ld: Optional[int] = None,
                              ln: Optional[int] = None) -> Dict[str, Any]:
        """
        신구법 본문을 조회합니다. (API #22)
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
            output_type: 출력형태
            lm: 법령명
            ld: 공포일자
            ln: 공포번호
        
        Returns:
            신구법 상세
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {
                'type': output_type.lower()
            }
            
            if law_id: params['ID'] = law_id
            if mst: params['MST'] = mst
            if lm: params['LM'] = lm
            if ld: params['LD'] = ld
            if ln: params['LN'] = ln
            
            logger.info(f"신구법 상세 조회 - ID: {law_id or mst}")
            
            result = self.client.get_detail(target=self.TARGETS['OLD_AND_NEW'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"신구법 상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 23. 3단 비교 목록 조회 API ====================
    
    def search_three_way_comparison(self,
                                   query: str = "",
                                   output_type: str = "json",
                                   display: int = 20,
                                   page: int = 1,
                                   sort: str = "lasc",
                                   ef_yd: Optional[str] = None,
                                   anc_yd: Optional[str] = None,
                                   date: Optional[int] = None,
                                   nb: Optional[int] = None,
                                   anc_no: Optional[str] = None,
                                   rr_cls_cd: Optional[str] = None,
                                   org: Optional[str] = None,
                                   knd: Optional[str] = None,
                                   gana: Optional[str] = None,
                                   pop_yn: Optional[str] = None) -> Dict[str, Any]:
        """
        3단 비교 목록을 조회합니다. (API #23)
        
        Args:
            query: 검색어
            output_type: 출력형태
            기타 파라미터는 search_laws와 동일
        
        Returns:
            3단 비교 목록
        """
        try:
            params = {
                'query': query if query else '*',
                'display': min(display, 100),
                'page': page,
                'sort': sort,
                'type': output_type.lower()
            }
            
            if ef_yd: params['efYd'] = ef_yd
            if anc_yd: params['ancYd'] = anc_yd
            if date: params['date'] = date
            if nb: params['nb'] = nb
            if anc_no: params['ancNo'] = anc_no
            if rr_cls_cd: params['rrClsCd'] = rr_cls_cd
            if org: params['org'] = org
            if knd: params['knd'] = knd
            if gana: params['gana'] = gana
            if pop_yn: params['popYn'] = pop_yn
            
            logger.info(f"3단 비교 목록 검색 - 검색어: {query}")
            
            result = self.client.search(target=self.TARGETS['THD_CMP'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('thdCmp', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"3단 비교 목록 검색 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 24. 3단 비교 본문 조회 API ====================
    
    def get_three_way_comparison_detail(self,
                                       law_id: Optional[str] = None,
                                       mst: Optional[str] = None,
                                       knd: int = 1,
                                       output_type: str = "json",
                                       lm: Optional[str] = None,
                                       ld: Optional[int] = None,
                                       ln: Optional[int] = None) -> Dict[str, Any]:
        """
        3단 비교 본문을 조회합니다. (API #24)
        
        Args:
            law_id: 법령 ID
            mst: 법령 마스터 번호
            knd: 3단비교 종류 (1: 인용조문, 2: 위임조문, 필수)
            output_type: 출력형태
            lm: 법령명
            ld: 공포일자
            ln: 공포번호
        
        Returns:
            3단 비교 상세
        """
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나는 필수입니다.")
        
        try:
            params = {
                'knd': knd,
                'type': output_type.lower()
            }
            
            if law_id: params['ID'] = law_id
            if mst: params['MST'] = mst
            if lm: params['LM'] = lm
            if ld: params['LD'] = ld
            if ln: params['LN'] = ln
            
            logger.info(f"3단 비교 상세 조회 - ID: {law_id or mst}, 종류: {knd}")
            
            result = self.client.get_detail(target=self.TARGETS['THD_CMP'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"3단 비교 상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 25. 법령명 약칭 조회 API ====================
    
    def search_law_abbreviations(self,
                                std_dt: Optional[int] = None,
                                end_dt: Optional[int] = None,
                                output_type: str = "json") -> Dict[str, Any]:
        """
        법령명 약칭을 조회합니다. (API #25)
        
        Args:
            std_dt: 등록일 시작
            end_dt: 등록일 종료
            output_type: 출력형태
        
        Returns:
            법령 약칭 목록
        """
        try:
            params = {
                'type': output_type.lower()
            }
            
            if std_dt: params['stdDt'] = std_dt
            if end_dt: params['endDt'] = end_dt
            
            logger.info("법령명 약칭 조회")
            
            result = self.client.search(target=self.TARGETS['LS_ABRV'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'results': result.get('lsAbrv', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"법령명 약칭 조회 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 26. 삭제 데이터 목록 조회 API ====================
    
    def search_deleted_data(self,
                           knd: Optional[int] = None,
                           del_dt: Optional[int] = None,
                           frm_dt: Optional[int] = None,
                           to_dt: Optional[int] = None,
                           output_type: str = "json",
                           display: int = 20,
                           page: int = 1) -> Dict[str, Any]:
        """
        삭제 데이터 목록을 조회합니다. (API #26)
        
        Args:
            knd: 데이터 종류 (1: 법령, 2: 행정규칙, 3: 자치법규, 13: 학칙공단)
            del_dt: 삭제일자 (YYYYMMDD)
            frm_dt: 시작일자
            to_dt: 종료일자
            output_type: 출력형태
            display: 결과 개수
            page: 페이지
        
        Returns:
            삭제 데이터 목록
        """
        try:
            params = {
                'display': min(display, 100),
                'page': page,
                'type': output_type.lower()
            }
            
            if knd: params['knd'] = knd
            if del_dt: params['delDt'] = del_dt
            if frm_dt: params['frmDt'] = frm_dt
            if to_dt: params['toDt'] = to_dt
            
            logger.info(f"삭제 데이터 조회 - 종류: {knd}, 날짜: {del_dt}")
            
            result = self.client.search(target=self.TARGETS['DEL_HST'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('delHst', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"삭제 데이터 조회 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 27. 한눈보기 목록 조회 API ====================
    
    def search_oneview(self,
                       query: str = "",
                       output_type: str = "json",
                       display: int = 20,
                       page: int = 1) -> Dict[str, Any]:
        """
        한눈보기 목록을 조회합니다. (API #27)
        
        Args:
            query: 검색어
            output_type: 출력형태
            display: 결과 개수
            page: 페이지
        
        Returns:
            한눈보기 목록
        """
        try:
            params = {
                'query': query if query else '*',
                'display': min(display, 100),
                'page': page,
                'type': output_type.lower()
            }
            
            logger.info(f"한눈보기 목록 검색 - 검색어: {query}")
            
            result = self.client.search(target=self.TARGETS['ONEVIEW'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error'], 'totalCnt': 0, 'results': []}
            
            if isinstance(result, dict):
                return {
                    'totalCnt': result.get('totalCnt', 0),
                    'page': result.get('page', page),
                    'results': result.get('oneview', [])
                }
            
            return {'error': 'Invalid response', 'totalCnt': 0, 'results': []}
            
        except Exception as e:
            logger.error(f"한눈보기 목록 검색 실패: {str(e)}")
            return {'error': str(e), 'totalCnt': 0, 'results': []}
    
    # ==================== 28. 한눈보기 본문 조회 API ====================
    
    def get_oneview_detail(self,
                          mst: str,
                          output_type: str = "json",
                          lm: Optional[str] = None,
                          ld: Optional[int] = None,
                          ln: Optional[int] = None,
                          jo: Optional[int] = None) -> Dict[str, Any]:
        """
        한눈보기 본문을 조회합니다. (API #28)
        
        Args:
            mst: 법령 마스터 번호 (필수)
            output_type: 출력형태
            lm: 법령명
            ld: 공포일자
            ln: 공포번호
            jo: 조번호
        
        Returns:
            한눈보기 상세
        """
        try:
            params = {
                'MST': mst,
                'type': output_type.lower()
            }
            
            if lm: params['LM'] = lm
            if ld: params['LD'] = ld
            if ln: params['LN'] = ln
            if jo: params['JO'] = jo
            
            logger.info(f"한눈보기 상세 조회 - MST: {mst}")
            
            result = self.client.get_detail(target=self.TARGETS['ONEVIEW'], **params)
            
            if isinstance(result, dict) and 'error' in result:
                return {'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"한눈보기 상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    # ==================== 파싱 헬퍼 메서드 ====================
    
    def _parse_response(self, response: Any, response_type: str) -> Dict[str, Any]:
        """
        API 응답을 파싱하여 통일된 형태로 반환
        
        Args:
            response: API 응답 (XML 문자열 또는 JSON 딕셔너리)
            response_type: 응답 유형
        
        Returns:
            파싱된 결과
        """
        try:
            # JSON 응답 처리
            if isinstance(response, dict):
                # 에러 체크
                if 'error' in response:
                    return {'error': response['error'], 'results': []}
                
                # 기본 구조로 변환
                return {
                    'type': response_type,
                    'totalCnt': response.get('totalCnt', 0),
                    'page': response.get('page', 1),
                    'results': response.get('law', response.get('items', response.get('results', [])))
                }
            
            # XML 응답 처리
            elif isinstance(response, str):
                # HTML 응답인 경우 그대로 반환
                if response.strip().startswith('<!DOCTYPE') or response.strip().startswith('<html'):
                    return {
                        'type': response_type,
                        'html': response
                    }
                
                # XML 파싱
                try:
                    root = ET.fromstring(response)
                    
                    # 에러 체크
                    error_msg = root.findtext('.//errorMsg')
                    if error_msg:
                        return {'error': error_msg, 'results': []}
                    
                    # 기본 정보 추출
                    total_cnt = root.findtext('.//totalCnt', '0')
                    page = root.findtext('.//page', '1')
                    
                    # 결과 추출 (다양한 태그명 처리)
                    items = []
                    for tag_name in ['law', 'item', 'eflaw', 'elaw', 'oldAndNew', 'thdCmp']:
                        items.extend(root.findall(f'.//{tag_name}'))
                    
                    # 결과 파싱
                    results = []
                    for item in items:
                        result_dict = {}
                        for child in item:
                            if child.text:
                                result_dict[child.tag] = child.text
                        if result_dict:
                            results.append(result_dict)
                    
                    return {
                        'type': response_type,
                        'totalCnt': int(total_cnt) if total_cnt.isdigit() else 0,
                        'page': int(page) if page.isdigit() else 1,
                        'results': results
                    }
                    
                except ET.ParseError as e:
                    logger.error(f"XML 파싱 오류: {str(e)}")
                    return {
                        'type': response_type,
                        'error': f'XML 파싱 오류: {str(e)}',
                        'raw': response[:500]  # 디버깅용
                    }
            
            else:
                return {
                    'type': response_type,
                    'error': f'알 수 없는 응답 형식: {type(response)}',
                    'results': []
                }
                
        except Exception as e:
            logger.error(f"응답 파싱 중 오류: {str(e)}")
            return {
                'type': response_type,
                'error': str(e),
                'results': []
            }
    
    # ==================== 유틸리티 메서드 ====================
    
    def get_department_codes(self) -> Dict[str, str]:
        """
        주요 소관부처 코드를 반환합니다.
        
        Returns:
            소관부처명과 코드 매핑
        """
        return {
            '법무부': '1270000',
            '행정안전부': '1741000',
            '국토교통부': '1613000',
            '산림청': '1400000',
            '경찰청': '1320000',
            '국세청': '1210000',
            '관세청': '1220000',
            '조달청': '1230000',
            '통계청': '1240000',
            '기상청': '1360000',
            '문화재청': '1550000',
            '농촌진흥청': '1390000',
            '특허청': '1430000',
            '교육부': '1342000',
            '과학기술정보통신부': '1721000',
            '외교부': '1262000',
            '통일부': '1263000',
            '국방부': '1290000',
            '기획재정부': '1051000',
            '문화체육관광부': '1371000',
            '농림축산식품부': '1543000',
            '산업통상자원부': '1450000',
            '보건복지부': '1352000',
            '환경부': '1480000',
            '고용노동부': '1492000',
            '여성가족부': '1383000',
            '해양수산부': '1192000',
            '중소벤처기업부': '1421000'
        }
    
    def get_law_type_codes(self) -> Dict[str, str]:
        """
        법령종류 코드를 반환합니다.
        
        Returns:
            법령종류명과 코드 매핑
        """
        return {
            '헌법': '001001',
            '법률': '001002',
            '대통령령': '001003',
            '총리령': '001004',
            '부령': '001005',
            '대통령훈령': '001006',
            '국무총리훈령': '001007',
            '부령외훈령': '001008',
            '국회규칙': '002001',
            '대법원규칙': '002002',
            '헌법재판소규칙': '002003',
            '중앙선거관리위원회규칙': '002004',
            '감사원규칙': '002005',
            '명령': '003001',
            '조례': '004001',
            '교육규칙': '004002',
            '규칙': '004003'
        }


# ==================== 테스트 코드 ====================

if __name__ == "__main__":
    """
    모듈 테스트 코드
    실행: python law_module.py
    """
    
    print("=" * 60)
    print("법제처 Open API 통합 모듈 테스트")
    print("=" * 60)
    
    # API 키 설정 (테스트용 'test' 사용)
    searcher = LawSearcher(oc_key='test')
    
    # 1. 현행법령 검색
    print("\n[TEST 1] 현행법령 검색")
    print("-" * 40)
    result = searcher.search_laws("자동차관리법", display=3)
    if 'error' not in result:
        print(f"✅ 검색 성공: {result.get('totalCnt', 0)}건")
        for idx, law in enumerate(result.get('results', [])[:3], 1):
            print(f"  {idx}. {law.get('법령명한글', 'N/A')}")
    else:
        print(f"❌ 오류: {result['error']}")
    
    # 2. 영문법령 검색
    print("\n[TEST 2] 영문법령 검색")
    print("-" * 40)
    result = searcher.search_english_laws("traffic", display=3)
    if 'error' not in result:
        print(f"✅ 검색 성공: {result.get('totalCnt', 0)}건")
    else:
        print(f"❌ 오류: {result['error']}")
    
    # 3. 법령 약칭 조회
    print("\n[TEST 3] 법령명 약칭 조회")
    print("-" * 40)
    result = searcher.search_law_abbreviations()
    if 'error' not in result:
        print(f"✅ 조회 성공")
    else:
        print(f"❌ 오류: {result['error']}")
    
    # 4. 소관부처 코드 확인
    print("\n[TEST 4] 소관부처 코드")
    print("-" * 40)
    dept_codes = searcher.get_department_codes()
    print(f"✅ 등록된 소관부처: {len(dept_codes)}개")
    print(f"  예시: 법무부 = {dept_codes['법무부']}")
    
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)
