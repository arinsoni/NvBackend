import os
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import safe_join
import uuid  
from elevenlabs import set_api_key
from elevenlabs import Voice, VoiceSettings, generate, save
import openai
from flask_cors import CORS
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app, resources={
    r"/process_query": {"origins": "*"}, 
    r"/delete-audios": {"origins": "*"}
    })

load_dotenv()
ElevenLabsKey = os.environ.get("ElevenLabs_API_KEY")


openai.api_key = os.environ.get('OPENAI_API_KEY')
set_api_key(ElevenLabsKey)


def getVoice(text, id):
    print("audio generating...")
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


def gpt(user_input):
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
    unique_id = str(uuid.uuid4())

    gpt_ans = gpt(user_input)
    audio_file_name = getVoice(gpt_ans, 1)

    response = {
        'unique_id': unique_id,  
        'text_response': gpt_ans,
        'audio_response': request.url_root + 'audio/' + audio_file_name  
    }
    print(response)
    return jsonify(response)


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






if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)