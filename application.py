from datetime import datetime
import json
import os
import uuid
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import safe_join
from elevenlabs import set_api_key
from elevenlabs import Voice, VoiceSettings, generate, save
import openai
from flask_cors import CORS
from dotenv import load_dotenv
from pymongo import MongoClient
import re



application = Flask(__name__)
CORS(application, resources={
    r"/process_query": {"origins": "*"}, 
    r"/delete-audios": {"origins": "*"},
    r"/get_messages/*": {"origins": "*"}
    })



load_dotenv()
ElevenLabsKey = os.environ.get("ElevenLabs_API_KEY")


openai.api_key = "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"
set_api_key("82a290bde21d59052827f6d2fc1e949f")

client = MongoClient('mongodb+srv://arinsoni:arinsoni@cluster0.kdmzwna.mongodb.net/')
db = client.nvdata
collection = db.collection


#  check


mod_q_prompt = """You are chatbot moderator and assistant. You'll be given a query(Q). You need to evaluate it on coherency, completeness and accuracy.
Context: The questions are asked by students aspiring for JEE/NEET examinations. Motion is coaching Institute in Kota headed by Nitin Vijay (NV) Sir. Also Remember the previous messages and use them to generate context-aware responses but don't repeat yourself.
Steps to follow:
 1. Understand what the query is trying to ask or convey.
 2. Classify question into following intents: Greeting, Personal, Conversational, Technical, Incomplete, Motion and Misc  
 2. If query is a difficult question, provide a few short hints outlining the answer. In case of incomplete info, ask for further info.
Language: Hinglish
Example Intent classification: 
1. Intent: Greeting: "Hi Sir", "Good Evening", "Namaste, kaise hain aap?".
2. Intent: Personal: Student's personal issues: "Sir padhai nahi ho rahi, kya karun?", "Sir depression aa raha hai".
3. Intent Motion: "Motion achi institute hai kya", "Motion mai teachers kese recruit karte ho". 
4. Intent Conversational: "ok", "thank you", "acha", "Mai theek hun".
5. Intent Incomplete: question that require more information or context to answer: "swati mam kesi hai", "sir radhika ke kitne marks aaye".
Syntax:
Understand Q: <question-understanding>
Intent: <intent>
Hint: <prompt/none>
Example:

Q: Sir swati mam kaisi hai?
Understand Q: The user is asking about the well-being or opinion of Swati Mam. But no information about who is Swati mam is given.
Intent: Incomplete
Hint: Ask who is swati mam
"""




mod_default = """You are conversation quality evaluation and moderation agent. You'll be given a question(Q) answer(A) pair with optional answer outline. You need to evaluate it on coherency, completeness and accuracy.
Context: The conversation is between students aspiring for JEE/NEET examinations and chatbot. Also Remember the previous messages and use them to generate context-aware responses but don't repeat yourself.
Steps to follow:
 1. Analyse the given Answer. In case of incomplete info, chatbot must ask for further info.:
    i. Is the A helpful to the student?
    ii. Is the tone empathetic?
    iii. Is A correct solution to the query? If outline is provided, does the Answer cover points from the outline?
 2. if Q is not a question, answer should continue the conversation.
 3. Score the answer between 0 and 10 points.
Language: English 
Input: Hinglish
Syntax:
Analysis of A: <analysis>
Score: <0-10>"""

mod_personal = """You are conversation quality evaluation and moderation agent. You'll be given a personal question(Q) answer(A) pair with optional answer outline. You need to evaluate it on coherency, completeness and accuracy.
Context: The conversation is between students aspiring for JEE/NEET examinations and chatbot. Also Remember the previous messages and use them to generate context-aware responses but don't repeat yourself.
Steps to follow:
 1. Analyse the given Answer.
    i. Is the A helpful to the student?
    ii. Is the tone empathetic?
    iii. Is A correct solution to the query? If outline is provided, does the Answer cover points from the outline?
 3. Score the answer between 0 and 10 points.
Language: English 
Input: Hinglish
Syntax:
Analysis of A: <analysis>
Score: <0-10>"""

mod_conv = """You are conversation quality evaluation and moderation agent. You'll be given a query(Q) answer(A) pair with optional answer outline. You need to evaluate it on coherency and completeness.
Context: The conversation is between students aspiring for JEE/NEET examinations and chatbot. Also Remember the previous messages and use them to generate context-aware responses but don't repeat yourself.
Steps to follow:
 1. Analyse the given Answer.
    i. Is the tone empathetic?
    ii. Is the A is natural sounding?
 2. Score the answer between 0 and 10 points based on above analysis.
Language: English 
Input: Hinglish
Syntax:
Analysis of A: <analysis>
Score: <0-10>"""

mod_technical = """You are conversation quality evaluation and moderation agent. You'll be given a technical question(Q) answer(A) pair with optional answer outline. You need to evaluate it on coherency, completeness and accuracy.
Context: The conversation is between students aspiring for JEE/NEET examinations and chatbot. Also Remember the previous messages and use them to generate context-aware responses but don't repeat yourself.
Steps to follow:
 1. Analyse the given Answer. In case of incomplete info, chatbot must ask for further info.:
    i. Is the A helpful to the student?
    ii. Is A correct solution to the query? If outline is provided, does the Answer cover points from the outline?
 3. Score the answer between 0 and 10 points.
Language: English 
Input: Hinglish
Syntax:
Analysis of A: <analysis>
Score: <0-10>"""

mod_motion = """You are conversation quality evaluation and moderation agent. You'll be given a question(Q) answer(A) pair regarding Motion institute, Kota whose founder is Nitin Vijay (NV) Sir. You might be provided with answer outline. You need to evaluate it on coherency, completeness and accuracy.
Context: The conversation is between students aspiring for JEE/NEET examinations and chatbot. Also Remember the previous messages and use them to generate context-aware responses but don't repeat yourself.
Steps to follow:
 1. Analyse the given Answer. In case of incomplete info, chatbot must ask for further info.:
    i. Is the A helpful to the student?
    ii. Is the tone empathetic?
    iii. Is A correct solution to the query? If outline is provided, does the Answer cover points from the outline?
 3. Score the answer between 0 and 10 points.
Language: English 
Input: Hinglish
Syntax:
Analysis of A: <analysis>
Score: <0-10>"""

mod_incomplete = """You are conversation quality evaluation and moderation agent. You'll be given a question(Q) answer(A). You might be provided with answer outline. The question(Q) requires further information, answer should ask for further information.
Context: The conversation is between students aspiring for JEE/NEET examinations and chatbot. Also Remember the previous messages and use them to generate context-aware responses but don't repeat yourself.
Steps to follow:
 1. Analyse the given Answer.
    i. Is the tone empathetic?
    ii. Is A answer asking for the correct information for the query? If outline is provided, does the Answer cover points from the outline?
 2. Score the answer between 0 and 10 points.
Language: English 
Input: Hinglish
Syntax:
Analysis of A: <analysis>
Score: <0-10>"""



mod_a_strict = """"You are chatbot moderation agent. You are supposed to do language moderation.
Ensure that the language of text is appropriate for students. Only if inappropriate words are used in the text, flag the text as "Appropriate: no"
Syntax:
Appropriate: <yes/no>"""


def get_hint(q, messages):
    eval = gpt_history(f"{q}", mod_q_prompt, messages, temp=1)
    if "Hint:" in eval:
      eval, hint = eval.split("Hint:")
      if hint.lower().strip() == "none":
        hint = ""
    else:
      hint = ""
    if "Intent:" in eval:
      eval, intent = eval.split("Intent:")
      if intent.lower().strip() == "none":
        intent = ""
      else:
          intent = intent.split()[0]
    else:
      intent = ""

    return eval, intent, hint

def gpt_history(txt, sys_prompt, messages, model="gpt-3.5-turbo", temp=0.7):
    messages.append({
        'role': "user",
        'content': txt
    })
    messages.insert(0, {
        'role': 'system',
        'content': sys_prompt
    })

    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temp,
        top_p=0.9,
        frequency_penalty=0.4,
        presence_penalty=0.3,
        stop=None
    )
    res = response.choices[0].message.content
    return res

def eval_a(QA, hint, mod_a_prompt, messages):
    q = QA[0]
    a = QA[1]
    if mod_a_prompt is None:
        return 10, ""
    if len(hint.strip()) and hint.lower().strip() != "none":
        eval = gpt_history(f"Q: {q}\nOutline: {hint}\nA: {a} Analysis of A: ", mod_a_prompt, messages, temp=1)
    else:
        eval = gpt_history(f"{q}\n{a}", mod_a_prompt, messages, temp=1)

    if "Score:" in eval:
      eval, score = eval.split("Score:")
    else:
      score = "-1"

    if '/' in score:
      score = float(score.strip().split('/')[0])
    else:
      score = float(score.strip())
    return score, eval


def motivation(user_input, messages):
    
    print("user input: ", user_input)
    
    # Insert the system message at the start of the messages list
    system_message = """You are Nitin Vijay Sir(NV). You are a senior JEE/NEET faculty and empathetic mentor at Motion, Kota. Your task is to only help students and answer their queries. Language: Hinglish.Also Remember the previous messages and use them to generate context-aware responses but don't repeat yourself.
        
    Language: Hinglish
    Study Language: English
    Syntax:
    Q: <question>
    Hint: <optional>
    A: <answer>"""

    
    
    # Add the current user message to the messages list
    q_analysis, intent, hint = get_hint(f"Q: {user_input}\nEvaluate Q:", messages.copy())
    # messages.append({"role": "user", "content": f"Q: {user_input}\nHint: {hint}"})

    # print(json.dumps(messages, indent=4, ensure_ascii=False))
    print("text output generating...")
    # print(f"Q: {q}")
    
    print( f"q_analysis: `{q_analysis}`\nhint: `{hint}`\n Intent: `{intent}`\n")
    match intent.lower().strip():
        case "greeting":
            hint  = "Greeting"
            mod_a_prompt = None
        case "personal":
            hint = "Personal query. " + hint
            mod_a_prompt = mod_personal
        case "conversational":
            hint = "Continue the conversation or ask for more question. " + hint
            mod_a_prompt = mod_conv
        case "technical":
            hint = "Techical query. " + hint
            mod_a_prompt = mod_technical
        case "motion":
            hint = "Regarding Motion Coaching. " + hint
            mod_a_prompt = mod_motion
        case "incomplete":
            hint = "Ask for more information. " + hint
            mod_a_prompt = mod_incomplete
        case _:
            mod_a_prompt = mod_default

    if len(hint.strip()) and hint.lower().strip() != "none":
        a = gpt_history(f"Q: {user_input}\nHint: {hint}\nA:", system_message, messages.copy(),  temp=0.85, model="ft:gpt-3.5-turbo-0613:personal::8F3EDZaq")
    else:
        a = gpt_history(f"Q: {user_input}\nA: ", system_message, messages.copy(),  temp=0.85, model="ft:gpt-3.5-turbo-0613:personal::8F3EDZaq")
    print(f"answer with hint: {a}")
    score, eval = eval_a([user_input,a], hint, mod_a_prompt, messages.copy())
    print(score, eval)
    if score <= 7:
        a = gpt_history(f"Q: {user_input}\nA: ", system_message, messages.copy(),  temp=0.85, model="ft:gpt-3.5-turbo-0613:personal::8F3EDZaq")
        print(f"answer without hint: {a}")
    
    if(a.startswith('A:') ):
        a = a[2:].strip()
    if(a.startswith('Hint:') ):
        a = a[5:].strip()
    check = gpt_history(a, mod_a_strict, [], temp = 1)
    if "no" in check:
        a = "Server Error"
        print("check : ", check)
    
    print("got final answer")
    print("------------------------------------------------------------------------------------------")
    # print("messages " , messages)

    return a



def getVoice(text, id):
    print(f"audio generating... ")
    # print(f"audio of {text}")
    audio = generate(
        text,
        voice=Voice(
            voice_id='wOgkbJGGYoE5gYRTT9s4',
            settings=VoiceSettings(stability=0.35, similarity_boost=0.93, style=0.48, use_speaker_boost=True)
        ),
        model="eleven_multilingual_v2",
    )
    print("audio generated")

    save(audio, f"audio{id}.mp3")
    audio_file = f'audio{id}.mp3'
    return audio_file




@application.route('/<user_id>/process_query', methods=['POST'])
def process_input(user_id):
    data = request.json
    user_input = data['user_input']
    userId = data['userId']  
    unique_id = str(uuid.uuid4())
    threadId = data['threadId'] 
    isFirstMessageSent = data['isFirstMessageSent']

    user = db.collection.find_one({'userId': userId})
    print("userId  = "  + userId + ' threadId = ' + threadId  + " ------------------------------------------------------------------------------------------" )

    if user:
        thread = next((t for t in user['threads'] if t['threadId'] == threadId), None)
        if thread:
            messages = thread['messages'][-10:]  
        else:
            messages = []
    else:
        messages = []

    cleaned_messages = []
    print("start")
    
    for m in messages:
        if 'input' in m:
            cleaned_messages.append({'role': 'user', 'content': m['input']})
        if 'output' in m:
            cleaned_messages.append({'role': 'assistant', 'content': m['output']})

    print("end")

    # gpt_ans = motivation(user_input)
    gpt_ans = motivation(user_input, cleaned_messages)

    
# 
    

    audio_file_name = getVoice(gpt_ans, unique_id)

    timestamp_dt = datetime.strptime(data['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")
   
    # print(f"isFirstMessageSent: {isFirstMessageSent}")
    
    response = {
        'text_response': gpt_ans,
        'audio_response': request.url_root + 'audio/' + audio_file_name,
    }


   
    message_content = {
        'input': user_input,
        'output': response['text_response'],
        'audioUrl': response['audio_response'],
        'timestamp': timestamp_dt.strftime("%Y-%m-%dT%H:%M:%S.%f"),
    }

    user = db.collection.find_one({'userId': userId})
    if user:
        thread = next((t for t in user['threads'] if t['threadId'] == threadId), None)
        if thread:
            db.collection.update_one(
                {'userId': userId, 'threads.threadId': threadId},
                {'$push': {'threads.$.messages': message_content}}
            )
        else:
            threadName = truncate_string(user_input)
            new_thread = {
                'threadId': threadId,
                'threadName': threadName,
                'messages': [message_content],
                'isFavorite': False,
            }
            db.collection.update_one(
                {'userId': userId},
                {'$push': {'threads': new_thread}}
            )
    else:
        threadName = truncate_string(user_input)
        new_user = {
            'userId': userId,
            'threads': [{
                'threadId': threadId,
                'threadName': threadName,
                'messages': [message_content],
                'isFavorite': False,
                
            }]
        }
        db.collection.insert_one(new_user)

    # print('Received message with timestamp:', timestamp_dt)
    # print(response)

    return jsonify(response)



def truncate_string(text, max_words=100):
    words = text.split()
    truncated_words = words[:max_words]
    truncated_text = ' '.join(truncated_words)
    if len(words) > max_words:
        truncated_text += ' ...'
    return truncated_text



@application.route('/audio/<filename>', methods=['GET'])
def serve_audio(filename):
    audio_directory = '.'  
    file_path = safe_join(audio_directory, filename)  

    if os.path.isfile(file_path):
        return send_file(file_path, as_attachment=True, download_name=filename, mimetype='audio/mpeg')
    else:
        return "File not found", 404
    

@application.route('/get_messages/<user_id>/<thread_id>', methods=['GET'])
def get_messages(user_id, thread_id):
    print(f"Fetching messages for user_id: {user_id} and thread_id: {thread_id}")

    user = db.collection.find_one({"userId": user_id})
    
    if user:
        thread = next((t for t in user['threads'] if t['threadId'] == thread_id), None)

        if thread:
            messages = thread['messages']
            thread_name = thread.get('threadName', 'Default Thread Name')  

            # print(f"Fetched messages: {messages}")

            return jsonify({
                'messages': messages,
                'threadName': thread_name  
            })
        else:
            return jsonify({"error": "Thread not found"}), 404  
    else:
        return jsonify({"error": "User not found"}), 404  



@application.route('/<user_id>/get_threads', methods=['GET'])
def get_threads(user_id):
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        # print("in get threads fun")
        user_document = db.collection.find_one({"userId": user_id}, {"_id": 0, "threads": 1})
        # print(user_document)

        if not user_document:
            # print("nahi hai")
            db.collection.insert_one({"userId": user_id, "threads": []})
            return jsonify([]), 200  

        if user_document and 'threads' in user_document:
            threads = user_document['threads']
            # print(f"threads {threads}")
            formatted_threads = []
            for thread in threads:
                # print("Processing Thread:", thread)
                if 'threadId' in thread and 'threadName' in thread and 'isFavorite' in thread and 'messages' in thread:
                    lastMessageTimestamp = thread['messages'][-1]['timestamp'] if thread['messages'] else None
                    msg = thread['messages'][-1]['input']

                    formatted_thread = {
                        "threadId": thread['threadId'],
                        "threadName": thread['threadName'],
                        "isFavorite": thread['isFavorite'],
                        "lastMessageTimestamp": lastMessageTimestamp,
                        "msg": msg
                        
                    }
                    formatted_threads.append(formatted_thread)
                    # print("Added Thread:", formatted_thread)
                else:
                    print("Thread Skipped")

            
            # print(f"formatted_threads: {formatted_threads}")


            if formatted_threads:
                return jsonify(formatted_threads), 200
            else:
                return jsonify({"message": "No threads found for the given user ID"}), 200
        else:
            return jsonify({"message": "No user found with the given user ID or the user has no threads"}), 404
    except Exception as e:
        print(e)
        return jsonify({"error": "An error occurred while fetching the threads"}), 500
    

@application.route('/update-favorite-thread', methods=['POST'])
def update_favorite_thread():
    try:
        data = request.json
        # print('Received data: ', data)

        required_fields = ['userId', 'threadId', 'isFavorite']
        if not all(field in data for field in required_fields):
            raise ValueError(f"Missing one or more required fields: {', '.join(required_fields)}")

        user_id = data['userId']
        thread_id = data['threadId']
        is_favorite = data['isFavorite']

        query = {
            'userId': user_id,
            'threads.threadId': thread_id
        }

        update = {
            '$set': {
                'threads.$.isFavorite': is_favorite
            }
        }

        result = db.collection.update_one(query, update)

        # print('Update result: ', result.raw_result)  
        if result.matched_count > 0:
            return jsonify(success=True)
        else:
            return jsonify(success=False, error="Thread not found")

    except Exception as e:
        print('Error: ', e)
        return jsonify(success=False, error=str(e))


@application.route('/delete_message', methods=['POST'])
def delete_message():
    data = request.json
    user_id = data.get('userId')
    thread_id = data.get('threadId')
    index = data.get('index')  

    if not user_id or not thread_id or index is None:
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        user = db.collection.find_one({'userId': user_id})
        
        if user:
            thread = next((t for t in user['threads'] if t['threadId'] == thread_id), None)
            
            if thread and 0 <= index < len(thread['messages']):
                # Remove the message at the specified index
                # print(f"before delete debug {json.dumps(user['threads'], indent=4, ensure_ascii=False)}")
                print(thread['messages'][len(thread['messages'])-1])
                del thread['messages'][len(thread['messages'])-1]


                print(f"after delete debug {json.dumps(user['threads'], indent=4, ensure_ascii=False)}")

                db.collection.update_one(
                    {'userId': user_id},
                    {'$set': {'threads': user['threads']}}
                )
                
                return jsonify({'success': True}), 200
            else:
                return jsonify({'error': 'Index out of range or thread not found'}), 404
        else:
            return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        print(e)
        return jsonify({'error': 'An error occurred while deleting the message'}), 500
    



@application.route('/delete_thread', methods=['POST'])
def delete_thread():
    data = request.json
    user_id = data.get('userId')
    thread_id = data.get('threadId')

    if not user_id or not thread_id:
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        result = db.collection.update_one(
            {'userId': user_id}, 
            {'$pull': {'threads': {'threadId': thread_id}}}
        )
        # print(f"Thread {thread_id} deleted.")

        if result.matched_count > 0:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Thread not found'}), 404
    except Exception as e:
        print(e)
        return jsonify({'error': 'An error occurred while deleting the thread'}), 500





if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000)