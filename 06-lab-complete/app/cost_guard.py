import time
import logging
from fastapi import HTTPException
from app.config import settings

logger = logging.getLogger(__name__)

# Price definitions (GPT-4o-mini as reference)
PRICE_PER_1K_INPUT_TOKENS = 0.00015   # $0.15 / 1M input tokens
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006   # $0.60 / 1M output tokens

USE_REDIS = False
_redis = None

if settings.redis_url:
    try:
        import redis
        _redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0
        )
        _redis.ping()
        USE_REDIS = True
        logger.info("Cost guard connected to Redis.")
    except Exception as e:
        logger.error(f"Cost Guard Redis connection failed: {e}. Using in-memory fallback.")

# In-memory budget fallback
# Format: {user_id: {date: cost}}
_in_memory_daily_costs = {}
# Format: {user_id: {month: cost}}
_in_memory_monthly_costs = {}

def check_and_record_cost(user_id: str, input_tokens: int, output_tokens: int):
    """
    Check if the user is within their daily budget and $10/month budget.
    We track usage in Redis if available, otherwise fallback to in-memory dictionary.
    """
    cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
    
    today = time.strftime("%Y-%m-%d")
    current_month = time.strftime("%Y-%m")
    
    daily_budget = settings.daily_budget_usd
    monthly_budget = 10.0  # As specified in checklist: Cost guard ($10/month)

    if not USE_REDIS:
        # Check daily
        if user_id not in _in_memory_daily_costs:
            _in_memory_daily_costs[user_id] = {}
        if today not in _in_memory_daily_costs[user_id]:
            _in_memory_daily_costs[user_id] = {today: 0.0}
        
        # Check monthly
        if user_id not in _in_memory_monthly_costs:
            _in_memory_monthly_costs[user_id] = {}
        if current_month not in _in_memory_monthly_costs[user_id]:
            _in_memory_monthly_costs[user_id] = {current_month: 0.0}
            
        current_daily = _in_memory_daily_costs[user_id][today]
        current_monthly = _in_memory_monthly_costs[user_id][current_month]
        
        if current_daily + cost > daily_budget:
            raise HTTPException(
                status_code=402,
                detail=f"Daily budget of ${daily_budget} exceeded for user {user_id}."
            )
            
        if current_monthly + cost > monthly_budget:
            raise HTTPException(
                status_code=402,
                detail=f"Monthly budget of ${monthly_budget} exceeded for user {user_id}."
            )
            
        _in_memory_daily_costs[user_id][today] += cost
        _in_memory_monthly_costs[user_id][current_month] += cost
        return

    # Redis-based cost tracking
    daily_key = f"cost:{user_id}:daily:{today}"
    monthly_key = f"cost:{user_id}:monthly:{current_month}"
    global_daily_key = f"cost:global:daily:{today}"
    
    try:
        pipe = _redis.pipeline()
        pipe.get(daily_key)
        pipe.get(monthly_key)
        daily_spent, monthly_spent = pipe.execute()
        
        daily_spent = float(daily_spent) if daily_spent else 0.0
        monthly_spent = float(monthly_spent) if monthly_spent else 0.0
        
        if daily_spent + cost > daily_budget:
            raise HTTPException(
                status_code=402,
                detail=f"Daily budget of ${daily_budget} exceeded for user {user_id}."
            )
            
        if monthly_spent + cost > monthly_budget:
            raise HTTPException(
                status_code=402,
                detail=f"Monthly budget of ${monthly_budget} exceeded for user {user_id}."
            )
            
        # Update cost
        pipe = _redis.pipeline()
        pipe.incrbyfloat(daily_key, cost)
        pipe.expire(daily_key, 24 * 3600 * 2)  # expire in 2 days
        pipe.incrbyfloat(monthly_key, cost)
        pipe.expire(monthly_key, 24 * 3600 * 32)  # expire in 32 days
        
        # Increment global daily cost
        pipe.incrbyfloat(global_daily_key, cost)
        pipe.expire(global_daily_key, 24 * 3600 * 2)
        pipe.execute()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Redis cost guard error: {e}. Falling back to in-memory.")
        # Fallback to in-memory logic
        if user_id not in _in_memory_daily_costs:
            _in_memory_daily_costs[user_id] = {}
        if today not in _in_memory_daily_costs[user_id]:
            _in_memory_daily_costs[user_id] = {today: 0.0}
        
        if user_id not in _in_memory_monthly_costs:
            _in_memory_monthly_costs[user_id] = {}
        if current_month not in _in_memory_monthly_costs[user_id]:
            _in_memory_monthly_costs[user_id] = {current_month: 0.0}
            
        current_daily = _in_memory_daily_costs[user_id][today]
        current_monthly = _in_memory_monthly_costs[user_id][current_month]
        
        if current_daily + cost > daily_budget:
            raise HTTPException(
                status_code=402,
                detail=f"Daily budget of ${daily_budget} exceeded for user {user_id}."
            )
            
        if current_monthly + cost > monthly_budget:
            raise HTTPException(
                status_code=402,
                detail=f"Monthly budget of ${monthly_budget} exceeded for user {user_id}."
            )
            
        _in_memory_daily_costs[user_id][today] += cost
        _in_memory_monthly_costs[user_id][current_month] += cost
