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



application = Flask(__name__)
CORS(application, resources={
    r"/process_query": {"origins": "*"}, 
    r"/delete-audios": {"origins": "*"},
    r"/get_messages/*": {"origins": "http://127.0.0.1:5000"}
    })



load_dotenv()
ElevenLabsKey = os.environ.get("ElevenLabs_API_KEY")


openai.api_key = "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"
set_api_key("82a290bde21d59052827f6d2fc1e949f")

client = MongoClient('mongodb+srv://arinsoni:arinsoni@cluster0.kdmzwna.mongodb.net/')
db = client.nvdata
collection = db.collection



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

def get_past_messages(user_id, thread_id):
    user = db.collection.find_one({"userId": user_id})
    if user:
        thread = next((t for t in user['threads'] if t['threadId'] == thread_id), None)
        if thread:
            return thread['messages']
    return []

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
    




def motivation(user_input, threadId, userId, messages):
    
    # Insert the system message at the start of the messages list
    system_message = {
        "role": "system",
        "content": "You are Nitin Vijay Sir(NV). You are a senior JEE/NEET faculty and empathetic mentor at Motion, Kota. Your task is to help students and answer their queries. Also Remember the previous messages and use them to generate context-aware responses. Language: Hinglish"
    }
    messages.insert(0, system_message)
    
    # Add the current user message to the messages list
    messages.append({"role": "user", "content": user_input})

    # print(json.dumps(messages, indent=4, ensure_ascii=False))
    print("text output generating...")

    response = openai.ChatCompletion.create(
        model="ft:gpt-3.5-turbo-0613:personal::866dUQhT",
        messages=messages,
        temperature=0.5,
        top_p=0.9,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None
    )

    gpt_ans = response.choices[0].message.content

    return gpt_ans


# Processs query



@application.route('/<user_id>/process_query', methods=['POST'])
def process_input(user_id):
    data = request.json
    user_input = data['user_input']
    userId = data['userId']  
    unique_id = str(uuid.uuid4())
    threadId = data['threadId'] 
    isFirstMessageSent = data['isFirstMessageSent']

    user = db.collection.find_one({'userId': userId})

    if user:
        thread = next((t for t in user['threads'] if t['threadId'] == threadId), None)
        if thread:
            messages = thread['messages'][-10:]  
        else:
            messages = []
    else:
        messages = []

    cleaned_messages = []
    
    for m in messages:
        if 'input' in m:
            cleaned_messages.append({'role': 'user', 'content': m['input']})
        if 'output' in m:
            cleaned_messages.append({'role': 'assistant', 'content': m['output']})



    # gpt_ans = motivation(user_input)
    gpt_ans = motivation(user_input, threadId, userId, cleaned_messages)

    

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
                return jsonify({"message": "No threads found for the given user ID"}), 404
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