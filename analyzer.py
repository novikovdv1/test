import json
import os
from dotenv import load_dotenv
import requests
import re

load_dotenv()

# Ключ можно хранить в .env, но для теста вставим явно
GROQ_API_KEY = os.getenv('GROQ_API_KEY') or "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def extract_json(text):
    # Берём подстроку между первой { и последней }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
    raise ValueError("Не удалось извлечь валидный JSON из ответа LLM:\n" + text)

def get_groq_response(prompt):
    import time
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4000
    }
    while True:
        response = requests.post(GROQ_API_URL, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        elif response.status_code == 429:
            # Попытаться извлечь время ожидания из текста ошибки
            try:
                resp_json = response.json()
                msg = resp_json.get("error", {}).get("message", "")
                wait_match = re.search(r"try again in ([0-9.]+)s", msg)
                if wait_match:
                    wait_time = float(wait_match.group(1)) + 1  # небольшой запас
                else:
                    wait_time = 20  # по умолчанию 20 секунд
            except Exception:
                wait_time = 20
            print(f"Rate limit reached. Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
        else:
            raise Exception(f"API Error: {response.status_code}, {response.text}")

def analyze_info_anchors(messages):
    dialogue_text = "\n".join([f"{msg['sender']}: {msg['text']}" for msg in messages])
    prompt = f"""Analyze the following dialogue between a manager and a client.\nDetermine which of these 5 key topics were discussed:\n1. Goals and KPIs - target KPIs (CPA/ROMI/leads), success criteria\n2. Current traffic sources - current advertising channels, previous partnerships\n3. Budget - planned budget, payment model, minimum deposits\n4. URLs/artifacts - landing page links, creatives, materials\n5. Partner expectations - what's important to the client, critical conditions\n\nDialogue:\n{dialogue_text}\n\nReturn only a valid JSON object with two lists:\n\"info_anchors_found\": topics that were discussed,\n\"info_anchors_missing\": topics that were not discussed.\nNo explanations, no text outside JSON, only JSON!"""
    response = get_groq_response(prompt)
    try:
        return json.loads(response)
    except Exception:
        return extract_json(response)

def analyze_objections(messages):
    dialogue_text = "\n".join([f"{msg['sender']}: {msg['text']}" for msg in messages])
    prompt = f"""Analyze the following dialogue between a manager and a client.\nFind client objections and evaluate how the manager handled them.\n\nObjection types:\n1. Financial limitations (triggers: \"expensive\", \"no budget\", \"high commission\")\n2. Unfavorable cooperation terms (triggers: \"terms don't work\", \"deposit too high\", \"want different model\")\n3. Loss to competitor (triggers: \"found another agency\", \"competitor better\", \"better terms\")\n\nFor each objection found, indicate:\n- objection_type\n- client_quote (brief quote)\n- manager_handled (true/false)\n- manager_actions (2-3 specific actions taken)\n\nDialogue:\n{dialogue_text}\n\nReturn only a valid JSON object with \"objections_found\" list containing found objections. No explanations, no text outside JSON, only JSON!"""
    response = get_groq_response(prompt)
    try:
        return json.loads(response)
    except Exception:
        return extract_json(response)

def analyze_dialogue(messages):
    info_anchors = analyze_info_anchors(messages)
    objections = analyze_objections(messages)
    return {
        "info_anchors_analysis": info_anchors,
        "objections_analysis": objections
    }

def main():
    with open('dialogues_sample.json', 'r', encoding='utf-8') as f:
        dialogues = json.load(f)
    results = []
    for dialogue in dialogues:
        print(f"\nAnalyzing dialogue {dialogue['dialogue_id']}...")
        analysis = analyze_dialogue(dialogue['messages'])
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        results.append({
            'dialogue_id': dialogue.get('dialogue_id'),
            'analysis': analysis
        })
    with open('result.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print('Анализ завершён. Результаты сохранены в result.json')

if __name__ == "__main__":
    main()