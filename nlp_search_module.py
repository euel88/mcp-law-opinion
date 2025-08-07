"""
nlp_search_module.py - 자연어 검색 프로세서
자연어 질문을 분석하여 최적의 검색 전략을 수립하고 실행합니다.
"""

from typing import Dict, List, Optional, Any, Tuple
import logging
import json
import re
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """검색 의도 분류"""
    LEGAL_INFO = "legal_info"          # 법률 정보 조회
    CASE_SEARCH = "case_search"        # 판례 검색
    PROCEDURE = "procedure"             # 절차 문의
    DEFINITION = "definition"           # 용어 정의
    CALCULATION = "calculation"         # 계산 (벌금, 기간 등)
    DOCUMENT = "document"               # 문서 작성
    RIGHTS = "rights"                   # 권리/의무 확인
    VIOLATION = "violation"             # 위반사항 확인
    CONTRACT = "contract"               # 계약 관련
    GENERAL = "general"                 # 일반 질문


@dataclass
class QueryAnalysis:
    """쿼리 분석 결과"""
    original_query: str
    intent: QueryIntent
    keywords: List[str]
    entities: Dict[str, Any]
    search_targets: List[str]
    time_context: Optional[str]
    location_context: Optional[str]
    confidence: float


class NaturalLanguageSearchProcessor:
    """자연어 검색 프로세서"""
    
    def __init__(self, ai_helper=None):
        self.ai_helper = ai_helper
        
        # 법률 분야별 키워드 사전
        self.legal_domains = {
            "노동": ["근로", "해고", "임금", "퇴직", "노동", "근무", "휴가", "연차", "야근", "잔업"],
            "부동산": ["매매", "임대", "전세", "월세", "부동산", "건물", "토지", "아파트", "주택"],
            "교통": ["사고", "음주", "운전", "교통", "자동차", "면허", "벌점", "과속", "신호위반"],
            "형사": ["폭행", "절도", "사기", "명예훼손", "모욕", "협박", "상해", "강도", "살인"],
            "가족": ["이혼", "양육", "상속", "유언", "혼인", "친권", "양육비", "재산분할"],
            "소비자": ["환불", "교환", "하자", "피해", "보상", "계약취소", "소비자", "AS"],
            "개인정보": ["개인정보", "정보유출", "프라이버시", "동의", "열람", "정정", "삭제"],
            "세금": ["세금", "소득세", "부가세", "재산세", "종합소득세", "연말정산", "세무"],
            "의료": ["의료", "진료", "수술", "의료사고", "보험", "건강보험", "산재"],
            "계약": ["계약서", "계약", "위약금", "해지", "해제", "취소", "무효", "조항"],
        }
        
        # 의도 분류 패턴
        self.intent_patterns = {
            QueryIntent.LEGAL_INFO: [
                r"어떻게|방법|절차|조건|요건|기준",
                r"무엇|뭐|뭘|어떤",
                r"가능|할 수 있|될까|되나요"
            ],
            QueryIntent.CASE_SEARCH: [
                r"판례|판결|사례|케이스",
                r"법원|대법원|헌재",
                r"어떻게 판단|어떤 판결"
            ],
            QueryIntent.PROCEDURE: [
                r"신청|접수|제출|신고",
                r"어디서|어디에|언제까지",
                r"서류|준비|필요한"
            ],
            QueryIntent.DEFINITION: [
                r"무엇인가요|뜻|의미|정의",
                r"란 무엇|이란|라는",
                r"개념|설명"
            ],
            QueryIntent.CALCULATION: [
                r"얼마|금액|비용|벌금",
                r"기간|기한|며칠|언제",
                r"계산|산정|산출"
            ],
            QueryIntent.RIGHTS: [
                r"권리|의무|책임",
                r"받을 수|청구|요구",
                r"해야|의무|필수"
            ],
            QueryIntent.VIOLATION: [
                r"위반|위법|불법|처벌",
                r"벌금|과태료|형량",
                r"고소|고발|신고"
            ],
            QueryIntent.CONTRACT: [
                r"계약|계약서|약정",
                r"조항|조건|내용",
                r"유효|무효|취소"
            ]
        }
        
        # 법령명 패턴
        self.law_patterns = [
            r"(\w+법)\s*(?:제)?(\d+조)?",
            r"(\w+법)\s*시행[령규칙]",
            r"(\w+에 관한 법률)",
            r"(\w+에 관한 특별법)"
        ]
        
        # 시간 표현 패턴
        self.time_patterns = [
            r"(\d{4}년)",
            r"(\d+개월)",
            r"(\d+일)",
            r"최근|현재|지금|요즘",
            r"작년|올해|내년",
            r"이전|이후|전|후"
        ]
    
    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        자연어 쿼리 분석
        
        Args:
            query: 사용자 입력 자연어
            
        Returns:
            쿼리 분석 결과
        """
        # 1. 의도 파악
        intent = self._classify_intent(query)
        
        # 2. 키워드 추출
        keywords = self._extract_keywords(query)
        
        # 3. 개체명 인식
        entities = self._extract_entities(query)
        
        # 4. 검색 대상 결정
        search_targets = self._determine_search_targets(query, intent, keywords)
        
        # 5. 시간/장소 컨텍스트
        time_context = self._extract_time_context(query)
        location_context = self._extract_location_context(query)
        
        # 6. 신뢰도 계산
        confidence = self._calculate_confidence(keywords, entities)
        
        return QueryAnalysis(
            original_query=query,
            intent=intent,
            keywords=keywords,
            entities=entities,
            search_targets=search_targets,
            time_context=time_context,
            location_context=location_context,
            confidence=confidence
        )
    
    def generate_search_queries(self, analysis: QueryAnalysis) -> List[Dict[str, Any]]:
        """
        분석 결과를 바탕으로 검색 쿼리 생성
        
        Args:
            analysis: 쿼리 분석 결과
            
        Returns:
            검색 쿼리 리스트
        """
        queries = []
        
        # 1. 핵심 키워드 조합
        if len(analysis.keywords) > 0:
            # 단일 키워드 검색
            for keyword in analysis.keywords[:3]:  # 상위 3개
                queries.append({
                    'query': keyword,
                    'type': 'keyword',
                    'priority': 1
                })
            
            # 복합 키워드 검색
            if len(analysis.keywords) >= 2:
                queries.append({
                    'query': ' '.join(analysis.keywords[:2]),
                    'type': 'compound',
                    'priority': 2
                })
        
        # 2. 법령명이 있으면 추가
        if 'laws' in analysis.entities:
            for law in analysis.entities['laws']:
                queries.append({
                    'query': law,
                    'type': 'law_name',
                    'priority': 1
                })
        
        # 3. 도메인별 확장 검색
        domain = self._identify_domain(analysis.keywords)
        if domain:
            domain_keywords = self.legal_domains.get(domain, [])
            for dk in domain_keywords[:2]:
                if dk not in analysis.keywords:
                    queries.append({
                        'query': dk,
                        'type': 'domain_expansion',
                        'priority': 3
                    })
        
        # 4. 시간 컨텍스트가 있으면 최신 자료 우선
        if analysis.time_context and '최근' in analysis.time_context:
            for q in queries:
                q['sort'] = 'date_desc'
        
        return queries
    
    def expand_query_with_ai(self, query: str) -> Dict[str, Any]:
        """
        AI를 사용한 쿼리 확장
        
        Args:
            query: 원본 쿼리
            
        Returns:
            확장된 검색 정보
        """
        if not self.ai_helper:
            return self._fallback_expansion(query)
        
        prompt = f"""
        다음 법률 질문을 분석하여 검색에 필요한 정보를 JSON 형식으로 추출하세요:
        
        질문: {query}
        
        다음 형식으로 응답하세요:
        {{
            "keywords": ["핵심키워드1", "핵심키워드2", ...],
            "law_names": ["관련법령명1", "관련법령명2", ...],
            "search_type": "law|case|all",
            "domain": "노동|부동산|교통|형사|가족|소비자|개인정보|세금|의료|계약|일반",
            "related_terms": ["관련용어1", "관련용어2", ...],
            "specific_articles": ["제N조", ...],
            "search_strategy": "검색 전략 설명"
        }}
        
        주의: 반드시 유효한 JSON만 출력하고, 다른 설명은 포함하지 마세요.
        """
        
        try:
            response = self.ai_helper.analyze_legal_text(prompt, {})
            
            # JSON 파싱
            # 마크다운 코드 블록 제거
            response = response.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(response)
            
            # 검증 및 정제
            result['keywords'] = result.get('keywords', [])[:5]
            result['law_names'] = result.get('law_names', [])[:3]
            result['related_terms'] = result.get('related_terms', [])[:5]
            
            logger.info(f"AI 쿼리 확장 성공: {result}")
            return result
            
        except Exception as e:
            logger.error(f"AI 쿼리 확장 실패: {e}")
            return self._fallback_expansion(query)
    
    def _classify_intent(self, query: str) -> QueryIntent:
        """의도 분류"""
        query_lower = query.lower()
        
        # 패턴 매칭으로 의도 파악
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent
        
        return QueryIntent.GENERAL
    
    def _extract_keywords(self, query: str) -> List[str]:
        """키워드 추출"""
        keywords = []
        
        # 1. 법률 도메인 키워드 추출
        for domain, domain_keywords in self.legal_domains.items():
            for keyword in domain_keywords:
                if keyword in query:
                    keywords.append(keyword)
        
        # 2. 명사 추출 (간단한 규칙 기반)
        # 조사 제거
        particles = ['은', '는', '이', '가', '을', '를', '에', '에서', '에게', '한테', '와', '과', '하고', '이나', '거나', '든지']
        words = query.split()
        for word in words:
            for particle in particles:
                if word.endswith(particle):
                    word = word[:-len(particle)]
            
            # 2글자 이상의 단어만
            if len(word) >= 2 and word not in keywords:
                keywords.append(word)
        
        # 3. 중복 제거 및 우선순위 정렬
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords[:10]  # 상위 10개만
    
    def _extract_entities(self, query: str) -> Dict[str, Any]:
        """개체명 인식"""
        entities = {}
        
        # 1. 법령명 추출
        laws = []
        for pattern in self.law_patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                if isinstance(match, tuple):
                    law_name = match[0] if match[0] else match[1] if len(match) > 1 else ''
                else:
                    law_name = match
                if law_name:
                    laws.append(law_name)
        
        if laws:
            entities['laws'] = laws
        
        # 2. 금액 추출
        money_pattern = r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:원|만원|억원)'
        money_matches = re.findall(money_pattern, query)
        if money_matches:
            entities['amounts'] = money_matches
        
        # 3. 날짜 추출
        date_pattern = r'(\d{4})[년\.\-/](\d{1,2})[월\.\-/](\d{1,2})[일]?'
        date_matches = re.findall(date_pattern, query)
        if date_matches:
            entities['dates'] = ['-'.join(match) for match in date_matches]
        
        # 4. 조문 추출
        article_pattern = r'제(\d+)조(?:의(\d+))?'
        article_matches = re.findall(article_pattern, query)
        if article_matches:
            entities['articles'] = article_matches
        
        return entities
    
    def _determine_search_targets(self, query: str, intent: QueryIntent, keywords: List[str]) -> List[str]:
        """검색 대상 결정"""
        targets = []
        
        # 의도별 기본 검색 대상
        intent_targets = {
            QueryIntent.CASE_SEARCH: ['cases', 'constitutional', 'interpretations'],
            QueryIntent.PROCEDURE: ['laws', 'admin_rules', 'interpretations'],
            QueryIntent.DEFINITION: ['terms', 'laws'],
            QueryIntent.VIOLATION: ['laws', 'cases', 'tribunals'],
            QueryIntent.CONTRACT: ['laws', 'cases', 'interpretations'],
            QueryIntent.RIGHTS: ['laws', 'interpretations', 'cases'],
        }
        
        targets.extend(intent_targets.get(intent, ['laws', 'cases']))
        
        # 키워드 기반 추가
        if any(kw in ['판례', '판결', '법원'] for kw in keywords):
            targets.append('cases')
        if any(kw in ['헌법', '헌재', '위헌'] for kw in keywords):
            targets.append('constitutional')
        if any(kw in ['해석', '유권해석'] for kw in keywords):
            targets.append('interpretations')
        if any(kw in ['위원회', '결정'] for kw in keywords):
            targets.append('committees')
        if any(kw in ['조약', '협정'] for kw in keywords):
            targets.append('treaties')
        if any(kw in ['행정규칙', '훈령', '예규', '고시'] for kw in keywords):
            targets.append('admin_rules')
        if any(kw in ['조례', '규칙', '자치법규'] for kw in keywords):
            targets.append('local_laws')
        
        # 중복 제거
        return list(set(targets))
    
    def _extract_time_context(self, query: str) -> Optional[str]:
        """시간 컨텍스트 추출"""
        for pattern in self.time_patterns:
            match = re.search(pattern, query)
            if match:
                return match.group(0)
        return None
    
    def _extract_location_context(self, query: str) -> Optional[str]:
        """장소 컨텍스트 추출"""
        location_keywords = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
                           '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주']
        
        for location in location_keywords:
            if location in query:
                return location
        return None
    
    def _calculate_confidence(self, keywords: List[str], entities: Dict) -> float:
        """신뢰도 계산"""
        confidence = 0.5  # 기본값
        
        # 키워드가 많을수록 신뢰도 증가
        if len(keywords) > 0:
            confidence += min(len(keywords) * 0.05, 0.2)
        
        # 개체명이 인식되면 신뢰도 증가
        if entities:
            confidence += len(entities) * 0.1
        
        # 법령명이 명확하면 신뢰도 크게 증가
        if 'laws' in entities:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _identify_domain(self, keywords: List[str]) -> Optional[str]:
        """법률 도메인 식별"""
        domain_scores = {}
        
        for domain, domain_keywords in self.legal_domains.items():
            score = sum(1 for kw in keywords if kw in domain_keywords)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        return None
    
    def _fallback_expansion(self, query: str) -> Dict[str, Any]:
        """AI 없이 쿼리 확장 (폴백)"""
        analysis = self.analyze_query(query)
        
        return {
            'keywords': analysis.keywords,
            'law_names': analysis.entities.get('laws', []),
            'search_type': 'all',
            'domain': self._identify_domain(analysis.keywords) or '일반',
            'related_terms': [],
            'specific_articles': [f"제{a[0]}조" for a in analysis.entities.get('articles', [])],
            'search_strategy': '키워드 기반 검색'
        }
    
    def optimize_search_strategy(self, query: str, context: Dict = None) -> Dict[str, Any]:
        """
        최적의 검색 전략 수립
        
        Args:
            query: 사용자 쿼리
            context: 추가 컨텍스트
            
        Returns:
            검색 전략
        """
        # 1. 쿼리 분석
        analysis = self.analyze_query(query)
        
        # 2. AI 확장 (가능한 경우)
        ai_expansion = self.expand_query_with_ai(query)
        
        # 3. 검색 쿼리 생성
        search_queries = self.generate_search_queries(analysis)
        
        # 4. 전략 수립
        strategy = {
            'original_query': query,
            'analysis': {
                'intent': analysis.intent.value,
                'confidence': analysis.confidence,
                'keywords': analysis.keywords,
                'entities': analysis.entities,
                'domain': self._identify_domain(analysis.keywords)
            },
            'ai_expansion': ai_expansion,
            'search_queries': search_queries,
            'search_targets': analysis.search_targets,
            'search_params': {
                'sort': 'relevance' if analysis.confidence > 0.7 else 'date_desc',
                'limit_per_type': 10 if len(analysis.keywords) > 2 else 20,
                'search_in_content': len(query) > 20  # 긴 질문은 본문 검색
            },
            'execution_plan': self._create_execution_plan(analysis, ai_expansion)
        }
        
        return strategy
    
    def _create_execution_plan(self, analysis: QueryAnalysis, ai_expansion: Dict) -> List[Dict]:
        """검색 실행 계획 생성"""
        plan = []
        
        # 1단계: 핵심 키워드로 법령 검색
        if analysis.keywords:
            plan.append({
                'step': 1,
                'action': 'search_laws',
                'query': ' '.join(analysis.keywords[:2]),
                'reason': '관련 법령 우선 검색'
            })
        
        # 2단계: 판례 검색 (필요시)
        if QueryIntent.CASE_SEARCH in [analysis.intent] or 'cases' in analysis.search_targets:
            plan.append({
                'step': 2,
                'action': 'search_cases',
                'query': ai_expansion.get('keywords', analysis.keywords)[0] if ai_expansion.get('keywords') else analysis.keywords[0],
                'reason': '관련 판례 검색'
            })
        
        # 3단계: 해석례/위원회 결정 검색
        if len(plan) < 3 and analysis.confidence < 0.8:
            plan.append({
                'step': 3,
                'action': 'search_interpretations',
                'query': analysis.original_query[:50],
                'reason': '추가 해석 자료 검색'
            })
        
        return plan


class SmartSearchOrchestrator:
    """스마트 검색 오케스트레이터"""
    
    def __init__(self, nlp_processor, api_clients):
        self.nlp_processor = nlp_processor
        self.api_clients = api_clients
        self.search_history = []
    
    def execute_smart_search(self, query: str) -> Dict[str, Any]:
        """
        스마트 검색 실행
        
        Args:
            query: 자연어 쿼리
            
        Returns:
            통합 검색 결과
        """
        logger.info(f"스마트 검색 시작: {query}")
        
        # 1. 검색 전략 수립
        strategy = self.nlp_processor.optimize_search_strategy(query)
        
        # 2. 검색 실행
        results = {
            'query': query,
            'strategy': strategy,
            'search_results': {},
            'total_count': 0,
            'execution_time': 0
        }
        
        start_time = datetime.now()
        
        # 실행 계획에 따라 검색
        for step in strategy['execution_plan']:
            step_results = self._execute_search_step(step, strategy)
            if step_results:
                results['search_results'][step['action']] = step_results
                results['total_count'] += step_results.get('count', 0)
        
        # 3. 결과 통합 및 순위 조정
        results['ranked_results'] = self._rank_results(results['search_results'], strategy)
        
        # 4. 실행 시간 기록
        results['execution_time'] = (datetime.now() - start_time).total_seconds()
        
        # 5. 검색 이력 저장
        self.search_history.append({
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'total_count': results['total_count'],
            'strategy': strategy['analysis']['intent']
        })
        
        logger.info(f"스마트 검색 완료: {results['total_count']}건, {results['execution_time']:.2f}초")
        
        return results
    
    def _execute_search_step(self, step: Dict, strategy: Dict) -> Optional[Dict]:
        """검색 단계 실행"""
        try:
            action = step['action']
            query = step['query']
            
            if action == 'search_laws' and self.api_clients.get('law_searcher'):
                result = self.api_clients['law_searcher'].search_laws(
                    query=query,
                    display=strategy['search_params']['limit_per_type']
                )
                return {
                    'items': result.get('results', []),
                    'count': result.get('totalCnt', 0)
                }
            
            elif action == 'search_cases' and self.api_clients.get('case_searcher'):
                result = self.api_clients['case_searcher'].search_court_cases(
                    query=query,
                    display=strategy['search_params']['limit_per_type'],
                    search_type=2 if strategy['search_params']['search_in_content'] else 1
                )
                return {
                    'items': result.get('cases', []),
                    'count': result.get('total_count', 0)
                }
            
            elif action == 'search_interpretations' and self.api_clients.get('case_searcher'):
                result = self.api_clients['case_searcher'].search_legal_interpretations(
                    query=query,
                    display=strategy['search_params']['limit_per_type']
                )
                return {
                    'items': result.get('interpretations', []),
                    'count': result.get('total_count', 0)
                }
            
        except Exception as e:
            logger.error(f"검색 단계 실행 오류: {e}")
        
        return None
    
    def _rank_results(self, search_results: Dict, strategy: Dict) -> List[Dict]:
        """결과 순위 조정"""
        ranked = []
        
        # 각 결과에 점수 부여
        for result_type, results in search_results.items():
            for item in results.get('items', []):
                score = self._calculate_relevance_score(item, strategy)
                ranked.append({
                    'type': result_type,
                    'item': item,
                    'score': score
                })
        
        # 점수순 정렬
        ranked.sort(key=lambda x: x['score'], reverse=True)
        
        return ranked[:50]  # 상위 50개만 반환
    
    def _calculate_relevance_score(self, item: Dict, strategy: Dict) -> float:
        """관련성 점수 계산"""
        score = 0.0
        keywords = strategy['analysis']['keywords']
        
        # 제목에 키워드 포함 여부
        title = str(item.get('title', item.get('법령명한글', item.get('사건명', ''))))
        for keyword in keywords:
            if keyword in title:
                score += 10
        
        # 최신성 (날짜가 있으면)
        date_field = item.get('date', item.get('공포일자', item.get('선고일자', '')))
        if date_field:
            try:
                # 최근 1년 이내면 가산점
                if '2024' in str(date_field) or '2025' in str(date_field):
                    score += 5
            except:
                pass
        
        # 의도와의 일치도
        if strategy['analysis']['intent'] == 'case_search' and 'case' in str(item):
            score += 3
        
        return score


# 사용 예시
if __name__ == "__main__":
    print("=== 자연어 검색 프로세서 테스트 ===\n")
    
    # 프로세서 초기화
    processor = NaturalLanguageSearchProcessor()
    
    # 테스트 쿼리들
    test_queries = [
        "회사에서 갑자기 해고 통보를 받았는데 어떻게 대응해야 하나요?",
        "음주운전으로 면허 취소되면 언제 다시 취득할 수 있나요?",
        "전세 계약 만료 시 보증금을 못 받으면 어떻게 해야 하나요?",
        "개인정보 유출로 인한 피해 보상은 어떻게 받나요?",
        "근로기준법 제23조의 부당해고 요건이 뭔가요?"
    ]
    
    for query in test_queries:
        print(f"\n질문: {query}")
        print("-" * 50)
        
        # 쿼리 분석
        analysis = processor.analyze_query(query)
        
        print(f"의도: {analysis.intent.value}")
        print(f"키워드: {analysis.keywords[:5]}")
        print(f"검색 대상: {analysis.search_targets}")
        print(f"신뢰도: {analysis.confidence:.2f}")
        
        # 검색 쿼리 생성
        search_queries = processor.generate_search_queries(analysis)
        print(f"\n생성된 검색 쿼리:")
        for sq in search_queries[:3]:
            print(f"  - '{sq['query']}' (유형: {sq['type']}, 우선순위: {sq['priority']})")
        
        # 검색 전략
        strategy = processor.optimize_search_strategy(query)
        print(f"\n실행 계획:")
        for step in strategy['execution_plan']:
            print(f"  {step['step']}. {step['action']}: '{step['query'][:30]}...' ({step['reason']})")
    
    print("\n테스트 완료!")
