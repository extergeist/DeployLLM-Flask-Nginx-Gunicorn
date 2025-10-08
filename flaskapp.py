from flask import Flask, render_template, request, jsonify
import subprocess
import threading
import queue
import time
import re

app = Flask(__name__)


MODEL_PATH = "./chat/gpt4all-linux"
model_process = None
output_queue = queue.Queue()


def clean_text(text):
    # Remove weird formatting from text
    ansi_pattern = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    return ansi_pattern.sub('', text)

def read_model_messages():
    # This function runs in the background and reads what the model says
    while True:
        line = model_process.stdout.readline()
        if not line:
            break
        clean_line = clean_text(line).strip()
        if clean_line:
            output_queue.put(clean_line)

def empty_the_queue():
    # Throw away all old messages
    while not output_queue.empty():
        try:
            output_queue.get_nowait()
        except queue.Empty:
            break

def setup_model():
    # Start the AI model and get it ready
    global model_process

    # Starts the executable defined under MODEL_PATH
    model_process = subprocess.Popen(
        [MODEL_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        universal_newlines=True,
        encoding='utf-8'
    )
    # Start listening to the model's output
    thread = threading.Thread(target=read_model_messages)
    thread.daemon = True
    thread.start()
    # give it a practice message
    time.sleep(3)
    model_process.stdin.write("hi\n")
    model_process.stdin.flush()
    time.sleep(5)
    empty_the_queue() # throw away the response

def get_ai_response(user_message):
    # send the message to the model and retrieve the response
    empty_the_queue()

    # send the user's message
    model_process.stdin.write(user_message + "\n")
    model_process.stdin.flush()

    # collect the model's response
    response_parts = []
    start_time = time.time()
    got_response = False

   # wait up to 60 seconds for a response
    while time.time() - start_time < 60:
        try:
            line = output_queue.get(timeout=0.5)

            # look for the start of the model's response
            if ">" in line and not got_response:
                got_response = True
                after_arrow = line.split(">", 1)
                if len(after_arrow) > 1 and after_arrow[1].strip():
                    response_parts.append(after_arrow[1].strip())
            elif got_response and line.strip():
                # skip system messages that we would usually see if we ran the model in our cmdline
                if not any(skip in line for skip in ['System:', 'User:', 'LLM Model:']):
                    response_parts.append(line)

        except queue.Empty:
            if got_response and response_parts:
                break
            continue

    return " ".join(response_parts).strip()

# ----------------------------------------------------
@app.route('/')

def home_page():
    return render_template('index.html') # our website

# -----------------------------------------------------

@app.route('/start_model', methods=['POST'])
def start_the_model():
    global model_process

    # check if the model is already running
    if model_process and model_process.poll() is None:
        return jsonify({'status': 'already_running'})

    setup_model()
    return jsonify({'status': 'started'})

# ----------------------------------------------------

@app.route('/stop_model', methods=['POST'])
def stop_the_model():
    global model_process

    if model_process:
        model_process.terminate()
        model_process = None
    return jsonify({'status': 'stopped'})

# ---------------------------------------------------

@app.route('/chat', methods=['POST'])
def chat_with_ai():
    user_message = request.json.get('message', '').strip()
    response = get_ai_response(user_message)
    return jsonify({'response': response})

#  ---------------------------------------------------

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=False)
                                                                              
