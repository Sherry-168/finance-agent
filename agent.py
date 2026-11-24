import requests
import json
import os
import re

def add_expense(user_input):
    """调用记账工作流"""
    url="https://api.dify.ai/v1/workflows/run"
    api_key=os.getenv("DIFY_API_KEY")
    if not api_key:
        raise ValueError("未设置记账工作流API密钥")
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"

    }
    payload={
        "inputs":{
            "user_input":user_input
        },
        "response_mode":"blocking",
        "user":"test_user"
    }
    try:
        response=requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result=response.json()
        ai_text = result.get("data", {}).get("outputs", {}).get("result", "")

        # 去掉模型的思考内容
        ai_text = re.sub(r"<think>.*?</think>", "", ai_text, flags=re.S).strip()

        # 提取 JSON 数组
        start = ai_text.find("[")
        end = ai_text.rfind("]")

        if start == -1 or end == -1:
            raise ValueError("没有找到有效的 JSON 数组")

        json_data = json.loads(ai_text[start:end + 1])

        return json.dumps(json_data, ensure_ascii=False)
    except requests.exceptions.RequestException as e:
        return {"error":str(e)}
    except ValueError as e:
        return {"error":str(e)}
if __name__ == "__main__":
    result = add_expense("昨天在瑞幸买饮料花了25块")
    print(result)
