"""
조약/행정규칙/자치법규/별표서식/법령용어 검색 모듈
법제처 API를 활용한 다양한 법령 관련 문서 검색 기능 제공
"""

from typing import Optional, Dict, List, Any, Literal
from datetime import datetime
import logging
from common_api import LawAPIClient

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TreatyAdminSearcher:
    """조약, 행정규칙, 자치법규, 별표서식, 법령용어 검색 클래스"""
    
    def __init__(self, oc_key: Optional[str] = None):
        """
        초기화
        
        Args:
            oc_key: 법제처 API OC 키 (없으면 환경변수에서 읽음)
        """
        self.api_client = LawAPIClient(oc_key)
        
    # ================== 조약 관련 기능 ==================
    
    def search_treaties(
        self,
        query: str = "",
        cls: Optional[int] = None,
        search_type: int = 1,
        nat_cd: Optional[int] = None,
        eft_yd: Optional[str] = None,
        conc_yd: Optional[str] = None,
        sort: str = "lasc",
        display: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        조약 목록 검색
        
        Args:
            query: 검색어
            cls: 조약 유형 (1: 양자조약, 2: 다자조약)
            search_type: 검색범위 (1: 조약명, 2: 조약본문)
            nat_cd: 국가코드
            eft_yd: 발효일자 범위 (예: "20200101~20201231")
            conc_yd: 체결일자 범위
            sort: 정렬옵션 (lasc: 조약명 오름차순, ldes: 내림차순 등)
            display: 결과 개수
            page: 페이지 번호
            
        Returns:
            검색 결과 딕셔너리
        """
        params = {
            "target": "trty",
            "search": search_type,
            "query": query or "*",
            "display": display,
            "page": page,
            "sort": sort
        }
        
        if cls:
            params["cls"] = cls
        if nat_cd:
            params["natCd"] = nat_cd
        if eft_yd:
            params["eftYd"] = eft_yd
        if conc_yd:
            params["concYd"] = conc_yd
            
        try:
            result = self.api_client.search(**params)
            logger.info(f"조약 검색 완료: {query}, 결과 수: {result.get('totalCnt', 0)}")
            return result
        except Exception as e:
            logger.error(f"조약 검색 실패: {e}")
            return {"error": str(e), "totalCnt": 0, "treaties": []}
    
    def get_treaty_detail(
        self,
        treaty_id: int,
        chr_cls_cd: str = "010202"
    ) -> Dict[str, Any]:
        """
        조약 본문 조회
        
        Args:
            treaty_id: 조약 ID
            chr_cls_cd: 언어 구분 (010202: 한글, 010203: 영문)
            
        Returns:
            조약 상세 정보
        """
        params = {
            "target": "trty",
            "ID": treaty_id,
            "chrClsCd": chr_cls_cd
        }
        
        try:
            result = self.api_client.get_detail(**params)
            logger.info(f"조약 상세 조회 완료: ID {treaty_id}")
            return result
        except Exception as e:
            logger.error(f"조약 상세 조회 실패: {e}")
            return {"error": str(e)}
    
    # ================== 행정규칙 관련 기능 ==================
    
    def search_admin_rules(
        self,
        query: str = "",
        org: Optional[str] = None,
        kind: Optional[int] = None,
        search_type: int = 1,
        nw: int = 1,
        date: Optional[int] = None,
        sort: str = "lasc",
        display: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        행정규칙 검색
        
        Args:
            query: 검색어
            org: 소관부처 코드
            kind: 행정규칙 종류 (1: 훈령, 2: 예규, 3: 고시, 4: 지침)
            search_type: 검색범위 (1: 행정규칙명, 2: 본문)
            nw: 현행/연혁 구분 (1: 현행, 2: 연혁)
            date: 발령일자
            sort: 정렬옵션
            display: 결과 개수
            page: 페이지 번호
            
        Returns:
            검색 결과
        """
        params = {
            "target": "admrul",
            "search": search_type,
            "query": query or "*",
            "nw": nw,
            "display": display,
            "page": page,
            "sort": sort
        }
        
        if org:
            params["org"] = org
        if kind:
            params["knd"] = kind
        if date:
            params["date"] = date
            
        try:
            result = self.api_client.search(**params)
            logger.info(f"행정규칙 검색 완료: {query}")
            return result
        except Exception as e:
            logger.error(f"행정규칙 검색 실패: {e}")
            return {"error": str(e), "totalCnt": 0, "rules": []}
    
    def get_admin_rule_detail(
        self,
        rule_id: Optional[int] = None,
        lid: Optional[int] = None,
        lm: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        행정규칙 상세 조회
        
        Args:
            rule_id: 행정규칙 일련번호
            lid: 행정규칙 ID
            lm: 행정규칙명
            
        Returns:
            행정규칙 상세 정보
        """
        params = {"target": "admrul"}
        
        if rule_id:
            params["ID"] = rule_id
        elif lid:
            params["LID"] = lid
        elif lm:
            params["LM"] = lm
        else:
            raise ValueError("rule_id, lid, lm 중 하나는 필수입니다.")
            
        try:
            result = self.api_client.get_detail(**params)
            logger.info(f"행정규칙 상세 조회 완료")
            return result
        except Exception as e:
            logger.error(f"행정규칙 상세 조회 실패: {e}")
            return {"error": str(e)}
    
    # ================== 자치법규 관련 기능 ==================
    
    def search_local_laws(
        self,
        query: str = "",
        org: Optional[str] = None,
        sborg: Optional[str] = None,
        search_type: int = 1,
        nw: int = 1,
        kind: Optional[int] = None,
        sort: str = "lasc",
        display: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        자치법규 검색
        
        Args:
            query: 검색어
            org: 지자체 코드
            sborg: 시군구 코드 (org와 함께 사용)
            search_type: 검색범위 (1: 자치법규명, 2: 본문)
            nw: 현행/연혁 구분
            kind: 자치법규 종류 (1: 조례, 2: 규칙, 3: 훈령 등)
            sort: 정렬옵션
            display: 결과 개수
            page: 페이지 번호
            
        Returns:
            검색 결과
        """
        params = {
            "target": "ordin",
            "search": search_type,
            "query": query or "*",
            "nw": nw,
            "display": display,
            "page": page,
            "sort": sort
        }
        
        if org:
            params["org"] = org
        if sborg:
            params["sborg"] = sborg
        if kind:
            params["knd"] = kind
            
        try:
            result = self.api_client.search(**params)
            logger.info(f"자치법규 검색 완료: {query}")
            return result
        except Exception as e:
            logger.error(f"자치법규 검색 실패: {e}")
            return {"error": str(e), "totalCnt": 0, "ordinances": []}
    
    def get_local_law_detail(
        self,
        law_id: Optional[int] = None,
        lid: Optional[int] = None,
        lm: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        자치법규 상세 조회
        
        Args:
            law_id: 자치법규 일련번호
            lid: 자치법규 ID
            lm: 자치법규명
            
        Returns:
            자치법규 상세 정보
        """
        params = {"target": "ordin"}
        
        if law_id:
            params["ID"] = law_id
        elif lid:
            params["LID"] = lid
        elif lm:
            params["LM"] = lm
        else:
            raise ValueError("law_id, lid, lm 중 하나는 필수입니다.")
            
        try:
            result = self.api_client.get_detail(**params)
            logger.info(f"자치법규 상세 조회 완료")
            return result
        except Exception as e:
            logger.error(f"자치법규 상세 조회 실패: {e}")
            return {"error": str(e)}
    
    # ================== 별표서식 관련 기능 ==================
    
    def search_attachments(
        self,
        query: str = "",
        target: Literal["licbyl", "admbyl", "ordinbyl"] = "licbyl",
        search_type: int = 1,
        org: Optional[str] = None,
        kind: Optional[str] = None,
        sort: str = "lasc",
        display: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        별표서식 검색
        
        Args:
            query: 검색어
            target: 대상 (licbyl: 법령, admbyl: 행정규칙, ordinbyl: 자치법규)
            search_type: 검색범위 (1: 별표서식명, 2: 해당법령, 3: 본문)
            org: 소관부처 코드
            kind: 별표 종류 (1: 별표, 2: 서식, 3: 별지 등)
            sort: 정렬옵션
            display: 결과 개수
            page: 페이지 번호
            
        Returns:
            검색 결과
        """
        params = {
            "target": target,
            "search": search_type,
            "query": query or "*",
            "display": display,
            "page": page,
            "sort": sort
        }
        
        if org:
            params["org"] = org
        if kind:
            params["knd"] = kind
            
        try:
            result = self.api_client.search(**params)
            logger.info(f"별표서식 검색 완료: {query}")
            return result
        except Exception as e:
            logger.error(f"별표서식 검색 실패: {e}")
            return {"error": str(e), "totalCnt": 0, "attachments": []}
    
    # ================== 법령용어 관련 기능 ==================
    
    def search_legal_terms(
        self,
        query: str = "",
        dic_knd_cd: Optional[int] = None,
        reg_dt: Optional[str] = None,
        gana: Optional[str] = None,
        sort: str = "lasc",
        display: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        법령용어 검색
        
        Args:
            query: 검색할 법령용어
            dic_knd_cd: 법령 종류 코드 (010101: 법령, 010102: 행정규칙)
            reg_dt: 등록일자 범위 (예: "20200101~20201231")
            gana: 사전식 검색 (ga, na, da 등)
            sort: 정렬옵션
            display: 결과 개수
            page: 페이지 번호
            
        Returns:
            검색 결과
        """
        params = {
            "target": "lstrm",
            "query": query or "*",
            "display": display,
            "page": page,
            "sort": sort
        }
        
        if dic_knd_cd:
            params["dicKndCd"] = dic_knd_cd
        if reg_dt:
            params["regDt"] = reg_dt
        if gana:
            params["gana"] = gana
            
        try:
            result = self.api_client.search(**params)
            logger.info(f"법령용어 검색 완료: {query}")
            return result
        except Exception as e:
            logger.error(f"법령용어 검색 실패: {e}")
            return {"error": str(e), "totalCnt": 0, "terms": []}
    
    def get_term_definition(self, term: str) -> Dict[str, Any]:
        """
        법령용어 정의 조회
        
        Args:
            term: 조회할 법령용어명
            
        Returns:
            법령용어 정의
        """
        params = {
            "target": "lstrm",
            "query": term
        }
        
        try:
            result = self.api_client.get_detail(**params)
            logger.info(f"법령용어 정의 조회 완료: {term}")
            return result
        except Exception as e:
            logger.error(f"법령용어 정의 조회 실패: {e}")
            return {"error": str(e)}
    
    # ================== 맞춤형 분류 관련 기능 ==================
    
    def search_custom_laws(
        self,
        vcode: str,
        target: Literal["couseLs", "couseAdmrul", "couseOrdin"] = "couseLs",
        lj: Optional[str] = None,
        display: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        맞춤형 법령/행정규칙/자치법규 검색
        
        Args:
            vcode: 분류코드 (L: 법령, A: 행정규칙, O: 자치법규로 시작하는 14자리)
            target: 대상 (couseLs: 법령, couseAdmrul: 행정규칙, couseOrdin: 자치법규)
            lj: 조문 여부 ("jo"로 설정시 조문 검색)
            display: 결과 개수
            page: 페이지 번호
            
        Returns:
            검색 결과
        """
        params = {
            "target": target,
            "vcode": vcode,
            "display": display,
            "page": page
        }
        
        if lj:
            params["lj"] = lj
            
        try:
            result = self.api_client.search(**params)
            logger.info(f"맞춤형 분류 검색 완료: {vcode}")
            return result
        except Exception as e:
            logger.error(f"맞춤형 분류 검색 실패: {e}")
            return {"error": str(e), "totalCnt": 0, "items": []}
    
    # ================== 학칙공단공공기관 관련 기능 ==================
    
    def search_school_rules(
        self,
        query: str = "",
        target: Literal["school", "public", "pi"] = "school",
        search_type: int = 1,
        nw: int = 1,
        kind: Optional[int] = None,
        sort: str = "lasc",
        display: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        학칙/공단/공공기관 규정 검색
        
        Args:
            query: 검색어
            target: 대상 (school: 대학, public: 지방공사공단, pi: 공공기관)
            search_type: 검색범위 (1: 규정명, 2: 본문)
            nw: 현행/연혁 구분 (1: 현행, 2: 연혁)
            kind: 규정 종류 (1: 학칙, 2: 학교규정 등)
            sort: 정렬옵션
            display: 결과 개수
            page: 페이지 번호
            
        Returns:
            검색 결과
        """
        params = {
            "target": target,
            "search": search_type,
            "query": query or "*",
            "nw": nw,
            "display": display,
            "page": page,
            "sort": sort
        }
        
        if kind:
            params["knd"] = kind
            
        try:
            result = self.api_client.search(**params)
            logger.info(f"학칙/공단 규정 검색 완료: {query}")
            return result
        except Exception as e:
            logger.error(f"학칙/공단 규정 검색 실패: {e}")
            return {"error": str(e), "totalCnt": 0, "rules": []}
    
    def get_school_rule_detail(
        self,
        target: Literal["school", "public", "pi"],
        rule_id: Optional[int] = None,
        lid: Optional[int] = None,
        lm: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        학칙/공단/공공기관 규정 상세 조회
        
        Args:
            target: 대상 (school, public, pi)
            rule_id: 규정 일련번호
            lid: 규정 ID
            lm: 규정명
            
        Returns:
            규정 상세 정보
        """
        params = {"target": target}
        
        if rule_id:
            params["ID"] = rule_id
        elif lid:
            params["LID"] = lid
        elif lm:
            params["LM"] = lm
        else:
            raise ValueError("rule_id, lid, lm 중 하나는 필수입니다.")
            
        try:
            result = self.api_client.get_detail(**params)
            logger.info(f"학칙/공단 규정 상세 조회 완료")
            return result
        except Exception as e:
            logger.error(f"학칙/공단 규정 상세 조회 실패: {e}")
            return {"error": str(e)}
    
    # ================== 법령정보지식베이스 관련 기능 ==================
    
    def search_ai_legal_terms(
        self,
        query: str = "",
        homonym_yn: Optional[str] = None,
        display: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        법령정보지식베이스 법령용어 검색
        
        Args:
            query: 검색할 법령용어
            homonym_yn: 동음이의어 존재여부 (Y/N)
            display: 결과 개수
            page: 페이지 번호
            
        Returns:
            검색 결과
        """
        params = {
            "target": "lstrmAI",
            "query": query or "*",
            "display": display,
            "page": page
        }
        
        if homonym_yn:
            params["homonymYn"] = homonym_yn
            
        try:
            result = self.api_client.search(**params)
            logger.info(f"AI 법령용어 검색 완료: {query}")
            return result
        except Exception as e:
            logger.error(f"AI 법령용어 검색 실패: {e}")
            return {"error": str(e), "totalCnt": 0, "terms": []}
    
    def search_daily_terms(
        self,
        query: str = "",
        display: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        법령정보지식베이스 일상용어 검색
        
        Args:
            query: 검색할 일상용어
            display: 결과 개수
            page: 페이지 번호
            
        Returns:
            검색 결과
        """
        params = {
            "target": "dlytrm",
            "query": query or "*",
            "display": display,
            "page": page
        }
        
        try:
            result = self.api_client.search(**params)
            logger.info(f"일상용어 검색 완료: {query}")
            return result
        except Exception as e:
            logger.error(f"일상용어 검색 실패: {e}")
            return {"error": str(e), "totalCnt": 0, "terms": []}
    
    def get_term_relations(
        self,
        query: str,
        target: Literal["lstrmRlt", "dlytrmRlt"] = "lstrmRlt",
        trm_rlt_cd: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        법령용어-일상용어 연계 정보 조회
        
        Args:
            query: 검색할 용어
            target: 대상 (lstrmRlt: 법령용어 기준, dlytrmRlt: 일상용어 기준)
            trm_rlt_cd: 용어관계 (140301: 동의어, 140302: 반의어 등)
            
        Returns:
            연계 정보
        """
        params = {
            "target": target,
            "query": query
        }
        
        if trm_rlt_cd:
            params["trmRltCd"] = trm_rlt_cd
            
        try:
            result = self.api_client.get_detail(**params)
            logger.info(f"용어 연계 정보 조회 완료: {query}")
            return result
        except Exception as e:
            logger.error(f"용어 연계 정보 조회 실패: {e}")
            return {"error": str(e)}
    
    def get_term_article_relations(
        self,
        query: str,
        target: Literal["lstrmRltJo", "joRltLstrm"] = "lstrmRltJo",
        law_id: Optional[int] = None,
        jo: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        법령용어-조문 연계 정보 조회
        
        Args:
            query: 검색할 용어 또는 법령명
            target: 대상 (lstrmRltJo: 법령용어 기준, joRltLstrm: 조문 기준)
            law_id: 법령 ID (joRltLstrm 사용시)
            jo: 조번호 (joRltLstrm 사용시 필수)
            
        Returns:
            연계 정보
        """
        params = {
            "target": target,
            "query": query
        }
        
        if law_id:
            params["ID"] = law_id
        if jo:
            params["JO"] = jo
            
        try:
            result = self.api_client.get_detail(**params)
            logger.info(f"용어-조문 연계 정보 조회 완료: {query}")
            return result
        except Exception as e:
            logger.error(f"용어-조문 연계 정보 조회 실패: {e}")
            return {"error": str(e)}
    
    def search_related_laws(
        self,
        query: str = "",
        law_id: Optional[int] = None,
        ls_rlt_cd: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        법령정보지식베이스 관련법령 검색
        
        Args:
            query: 기준법령명
            law_id: 법령 ID
            ls_rlt_cd: 법령 간 관계 코드
            
        Returns:
            관련법령 목록
        """
        params = {
            "target": "lsRlt"
        }
        
        if query:
            params["query"] = query
        if law_id:
            params["ID"] = law_id
        if ls_rlt_cd:
            params["lsRltCd"] = ls_rlt_cd
            
        try:
            result = self.api_client.search(**params)
            logger.info(f"관련법령 검색 완료: {query or law_id}")
            return result
        except Exception as e:
            logger.error(f"관련법령 검색 실패: {e}")
            return {"error": str(e), "totalCnt": 0, "laws": []}
    
    # ================== 통합 검색 기능 ==================
    
    def search_all_documents(
        self,
        query: str,
        search_types: Optional[List[str]] = None,
        max_results: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        모든 문서 유형 통합 검색
        
        Args:
            query: 검색어
            search_types: 검색할 문서 유형 리스트 (없으면 전체 검색)
            max_results: 각 유형별 최대 결과 수
            
        Returns:
            문서 유형별 검색 결과
        """
        if not search_types:
            search_types = ["treaties", "admin_rules", "local_laws", 
                          "attachments", "legal_terms", "school_rules"]
        
        results = {}
        
        if "treaties" in search_types:
            results["treaties"] = self.search_treaties(query, display=max_results)
            
        if "admin_rules" in search_types:
            results["admin_rules"] = self.search_admin_rules(query, display=max_results)
            
        if "local_laws" in search_types:
            results["local_laws"] = self.search_local_laws(query, display=max_results)
            
        if "attachments" in search_types:
            results["attachments"] = self.search_attachments(query, display=max_results)
            
        if "legal_terms" in search_types:
            results["legal_terms"] = self.search_legal_terms(query, display=max_results)
            
        if "school_rules" in search_types:
            results["school_rules"] = self.search_school_rules(query, display=max_results)
            
        logger.info(f"통합 검색 완료: {query}")
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        검색 가능한 문서 통계 정보 조회
        
        Returns:
            각 문서 유형별 통계 정보
        """
        stats = {
            "timestamp": datetime.now().isoformat(),
            "available_searches": {
                "treaties": ["양자조약", "다자조약"],
                "admin_rules": ["훈령", "예규", "고시", "지침"],
                "local_laws": ["조례", "규칙", "훈령", "예규", "고시", "규정"],
                "attachments": ["별표", "서식", "별지", "별도", "부록"],
                "legal_terms": ["법령용어", "일상용어", "용어관계"],
                "school_rules": ["학칙", "학교규정", "공단규정", "공공기관규정"]
            }
        }
        
        return stats


# 테스트 코드
if __name__ == "__main__":
    # 모듈 테스트
    searcher = TreatyAdminSearcher()
    
    # 1. 조약 검색 테스트
    print("=== 조약 검색 ===")
    treaties = searcher.search_treaties("FTA", cls=1)  # 양자조약 중 FTA 검색
    print(f"검색 결과: {treaties.get('totalCnt', 0)}건")
    
    # 2. 행정규칙 검색 테스트
    print("\n=== 행정규칙 검색 ===")
    admin_rules = searcher.search_admin_rules("시행규칙", kind=3)  # 고시 중 검색
    print(f"검색 결과: {admin_rules.get('totalCnt', 0)}건")
    
    # 3. 자치법규 검색 테스트
    print("\n=== 자치법규 검색 ===")
    local_laws = searcher.search_local_laws("주차", kind=1)  # 조례 중 검색
    print(f"검색 결과: {local_laws.get('totalCnt', 0)}건")
    
    # 4. 법령용어 검색 테스트
    print("\n=== 법령용어 검색 ===")
    terms = searcher.search_legal_terms("선박")
    print(f"검색 결과: {terms.get('totalCnt', 0)}건")
    
    # 5. 통합 검색 테스트
    print("\n=== 통합 검색 ===")
    all_results = searcher.search_all_documents(
        "환경", 
        search_types=["treaties", "admin_rules", "legal_terms"],
        max_results=5
    )
    for doc_type, results in all_results.items():
        print(f"{doc_type}: {results.get('totalCnt', 0)}건")
