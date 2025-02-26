import requests
import openai
import json
import re
import os
import tiktoken
import aisuite as ai


def cut_before_embedding(data:dict) -> str:
    # data:{"title": <str>, "content": [<str>, <str>, ...], "editor": [<str>, <str>, ...]}
    headers = {"Content-Type": "application/json"}
    url = 'https://ckiptagger.cna.com.tw:8881/origin/'
    res = requests.post(url, data=json.dumps(data), headers=headers).json()
    if res['Result'] == 'Y':
        cut = [y for x in res['ResultData']['cut'] for y in x]
        pos = [y for x in res['ResultData']['pos'] for y in x]
        entity = [y for x in res['ResultData']['entity'] for y in x]
        text = pos_filter(cut, pos, entity)

    def group_entities(entity):
        result = {'PERSON': [], 'EVENT':[], 'GPE': [], 'DATE': [], 'ORG': [], 'FAC': []}
        for entity in entity:
            entity_text, entity_type, _ = entity  # Ignore the last index
            if entity_type in result:
                if entity_text not in result[entity_type]:
                    result[entity_type].append(entity_text)
        
        # Remove empty lists
        return {k: v for k, v in result.items() if v}

    entity_list = group_entities(entity)
    return {'text_for_embedding': f"{data['title']} {text}", 'entity': entity_list}

# !!! templarily for testing
def cut_before_embedding_1(data:dict) -> str:
    # data:{"title": <str>, "content": [<str>, <str>, ...], "editor": [<str>, <str>, ...]}
    headers = {"Content-Type": "application/json"}
    url = 'https://ckiptagger.cna.com.tw:8881/cut-for-embedding/'
    res = requests.post(url, data=json.dumps(data), headers=headers).json()
    if res['Result'] == 'Y':
        cut = [y for x in res['ResultData']['cut'] for y in x]
        pos = [y for x in res['ResultData']['pos'] for y in x]
        entity = res['ResultData']['entity']
        text = pos_filter(cut, pos, entity)

    return {'text_for_embedding': f"{data['title']} {text}", 'result':  res['ResultData']}

# articut version
def cut_before_embedding_articut(data:dict, pure_text=False) -> str:
    # data:{"title": <str>, "content": [<str>, <str>, ...], "editor": [<str>, <str>, ...], "category": <str>}
    headers = {"Content-Type": "application/json"}
    url = 'http://dt.cna.com.tw:8000/cut'
    res = requests.post(url, data=json.dumps(data), headers=headers).json()
    if res['Result'] == 'Y':
        keyword_result = res['ResultData']['KeywordsResults'] # 原CKIP結果

        articut_result = res['ResultData']['ArticutResults']

        # 全文<tag>text</tag> 加空格 過濾掉特定字詞 後 丟embedding的方式
        filter_pos_result, pure_text = pos_filter_articut(articut_result)
        # print(filter_pos_result)
        
        # 全文<tag>text</tag> 加空格丟embedding的方式
        # articut_pos = [item for item in articut_result['result_pos'] if not re.search(r'[，。、；：？！「」『』（）《》〈〉【】〔〕［］｛｝]', item)]
        # text = str(' '.join(articut_pos)) # peter 說要每個pos加空格
    return {
        # 'text_for_embedding': text, 
        'text_for_embedding': filter_pos_result, 
        'keyword_result': keyword_result
        }

def pos_filter_articut(articut_result):
    # 根據指定的規則篩選並標記詞性
    result = ""
    pure_text = ""
    for obj in articut_result['result_obj']:
        for line in obj:
            pos = line['pos']
            text = line['text']
            if re.match(r'^(ENTITY_|KNOWLEDGE_|ACTION_|MODIFIER|Medialab|TmpDict_|TIME_|ACT_|ENTY_)', pos):
                if pos.startswith('ENTITY_'):
                    pos = pos.replace('ENTITY_', '')
                    result += f"<{pos}>{text}</{pos}> "
                    pure_text += f"{text} "
                elif pos.startswith('ACTION_'):
                    pos = pos.replace('ACTION_', '')
                    result += f"<{pos}>{text}</{pos}> "
                    pure_text += f"{text} "
                elif pos.startswith('Medialab'):
                    pos = pos.replace('MedialabCNA_', '').replace("_dict", "")
                    result += f"<{pos}>{text}</{pos}> "
                    pure_text += f"{text} "
                elif pos.startswith('TmpDict_'):
                    pos = pos.replace('TmpDict_', '').replace("_ckip_dict", "")
                    result += f"<{pos}>{text}</{pos}> "
                    pure_text += f"{text} "
                elif pos.startswith('KNOWLEDGE_'):
                    pos = pos.replace('KNOWLEDGE_', '')
                    result += f"<{pos}>{text}</{pos}> "
                    pure_text += f"{text} "
                    pure_text += f"{text} "
                elif pos.startswith('TIME_'):
                    pos = pos.replace('TIME_', '')
                    result += f"<{pos}>{text}</{pos}> "
                    pure_text += f"{text} "
                elif pos.startswith('ENTY_'):
                    pos = pos.replace('ENTY_', '')
                    result += f"<{pos}>{text}</{pos}> "
                    pure_text += f"{text} "
                elif pos.startswith('ACT_'):
                    pos = pos.replace('ACT_', '')
                    result += f"<{pos}>{text}</{pos}> "
                    pure_text += f"{text} "
                else:
                    result += f"<{pos}>{text}</{pos}> "
                    pure_text += f"{text} "
    return result, pure_text


def pos_filter(cut, pos, entity):
    mark = ["COLONCATEGORY","COMMACATEGORY","DASHCATEGORY","DOTCATEGORY","ETCCATEGORY","EXCLAMATIONCATEGORY","PARENTHESISCATEGORY","PAUSECATEGORY","PERIODCATEGORY","QUESTIONCATEGORY","SEMICOLONCATEGORY","SPCHANGECATEGORY","WHITESPACE"]
    text = ''
    for c, p in zip(cut, pos):
        if bool(re.search('^N|^V|Cbb|Caa|^D$', p)):
            text += c
        elif p in mark:
            text += ' '
    # e = sorted(set([ent[0] for ent in entity if ent[1] in ['ORG', 'GPE', 'DATE', 'PERSON','EVENT', 'FAC', 'WORK_OF_ART', 'LAW','LOC'] and len(ent[0]) > 1]))
    e = [item for sublist in entity.values() for item in sublist if item]
    e_text = ' '.join(e)
    return text + ' entities: '+ e_text



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

def get_completion(messages, api_key, model="gpt-4o", temperature=0):
    """
    Get completion from either OpenAI or Claude API based on model parameter
    Args:
        messages: List of message dictionaries with 'role' and 'content'
        api_key: API key (either OpenAI or Anthropic)
        model: Model name (use "claude-3-sonnet" for Claude API)
        temperature: Temperature for response generation
    Returns:
        Generated text response
    """
    # Check if using Claude API
    if model.startswith('claude'):
        # Convert OpenAI message format to Claude format
        prompt = ""
        for message in messages:
            if message['role'] == 'system':
                prompt += f"System: {message['content']}\n\n"
            elif message['role'] == 'user':
                prompt += f"Human: {message['content']}\n\n"
            elif message['role'] == 'assistant':
                prompt += f"Assistant: {message['content']}\n\n"
        
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": "claude-3-sonnet-20240229",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 1024
        }

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            
            if 'error' in result:
                print(f"Error: {result['error']}")
                return None
                
            return result['content'][0]['text']
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return None
        except (KeyError, IndexError) as e:
            print(f"Error parsing response: {e}")
            return None

    else:
        # Original OpenAI implementation
        payload = {
            "model": model,
            "temperature": temperature,
            "messages": messages
        }
        headers = {
            "Authorization": f'Bearer {api_key}',
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                data=json.dumps(payload)
            )
            response.raise_for_status()
            
            obj = json.loads(response.text)
            
            if 'error' in obj:
                print(f"Error: {obj['error']['message']}")
                return None
            
            return obj['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return None
        except (KeyError, IndexError) as e:
            print(f"Error parsing response: {e}")
            return None


def get_completion_dd(messages, api_key, model_type, temperature):
    """
    統一的 completion 函數，支援 OpenAI 和 Claude AI
    :param model_type: 'gpt-4o' 或 'claude' 等
    """
    if model_type.startswith('gpt'):
        # OpenAI API
        model_name = "gpt-4-0125-preview" if model_type == "gpt" else model_type
        payload = {"model": "gpt-4o-2024-08-06", "temperature": temperature, "messages": messages}
        headers = {"Authorization": f'Bearer {api_key}', "Content-Type": "application/json"}
        response = requests.post('https://api.openai.com/v1/chat/completions', 
                               headers=headers, 
                               json=payload)
        obj = response.json()
        
        if 'error' in obj:
            print(f"Error: {obj['error']['message']}")
            return None
        
        return obj['choices'][0]['message']['content']
        
    elif model_type == "claude":
        # Claude API
        formatted_messages = [{"role": msg["role"], "content": msg["content"]} 
                            for msg in messages]
        
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "temperature": temperature,
            "messages": formatted_messages,
            "max_tokens": 4096
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        response = requests.post("https://api.anthropic.com/v1/messages", 
                               headers=headers, 
                               json=payload)
        obj = response.json()
        
        if response.status_code != 200:
            print(f"Error: {obj.get('error', {}).get('message', 'Unknown error')}")
            return None
            
        return obj['content'][0]['text']
        
    else:
        raise ValueError("model_type must be either 'gpt-4o' or 'claude'")


# openai 1.X 版本的 結構化輸出by chiatzu
def get_completion_structoutput(messages, response_BaseModel, model="gpt-4o", temperature=0, max_tokens=1000):
    client = openai.OpenAI()
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=messages,
        response_format=response_BaseModel,
        max_tokens=max_tokens,
        temperature=temperature
    )
    '''
    completion.choices[0].message 的結果：
    ChatCompletionMessage(content='回覆本體', refusal=None, role='assistant', function_call=None, tool_calls=None)
    '''
    return completion.choices[0].message.parsed


def text_embeddings_3(text):
    #搭配aisuite openai升級，修改寫法
    client = openai.OpenAI()
    t = client.embeddings.create(model="text-embedding-3-large", input=text)
    return t.data[0].embedding


def msgTokenCnt(msg):
    encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(msg))
    return num_tokens