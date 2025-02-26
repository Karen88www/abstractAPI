# from utils.config import *
import json
import os
from elasticsearch import Elasticsearch
from typing import List, Dict, Any, Optional, Union
from dotenv import load_dotenv

load_dotenv()

es_username = os.getenv("es_username")
es_password = os.getenv("es_password")

# pattern_today = f"{datetime.today().strftime('%Y-%m-%d')}"
es = Elasticsearch("https://media-vector.es.asia-east1.gcp.elastic-cloud.com", basic_auth=(es_username, es_password))
# res = es_search_certain_date(es, index="lab_mainsite_search", date_column_name="dt", date=pattern_today)


##### 原生 query 搜尋，可自定義 query
### query 搜尋 (自定義 query)
def es_search_queryJSON(es, index, query):
    response = es.search(index=index, body=query)
    print(f"Found {response['hits']['total']['value']} documents")
    return response['hits']['hits']



##### 欄位字串搜尋
### 使用 match 單一搜尋
def es_search_string_match(es, index, field_name, search_string, recall_size=10):
    query = { "size": recall_size, "query": { "match": { field_name: search_string } } }
    response = es.search(index=index, body=query)
    print(f"Found {response['hits']['total']['value']} documents")
    return response['hits']['hits']




### 使用 term 單一搜尋
def es_search_string_term(es, index, field_name, search_string, recall_size=10):
    query = { "size": recall_size, "query": { "term": { field_name: search_string } } }
    response = es.search(index=index, body=query)
    print(f"Found {response['hits']['total']['value']} documents")
    return response['hits']['hits']



##### 顯示日期
### 使用特定日期搜尋

def es_search_certain_date(es, index, date_column_name, date):
    query = {"query":{"bool":{"must":[{"range":{date_column_name:{"gte":date,"lte":date}}}],"must_not":[],"should":[]}},"from":0,"size":1000,"sort":[],"aggs":{}}
    response = es.search(index=index, body=query)
    print(f"Found {response['hits']['total']['value']} documents")
    return response['hits']['hits']




### 使用日期範圍搜尋
def es_search_date_range(es, index, date_column_name, start_date, end_date): # 前後皆含
    query = {"query":{"bool":{"must":[{"range":{date_column_name:{"gte":start_date,"lte":end_date}}}],"must_not":[],"should":[]}},"from":0,"size":1000,"sort":[],"aggs":{}}
    response = es.search(index=index, body=query)
    print(f"Found {response['hits']['total']['value']} documents")
    return response['hits']['hits']



##### Vector Search
### 純粹向量搜尋
def es_vector_search(es, index, embedding_column_name, input_embedding, recall_size=10):
    query = {
        "size": recall_size,
        "query": {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "source": f"cosineSimilarity(params.query_vector, '{embedding_column_name}') + 1.0",
                    "params": {"query_vector": input_embedding}
                }
            }
        }
    }
    response = es.search(index=index, body=query)
    return response['hits']['hits']


### 加入1個query條件篩選。
def es_vector_search_with_queryString(es, index, embedding_column_name, input_embedding, query_column_name, filter_query, recall_size=10):
    query = { "size": recall_size,  "query": { "bool": { "must": [ { "term": { query_column_name: filter_query } }, { "script_score": { "query": {"match_all": {}}, "script": { "source": f"cosineSimilarity(params.query_vector, '{embedding_column_name}') + 1.0", "params": { "query_vector": input_embedding } } } } ] } } }
    response = es.search(index=index, body=query)
    return response['hits']['hits']


### 加入多個query條件篩選。
def es_advanced_vector_search(
    es,
    index: str,
    embedding_column_name: str,
    input_embedding,
    filters: List[Dict[str, Any]],
    recall_size: int = 10
) -> List[Dict[str, Any]]:
    """
    執行向量搜尋，並結合多種過濾條件，支持同一欄位多個match_phrase query (OR 條件)
    :param filters: 過濾條件列表，每個條件是一個字典，格式如下：
                    {
                        "type": "term"/"match"/"match_phrase"/"range",
                        "field": "欄位名稱",
                        "value": 過濾值 或 [過濾值1, 過濾值2, ...]
                    }
    :param recall_size: 返回的結果數量
    :return: 匹配的文檔列表
    """
    must_conditions = []
    should_conditions = []

    # 處理所有過濾條件
    for filter_condition in filters:
        filter_type = filter_condition["type"]
        field = filter_condition["field"]
        value = filter_condition["value"]

        if filter_type == "term":
            if isinstance(value, list):
                must_conditions.append({"terms": {field: value}})
            else:
                must_conditions.append({"term": {field: value}})
        elif filter_type == "match" or filter_type == "match_phrase":
            # 如果是多個值，則應將它們加到 should_conditions 中，作為 OR 條件
            if isinstance(value, list):
                for v in value:
                    should_conditions.append({filter_type: {field: v}})
            else:
                should_conditions.append({filter_type: {field: value}})
        elif filter_type == "range":
            must_conditions.append({"range": {field: value}})
        else:
            must_conditions.append({filter_type: {field: value}})
            # raise ValueError(f"不支持的過濾類型: {filter_type}")

    # 構建完整的查詢
    query = {
        "size": recall_size,
        "query": {
            "script_score": {
                "query": {
                    "bool": {
                        "must": must_conditions,
                        "should": should_conditions,
                        "minimum_should_match": 1 if should_conditions else 0  # 至少匹配一個 should 條件
                    }
                },
                "script": {
                    "source": f"cosineSimilarity(params.query_vector, '{embedding_column_name}') + 1.0",
                    "params": {"query_vector": input_embedding}
                }
            }
        }
    }

    # 執行搜尋
    response = es.search(index=index, body=query)
    return response['hits']['hits']
#  filters = [
#     {"type": "term", "field": "image_type.raw", "value": "其他照片"},
#     {"type": "match", "field": "exp", "value": "降雨"}#,
#     {"type": "range", "field": "price", "value": {"gte": 100, "lte": 500}}
# ]
# results = es_advanced_vector_search(es, "lab_photo_search", "embedding_desc", input_embedding, filters, recall_size=20)


### query加權搜尋
def es_keyword_weighted_search(
    es,
    index: str,
    embedding_column_name: str,
    input_embedding: List[float],
    keyword_fields: Optional[List[Dict[str, Any]]] = None,
    filters: Optional[List[Dict[str, Any]]] = None,
    recall_size: int = 10
) -> List[Dict[str, Any]]:
    """
    執行向量搜尋，可選擇性地結合關鍵字加權和多種過濾條件
    :param keyword_fields: 可選的關鍵字欄位列表，每個項目是一個字典，格式如下：
                           {
                               "field": "欄位名稱",
                               "keywords": ["關鍵字1", "關鍵字2", ...],
                               "weight": 加權值 (可選，默認為1.0)
                           }
    :param filters: 可選的過濾條件列表，每個條件是一個字典，格式如下：
                    {
                        "type": "term"/"match"/"range",
                        "field": "欄位名稱",
                        "value": 過濾值
                    }
    :param recall_size: 返回的結果數量
    :return: 匹配的文檔列表
    """
    must_conditions = []
    should_conditions = []

    # 處理關鍵字加權（如果提供）
    if keyword_fields:
        for field_info in keyword_fields:
            field = field_info["field"]
            keywords = field_info["keywords"]
            weight = field_info.get("weight", 1.0)
            
            for keyword in keywords:
                should_conditions.append({
                    "match": {
                        field: {
                            "query": keyword,
                            "boost": weight
                        }
                    }
                })

    # 處理所有過濾條件（如果提供）
    if filters:
        for filter_condition in filters:
            filter_type = filter_condition["type"]
            field = filter_condition["field"]
            value = filter_condition["value"]

            if filter_type == "term":
                must_conditions.append({"term": {field: value}})
            elif filter_type == "match":
                must_conditions.append({"match": {field: value}})
            elif filter_type == "range":
                must_conditions.append({"range": {field: value}})
            else:
                raise ValueError(f"不支持的過濾類型: {filter_type}")

    # 添加向量搜尋條件
    must_conditions.append({
        "script_score": {
            "query": {"match_all": {}},
            "script": {
                "source": f"cosineSimilarity(params.query_vector, '{embedding_column_name}') + 1.0",
                "params": {"query_vector": input_embedding}
            }
        }
    })

    # 構建完整的查詢
    query = {
        "size": recall_size,
        "query": {
            "bool": {
                "must": must_conditions
            }
        }
    }

    # 如果有 should 條件，添加到查詢中
    if should_conditions:
        query["query"]["bool"]["should"] = should_conditions

    # 將查詢轉換為JSON字符串，然後再解析回Python對象
    # 這可以解決一些JSON序列化的問題
    query_json = json.dumps(query)
    query = json.loads(query_json)

    # 執行搜尋
    try:
        response = es.search(index=index, body=query)
        return response['hits']['hits']
    except Exception as e:
        print(f"搜索出錯: {str(e)}")
        return []





##### 顯示資料
### 顯示搜尋結果，可自定義結果數量。
def es_search_extend_data(es_reponse_hits_hits, show_data=10):
    count = 0
    for hit in es_reponse_hits_hits:
        print(f"Score: {hit['_score']}")
        print(f"Document ID: {hit['_id']}")
        print(f"Document source: {hit['_source']}")
        print("---")
        count += 1
        if count >= show_data:
            break
    return


### 顯示搜尋結果，可自定義顯示欄位和結果數量。
def es_search_extend_data_spec(es_response_hits_hits, fields_to_show=None, show_data=10):
    for count, hit in enumerate(es_response_hits_hits, 1): # 計數從 1 開始
        print(f"Score: {hit['_score']}")
        print(f"文件 ID: {hit['_id']}")
        
        if fields_to_show:
            for field in fields_to_show:
                if field in hit['_source']:
                    print(f"{field}: {hit['_source'][field]}")
        else:
            print(f"文件內容: {hit['_source']}")
        
        print("---")
        
        if count >= show_data:
            break
    return


