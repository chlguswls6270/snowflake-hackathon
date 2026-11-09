import json
import os
import re
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Annotated
from app.security import BodyLimitMiddleware, require_access
from app.database import get_snowflake_session, get_db_names

app = FastAPI(
    title="Q-Dong (큐동) API",
    description="AI-powered neighborhood recommendation engine powered by Snowflake Cortex",
    version="1.0.0",
    dependencies=[Depends(require_access)]
)

app.add_middleware(BodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Snowflake session
session = None

@app.on_event("startup")
def startup_event():
    global session
    session = get_snowflake_session()
    print("Snowflake session initialized on startup.")

class PromptPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)

class DongPromptPayload(BaseModel):
    dong_name: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=8000)

class RentalInsightPayload(BaseModel):
    dong_name: str = Field(min_length=1, max_length=100)
    sgg_name: str = Field(min_length=1, max_length=100)
    sd_name: str = Field(min_length=1, max_length=100)

class RecommendationPayload(BaseModel):
    budget_max: int = Field(default=0, ge=0, le=100_000_000_000_000, strict=True)
    custom_keywords: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=50)
    consumption_preferences: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=50)
    transportation_preferences: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=50)
    scores_required: dict[str, bool] = Field(default_factory=dict, max_length=14)

@app.get("/")
def read_root():
    return {"message": "Welcome to SmartHome Matchmaker API"}

@app.post("/api/analyze-prompt")
def analyze_prompt(payload: PromptPayload):
    try:
        # 2. Define the System Instructions for the AI Data Extraction
        system_instructions = """You are a real estate and lifestyle data parser. 
        Analyze the user's natural language input and extract their preferences into a strict JSON format. 
        
        We need a few strictly formatted fields for database filtering, but we ALSO need you to extract ANY other lifestyle markers so we can match them flexibly against open databases.
        
        Your JSON must contain these exact keys:
        - "budget_max" (integer, carefully convert Korean won strings like "5억" to 500000000, "3억" to 300000000. If no budget is specified, return 0)
        - "household_type" (string, choose one from: "single", "newlywed", "family", "unknown")
        
        Now, for the flexible parameters:
        - "custom_keywords" (Array of Strings in KOREAN): Extract ALL specific spatial, physical, or environmental preferences they mention. For example: ["헬스장 근처", "자전거 타기 좋음", "고층", "한강 근처", "조용함"]. If none, return [].
        - "consumption_preferences" (Array of Strings in KOREAN): Extract ANY commercial or dining habits. If none, return [].
        - "transportation_preferences" (Array of Strings in KOREAN): Extract ANY transit requirements. If none, return [].
        
        CRITICAL - SPH CLASSIFICATION FLAGS:
        You MUST provide a "scores_required" object. Set the boolean to true ONLY if the user's input implies they care about this category.
        - "scores_required": {
            "cafe": boolean (true if they mention cafe, coffee, bakery, dessert),
            "food": boolean (true if they mention dining out, restaurants, delivery, food),
            "leisure": boolean (true if they mention parks, jogging, gym, running, quiet nature, walking, outdoors),
            "education": boolean (true if they mention children, schools, academies, raising kids, studying),
            "medical": boolean (true if they mention health, hospital, medical, clinic, sick),
            "shopping": boolean (true if they mention malls, shopping, department stores, emart, costco, large discount stores),
            "convenience": boolean (true if they mention convenience stores, small marts, simple groceries, living nearby stores),
            "beauty": boolean (true if they mention hair salons, beauty, cosmetics, nails, grooming),
            "entertain": boolean (true if they mention nightlife, drinking, pubs, bars, entertainment, young activities),
            "auto": boolean (true if they mention driving, car commute, gas station, auto repair),
            "interior": boolean (true if they mention self interior, furniture, home decor, living style),
            "mz_gen": boolean (true if they mention MZ generation, young people, 20s, 30s, trendy areas, energetic young neighborhood),
            "night": boolean (true if they mention late night safe, active at night, night owl, late work commute),
            "weekend": boolean (true if they mention weekend hot place, crowded on weekends, weekend out)
        }

        You must ONLY output valid JSON. Do not include markdown blocks like ```json or any conversational text."""

        sql_query = "SELECT snowflake.cortex.complete('mistral-large2', ?) as llm_response"
        result = session.sql(
            sql_query, params=[f"{system_instructions}\n\nUser Input: {payload.prompt}"]
        ).collect()
        llm_output = result[0]['LLM_RESPONSE']
        
        # 5. Clean up any potential markdown formatting the AI might have stubbornly included
        llm_output = llm_output.strip().removeprefix("```json").removesuffix("```").strip()
        
        # 6. Parse and return the JSON
        parsed_json = json.loads(llm_output)
        
        return {"status": "success", "parsed": parsed_json}
        
    except Exception:
        raise HTTPException(status_code=500, detail="요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.") from None

@app.post("/api/ask-dong")
def ask_dong(payload: DongPromptPayload):
    try:
        # System instructions injected dynamically with the focused neighborhood
        system_instructions = f"""You are an intuitive, extremely knowledgeable real estate and neighborhood lifestyle expert. 
        The user is asking a specific question about the neighborhood [{payload.dong_name}] in Seoul, South Korea.
        Answer their question concisely and helpfully based on your rich knowledge of this specific area's housing, transportation, demographics, and commercial infrastructure.
        Output ONLY the specific answer to their question in an engaging, natural Korean tone. Avoid unprompted markdown blocks."""
        
        sql_query = "SELECT snowflake.cortex.complete('mistral-large2', ?) as llm_response"
        result = session.sql(
            sql_query, params=[f"{system_instructions}\n\nUser Question: {payload.question}"]
        ).collect()
        llm_output = result[0]['LLM_RESPONSE']
        
        return {"status": "success", "answer": llm_output.strip()}
        
    except Exception:
        raise HTTPException(status_code=500, detail="요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.") from None

@app.post("/api/rental-insight")
def rental_insight(payload: RentalInsightPayload):
    """Query AJD rental data for a city/district, then use Cortex to generate a
    natural-language appliance rental recommendation for the specific dong."""
    try:
        ajd_db = get_db_names()["ajd"]

        # 1. Pull top rental categories for the province from AJD
        #    V06 has INSTALL_STATE (province) + RENTAL_MAIN_CATEGORY + RENTAL_SUB_CATEGORY
        rental_sql = f"""
            SELECT
                RENTAL_MAIN_CATEGORY,
                RENTAL_SUB_CATEGORY,
                SUM(CONTRACT_COUNT) AS TOTAL_CONTRACTS,
                ROUND(AVG(OPEN_CVR), 1) AS AVG_OPEN_CVR,
                ROUND(AVG(AVG_NET_SALES) / 12) AS AVG_MONTHLY_FEE
            FROM {ajd_db}.TELECOM_INSIGHTS.V06_RENTAL_CATEGORY_TRENDS
            WHERE INSTALL_STATE = ?
              AND RENTAL_MAIN_CATEGORY NOT IN ('미분류')
            GROUP BY RENTAL_MAIN_CATEGORY, RENTAL_SUB_CATEGORY
            ORDER BY TOTAL_CONTRACTS DESC
            LIMIT 8
        """
        rental_rows = session.sql(rental_sql, params=[payload.sd_name]).collect()

        if not rental_rows:
            # Fallback – no regional data, run pure Cortex
            rental_summary = "지역 렌탈 데이터를 찾을 수 없습니다."
        else:
            parts = []
            for r in rental_rows:
                monthly = int(r['AVG_MONTHLY_FEE']) if r['AVG_MONTHLY_FEE'] else 0
                parts.append(
                    f"- {r['RENTAL_MAIN_CATEGORY']} > {r['RENTAL_SUB_CATEGORY']}: "
                    f"계약 {r['TOTAL_CONTRACTS']}건, 월 평균 {monthly:,}원"
                )
            rental_summary = "\n".join(parts)

        # 2. Ask Cortex to synthesize the data into a personalized recommendation
        system_prompt = f"""당신은 이사 전문 컨설턴트입니다. 사용자가 서울 {payload.sgg_name} {payload.dong_name}으로 이사를 준비하고 있습니다.
아래는 해당 지역({payload.sd_name})의 실제 아정당(AJD) 렌탈 서비스 계약 데이터입니다:

{rental_summary}

이 데이터를 바탕으로, {payload.dong_name} 이사 준비생에게 어울리는 렌탈 가전 추천을 해주세요.
다음 형식으로 반드시 출력하세요 (JSON 없이 자연스러운 한국어로):
1. 해당 동네에서 가장 인기 있는 렌탈 품목 2~3개 추천 (이유 포함)
2. 월 예상 렌탈 비용 범위
3. 한 줄 요약 팁
짧고 실용적으로, 이모지를 적절히 활용해 친근하게 작성해주세요."""

        cortex_sql = "SELECT snowflake.cortex.complete('mistral-large2', ?) AS llm_response"
        result = session.sql(cortex_sql, params=[system_prompt]).collect()
        answer = result[0]['LLM_RESPONSE'].strip()

        return {"status": "success", "insight": answer}

    except Exception:
        raise HTTPException(status_code=500, detail="요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.") from None


@app.post("/api/recommend-apartments")
def recommend_apartments(payload: RecommendationPayload):
    payload = payload.model_dump()
    try:
        db_names = get_db_names()
        richgo_db = db_names["richgo"]
        sph_db = db_names["sph"]
        
        budget_max = payload.get("budget_max", 0)
        
        if not budget_max or budget_max == 0:
            budget_max = 500000000
            
        custom_keywords = payload.get("custom_keywords", [])
        consumption_prefs = payload.get("consumption_preferences", [])
        all_prefs = " ".join(custom_keywords + consumption_prefs).lower()
            
        # Real SPH x RICHGO DATA JOIN using BJD Code mapping
        # SPH DISTRICT_CODE is 8 digits. RICHGO BJD_CODE may be 8 or 10 digits.
        sql_query = f"""
            WITH SPH_AGG AS (
                SELECT 
                    LEFT(DISTRICT_CODE, 8) as DONG_CODE,
                    SUM(COFFEE_SALES) as TOTAL_COFFEE,
                    RANK() OVER(ORDER BY SUM(COFFEE_SALES) DESC) as RANK_COFFEE,
                    SUM(FOOD_SALES) as TOTAL_FOOD,
                    RANK() OVER(ORDER BY SUM(FOOD_SALES) DESC) as RANK_FOOD,
                    SUM(SPORTS_CULTURE_LEISURE_SALES) as TOTAL_LEISURE,
                    RANK() OVER(ORDER BY SUM(SPORTS_CULTURE_LEISURE_SALES) DESC) as RANK_LEISURE,
                    SUM(EDUCATION_ACADEMY_SALES) as TOTAL_EDU,
                    RANK() OVER(ORDER BY SUM(EDUCATION_ACADEMY_SALES) DESC) as RANK_EDU,
                    SUM(MEDICAL_SALES) as TOTAL_MED,
                    RANK() OVER(ORDER BY SUM(MEDICAL_SALES) DESC) as RANK_MED,
                    SUM(DEPARTMENT_STORE_SALES + LARGE_DISCOUNT_STORE_SALES) as TOTAL_SHOPPING,
                    RANK() OVER(ORDER BY SUM(DEPARTMENT_STORE_SALES + LARGE_DISCOUNT_STORE_SALES) DESC) as RANK_SHOPPING,
                    SUM(SMALL_RETAIL_STORE_SALES) as TOTAL_CONVENIENCE,
                    RANK() OVER(ORDER BY SUM(SMALL_RETAIL_STORE_SALES) DESC) as RANK_CONVENIENCE,
                    SUM(BEAUTY_SALES) as TOTAL_BEAUTY,
                    RANK() OVER(ORDER BY SUM(BEAUTY_SALES) DESC) as RANK_BEAUTY,
                    SUM(ENTERTAINMENT_SALES) as TOTAL_ENTERTAIN,
                    RANK() OVER(ORDER BY SUM(ENTERTAINMENT_SALES) DESC) as RANK_ENTERTAIN,
                    SUM(CAR_SERVICE_SUPPLIES_SALES + GAS_STATION_SALES) as TOTAL_AUTO,
                    RANK() OVER(ORDER BY SUM(CAR_SERVICE_SUPPLIES_SALES + GAS_STATION_SALES) DESC) as RANK_AUTO,
                    SUM(ELECTRONICS_FURNITURE_SALES) as TOTAL_INTERIOR,
                    RANK() OVER(ORDER BY SUM(ELECTRONICS_FURNITURE_SALES) DESC) as RANK_INTERIOR,
                    SUM(IFF(AGE_GROUP IN ('20', '25', '30', '35'), TOTAL_SALES, 0)) as TOTAL_MZ,
                    RANK() OVER(ORDER BY SUM(IFF(AGE_GROUP IN ('20', '25', '30', '35'), TOTAL_SALES, 0)) DESC) as RANK_MZ,
                    SUM(IFF(TIME_SLOT IN ('T21', 'T24'), TOTAL_SALES, 0)) as TOTAL_NIGHT,
                    RANK() OVER(ORDER BY SUM(IFF(TIME_SLOT IN ('T21', 'T24'), TOTAL_SALES, 0)) DESC) as RANK_NIGHT,
                    SUM(IFF(WEEKDAY_WEEKEND = 'H', TOTAL_SALES, 0)) as TOTAL_WEEKEND,
                    RANK() OVER(ORDER BY SUM(IFF(WEEKDAY_WEEKEND = 'H', TOTAL_SALES, 0)) DESC) as RANK_WEEKEND
                FROM {sph_db}.GRANDATA.CARD_SALES_INFO
                WHERE PROVINCE_CODE = '11' 
                GROUP BY LEFT(DISTRICT_CODE, 8)
            )
            SELECT 
                r.SD, 
                r.SGG, 
                r.EMD, 
                r.BJD_CODE,
                r.MEME_PRICE_PER_SUPPLY_PYEONG,
                r.TOTAL_HOUSEHOLDS,
                COALESCE(s.TOTAL_COFFEE, 0) as C_COFFEE,
                COALESCE(s.RANK_COFFEE, 999) as R_COFFEE,
                COALESCE(s.TOTAL_FOOD, 0) as C_FOOD,
                COALESCE(s.RANK_FOOD, 999) as R_FOOD,
                COALESCE(s.TOTAL_LEISURE, 0) as C_LEISURE,
                COALESCE(s.RANK_LEISURE, 999) as R_LEISURE,
                COALESCE(s.TOTAL_EDU, 0) as C_EDU,
                COALESCE(s.RANK_EDU, 999) as R_EDU,
                COALESCE(s.TOTAL_MED, 0) as C_MED,
                COALESCE(s.RANK_MED, 999) as R_MED,
                COALESCE(s.TOTAL_SHOPPING, 0) as C_SHOPPING,
                COALESCE(s.RANK_SHOPPING, 999) as R_SHOPPING,
                COALESCE(s.TOTAL_CONVENIENCE, 0) as C_CONVENIENCE,
                COALESCE(s.RANK_CONVENIENCE, 999) as R_CONVENIENCE,
                COALESCE(s.TOTAL_BEAUTY, 0) as C_BEAUTY,
                COALESCE(s.RANK_BEAUTY, 999) as R_BEAUTY,
                COALESCE(s.TOTAL_ENTERTAIN, 0) as C_ENTERTAIN,
                COALESCE(s.RANK_ENTERTAIN, 999) as R_ENTERTAIN,
                COALESCE(s.TOTAL_AUTO, 0) as C_AUTO,
                COALESCE(s.RANK_AUTO, 999) as R_AUTO,
                COALESCE(s.TOTAL_INTERIOR, 0) as C_INTERIOR,
                COALESCE(s.RANK_INTERIOR, 999) as R_INTERIOR,
                COALESCE(s.TOTAL_MZ, 0) as C_MZ,
                COALESCE(s.RANK_MZ, 999) as R_MZ,
                COALESCE(s.TOTAL_NIGHT, 0) as C_NIGHT,
                COALESCE(s.RANK_NIGHT, 999) as R_NIGHT,
                COALESCE(s.TOTAL_WEEKEND, 0) as C_WEEKEND,
                COALESCE(s.RANK_WEEKEND, 999) as R_WEEKEND
            FROM {richgo_db}.HACKATHON_2025Q2.REGION_APT_RICHGO_MARKET_PRICE_M_H r
            LEFT JOIN SPH_AGG s ON LEFT(r.BJD_CODE, 8) = s.DONG_CODE
            WHERE r.SD = '서울' 
              AND r.EMD IS NOT NULL
              AND r.EMD != ''
              AND r.MEME_PRICE_PER_SUPPLY_PYEONG > 0 
              AND (r.MEME_PRICE_PER_SUPPLY_PYEONG * 10000 * 20) <= ?
        """
        
        result = session.sql(sql_query, params=[budget_max]).collect()
        
        # Unpack all 14 lifestyle score flags from request
        scores_required = payload.get("scores_required", {})
        sr = scores_required if isinstance(scores_required, dict) else {}
        req_cafe     = sr.get("cafe", False)
        req_food     = sr.get("food", False)
        req_leisure  = sr.get("leisure", False)
        req_edu      = sr.get("education", False)
        req_med      = sr.get("medical", False)
        req_shop     = sr.get("shopping", False)
        req_conv     = sr.get("convenience", False)
        req_beauty   = sr.get("beauty", False)
        req_entertain = sr.get("entertain", False)
        req_auto     = sr.get("auto", False)
        req_interior = sr.get("interior", False)
        req_mz       = sr.get("mz_gen", False)
        req_night    = sr.get("night", False)
        req_weekend  = sr.get("weekend", False)

        recommendations = []

        # Count activated lifestyle tags and compute per-tag bonus ceiling
        # Base score is 65; max total bonus capped at 34 to keep scores 65–99
        num_req = sum([req_cafe, req_food, req_leisure, req_edu, req_med, req_shop,
                       req_conv, req_beauty, req_entertain, req_auto, req_interior,
                       req_mz, req_night, req_weekend])
        max_bonus_per_tag = 34.0 / num_req if num_req > 0 else 0

        # Rank-based decay: rank 1 → 100% bonus, rank 40+ → 0%
        def calc_bonus(rank):
            if rank == 999:
                return 0.0
            return max_bonus_per_tag * max(0.0, (40.0 - rank) / 39.0)

        for r in result:
            score = 65.0
            matched_tags = []

            # Unpack row values for readability
            c_coffee, r_coffee    = r['C_COFFEE'],    r['R_COFFEE']
            c_food,   r_food      = r['C_FOOD'],      r['R_FOOD']
            c_leisure, r_leisure  = r['C_LEISURE'],   r['R_LEISURE']
            c_edu,    r_edu       = r['C_EDU'],       r['R_EDU']
            c_med,    r_med       = r['C_MED'],       r['R_MED']
            c_shop,   r_shop      = r['C_SHOPPING'],  r['R_SHOPPING']
            c_conv,   r_conv      = r['C_CONVENIENCE'], r['R_CONVENIENCE']
            c_beauty, r_beauty    = r['C_BEAUTY'],    r['R_BEAUTY']
            c_entertain, r_entertain = r['C_ENTERTAIN'], r['R_ENTERTAIN']
            c_auto,   r_auto      = r['C_AUTO'],      r['R_AUTO']
            c_interior, r_interior = r['C_INTERIOR'], r['R_INTERIOR']
            c_mz,     r_mz        = r['C_MZ'],        r['R_MZ']
            c_night,  r_night     = r['C_NIGHT'],     r['R_NIGHT']
            c_weekend, r_weekend  = r['C_WEEKEND'],   r['R_WEEKEND']

            if req_cafe:
                score += calc_bonus(r_coffee)
                if r_coffee <= 10:
                    matched_tags.append({"icon": "☕️", "title": f"최상위 카페 상권 (서울 {r_coffee}위 동)", "desc": f"전체 매출이 약 {int(c_coffee/100000000)}억 원에 달하는 지역구 초밀집 핫플레이스입니다."})
                elif r_coffee <= 150:
                    matched_tags.append({"icon": "☕️", "title": f"우수 카페 상권 (서울 {r_coffee}위 동)", "desc": f"괜찮은 카페 인프라를 보유한 쾌적한 상권입니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                
            if req_food:
                score += calc_bonus(r_food)
                if r_food <= 10:
                    matched_tags.append({"icon": "🍽", "title": f"거대 외식 핫플레이스 (서울 {r_food}위 동)", "desc": f"대단위 식음료 결제가 일어나는 초거대 외식 상권입니다. (매출 {int(c_food/100000000)}억)"})
                elif r_food <= 150:
                    matched_tags.append({"icon": "🍽", "title": f"탄탄한 외식 상권 (서울 {r_food}위 동)", "desc": "선택지가 다양한 식당과 배달 인프라를 갖추었습니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_leisure:
                score += calc_bonus(r_leisure)
                if r_leisure <= 10:
                    matched_tags.append({"icon": "🌳", "title": f"산책/레저 인프라 특구 (서울 {r_leisure}위 동)", "desc": f"대규모 공원이나 문화 인프라가 갖추어져 만족도가 매우 높습니다."})
                elif r_leisure <= 150:
                    matched_tags.append({"icon": "🌳", "title": f"훌륭한 공원/레저 (서울 {r_leisure}위 동)", "desc": "훌륭한 산책로와 체육 시설 등이 인프라가 쾌적합니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_edu:
                score += calc_bonus(r_edu)
                if r_edu <= 10:
                    matched_tags.append({"icon": "📚", "title": f"프리미엄 최상위 학군 (서울 {r_edu}위 동)", "desc": f"학원 결제 매출이 {int(c_edu/100000000)}억 원에 달하는 압도적 명품 에듀타운입니다."})
                elif r_edu <= 150:
                    matched_tags.append({"icon": "📚", "title": f"탄탄한 교육 환경 (서울 {r_edu}위 동)", "desc": "교육열과 학원 분포 수준이 매우 우수한 지역입니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_med:
                score += calc_bonus(r_med)
                if r_med <= 10:
                    matched_tags.append({"icon": "🏥", "title": f"대형 의료 인프라 밀집 (서울 {r_med}위 동)", "desc": f"대형 병원 및 클리닉 밀집도가 선두급으로 안심할 수 있는 지역입니다."})
                elif r_med <= 150:
                    matched_tags.append({"icon": "🏥", "title": f"우수 의료 접근성 (서울 {r_med}위 동)", "desc": "생활형 의료 서비스와 병원 접근성이 쾌적합니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_shop:
                score += calc_bonus(r_shop)
                if r_shop <= 10:
                    matched_tags.append({"icon": "🛍️", "title": f"거대 쇼핑 메카 (서울 {r_shop}위 동)", "desc": f"백화점, 대형 복합 쇼핑몰 등 총 {int(c_shop/100000000)}억대 쇼핑 인프라가 있습니다."})
                elif r_shop <= 150:
                    matched_tags.append({"icon": "🛍️", "title": f"훌륭한 마트/쇼핑 (서울 {r_shop}위 동)", "desc": "장보기와 쇼핑 시설이 인접해 편리한 라이프가 가능합니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_conv:
                score += calc_bonus(r_conv)
                if r_conv <= 10:
                    matched_tags.append({"icon": "🏪", "title": f"하이퍼 슬세권 편의구역 (서울 {r_conv}위 동)", "desc": f"편의점/동네 마트 매출이 초당위권({int(c_conv/100000000)}억)인 밀집 편의 구역입니다."})
                elif r_conv <= 150:
                    matched_tags.append({"icon": "🏪", "title": f"편리하고 모던한 편의권 (서울 {r_conv}위 동)", "desc": "일상 편의 소매점과 마트가 거리에 빼곡하게 들어서 있습니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_beauty:
                score += calc_bonus(r_beauty)
                if r_beauty <= 10:
                    matched_tags.append({"icon": "💅", "title": f"초대형 뷰티/패션 거리 (서울 {r_beauty}위 동)", "desc": f"전체 매출이 약 {int(c_beauty/100000000)}억 원에 달하는 프리미엄 미용/패션 거리입니다."})
                elif r_beauty <= 150:
                    matched_tags.append({"icon": "💅", "title": f"우수 미용/뷰티 상권 (서울 {r_beauty}위 동)", "desc": "생활 밀착형 뷰티 시설이 수준급으로 구비되어 있습니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_entertain:
                score += calc_bonus(r_entertain)
                if r_entertain <= 10:
                    matched_tags.append({"icon": "🎉", "title": f"초대형 밤문화/유흥 특구 (서울 {r_entertain}위 동)", "desc": f"놀거리와 술자리가 끝없이 이어지는 최고 활성화 구역({int(c_entertain/100000000)}억대)입니다."})
                elif r_entertain <= 150:
                    matched_tags.append({"icon": "🎉", "title": f"우수 유흥/엔터테인 상권 (서울 {r_entertain}위 동)", "desc": "젊고 활기찬 분위기와 엔터테인먼트 인프라가 탁월합니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_auto:
                score += calc_bonus(r_auto)
                if r_auto <= 10:
                    matched_tags.append({"icon": "🚗", "title": f"오너드라이버 모빌리티 허브 (서울 {r_auto}위 동)", "desc": f"도로교통과 차량 정비/주유 소비가 가장 밀집된 허브급 구역({int(c_auto/100000000)}억)입니다."})
                elif r_auto <= 150:
                    matched_tags.append({"icon": "🚗", "title": f"탄탄한 차량 유지 인프라 (서울 {r_auto}위 동)", "desc": "모빌리티 관련 소비 거점이 매우 가까이에 유지되고 있습니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_interior:
                score += calc_bonus(r_interior)
                if r_interior <= 10:
                    matched_tags.append({"icon": "🛋️", "title": f"리빙/인테리어 핫플레이스 (서울 {r_interior}위 동)", "desc": f"가전/가구 소비가 집중된({int(c_interior/100000000)}억) 프리미엄 리빙 스팟입니다."})
                elif r_interior <= 150:
                    matched_tags.append({"icon": "🛋️", "title": f"우수 인테리어접근성 (서울 {r_interior}위 동)", "desc": "다양한 홈스타일 및 가구 쇼룸 등이 포진해 있습니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_mz:
                score += calc_bonus(r_mz)
                if r_mz <= 10:
                    matched_tags.append({"icon": "🔥", "title": f"2030 영 앤 트렌디 구역 (서울 {r_mz}위 동)", "desc": f"전체 매출 중 2030세대의 결제가 폭발적으로 점유하는 최정상급 인구통계 핫플입니다."})
                elif r_mz <= 150:
                    matched_tags.append({"icon": "🔥", "title": f"활기찬 MZ세대 활동지역 (서울 {r_mz}위 동)", "desc": "청년들의 소비 트렌드가 높게 집중되고 있는 활기찬 동네입니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_night:
                score += calc_bonus(r_night)
                if r_night <= 10:
                    matched_tags.append({"icon": "🌙", "title": f"불야성 심야 활성화 상권 (서울 {r_night}위 동)", "desc": f"21시~03시 심야시간 결제가 끊임없이 발생하는 가장 안전하고 빛나는 권역입니다."})
                elif r_night <= 150:
                    matched_tags.append({"icon": "🌙", "title": f"탄탄한 심야/야간 활동구역 (서울 {r_night}위 동)", "desc": "늦은 밤에도 문을 여는 상가와 안전한 유동인구 소비가 확보된 곳입니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                    
            if req_weekend:
                score += calc_bonus(r_weekend)
                if r_weekend <= 10:
                    matched_tags.append({"icon": "🎈", "title": f"주말 유동인구 폭발 구역 (서울 {r_weekend}위 동)", "desc": f"평일 대비 주말에 소비 인파가 정점에 이르는 서울시 톱클래스 휴일 위락 지역입니다."})
                elif r_weekend <= 150:
                    matched_tags.append({"icon": "🎈", "title": f"우수 주말 핫플레이스 (서울 {r_weekend}위 동)", "desc": "주말만 되면 사람들이 모여드는 활발한 주말 휴식 상권을 지녔습니다."})
                else:
                    matched_tags.append({"icon": "✅", "title": "맞춤 인프라 활성화 지역", "desc": "요청하신 라이프스타일에 부합하는 인프라 지점들이 상권 곳곳에 고루 배치되어 있습니다."})
                
            final_score = int(score)
            if final_score > 99: final_score = 99
            
            recommendations.append({
                "region": f"{r['SD']} {r['SGG']} {r['EMD']}",
                "emd": r['EMD'],
                "price_per_pyeong_krw": int(r['MEME_PRICE_PER_SUPPLY_PYEONG'] * 10000),
                "affordable_size_pyeong": round(budget_max / (r['MEME_PRICE_PER_SUPPLY_PYEONG'] * 10000), 1),
                "total_households": r['TOTAL_HOUSEHOLDS'],
                "lifestyle_score": final_score,
                "matched_tags": matched_tags,
            })

        # Re-sort by authentic data-driven score, then budget fit
        recommendations.sort(key=lambda x: (x['lifestyle_score'], x['affordable_size_pyeong']), reverse=True)
            
        # Collect unmapped or extra keywords to show the user we listened!
        extra_keywords = list(set(custom_keywords + payload.get("transportation_preferences", [])))
            
        # De-duplicate '당산동5가' style sub-dongs → treat as the same base dong
        seen = set()
        unique_recs = []
        for rec in recommendations:
            base_region = re.sub(r'\d+가$', '', str(rec['region']))
            if base_region not in seen:
                seen.add(base_region)
                unique_recs.append(rec)
            if len(unique_recs) == 50: break
            
        return {
            "status": "success", 
            "recommendations": unique_recs,
            "special_requests": extra_keywords
        }
        
    except Exception:
        raise HTTPException(status_code=500, detail="요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.") from None

