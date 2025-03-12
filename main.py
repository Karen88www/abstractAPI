import functions_framework
from dotenv import load_dotenv
import os
from elasticsearch import Elasticsearch
import aisuite as ai

load_dotenv()

es_username = os.getenv("es_username")
es_password = os.getenv("es_password")

es = Elasticsearch("https://media-vector.es.asia-east1.gcp.elastic-cloud.com", basic_auth=(es_username, es_password))


##### 欄位字串搜尋
### 使用 match 單一搜尋
def es_search_string_match(es, index, field_name, search_string, recall_size=10):
    query = { "size": recall_size, "query": { "match": { field_name: search_string } } }
    response = es.search(index=index, body=query)
    print(f"Found {response['hits']['total']['value']} documents")
    return response['hits']['hits']

# 使用aisuite生成摘要
def get_completion_aisuite(messages, model_type, temperature):
    """
    model_type的格式 : "openai:gpt-4o", "anthropic:claude-3-5-sonnet-20241022"
    api key直接用.env設定不需要經過config，命名要是 OPENAI_API_KEY, ANTHROPIC_API_KEY 
    """
    client = ai.Client()
    response = client.chat.completions.create(
        model=model_type,
        messages=messages,
        temperature=temperature
    )

    return response.choices[0].message.content

def summarize(input):
    # 先檢查input是不是空的
    if not input or input.strip() == "":
        return {
            "ResultData": "",
            "Result": "N",
            "Message": "未提供文章內容"
        }
    
    print("[INFO] AI生成新聞摘要...")

    prompt = """
    你是新聞編輯 任務 根據input的內容寫新聞摘要

    寫作要根據以下規範和限制：
    1. 格式要求：
    - 採用中央社新聞寫作風格：多用直述句，一行句子不宜過長。
    - 人名：頭銜+中文（原文）
    - 時間：年月日 時:分
    - 必須引用原文的消息來源 例如：某某某說、某某某表示

    2. 禁止事項：
    - 只能陳述事實，禁止評論議題
    - 禁止使用「對...而言」等籠統說法
    - 禁止添加原文未提及的資訊
    - 省略新聞稿頭 例如 中央社1日專電

    最後只要印摘要結果 純文字不需要markdown
    """

    if len(input) < 100:
        messages = [
            {"role": "system", "content": "你是新聞編輯 任務 根據input的內容寫50字新聞摘要"},
            {"role": "user", "content": prompt + input}
        ]
    
    else:
        messages = [
            {"role": "system", "content": "你是新聞編輯 任務 根據input的內容寫100字新聞摘要"},
            {"role": "user", "content": prompt + input}
        ]

    try:
        summary = get_completion_aisuite(messages, model_type="openai:gpt-4o", temperature=0)
        print("[INFO] 摘要生成完畢")
        print(summary)
        print("=" * 20)
        
        return {
            "ResultData": summary,
            "Result": "Y",
            "Message": ""
        }
    
    except Exception as e:
        return {
            "ResultData": "",
            "Result": "N",
            "Message": f"摘要生成失敗: {str(e)}"
        }
    

def find_exact_article_content(input_text: str) -> dict:
    try:
        # 使用 es_search_string_match 來搜尋匹配的文章
        results = es_search_string_match(es, "lab_mainsite_search", "content", input_text, recall_size=1)
        
        # 如果有找到匹配的文章
        if results:
            # 回傳第一個匹配文章的 whatHappen200 欄位
            summary = results[0]["_source"].get("whatHappen200", "")
            # print(">>> 從elastic search 回傳摘要：\n", summary)
            return {
                "ResultData": summary,
                "Result": "Y",
                "Message": ""
            }
        else:
            return {
                "ResultData": "",
                "Result": "N",
                "Message": "沒有找到匹配的文章"
            }
            
    except Exception as e:
        return {
            "ResultData": "",
            "Result": "N",
            "Message": f"從elastic search 回傳摘要失敗: {str(e)}"
        }

def GenerateSummary(input_text):
    # 先嘗試從 ES 找完全匹配的文章
    es_result = find_exact_article_content(input_text)
    # print(">>> es_result", es_result)
    
    if es_result["Result"] == "Y" and es_result["ResultData"]:
        print("[INFO] 成功從elastic search 回傳摘要")
        return es_result
    else:
        print("[INFO] elastic search 沒有找到完全匹配的文章")
        return summarize(input_text)

# cloud function post
@functions_framework.http
def main(request):
    # 設定 CORS headers
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': 'https://localbackend.cna.com.tw',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600' 
        }
        return ('', 204, headers)

    headers = {
        'Access-Control-Allow-Origin': 'https://localbackend.cna.com.tw'
    }

    # 檢查請求格式
    if not request.is_json:
        return ({
            "ResultData": "",
            "Result": "N",
            "Message": "請求必須是 JSON 格式"
        }, 400, headers)
    
    # 取得請求內容
    data = request.get_json()
    input_text = data.get('text')
    
    if not input_text:
        return ({
            "ResultData": "",
            "Result": "N",
            "Message": "缺少文章內容"
        }, 400, headers)

    # 使用摘要邏輯
    result = GenerateSummary(input_text)
    return (result, 200, headers)