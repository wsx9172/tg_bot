import requests
from db import log_llm


def ask_llm(
    user_id,
    channel_id,
    bot_instance_id,
    provider_id,
    config,
    prompt,
):
    try:
        r = requests.post(
            config["api_url"],
            headers={"Authorization": f"Bearer {config['api_key']}"},
            json={
                "model": config["model"],
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )

        if r.status_code != 200:
            error = r.text[:200]
            return f"❌ API Error: {r.status_code} - {error}"

        try:
            data = r.json()
        except ValueError:
            return "❌ Invalid API response format"

        if "choices" not in data or not data["choices"]:
            return "❌ Empty response from API"

        result = data["choices"][0].get("message", {}).get("content", "")
        if not result:
            return "❌ No content in API response"

        log_llm(user_id, channel_id, bot_instance_id, provider_id, prompt, result)
        return result

    except requests.Timeout:
        return "❌ API request timeout"
    except Exception as e:
        return f"❌ LLM Error: {str(e)}"
