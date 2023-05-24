from io import BytesIO
from flask import request, jsonify
from flask_restx import Resource, Api, Namespace, fields
from pymongo import MongoClient
from bson.objectid import ObjectId
import openai
import time
from datetime import datetime
from flask import send_file
import json
import os
import requests
import openai  # for OpenAI API calls
from random import randint
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)  # for exponential backoff

English = Namespace(
    name="English",
    description="영어 교육",
)

system_message =[{'role' : 'system' , 'content' : "You're going to role play with me in English."}]
client = MongoClient('mongodb://localhost:11084/', username= 'dba', password = '04231108')
db = client['JUNGMO_FLASK']

def setKey():
    keys = list(os.getenv("OPENAI_API_KEYS").split(','))
    openai.api_key = keys[randint(0,len(keys)-1)]
    English.logger.warn("key : " + str(openai.api_key))

@retry(wait=wait_random_exponential(min=1, max=1.5), stop=stop_after_attempt(6))
def completions_with_backoff(**kwargs):
    setKey()
    return openai.ChatCompletion.create(**kwargs)

def make_won(a,b):
    return 1330*(a+b)/1000*0.002


@English.route('/makeChat') # chat에 emoji랑 summary 추가 / role 추가 / user에 role_list에 추가 및 징수
class EnglishSimple(Resource):
    def post(self):
        English.logger.info("/chat/makeChat")
        problem = request.json.get('problem')
        problem_collection = db['English']
        chat_collection = db['EnglishChat']
        info = problem_collection.find_one({"_id": problem})
        if 'count' not in info: info['count']=0
        info['count']+=1
        problem_collection.find_one_and_update({'_id' : problem}, {'$set':info},return_document=False)
        # 대화 생성
        new_conversation = []
        for i in range(len(info['initial prompts'])):
            cur = {}
            cur['time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur['token'] = 0
            cur['text'] = info['initial prompts'][i]
            if i%2==0:
                cur['role'] = "user"
            else:
                cur['role'] = "assistant"
                cur['prompt_token'] = 0
                cur['completion_token'] = 0
                cur['won'] = 0
                cur['talk_time'] = 0
            new_conversation.append(cur)
        
        new_document = {
                'problem': problem,
                'created_time' : datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                'prompt_token' : 0, 
                'completion_token' : 0,
                'won': 0,
                'conversation': new_conversation,
                }
        chat_id = chat_collection.insert_one(new_document).inserted_id
        
        return {"chat_id": str(chat_id), "result": info['initial prompts'][-1]}

@English.route('/askGPT')
class Englishsimple(Resource):
    def post(self):
        chat_id = request.json.get('chat_id')
        text = request.json.get('text')
        English.logger.info("/chat/askGPT "+ ", chat_id = "+chat_id)
        chat_collection = db['EnglishChat']
        chat = chat_collection.find_one({"_id" : ObjectId(chat_id)})
        chat['conversation'].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "token" : 0,
            "text": text,
            "role": "user",
        })
        current_token = 0
        cur_messages = system_message[:]
        for i in chat['conversation']:
            cur_messages.append({"role": i['role'], "content": i['text']})
            current_token += i['token']
        if current_token>=3000:
            chat['conversation'].append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "token" : 0,
                "text": "Sorry, something came up and I have to go! We'll be in touch. See you next time",
                "role": "assistant",
                "prompt_token": 0,
                "completion_token": 0,
                "won": 0,
                "talk_time": 0
            })
            chat_collection.find_one_and_update({'_id' : ObjectId(chat_id)}, {'$set':chat},return_document=False)
            return {"result": "Sorry, something came up and I have to go! We'll be in touch. See you next time"}
        
        chat_collection.find_one_and_update({'_id' : ObjectId(chat_id)}, {'$set':chat},return_document=False)
        input_time= time.time()

        hi = completions_with_backoff(
                model="gpt-3.5-turbo",
                messages= cur_messages[:],
                temperature= 0,
                max_tokens=60,
                stop='\n',
            )
        response=hi['choices'][0]['message']['content']
        output_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S") 

        output = {
            "time": output_time,
            "token": hi['usage']['completion_tokens'],
            'text': response,
            'role': "assistant",
            "prompt_token": hi['usage']['prompt_tokens'],
            "completion_token": hi['usage']['completion_tokens'],
            "won": make_won(hi['usage']['prompt_tokens'], hi['usage']['completion_tokens']),
            "talk_time": time.time() - input_time
        }

        chat = chat_collection.find_one({"_id" : ObjectId(chat_id)})
        chat['conversation'][-1]['token'] = hi['usage']['prompt_tokens'] - current_token # insertDB에서 미리 넣어둔 user의 text 토큰 갱신
        chat['conversation'].append(output)
        chat['prompt_token']+=hi['usage']['prompt_tokens']
        chat['completion_token']+=hi['usage']['completion_tokens']
        chat['won']+=make_won(hi['usage']['prompt_tokens'], hi['usage']['completion_tokens'])
        update = {'$set': chat}
        chat_collection.find_one_and_update({"_id" : ObjectId(chat_id)},update,return_document=False)
        return {"result": response}

@English.route('/translate')
class Englishsimple(Resource):
    def post(self):
        text= request.json.get("text")
        data = {
              'source': 'en',
              'target': 'ko',
              'text': text,
              #'honorific': True
            }
        url = 'https://naveropenapi.apigw.ntruss.com/nmt/v1/translation'
        headers = {
            'Content-Type': 'application/json',
            'X-NCP-APIGW-API-KEY-ID': os.getenv("naver_id"),
            'X-NCP-APIGW-API-KEY': os.getenv("naver_secret")
        }

        response2 = requests.post(url, headers=headers, data=json.dumps(data))
        response_dict = json.loads(response2.content.decode('utf-8'))
        if response2.status_code == 200:
            translated_text = response_dict['message']['result']['translatedText']
            return {"result": translated_text}
        return {"result": text}