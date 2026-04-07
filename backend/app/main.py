import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.database import get_snowflake_session

app = FastAPI(
    title="SmartHome Matchmaker API",
    description="Backend API for Real Estate & Rental Recommender",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
    prompt: str

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

        # 3. Formulate the Snowflake Cortex SQL Query 
        # We use $$ syntax to safely wrap the entire prompt containing single/double quotes.
        sql_query = f"""
            SELECT snowflake.cortex.complete(
                'mistral-large2',
                $$ {system_instructions} \n\n User Input: {payload.prompt} $$
            ) as llm_response
        """
        
        # 4. Execute the query on your Snowflake Warehouse
        result = session.sql(sql_query).collect()
        llm_output = result[0]['LLM_RESPONSE']
        
        # 5. Clean up any potential markdown formatting the AI might have stubbornly included
        llm_output = llm_output.strip().removeprefix("```json").removesuffix("```").strip()
        
        # 6. Parse and return the JSON
        parsed_json = json.loads(llm_output)
        
        return {"status": "success", "parsed": parsed_json}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import os

@app.post("/api/recommend-apartments")
def recommend_apartments(payload: dict):
    try:
        richgo_db = os.getenv("SNOWFLAKE_DB_RICHGO")
        sph_db = os.getenv("SNOWFLAKE_DB_SPH")
        
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
              AND r.MEME_PRICE_PER_SUPPLY_PYEONG > 0 
              AND (r.MEME_PRICE_PER_SUPPLY_PYEONG * 10000 * 20) <= {budget_max}
        """
        
        result = session.sql(sql_query).collect()
        
        scores_required = payload.get("scores_required", {})
        req_cafe = scores_required.get("cafe", False) if isinstance(scores_required, dict) else False
        req_food = scores_required.get("food", False) if isinstance(scores_required, dict) else False
        req_leisure = scores_required.get("leisure", False) if isinstance(scores_required, dict) else False
        req_edu = scores_required.get("education", False) if isinstance(scores_required, dict) else False
        req_med = scores_required.get("medical", False) if isinstance(scores_required, dict) else False
        req_shop = scores_required.get("shopping", False) if isinstance(scores_required, dict) else False
        req_conv = scores_required.get("convenience", False) if isinstance(scores_required, dict) else False
        req_beauty = scores_required.get("beauty", False) if isinstance(scores_required, dict) else False
        req_entertain = scores_required.get("entertain", False) if isinstance(scores_required, dict) else False
        req_auto = scores_required.get("auto", False) if isinstance(scores_required, dict) else False
        req_interior = scores_required.get("interior", False) if isinstance(scores_required, dict) else False
        req_mz = scores_required.get("mz_gen", False) if isinstance(scores_required, dict) else False
        req_night = scores_required.get("night", False) if isinstance(scores_required, dict) else False
        req_weekend = scores_required.get("weekend", False) if isinstance(scores_required, dict) else False
        
        recommendations = []
        
        # Count how many total lifestyle tags the user activated
        num_req = sum([req_cafe, req_food, req_leisure, req_edu, req_med, req_shop, req_conv, req_beauty, req_entertain, req_auto, req_interior, req_mz, req_night, req_weekend])
        # Maximum possible bonus is 34 points (65 to 99). Distribute this evenly among activated tags.
        max_bonus_per_tag = 34.0 / num_req if num_req > 0 else 0
        
        for r in result:
            score = 65.0 
            matched_tags = []
            
            c_coffee = r['C_COFFEE']
            r_coffee = r['R_COFFEE']
            c_food = r['C_FOOD']
            r_food = r['R_FOOD']
            c_leisure = r['C_LEISURE']
            r_leisure = r['R_LEISURE']
            c_edu = r['C_EDU']
            r_edu = r['R_EDU']
            c_med = r['C_MED']
            r_med = r['R_MED']
            c_shop = r['C_SHOPPING']
            r_shop = r['R_SHOPPING']
            c_conv = r['C_CONVENIENCE']
            r_conv = r['R_CONVENIENCE']
            c_beauty = r['C_BEAUTY']
            r_beauty = r['R_BEAUTY']
            c_entertain = r['C_ENTERTAIN']
            r_entertain = r['R_ENTERTAIN']
            c_auto = r['C_AUTO']
            r_auto = r['R_AUTO']
            c_interior = r['C_INTERIOR']
            r_interior = r['R_INTERIOR']
            c_mz = r['C_MZ']
            r_mz = r['R_MZ']
            c_night = r['C_NIGHT']
            r_night = r['R_NIGHT']
            c_weekend = r['C_WEEKEND']
            r_weekend = r['R_WEEKEND']
            
            # Precise mathematical decay based on Rank (1st = 100% bonus, 40th=0%)
            def calc_bonus(rank):
                if rank == 999: return 0.0
                return max_bonus_per_tag * max(0.0, (40.0 - rank) / 39.0)
            
            if req_cafe:
                score += calc_bonus(r_coffee)
                if r_coffee <= 10:
                    matched_tags.append({"icon": "☕️", "title": f"최상위 카페 상권 (서울 {r_coffee}위 동)", "desc": f"전체 매출이 약 {int(c_coffee/100000000)}억 원에 달하는 지역구 초밀집 핫플레이스입니다."})
                elif r_coffee <= 35:
                    matched_tags.append({"icon": "☕️", "title": f"우수 카페 상권 (서울 {r_coffee}위 동)", "desc": f"괜찮은 카페 인프라를 보유한 쾌적한 상권입니다."})
                
            if req_food:
                score += calc_bonus(r_food)
                if r_food <= 10:
                    matched_tags.append({"icon": "🍽", "title": f"거대 외식 핫플레이스 (서울 {r_food}위 동)", "desc": f"대단위 식음료 결제가 일어나는 초거대 외식 상권입니다. (매출 {int(c_food/100000000)}억)"})
                elif r_food <= 35:
                    matched_tags.append({"icon": "🍽", "title": f"탄탄한 외식 상권 (서울 {r_food}위 동)", "desc": "선택지가 다양한 식당과 배달 인프라를 갖추었습니다."})
                    
            if req_leisure:
                score += calc_bonus(r_leisure)
                if r_leisure <= 10:
                    matched_tags.append({"icon": "🌳", "title": f"산책/레저 인프라 특구 (서울 {r_leisure}위 동)", "desc": f"대규모 공원이나 문화 인프라가 갖추어져 만족도가 매우 높습니다."})
                elif r_leisure <= 35:
                    matched_tags.append({"icon": "🌳", "title": f"훌륭한 공원/레저 (서울 {r_leisure}위 동)", "desc": "훌륭한 산책로와 체육 시설 등이 인프라가 쾌적합니다."})
                    
            if req_edu:
                score += calc_bonus(r_edu)
                if r_edu <= 10:
                    matched_tags.append({"icon": "📚", "title": f"프리미엄 최상위 학군 (서울 {r_edu}위 동)", "desc": f"학원 결제 매출이 {int(c_edu/100000000)}억 원에 달하는 압도적 명품 에듀타운입니다."})
                elif r_edu <= 35:
                    matched_tags.append({"icon": "📚", "title": f"탄탄한 교육 환경 (서울 {r_edu}위 동)", "desc": "교육열과 학원 분포 수준이 매우 우수한 지역입니다."})
                    
            if req_med:
                score += calc_bonus(r_med)
                if r_med <= 10:
                    matched_tags.append({"icon": "🏥", "title": f"대형 의료 인프라 밀집 (서울 {r_med}위 동)", "desc": f"대형 병원 및 클리닉 밀집도가 선두급으로 안심할 수 있는 지역입니다."})
                elif r_med <= 35:
                    matched_tags.append({"icon": "🏥", "title": f"우수 의료 접근성 (서울 {r_med}위 동)", "desc": "생활형 의료 서비스와 병원 접근성이 쾌적합니다."})
                    
            if req_shop:
                score += calc_bonus(r_shop)
                if r_shop <= 10:
                    matched_tags.append({"icon": "🛍️", "title": f"거대 쇼핑 메카 (서울 {r_shop}위 동)", "desc": f"백화점, 대형 복합 쇼핑몰 등 총 {int(c_shop/100000000)}억대 쇼핑 인프라가 있습니다."})
                elif r_shop <= 35:
                    matched_tags.append({"icon": "🛍️", "title": f"훌륭한 마트/쇼핑 (서울 {r_shop}위 동)", "desc": "장보기와 쇼핑 시설이 인접해 편리한 라이프가 가능합니다."})
                    
            if req_conv:
                score += calc_bonus(r_conv)
                if r_conv <= 10:
                    matched_tags.append({"icon": "🏪", "title": f"하이퍼 슬세권 편의구역 (서울 {r_conv}위 동)", "desc": f"편의점/동네 마트 매출이 초당위권({int(c_conv/100000000)}억)인 밀집 편의 구역입니다."})
                elif r_conv <= 35:
                    matched_tags.append({"icon": "🏪", "title": f"편리하고 모던한 편의권 (서울 {r_conv}위 동)", "desc": "일상 편의 소매점과 마트가 거리에 빼곡하게 들어서 있습니다."})
                    
            if req_beauty:
                score += calc_bonus(r_beauty)
                if r_beauty <= 10:
                    matched_tags.append({"icon": "💅", "title": f"초대형 뷰티/패션 거리 (서울 {r_beauty}위 동)", "desc": f"전체 매출이 약 {int(c_beauty/100000000)}억 원에 달하는 프리미엄 미용/패션 거리입니다."})
                elif r_beauty <= 35:
                    matched_tags.append({"icon": "💅", "title": f"우수 미용/뷰티 상권 (서울 {r_beauty}위 동)", "desc": "생활 밀착형 뷰티 시설이 수준급으로 구비되어 있습니다."})
                    
            if req_entertain:
                score += calc_bonus(r_entertain)
                if r_entertain <= 10:
                    matched_tags.append({"icon": "🎉", "title": f"초대형 밤문화/유흥 특구 (서울 {r_entertain}위 동)", "desc": f"놀거리와 술자리가 끝없이 이어지는 최고 활성화 구역({int(c_entertain/100000000)}억대)입니다."})
                elif r_entertain <= 35:
                    matched_tags.append({"icon": "🎉", "title": f"우수 유흥/엔터테인 상권 (서울 {r_entertain}위 동)", "desc": "젊고 활기찬 분위기와 엔터테인먼트 인프라가 탁월합니다."})
                    
            if req_auto:
                score += calc_bonus(r_auto)
                if r_auto <= 10:
                    matched_tags.append({"icon": "🚗", "title": f"오너드라이버 모빌리티 허브 (서울 {r_auto}위 동)", "desc": f"도로교통과 차량 정비/주유 소비가 가장 밀집된 허브급 구역({int(c_auto/100000000)}억)입니다."})
                elif r_auto <= 35:
                    matched_tags.append({"icon": "🚗", "title": f"탄탄한 차량 유지 인프라 (서울 {r_auto}위 동)", "desc": "모빌리티 관련 소비 거점이 매우 가까이에 유지되고 있습니다."})
                    
            if req_interior:
                score += calc_bonus(r_interior)
                if r_interior <= 10:
                    matched_tags.append({"icon": "🛋️", "title": f"리빙/인테리어 핫플레이스 (서울 {r_interior}위 동)", "desc": f"가전/가구 소비가 집중된({int(c_interior/100000000)}억) 프리미엄 리빙 스팟입니다."})
                elif r_interior <= 35:
                    matched_tags.append({"icon": "🛋️", "title": f"우수 인테리어접근성 (서울 {r_interior}위 동)", "desc": "다양한 홈스타일 및 가구 쇼룸 등이 포진해 있습니다."})
                    
            if req_mz:
                score += calc_bonus(r_mz)
                if r_mz <= 10:
                    matched_tags.append({"icon": "🔥", "title": f"2030 영 앤 트렌디 구역 (서울 {r_mz}위 동)", "desc": f"전체 매출 중 2030세대의 결제가 폭발적으로 점유하는 최정상급 인구통계 핫플입니다."})
                elif r_mz <= 35:
                    matched_tags.append({"icon": "🔥", "title": f"활기찬 MZ세대 활동지역 (서울 {r_mz}위 동)", "desc": "청년들의 소비 트렌드가 높게 집중되고 있는 활기찬 동네입니다."})
                    
            if req_night:
                score += calc_bonus(r_night)
                if r_night <= 10:
                    matched_tags.append({"icon": "🌙", "title": f"불야성 심야 활성화 상권 (서울 {r_night}위 동)", "desc": f"21시~03시 심야시간 결제가 끊임없이 발생하는 가장 안전하고 빛나는 권역입니다."})
                elif r_night <= 35:
                    matched_tags.append({"icon": "🌙", "title": f"탄탄한 심야/야간 활동구역 (서울 {r_night}위 동)", "desc": "늦은 밤에도 문을 여는 상가와 안전한 유동인구 소비가 확보된 곳입니다."})
                    
            if req_weekend:
                score += calc_bonus(r_weekend)
                if r_weekend <= 10:
                    matched_tags.append({"icon": "🎈", "title": f"주말 유동인구 폭발 구역 (서울 {r_weekend}위 동)", "desc": f"평일 대비 주말에 소비 인파가 정점에 이르는 서울시 톱클래스 휴일 위락 지역입니다."})
                elif r_weekend <= 35:
                    matched_tags.append({"icon": "🎈", "title": f"우수 주말 핫플레이스 (서울 {r_weekend}위 동)", "desc": "주말만 되면 사람들이 모여드는 활발한 주말 휴식 상권을 지녔습니다."})
                
            final_score = int(score)
            if final_score > 99: final_score = 99
            
            recommendations.append({
                "region": f"{r['SD']} {r['SGG']} {r['EMD']}",
                "price_per_pyeong_krw": int(r['MEME_PRICE_PER_SUPPLY_PYEONG'] * 10000), 
                "affordable_size_pyeong": round(budget_max / (r['MEME_PRICE_PER_SUPPLY_PYEONG'] * 10000), 1),
                "total_households": r['TOTAL_HOUSEHOLDS'],
                "lifestyle_score": final_score,
                "matched_tags": matched_tags,
                "sph_raw": { "coffee": c_coffee, "food": c_food, "leisure": c_leisure } # Good for debug
            })
            
        # Re-sort by authentic data-driven score, then budget fit
        recommendations.sort(key=lambda x: (x['lifestyle_score'], x['affordable_size_pyeong']), reverse=True)
            
        # Collect unmapped or extra keywords to show the user we listened!
        extra_keywords = list(set(custom_keywords + payload.get("transportation_preferences", [])))
            
        # Return top 30 distinct areas for frontend pagination
        seen = set()
        unique_recs = []
        for rec in recommendations:
            if rec['region'] not in seen:
                seen.add(rec['region'])
                unique_recs.append(rec)
            if len(unique_recs) == 30: break
            
        return {
            "status": "success", 
            "recommendations": unique_recs,
            "special_requests": extra_keywords
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recommend-rentals")
def recommend_rentals(payload: dict):
    # TODO: Query AJD data from Snowflake
    return {"status": "success", "rentals": []}
