from datetime import datetime
import os
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import safe_join
import uuid  
from elevenlabs import set_api_key
from elevenlabs import Voice, VoiceSettings, generate, save
import openai
from flask_cors import CORS
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

app = Flask(__name__)
CORS(app, resources={
    r"/process_query": {"origins": "*"}, 
    r"/delete-audios": {"origins": "*"},
    r"/get_messages/*": {"origins": "http://127.0.0.1:5000"}
    })



load_dotenv()
ElevenLabsKey = os.environ.get("ElevenLabs_API_KEY")


openai.api_key = os.environ.get('OPENAI_API_KEY')
set_api_key(ElevenLabsKey)

client = MongoClient('mongodb+srv://arinsoni:arinsoni@cluster0.kdmzwna.mongodb.net/')
db = client.nvdata
collection = db.collection



def getVoice(text, id):
    print(f"audio generating... ")
    audio = generate(
        text,
        voice=Voice(
            voice_id='PzgV69yst4xP66RXGTSL',
            settings=VoiceSettings(stability=0.35, similarity_boost=0.93, style=0.48, use_speaker_boost=True)
        ),
        model="eleven_multilingual_v2",
    )
    print("audio generated")

    save(audio, f"audio{id}.mp3")
    audio_file = f'audio{id}.mp3'
    return audio_file


def motivation(user_input):

    messages = [
        {
            "role": "system",
            "content": "You are Nitin Vijay Sir(NV). You are a senior JEE/NEET faculty and empathetic mentor at Motion, Kota. Your task is to help students and answer their queries. Language: Hinglish"
        },
        {
            "role": "user",
            "content": user_input
        }
    ]
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
    print("text genereted")
    return gpt_ans



def threadSum(txt):
    print(f"summarizing...{txt}")
    messages = [
            {
                "role": "system",
                "content": f"summarize {txt}in less than 8 words "
            },
            {
                "role": "user",
                "content": txt
            }
        ]

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=messages,
        temperature=0,
        max_tokens=50  
    )

    threadName = response['choices'][0]['message']['content'].strip()
    return threadName


@app.route('/audio/<filename>', methods=['GET'])
def serve_audio(filename):
    audio_directory = '.'  
    file_path = safe_join(audio_directory, filename)  

    if os.path.isfile(file_path):
        return send_file(file_path, as_attachment=True, download_name=filename, mimetype='audio/mpeg')
    else:
        return "File not found", 404
    


@app.route('/process_query', methods=['POST'])
def process_input():
    data = request.json
    user_input = data['user_input']
    userId = data['userId']  
    threadId = data['threadId'] 
    isFirstMessageSent = data['isFirstMessageSent']
    gpt_ans = motivation(user_input)
    audio_file_name = getVoice(gpt_ans, userId)

    timestamp_dt = datetime.strptime(data['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")
   
    print(f"isFirstMessageSent: {isFirstMessageSent}")

    response = {
        'text_response': gpt_ans,
        'audio_response': request.url_root + 'audio/' + audio_file_name,
    }
   
    message_content = {
        'input': user_input,
        'output': response['text_response'],
        'audioUrl': response['audio_response'],
        'timestamp': timestamp_dt.strftime("%Y-%m-%dT%H:%M:%S.%f"),
        'isFavorite': False,
    }
    existing_thread = db.collection.find_one({'threadId': threadId})
    if existing_thread:
        
        db.collection.update_one({'threadId': threadId}, {'$push': {'messages': message_content}})
    else:
        threadName = threadSum(user_input)
        thread = {
            'userId': userId,
            'threadId': threadId,
            'threadName': threadName,
            'messages': [message_content],
        }
        db.collection.insert_one(thread)

    print('Received message with timestamp:', timestamp_dt)
    print(response)

    return jsonify(response)





@app.route('/get_messages/<user_id>/<thread_id>', methods=['GET'])
def get_messages(user_id, thread_id):
    print(f"Fetching messages for user_id: {user_id} and thread_id: {thread_id}")
    thread = db.collection.find_one({"userId": user_id, "threadId": thread_id})

    if thread:
        messages = thread['messages']
        thread_name = thread.get('threadName', 'Default Thread Name')  

        print(f"Fetched messages: {messages}")

        return jsonify({
            'messages': messages,
            'threadName': thread_name  
        })
    else:
        return jsonify([])  






@app.route('/get_threads/<user_id>', methods=['GET'])
def get_threads(user_id):
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        threads_cursor = db.collection.find({"userId": user_id}, {"_id": 0, "threadId": 1, "threadName": 1})

        threads = list(threads_cursor)
        if threads:
            distinct_threads = list({(x['threadId'], x['threadName']) for x in threads if 'threadId' in x and 'threadName' in x})
            formatted_threads = [{"threadId": x[0], "threadName": x[1]} for x in distinct_threads]
            print(f"formatted_threads {formatted_threads}")
            return jsonify(formatted_threads), 200
        else:
            return jsonify({"message": "No threads found for the given user ID"}), 404
    except Exception as e:
        print(e)
        return jsonify({"error": "An error occurred while fetching the threads"}), 500



@app.route('/delete-audios', methods=['DELETE'])
def delete_audios():
    try:
        audio_directory = '.'  
        for filename in os.listdir(audio_directory):
            if filename.endswith('.mp3'):
                file_path = os.path.join(audio_directory, filename)
                os.remove(file_path)
        return jsonify({"message": "All audio files deleted successfully"}), 200
    except Exception as e:
        print(e)
        return jsonify({"message": "An error occurred while deleting audio files"}), 500
    
# @app.route('/update-favorite', methods=['POST'])
# def update_favorite():
#     try:
#         data = request.json
#         print('Received data: ', data)  
#         message = data['message']
#         is_favorite = data['isFavorite']

#         result = db.collection.update_one(
#             {"message.input": message['input'], "message.output": message['output']},
#             {"$set": {"message.isFavorite": is_favorite}}
#         )
        
#         print('Update result: ', result.raw_result)  
#         if result.matched_count > 0:
#             return jsonify(success=True)
#         else:
#             return jsonify(success=False, error="Message not found")

#     except Exception as e:
#         print('Error: ', e)
#         return jsonify(success=False, error=str(e))





if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)