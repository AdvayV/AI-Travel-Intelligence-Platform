import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_travel_advisor_response(route_data: dict, user_question: str = None) -> str:
    '''
    AI Travel Advisor — analyzes route intelligence data and answers questions.
    Uses Qwen3-4B-Instruct via HuggingFace router (fast, free, good at structured reasoning).
    '''
    api_key = os.getenv('HUGGINGFACE_API_KEY')

    if not api_key:
        return 'Hugging Face API Key is not configured. Add HUGGINGFACE_API_KEY to backend/.env to enable live AI analysis.'

    try:
        client = OpenAI(
            base_url='https://router.huggingface.co/v1',
            api_key=api_key,
            timeout=4.0
        )

        daily_sched = route_data.get("daily_schedules", [])
        sched_context = ""
        if daily_sched:
            sched_context = "\n14-Day Calendar Price and Weather Schedule:\n"
            for s in daily_sched:
                t_max = s.get("temp_max_c")
                t_min = s.get("temp_min_c")
                temp_str = f", Temp: {t_min}°C to {t_max}°C" if t_max is not None and t_min is not None else ""
                sched_context += (
                    f"- Day {s['day_offset']} ({s['date']}): Weather: {s['weather_condition']}{temp_str} "
                    f"(Appeal: {s['weather_appeal']:.2f}), Price: ${s['price_usd']:.2f} (Surge: {s['surge_multiplier']:.2f}x)\n"
                )

        context = f'''Route: {route_data.get("origin")} to {route_data.get("destination")}
Opportunity score: {route_data.get("score")}/100
Tier: {route_data.get("tier")}
Final surge multiplier: {route_data.get("surge_multiplier")}x
Final price: ${route_data.get("current_price")}
Weather condition: {route_data.get("weather_label")}
Demand trend: {route_data.get("trend", "unknown")}
{sched_context}'''

        question = user_question or 'Summarize this route opportunity in 2 sentences for a travel agent.'

        completion = client.chat.completions.create(
            model='Qwen/Qwen3-4B-Instruct-2507',
            messages=[
                {'role': 'system', 'content': 'You are a travel pricing analyst. Be concise, factual, and reference the specific numbers given. Write in a natural, friendly paragraph format similar to ChatGPT or Gemini. Do not use markdown bolding (do not use double asterisks "**") or list bullet symbols in your response.'},
                {'role': 'user', 'content': f'{context}\n\nQuestion: {question}'}
            ],
            max_tokens=200,
            temperature=0.3,
            timeout=4.0
        )

        return completion.choices[0].message.content

    except Exception as e:
        print(f'HF Travel Advisor error: {e}')
        return f'AI advisor temporarily unavailable. Fallback summary: {route_data.get("origin")} to {route_data.get("destination")} is currently {route_data.get("tier", "WATCH")} tier with {route_data.get("surge_multiplier", 1.0)}x surge.'
