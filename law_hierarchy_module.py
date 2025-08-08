"""
법령 체계도 검색 및 다운로드 전문 모듈 (완전 개편 v5.0)
Law Hierarchy Search and Download Module - Complete Redesign
Version 5.0 - 단순하고 확실한 다중 검색 방식
"""

import os
import re
import json
import zipfile
import io
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# ===========================
# 데이터 클래스 정의
# ===========================

@dataclass
class AdminRules:
    """행정규칙 분류"""
    directive: List[Dict] = field(default_factory=list)  # 훈령
    regulation: List[Dict] = field(default_factory=list)  # 예규
    notice: List[Dict] = field(default_factory=list)      # 고시
    guideline: List[Dict] = field(default_factory=list)   # 지침
    rule: List[Dict] = field(default_factory=list)        # 규정
    etc: List[Dict] = field(default_factory=list)         # 기타
    
    def total_count(self) -> int:
        """전체 행정규칙 수"""
        return sum(len(v) for v in asdict(self).values())
    
    def get_all(self) -> List[Dict]:
        """모든 행정규칙 반환"""
        all_rules = []
        for rules_list in asdict(self).values():
            all_rules.extend(rules_list)
        return all_rules

@dataclass
class LawHierarchy:
    """법령 체계 구조"""
    main: Dict = field(default_factory=dict)
    decree: List[Dict] = field(default_factory=list)
    rule: List[Dict] = field(default_factory=list)
    admin_rules: AdminRules = field(default_factory=AdminRules)
    local_laws: List[Dict] = field(default_factory=list)
    attachments: List[Dict] = field(default_factory=list)
    admin_attachments: List[Dict] = field(default_factory=list)
    delegated: List[Dict] = field(default_factory=list)
    
    def get_all_laws(self) -> List[Dict]:
        """모든 관련 법령 반환"""
        all_laws = []
        if self.main:
            all_laws.append(self.main)
        all_laws.extend(self.decree)
        all_laws.extend(self.rule)
        all_laws.extend(self.admin_rules.get_all())
        all_laws.extend(self.local_laws)
        all_laws.extend(self.attachments)
        all_laws.extend(self.admin_attachments)
        all_laws.extend(self.delegated)
        return all_laws
    
    def get_statistics(self) -> Dict[str, int]:
        """통계 정보 반환"""
        return {
            'law': 1 if self.main else 0,
            'decree': len(self.decree),
            'rule': len(self.rule),
            'admin': self.admin_rules.total_count(),
            'local': len(self.local_laws),
            'attachment': len(self.attachments) + len(self.admin_attachments),
            'delegated': len(self.delegated)
        }

@dataclass
class SearchConfig:
    """검색 설정"""
    include_decree: bool = True
    include_rule: bool = True
    include_admin_rules: bool = True
    include_local: bool = True
    include_attachments: bool = True
    include_admin_attachments: bool = True
    include_delegated: bool = True
    search_depth: str = "최대"  # 표준/확장/최대
    debug_mode: bool = False

# ===========================
# 법령별 행정규칙 매핑 (하드코딩)
# ===========================

LAW_ADMIN_RULES_MAP = {
    '자본시장과 금융투자업에 관한 법률': {
        '금융위원회': [
            # 고시
            '증권의 발행 및 공시에 관한 규정',
            '기업공시서식 작성기준',
            '금융투자업규정',
            '금융투자회사의 영업 및 업무에 관한 규정',
            '집합투자재산 평가기준',
            '증권 인수업무 등에 관한 규정',
            '외국환거래규정',
            '파생상품시장 업무규정',
            '증권시장 업무규정',
            '코스닥시장 업무규정',
            '채무증권 발행 및 거래에 관한 규정',
            '공모펀드 분류체계 통일 가이드라인',
            '표준투자권유준칙',
            '금융투자상품 판매 표준 가이드라인',
            '장외파생상품 거래 위험관리 기준',
            '금융위원회 고시',
            # 규정
            '전자단기사채등의 발행 및 유통에 관한 규정',
            '대량보유상황 보고 규정',
            '주식대량소유상황 보고서 작성기준',
            '공개매수 규정',
            '위탁매매업무규정',
            '유가증권시장 상장규정',
            '코스닥시장 상장규정',
            '증권시장 공시규정',
            '코스닥시장 공시규정'
        ],
        '금융감독원': [
            '금융투자업 감독규정',
            '증권발행 및 공시규정 시행세칙',
            '기업공시서식 작성기준 시행세칙'
        ]
    },
    '도로교통법': {
        '경찰청': [
            '도로교통법 시행규칙 운전면허 행정처분 기준',
            '교통안전시설 설치·관리 매뉴얼',
            '교통신호기 설치·관리 매뉴얼',
            '교통사고조사규칙',
            '운전면허 적성검사 기준',
            '음주운전 단속기준',
            '교통단속처리지침',
            '도로교통법령 집행지침',
            '운전면허 행정처분 기준',
            '교통법규 위반 통고처분 기준'
        ],
        '국토교통부': [
            '도로안전시설 설치 및 관리지침',
            '교통안전시설 등 설치·관리에 관한 규칙'
        ]
    },
    '근로기준법': {
        '고용노동부': [
            '근로감독관 집무규정',
            '최저임금 고시',
            '통상임금 산정지침',
            '근로시간 운영지침',
            '유연근로시간제 운영지침',
            '퇴직급여 지급보장 규정',
            '사업장 노동시간 단축 가이드',
            '근로기준법 시행지침',
            '임금체불 청산 지도지침'
        ]
    },
    '개인정보 보호법': {
        '개인정보보호위원회': [
            '개인정보의 안전성 확보조치 기준',
            '개인정보 처리 방법에 관한 고시',
            '개인정보보호 법령 해석 예규',
            '표준 개인정보 처리방침',
            '개인정보 영향평가에 관한 고시',
            '개인정보 유출 통지 등에 관한 고시',
            '개인정보처리자 등록 및 관리에 관한 고시'
        ]
    }
}

# 부처별 일반 키워드 (부처명이 없을 때 사용)
DEPARTMENT_SEARCH_KEYWORDS = {
    '금융위원회': ['금융', '증권', '자본시장', '투자', '펀드', '파생', '공시', '상장'],
    '경찰청': ['교통', '운전', '면허', '도로', '신호', '안전'],
    '고용노동부': ['근로', '노동', '임금', '퇴직', '고용'],
    '국토교통부': ['도로', '건축', '주택', '교통', '철도', '항공', '부동산'],
    '개인정보보호위원회': ['개인정보', '정보보호', '프라이버시'],
    '보건복지부': ['의료', '건강', '복지', '국민연금', '건강보험'],
    '환경부': ['환경', '대기', '수질', '폐기물', '생태'],
    '기획재정부': ['세법', '조세', '관세', '국세', '부가가치세']
}

# ===========================
# 법령 체계도 검색 클래스 (단순화)
# ===========================

class LawHierarchySearcher:
    """법령 체계도 검색 클래스 - 단순하고 확실한 방식"""
    
    def __init__(self, law_client: Any, law_searcher: Any = None):
        self.law_client = law_client
        self.law_searcher = law_searcher
        
    def search_hierarchy(self, law_info: Dict, config: SearchConfig) -> LawHierarchy:
        """법령 체계도 전체 검색 (v5.0)"""
        hierarchy = LawHierarchy(main=law_info)
        
        law_id = law_info.get('법령ID') or law_info.get('법령일련번호')
        law_name = law_info.get('법령명한글', '')
        law_mst = law_info.get('법령MST')
        
        if not law_id or not law_name:
            logger.warning("법령 ID 또는 명칭이 없습니다.")
            return hierarchy
        
        logger.info(f"법령 체계도 검색 시작: {law_name} (ID: {law_id})")
        
        # 1. 시행령/시행규칙 검색 (단순 검색)
        if config.include_decree:
            hierarchy.decree = self._search_simple_decree(law_name)
        
        if config.include_rule:
            hierarchy.rule = self._search_simple_rule(law_name)
        
        # 2. 행정규칙 검색 (핵심 - 완전히 새로운 방식)
        if config.include_admin_rules:
            hierarchy.admin_rules = self._search_admin_rules_new(law_name, config)
        
        # 3. 별표서식 검색
        if config.include_attachments:
            hierarchy.attachments = self._search_attachments_simple(law_name)
        
        # 4. 자치법규 검색
        if config.include_local:
            hierarchy.local_laws = self._search_local_laws_simple(law_name)
        
        # 통계 로그
        stats = hierarchy.get_statistics()
        logger.info(f"검색 완료 - 시행령: {stats['decree']}, 시행규칙: {stats['rule']}, "
                   f"행정규칙: {stats['admin']}, 자치법규: {stats['local']}")
        
        return hierarchy
    
    def _search_simple_decree(self, law_name: str) -> List[Dict]:
        """시행령 단순 검색"""
        decrees = []
        seen_ids = set()
        
        if not self.law_searcher:
            return decrees
        
        try:
            # 법령명에서 기본 이름 추출
            base_name = re.sub(r'법$', '', law_name).strip()
            
            # 검색어 리스트
            queries = [
                f"{base_name} 시행령",
                f"{base_name}시행령",
                f"{law_name} 시행령"
            ]
            
            for query in queries:
                result = self.law_searcher.search_laws(query=query, display=20)
                
                if result.get('totalCnt', 0) > 0:
                    for item in result.get('results', []):
                        item_id = item.get('법령ID')
                        item_name = item.get('법령명한글', '')
                        
                        if item_id not in seen_ids and '시행령' in item_name:
                            if base_name in item_name or any(
                                keyword in item_name 
                                for keyword in base_name.split() 
                                if len(keyword) > 2
                            ):
                                decrees.append(item)
                                seen_ids.add(item_id)
                                logger.debug(f"시행령 추가: {item_name}")
        
        except Exception as e:
            logger.error(f"시행령 검색 오류: {e}")
        
        return decrees
    
    def _search_simple_rule(self, law_name: str) -> List[Dict]:
        """시행규칙 단순 검색"""
        rules = []
        seen_ids = set()
        
        if not self.law_searcher:
            return rules
        
        try:
            # 법령명에서 기본 이름 추출
            base_name = re.sub(r'법$', '', law_name).strip()
            
            # 검색어 리스트
            queries = [
                f"{base_name} 시행규칙",
                f"{base_name}시행규칙",
                f"{law_name} 시행규칙"
            ]
            
            for query in queries:
                result = self.law_searcher.search_laws(query=query, display=20)
                
                if result.get('totalCnt', 0) > 0:
                    for item in result.get('results', []):
                        item_id = item.get('법령ID')
                        item_name = item.get('법령명한글', '')
                        
                        if item_id not in seen_ids and '시행규칙' in item_name:
                            if base_name in item_name or any(
                                keyword in item_name 
                                for keyword in base_name.split() 
                                if len(keyword) > 2
                            ):
                                rules.append(item)
                                seen_ids.add(item_id)
                                logger.debug(f"시행규칙 추가: {item_name}")
        
        except Exception as e:
            logger.error(f"시행규칙 검색 오류: {e}")
        
        return rules
    
    def _search_admin_rules_new(self, law_name: str, config: SearchConfig) -> AdminRules:
        """행정규칙 검색 - 완전히 새로운 방식"""
        admin_rules = AdminRules()
        seen_ids = set()
        
        logger.info(f"행정규칙 검색 시작: {law_name}")
        
        # 1. 사전 정의된 행정규칙 검색 (최우선)
        predefined_rules = self._get_predefined_admin_rules(law_name)
        if predefined_rules:
            logger.info(f"사전 정의된 행정규칙 {len(predefined_rules)}개 검색")
            for rule_name in predefined_rules:
                self._search_and_add_admin_rule(rule_name, admin_rules, seen_ids)
        
        # 2. 법령명 기반 직접 검색
        base_name = re.sub(r'법$', '', law_name).strip()
        
        # 행정규칙 유형별 검색
        rule_types = ['고시', '훈령', '예규', '지침', '규정', '규칙', '기준', '요령']
        
        for rule_type in rule_types:
            # 다양한 검색어 조합
            search_queries = [
                f"{base_name} {rule_type}",
                f"{base_name}{rule_type}",
                f"{law_name} {rule_type}",
                base_name,  # 기본 이름만으로도 검색
            ]
            
            # 법령명의 주요 키워드 추출
            keywords = self._extract_keywords(law_name)
            for keyword in keywords:
                if len(keyword) > 2:
                    search_queries.append(f"{keyword} {rule_type}")
                    search_queries.append(keyword)
            
            # 각 검색어로 검색
            for query in search_queries:
                self._search_admin_rules_by_query(query, admin_rules, seen_ids, rule_type)
        
        # 3. 부처 키워드 기반 검색 (보조)
        dept_keywords = self._get_department_keywords(law_name)
        for keyword in dept_keywords[:5]:  # 상위 5개만
            self._search_admin_rules_by_query(keyword, admin_rules, seen_ids, None)
        
        logger.info(f"행정규칙 검색 완료: 총 {admin_rules.total_count()}개")
        
        # 디버그 모드에서 상세 정보 출력
        if config.debug_mode:
            self._log_admin_rules_detail(admin_rules)
        
        return admin_rules
    
    def _get_predefined_admin_rules(self, law_name: str) -> List[str]:
        """사전 정의된 행정규칙 목록 반환"""
        rules = []
        
        # 정확한 매칭 우선
        for law_key, departments in LAW_ADMIN_RULES_MAP.items():
            if law_key in law_name or law_name in law_key:
                for dept, dept_rules in departments.items():
                    rules.extend(dept_rules)
                return rules
        
        # 부분 매칭
        for law_key, departments in LAW_ADMIN_RULES_MAP.items():
            # 주요 키워드 추출
            law_keywords = set(re.findall(r'[가-힣]{2,}', law_key))
            name_keywords = set(re.findall(r'[가-힣]{2,}', law_name))
            
            # 공통 키워드가 2개 이상이면 관련
            if len(law_keywords & name_keywords) >= 2:
                for dept, dept_rules in departments.items():
                    rules.extend(dept_rules)
                return rules
        
        return rules
    
    def _search_and_add_admin_rule(self, rule_name: str, admin_rules: AdminRules, seen_ids: Set):
        """특정 행정규칙 검색 및 추가"""
        try:
            # 정확한 이름으로 검색
            result = self.law_client.search(
                target='admrul',
                query=rule_name,
                display=10
            )
            
            if result and result.get('totalCnt', 0) > 0:
                for rule in result.get('results', []):
                    rule_id = rule.get('행정규칙ID')
                    if rule_id and rule_id not in seen_ids:
                        self._categorize_admin_rule(rule, admin_rules)
                        seen_ids.add(rule_id)
                        logger.debug(f"행정규칙 추가: {rule.get('행정규칙명')}")
            else:
                # 부분 검색 (단어 분리)
                keywords = rule_name.split()
                if len(keywords) > 2:
                    # 주요 키워드만으로 재검색
                    main_keywords = [k for k in keywords if len(k) > 2][:3]
                    query = ' '.join(main_keywords)
                    
                    result = self.law_client.search(
                        target='admrul',
                        query=query,
                        display=20
                    )
                    
                    if result and result.get('totalCnt', 0) > 0:
                        for rule in result.get('results', []):
                            rule_id = rule.get('행정규칙ID')
                            found_name = rule.get('행정규칙명', '')
                            
                            # 관련성 체크
                            if rule_id and rule_id not in seen_ids:
                                if any(k in found_name for k in main_keywords[:2]):
                                    self._categorize_admin_rule(rule, admin_rules)
                                    seen_ids.add(rule_id)
                                    logger.debug(f"행정규칙 추가 (부분매칭): {found_name}")
                    
        except Exception as e:
            logger.error(f"행정규칙 검색 오류 ({rule_name}): {e}")
    
    def _search_admin_rules_by_query(self, query: str, admin_rules: AdminRules, 
                                    seen_ids: Set, rule_type: Optional[str]):
        """검색어로 행정규칙 검색"""
        try:
            result = self.law_client.search(
                target='admrul',
                query=query,
                display=50  # 충분히 많이 가져오기
            )
            
            if result and result.get('totalCnt', 0) > 0:
                for rule in result.get('results', []):
                    rule_id = rule.get('행정규칙ID')
                    rule_name = rule.get('행정규칙명', '')
                    
                    if rule_id and rule_id not in seen_ids:
                        # 규칙 유형이 지정된 경우 해당 유형만
                        if rule_type:
                            if rule_type in rule_name:
                                self._categorize_admin_rule(rule, admin_rules)
                                seen_ids.add(rule_id)
                        else:
                            # 모든 유형
                            if any(t in rule_name for t in ['고시', '훈령', '예규', '지침', '규정', '규칙', '기준', '요령']):
                                self._categorize_admin_rule(rule, admin_rules)
                                seen_ids.add(rule_id)
                        
                        # 최대 개수 제한
                        if admin_rules.total_count() >= 200:
                            logger.info("행정규칙 최대 개수(200개) 도달")
                            return
                            
        except Exception as e:
            logger.error(f"행정규칙 검색 오류 (query: {query}): {e}")
    
    def _extract_keywords(self, law_name: str) -> List[str]:
        """법령명에서 키워드 추출"""
        # 불필요한 단어 제거
        stop_words = {'관한', '법률', '법', '등에', '대한', '및', '의', '을', '를', '특별', '일반'}
        
        # 단어 분리
        words = re.findall(r'[가-힣]+', law_name)
        
        # 중요 키워드만 선택
        keywords = []
        for word in words:
            if word not in stop_words and len(word) >= 2:
                keywords.append(word)
        
        # 특수 케이스 처리
        if '자본시장' in law_name:
            keywords.extend(['자본시장', '금융투자', '증권', '파생상품', '집합투자'])
        elif '도로교통' in law_name:
            keywords.extend(['도로교통', '교통안전', '운전면허', '교통사고'])
        elif '근로기준' in law_name:
            keywords.extend(['근로', '노동', '임금', '근로조건'])
        elif '개인정보' in law_name:
            keywords.extend(['개인정보', '정보보호', '프라이버시'])
        
        # 중복 제거
        return list(dict.fromkeys(keywords))
    
    def _get_department_keywords(self, law_name: str) -> List[str]:
        """법령명에서 부처 관련 키워드 추출"""
        keywords = []
        
        # 부처별 키워드 매칭
        for dept, dept_keywords in DEPARTMENT_SEARCH_KEYWORDS.items():
            for keyword in dept_keywords:
                if keyword in law_name:
                    keywords.extend(dept_keywords)
                    break
        
        # 중복 제거
        return list(dict.fromkeys(keywords))
    
    def _search_attachments_simple(self, law_name: str) -> List[Dict]:
        """별표서식 단순 검색"""
        attachments = []
        seen_ids = set()
        
        try:
            # 법령명으로 검색
            result = self.law_client.search(
                target='licbyl',
                query=law_name,
                display=100
            )
            
            if result and result.get('totalCnt', 0) > 0:
                for attach in result.get('results', []):
                    attach_id = attach.get('별표서식ID')
                    if attach_id and attach_id not in seen_ids:
                        attachments.append(attach)
                        seen_ids.add(attach_id)
            
            # 기본 이름으로 추가 검색
            base_name = re.sub(r'법$', '', law_name).strip()
            if base_name != law_name:
                result = self.law_client.search(
                    target='licbyl',
                    query=base_name,
                    display=50
                )
                
                if result and result.get('totalCnt', 0) > 0:
                    for attach in result.get('results', []):
                        attach_id = attach.get('별표서식ID')
                        attach_law = attach.get('해당법령명', '')
                        
                        if attach_id and attach_id not in seen_ids:
                            if base_name in attach_law or attach_law in law_name:
                                attachments.append(attach)
                                seen_ids.add(attach_id)
                                
        except Exception as e:
            logger.error(f"별표서식 검색 오류: {e}")
        
        return attachments
    
    def _search_local_laws_simple(self, law_name: str) -> List[Dict]:
        """자치법규 단순 검색"""
        local_laws = []
        seen_ids = set()
        
        try:
            # 주요 키워드 추출
            keywords = self._extract_keywords(law_name)
            
            # 상위 키워드로 검색
            for keyword in keywords[:3]:
                if len(keyword) < 2:
                    continue
                    
                result = self.law_client.search(
                    target='ordin',
                    query=keyword,
                    display=30
                )
                
                if result and result.get('totalCnt', 0) > 0:
                    for law in result.get('results', []):
                        law_id = law.get('자치법규ID')
                        law_name_local = law.get('자치법규명', '')
                        
                        if law_id and law_id not in seen_ids:
                            # 관련성 체크
                            if any(k in law_name_local for k in keywords[:2]):
                                local_laws.append(law)
                                seen_ids.add(law_id)
                                
                                # 최대 100개 제한
                                if len(local_laws) >= 100:
                                    return local_laws
                                    
        except Exception as e:
            logger.error(f"자치법규 검색 오류: {e}")
        
        return local_laws
    
    def _categorize_admin_rule(self, rule: Dict, admin_rules: AdminRules):
        """행정규칙 분류"""
        rule_name = rule.get('행정규칙명', '')
        
        if '훈령' in rule_name:
            admin_rules.directive.append(rule)
        elif '예규' in rule_name:
            admin_rules.regulation.append(rule)
        elif '고시' in rule_name:
            admin_rules.notice.append(rule)
        elif '지침' in rule_name:
            admin_rules.guideline.append(rule)
        elif '규정' in rule_name or '규칙' in rule_name:
            admin_rules.rule.append(rule)
        else:
            admin_rules.etc.append(rule)
    
    def _log_admin_rules_detail(self, admin_rules: AdminRules):
        """행정규칙 상세 로그"""
        if admin_rules.notice:
            logger.info(f"  고시 {len(admin_rules.notice)}개:")
            for rule in admin_rules.notice[:3]:
                logger.info(f"    - {rule.get('행정규칙명')}")
        
        if admin_rules.directive:
            logger.info(f"  훈령 {len(admin_rules.directive)}개:")
            for rule in admin_rules.directive[:3]:
                logger.info(f"    - {rule.get('행정규칙명')}")
        
        if admin_rules.regulation:
            logger.info(f"  예규 {len(admin_rules.regulation)}개:")
            for rule in admin_rules.regulation[:3]:
                logger.info(f"    - {rule.get('행정규칙명')}")

# ===========================
# 다운로드 및 내보내기 클래스
# ===========================

class LawHierarchyExporter:
    """법령 체계도 내보내기 클래스"""
    
    def export_to_markdown(self, hierarchies: Dict[str, LawHierarchy], 
                          include_content: bool = False) -> str:
        """마크다운 형식으로 내보내기"""
        md_content = f"# 법령 체계도 기반 통합 문서\n\n"
        md_content += f"**생성일시:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        
        total_count = sum(len(h.get_all_laws()) for h in hierarchies.values())
        md_content += f"**총 법령 수:** {total_count}개\n\n"
        md_content += "---\n\n"
        
        # 체계도 요약
        md_content += "## 📊 법령 체계도 요약\n\n"
        
        for law_name, hierarchy in hierarchies.items():
            stats = hierarchy.get_statistics()
            md_content += f"### {law_name}\n\n"
            md_content += f"- **시행령:** {stats['decree']}개\n"
            md_content += f"- **시행규칙:** {stats['rule']}개\n"
            md_content += f"- **행정규칙:** {stats['admin']}개\n"
            
            # 행정규칙 세부
            admin_rules = hierarchy.admin_rules
            if admin_rules.directive:
                md_content += f"  - 훈령: {len(admin_rules.directive)}개\n"
            if admin_rules.regulation:
                md_content += f"  - 예규: {len(admin_rules.regulation)}개\n"
            if admin_rules.notice:
                md_content += f"  - 고시: {len(admin_rules.notice)}개\n"
            if admin_rules.guideline:
                md_content += f"  - 지침: {len(admin_rules.guideline)}개\n"
            if admin_rules.rule:
                md_content += f"  - 규정: {len(admin_rules.rule)}개\n"
            
            md_content += f"- **자치법규:** {stats['local']}개\n"
            md_content += f"- **별표서식:** {stats['attachment']}개\n"
            md_content += f"- **위임법령:** {stats['delegated']}개\n\n"
        
        md_content += "---\n\n"
        
        # 법령별 상세 내용
        md_content += "## 📚 법령 상세 내용\n\n"
        
        for law_name, hierarchy in hierarchies.items():
            md_content += f"### {law_name}\n\n"
            md_content += self._export_hierarchy_detail(hierarchy)
        
        return md_content
    
    def _export_hierarchy_detail(self, hierarchy: LawHierarchy) -> str:
        """체계도 상세 내용 생성"""
        content = ""
        
        # 주 법령
        if hierarchy.main:
            content += f"#### 📚 주 법령\n\n"
            content += self._format_law_info(hierarchy.main)
            content += "\n---\n\n"
        
        # 시행령
        if hierarchy.decree:
            content += f"#### 📘 시행령 ({len(hierarchy.decree)}개)\n\n"
            for idx, decree in enumerate(hierarchy.decree, 1):
                content += f"##### {idx}. {decree.get('법령명한글', 'N/A')}\n"
                content += self._format_law_info(decree)
                content += "\n"
        
        # 시행규칙
        if hierarchy.rule:
            content += f"#### 📗 시행규칙 ({len(hierarchy.rule)}개)\n\n"
            for idx, rule in enumerate(hierarchy.rule, 1):
                content += f"##### {idx}. {rule.get('법령명한글', 'N/A')}\n"
                content += self._format_law_info(rule)
                content += "\n"
        
        # 행정규칙
        admin_total = hierarchy.admin_rules.total_count()
        if admin_total > 0:
            content += f"#### 📑 행정규칙 ({admin_total}개)\n\n"
            content += self._format_admin_rules(hierarchy.admin_rules)
        
        # 자치법규
        if hierarchy.local_laws:
            content += f"#### 🏛️ 자치법규 ({len(hierarchy.local_laws)}개)\n\n"
            for idx, law in enumerate(hierarchy.local_laws[:20], 1):
                content += f"##### {idx}. {law.get('자치법규명', 'N/A')}\n"
                content += f"- **지자체:** {law.get('지자체명', 'N/A')}\n"
                content += f"- **발령일자:** {law.get('발령일자', 'N/A')}\n\n"
            
            if len(hierarchy.local_laws) > 20:
                content += f"... 외 {len(hierarchy.local_laws)-20}개\n\n"
        
        # 별표서식
        if hierarchy.attachments:
            content += f"#### 📋 법령 별표서식 ({len(hierarchy.attachments)}개)\n\n"
            for idx, attach in enumerate(hierarchy.attachments[:20], 1):
                content += f"##### {idx}. {attach.get('별표서식명', 'N/A')}\n"
                content += f"- **해당법령:** {attach.get('해당법령명', 'N/A')}\n"
                content += f"- **구분:** {attach.get('별표구분', 'N/A')}\n\n"
            
            if len(hierarchy.attachments) > 20:
                content += f"... 외 {len(hierarchy.attachments)-20}개\n\n"
        
        return content
    
    def _format_law_info(self, law: Dict) -> str:
        """법령 정보 포맷팅"""
        info = ""
        if law.get('법령ID'):
            info += f"- **법령ID:** {law.get('법령ID')}\n"
        if law.get('행정규칙ID'):
            info += f"- **행정규칙ID:** {law.get('행정규칙ID')}\n"
        if law.get('공포일자'):
            info += f"- **공포일자:** {law.get('공포일자')}\n"
        if law.get('시행일자'):
            info += f"- **시행일자:** {law.get('시행일자')}\n"
        if law.get('발령일자'):
            info += f"- **발령일자:** {law.get('발령일자')}\n"
        if law.get('소관부처명'):
            info += f"- **소관부처:** {law.get('소관부처명')}\n"
        return info
    
    def _format_admin_rules(self, admin_rules: AdminRules) -> str:
        """행정규칙 포맷팅"""
        content = ""
        
        # 카테고리별 정리
        categories = [
            ('고시', admin_rules.notice),
            ('훈령', admin_rules.directive),
            ('예규', admin_rules.regulation),
            ('지침', admin_rules.guideline),
            ('규정', admin_rules.rule),
            ('기타', admin_rules.etc)
        ]
        
        for category_name, rules in categories:
            if rules:
                content += f"##### {category_name} ({len(rules)}개)\n\n"
                
                # 최대 15개만 표시
                display_count = min(15, len(rules))
                for idx, rule in enumerate(rules[:display_count], 1):
                    content += f"{idx}. **{rule.get('행정규칙명', 'N/A')}**\n"
                    if rule.get('행정규칙ID'):
                        content += f"   - ID: {rule.get('행정규칙ID')}\n"
                    if rule.get('발령일자'):
                        content += f"   - 발령일자: {rule.get('발령일자')}\n"
                    if rule.get('소관부처명'):
                        content += f"   - 소관부처: {rule.get('소관부처명')}\n"
                
                if len(rules) > display_count:
                    content += f"   ... 외 {len(rules)-display_count}개\n"
                content += "\n"
        
        return content
    
    def export_to_zip(self, hierarchies: Dict[str, LawHierarchy], 
                     format_type: str = "markdown") -> bytes:
        """ZIP 파일로 내보내기"""
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 폴더 구조 생성
            folders = self._organize_by_folders(hierarchies)
            
            # 각 폴더별로 파일 생성
            for folder_path, laws in folders.items():
                if laws:
                    for idx, law in enumerate(laws, 1):
                        file_content = self._create_file_content(law, format_type)
                        file_name = self._create_safe_filename(law, idx, folder_path, format_type)
                        zip_file.writestr(file_name, file_content.encode('utf-8'))
            
            # 메타데이터 추가
            metadata = self._create_metadata(hierarchies)
            zip_file.writestr('00_metadata.json', 
                            json.dumps(metadata, ensure_ascii=False, indent=2).encode('utf-8'))
            
            # README 추가
            readme = self._create_readme(hierarchies, folders)
            zip_file.writestr('00_README.md', readme.encode('utf-8'))
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
    
    def _organize_by_folders(self, hierarchies: Dict[str, LawHierarchy]) -> Dict[str, List]:
        """폴더 구조로 정리"""
        folders = {
            '01_법률': [],
            '02_시행령': [],
            '03_시행규칙': [],
            '04_행정규칙/1_고시': [],
            '04_행정규칙/2_훈령': [],
            '04_행정규칙/3_예규': [],
            '04_행정규칙/4_지침': [],
            '04_행정규칙/5_규정': [],
            '04_행정규칙/9_기타': [],
            '05_자치법규': [],
            '06_별표서식': [],
            '07_위임법령': [],
            '99_기타': []
        }
        
        for hierarchy in hierarchies.values():
            # 주 법령
            if hierarchy.main:
                folders['01_법률'].append(hierarchy.main)
            
            # 시행령
            folders['02_시행령'].extend(hierarchy.decree)
            
            # 시행규칙
            folders['03_시행규칙'].extend(hierarchy.rule)
            
            # 행정규칙 (순서 변경: 고시를 먼저)
            folders['04_행정규칙/1_고시'].extend(hierarchy.admin_rules.notice)
            folders['04_행정규칙/2_훈령'].extend(hierarchy.admin_rules.directive)
            folders['04_행정규칙/3_예규'].extend(hierarchy.admin_rules.regulation)
            folders['04_행정규칙/4_지침'].extend(hierarchy.admin_rules.guideline)
            folders['04_행정규칙/5_규정'].extend(hierarchy.admin_rules.rule)
            folders['04_행정규칙/9_기타'].extend(hierarchy.admin_rules.etc)
            
            # 자치법규
            folders['05_자치법규'].extend(hierarchy.local_laws)
            
            # 별표서식
            folders['06_별표서식'].extend(hierarchy.attachments)
            folders['06_별표서식'].extend(hierarchy.admin_attachments)
            
            # 위임법령
            folders['07_위임법령'].extend(hierarchy.delegated)
        
        return folders
    
    def _create_file_content(self, law: Dict, format_type: str) -> str:
        """파일 내용 생성"""
        law_name = (law.get('법령명한글') or law.get('행정규칙명') or 
                   law.get('자치법규명') or law.get('별표서식명') or 
                   law.get('별표명', 'N/A'))
        
        law_id = (law.get('법령ID') or law.get('행정규칙ID') or 
                 law.get('자치법규ID') or law.get('별표서식ID', ''))
        
        if format_type == "markdown":
            content = f"# {law_name}\n\n"
            if law_id:
                content += f"**ID:** {law_id}\n\n"
            content += self._format_law_info(law)
        elif format_type == "json":
            content = json.dumps(law, ensure_ascii=False, indent=2)
        else:  # text
            content = f"{law_name}\n"
            content += "=" * 50 + "\n"
            if law_id:
                content += f"ID: {law_id}\n"
            content += self._format_law_info(law).replace('**', '').replace(':', ':')
        
        return content
    
    def _create_safe_filename(self, law: Dict, idx: int, 
                            folder_path: str, format_type: str) -> str:
        """안전한 파일명 생성"""
        law_name = (law.get('법령명한글') or law.get('행정규칙명') or 
                   law.get('자치법규명') or law.get('별표서식명') or 
                   law.get('별표명', 'N/A'))
        
        # 특수문자 제거
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', law_name)[:80]
        
        # 확장자 결정
        ext_map = {
            'markdown': 'md',
            'json': 'json',
            'text': 'txt'
        }
        ext = ext_map.get(format_type, 'txt')
        
        return f"{folder_path}/{idx:04d}_{safe_name}.{ext}"
    
    def _create_metadata(self, hierarchies: Dict[str, LawHierarchy]) -> Dict:
        """메타데이터 생성"""
        total_stats = {
            'law': 0, 'decree': 0, 'rule': 0, 'admin': 0,
            'local': 0, 'attachment': 0, 'delegated': 0
        }
        
        # 행정규칙 세부 통계
        admin_detail = {
            'notice': 0,    # 고시
            'directive': 0, # 훈령
            'regulation': 0, # 예규
            'guideline': 0, # 지침
            'rule': 0,      # 규정
            'etc': 0        # 기타
        }
        
        for hierarchy in hierarchies.values():
            stats = hierarchy.get_statistics()
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
            
            # 행정규칙 세부 집계
            admin_detail['notice'] += len(hierarchy.admin_rules.notice)
            admin_detail['directive'] += len(hierarchy.admin_rules.directive)
            admin_detail['regulation'] += len(hierarchy.admin_rules.regulation)
            admin_detail['guideline'] += len(hierarchy.admin_rules.guideline)
            admin_detail['rule'] += len(hierarchy.admin_rules.rule)
            admin_detail['etc'] += len(hierarchy.admin_rules.etc)
        
        return {
            'generated_at': datetime.now().isoformat(),
            'total_count': sum(total_stats.values()),
            'statistics': total_stats,
            'admin_detail': admin_detail,
            'laws': list(hierarchies.keys())
        }
    
    def _create_readme(self, hierarchies: Dict[str, LawHierarchy], 
                      folders: Dict[str, List]) -> str:
        """README 파일 생성"""
        readme = f"""# 법령 체계도 기반 통합 다운로드

생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}
검색 법령: {', '.join(hierarchies.keys())}

## 폴더 구조
- 01_법률: 기본 법률
- 02_시행령: 법률 시행령
- 03_시행규칙: 법률 시행규칙
- 04_행정규칙: 고시, 훈령, 예규, 지침, 규정
- 05_자치법규: 조례, 규칙
- 06_별표서식: 법령 및 행정규칙 별표서식
- 07_위임법령: 위임 법령
- 99_기타: 분류되지 않은 법령

## 통계
"""
        for folder, items in folders.items():
            if items:
                readme += f"- {folder}: {len(items)}개\n"
        
        # 행정규칙 세부 통계
        total_admin = sum(
            len(hierarchy.admin_rules.get_all()) 
            for hierarchy in hierarchies.values()
        )
        
        if total_admin > 0:
            readme += "\n## 행정규칙 세부\n"
            for hierarchy in hierarchies.values():
                if hierarchy.admin_rules.notice:
                    readme += f"- 고시: {len(hierarchy.admin_rules.notice)}개\n"
                    break
            for hierarchy in hierarchies.values():
                if hierarchy.admin_rules.directive:
                    readme += f"- 훈령: {len(hierarchy.admin_rules.directive)}개\n"
                    break
            for hierarchy in hierarchies.values():
                if hierarchy.admin_rules.regulation:
                    readme += f"- 예규: {len(hierarchy.admin_rules.regulation)}개\n"
                    break
        
        return readme

# ===========================
# 통합 인터페이스
# ===========================

class LawHierarchyManager:
    """법령 체계도 관리 통합 클래스"""
    
    def __init__(self, law_client: Any, law_searcher: Any = None):
        self.searcher = LawHierarchySearcher(law_client, law_searcher)
        self.exporter = LawHierarchyExporter()
        self.hierarchies = {}
    
    def search_law_hierarchy(self, law_info: Dict, 
                            config: SearchConfig = None) -> LawHierarchy:
        """법령 체계도 검색"""
        if config is None:
            config = SearchConfig()
        
        hierarchy = self.searcher.search_hierarchy(law_info, config)
        
        # 결과 저장
        law_name = law_info.get('법령명한글', 'Unknown')
        self.hierarchies[law_name] = hierarchy
        
        return hierarchy
    
    def export_markdown(self, include_content: bool = False) -> str:
        """마크다운으로 내보내기"""
        if not self.hierarchies:
            return "# 검색된 법령이 없습니다.\n"
        
        return self.exporter.export_to_markdown(self.hierarchies, include_content)
    
    def export_zip(self, format_type: str = "markdown") -> bytes:
        """ZIP 파일로 내보내기"""
        if not self.hierarchies:
            raise ValueError("검색된 법령이 없습니다.")
        
        return self.exporter.export_to_zip(self.hierarchies, format_type)
    
    def get_statistics(self) -> Dict:
        """전체 통계 반환"""
        total_stats = {
            'law': 0, 'decree': 0, 'rule': 0, 'admin': 0,
            'local': 0, 'attachment': 0, 'delegated': 0
        }
        
        # 행정규칙 세부 통계
        admin_detail = {
            'notice': 0,    # 고시
            'directive': 0, # 훈령
            'regulation': 0, # 예규
            'guideline': 0, # 지침
            'rule': 0,      # 규정
            'etc': 0        # 기타
        }
        
        for hierarchy in self.hierarchies.values():
            stats = hierarchy.get_statistics()
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
            
            # 행정규칙 세부 집계
            admin_detail['notice'] += len(hierarchy.admin_rules.notice)
            admin_detail['directive'] += len(hierarchy.admin_rules.directive)
            admin_detail['regulation'] += len(hierarchy.admin_rules.regulation)
            admin_detail['guideline'] += len(hierarchy.admin_rules.guideline)
            admin_detail['rule'] += len(hierarchy.admin_rules.rule)
            admin_detail['etc'] += len(hierarchy.admin_rules.etc)
        
        total_stats['total'] = sum(total_stats.values())
        total_stats['admin_detail'] = admin_detail
        
        return total_stats
    
    def clear(self):
        """저장된 체계도 초기화"""
        self.hierarchies.clear()

# 내보내기용 클래스들
__all__ = [
    'LawHierarchyManager',
    'LawHierarchySearcher', 
    'LawHierarchyExporter',
    'LawHierarchy',
    'AdminRules',
    'SearchConfig'
]
