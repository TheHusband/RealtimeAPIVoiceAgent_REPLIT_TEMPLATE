from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from pinecone_plugins.assistant.models.chat import Message
from fastapi.responses import Response
from pinecone import Pinecone
from prompts import SYSTEM_MESSAGE
import websockets
import requests
import asyncio
import json
import time
import os

# Retrieve the OpenAI API key and N8N webhook URL from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
REPL_PUBLIC_URL = os.getenv("REPL_PUBLIC_URL")

# Initialize FastAPI app
app = FastAPI()

# Some default constants used throughout the application
VOICE = 'shimmer'  # The voice for AI responses
PORT = int(os.getenv('PORT', 8000))

# Session management: Store session data for ongoing calls
sessions = {} 

# Event types to log to the console for debugging purposes
LOG_EVENT_TYPES = [
    'response.content.done',
    'rate_limits.updated',
    'response.done',
    'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped',
    'input_audio_buffer.speech_started',
    'session.created',
    'response.text.done',
    'conversation.item.input_audio_transcription.completed'
]

# Root route - just for checking if the server is running
@app.get("/")
async def root():
    return {"message": "Twilio Media Stream Server is running!"}

# Handle incoming calls from Twilio
@app.post("/incoming-call")
async def incoming_call(request: Request):
    form_data = await request.form()
    twilio_params = dict(form_data)
    print('Incoming call')
    print('Twilio Inbound Details:', json.dumps(twilio_params, indent=2))

    caller_number = twilio_params.get('From', 'Unknown')
    session_id = twilio_params.get('CallSid')
    print('Caller Number:', caller_number)
    print('Session ID (CallSid):', session_id)

    # Send the caller's number to N8N webhook to get a personalized first message
    first_message = "Hey, this is Sara from Agenix AI solutions. How can I assist you today?"

    try:
        webhook_response = requests.post(
            N8N_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            json={
                "route": "1",
                "number": caller_number,
                "data": "empty"
            }
        )
        if webhook_response.ok:
            response_text = webhook_response.text
            try:
                response_data = json.loads(response_text)
                if response_data and response_data.get('firstMessage'):
                    first_message = response_data['firstMessage']
                    print('Parsed firstMessage from N8N:', first_message)
            except json.JSONDecodeError:
                first_message = response_text.strip()
        else:
            print(f"Failed to send data to N8N webhook: {webhook_response.status_code}")
    except Exception as e:
        print(f"Error sending data to N8N webhook: {e}")

    # Set up a new session for this call
    session = {
        "transcript": "",
        "streamSid": None,
        "callerNumber": caller_number,
        "callDetails": twilio_params,
        "firstMessage": first_message
    }
    sessions[session_id] = session

    # Get Replit's public URL from environment variable
    host = REPL_PUBLIC_URL
    stream_url = f"{host.replace('https', 'wss')}/media-stream"

    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="firstMessage" value="{first_message}" />
            <Parameter name="callerNumber" value="{caller_number}" />
        </Stream>
    </Connect>
</Response>"""

    return Response(content=twiml_response, media_type="text/xml")

# WebSocket route to handle the media stream for real-time interaction
@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    print('Client connected to media-stream')

    first_message = ''
    stream_sid = ''
    openai_ws_ready = False
    queued_first_message = None
    thread_id = ''

    # Use a unique session ID per connection
    session_id = f"session_{int(time.time())}"
    session = sessions.get(session_id)
    if not session:
        session = {'transcript': '', 'streamSid': None}
        sessions[session_id] = session

    caller_number = session.get('callerNumber', 'Unknown')
    print('Caller Number:', caller_number)

    # Open a WebSocket connection to the OpenAI Realtime API
    openai_ws_url = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01'
    openai_ws_headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'OpenAI-Beta': 'realtime=v1'
    }

    async def send_session_update(openai_ws):
        session_update = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": VOICE,
                "instructions": SYSTEM_MESSAGE,
                "modalities": ["text", "audio"],
                "temperature": 0.8,
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "tools": [
                    {
                        "type": "function",
                        "name": "question_and_answer",
                        "description": "Get answers to customer questions especially about AI employees",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"}
                            },
                            "required": ["question"]
                        }
                    },
                    {
                        "type": "function",
                        "name": "schedule_meeting",
                        "description": "Schedule a meeting for a customer. Returns a message indicating whether the booking was successful or not.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                                "purpose": {"type": "string"},
                                "datetime": {"type": "string"},
                                "location": {"type": "string"}
                            },
                            "required": ["name", "email", "purpose", "datetime", "location"]
                        }
                    }
                ],
                "tool_choice": "auto"
            }
        }
        print('Sending session update:', json.dumps(session_update))
        await openai_ws.send(json.dumps(session_update))

    async def send_first_message(openai_ws):
        nonlocal queued_first_message, openai_ws_ready
        if queued_first_message and openai_ws_ready:
            print('Sending queued first message:', queued_first_message)
            await openai_ws.send(json.dumps(queued_first_message))
            await openai_ws.send(json.dumps({"type": "response.create"}))
            queued_first_message = None

    async def handle_twilio(openai_ws):
        nonlocal first_message, stream_sid, queued_first_message, openai_ws_ready, session_id, session, caller_number
        try:
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)
                if data.get('event') == 'start':
                    stream_sid = data['start']['streamSid']
                    call_sid = data['start']['callSid']
                    custom_parameters = data['start'].get('customParameters', {})

                    print('CallSid:', call_sid)
                    print('StreamSid:', stream_sid)
                    print('Custom Parameters:', custom_parameters)

                    caller_number = custom_parameters.get('callerNumber', 'Unknown')
                    session['callerNumber'] = caller_number
                    first_message = custom_parameters.get('firstMessage', "Hello, how can I assist you?")
                    print('First Message:', first_message)
                    print('Caller Number:', caller_number)

                    queued_first_message = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": first_message}]
                        }
                    }

                    if openai_ws_ready:
                        await send_first_message(openai_ws)

                elif data.get('event') == 'media':
                    if openai_ws and openai_ws.open:
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))

        except WebSocketDisconnect:
            print(f"Twilio WebSocket disconnected ({session_id}).")
            if openai_ws.open:
                await openai_ws.close()
            sessions.pop(session_id, None)
            await send_transcript_to_webhook(session)
        except Exception as e:
            print(f"Error in handle_twilio: {e}")
            import traceback
            traceback.print_exc()

    async def handle_openai(openai_ws):
        nonlocal openai_ws_ready, thread_id, stream_sid, session_id, session, websocket
        try:
            async for data in openai_ws:
                response = json.loads(data)
                # Handle OpenAI messages

                # Handle audio responses from OpenAI
                if response.get('type') == 'response.audio.delta' and response.get('delta'):
                    await websocket.send_text(json.dumps({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": response['delta']}
                    }))

                # Handle function calls
                elif response.get('type') == 'response.function_call_arguments.done':
                    function_name = response.get('name')
                    args = json.loads(response.get('arguments', '{}'))
                    if function_name == 'question_and_answer':
                        question = args.get('question')
    
                        try:
                            # Initialize Pinecone Assistant via SDK
                            pc = Pinecone(api_key=PINECONE_API_KEY)
                            assistant = pc.assistant.Assistant(assistant_name="rag-tool")
                            
                            # Create a message object with the user's question
                            msg = Message(content=question)
    
                            # Stream response chunks from Pinecone Assistant
                            chunks = assistant.chat(messages=[msg], stream=True)
    
                            # Accumulate the streamed content to form the complete answer
                            answer_message = ""
                            for chunk in chunks:
                                if chunk and chunk.type == "content_chunk":
                                    # Append content chunk to the answer message
                                    answer_message += chunk.delta.content
    
                            # Send the streamed response as OpenAI response
                            function_output_event = {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "role": "system",
                                    "output": answer_message
                                }
                            }
    
                            # Send the function call output (answer from Pinecone)
                            await openai_ws.send(json.dumps(function_output_event))
    
                            # Send the response to OpenAI to create a reply
                            await openai_ws.send(json.dumps({
                                "type": "response.create",
                                "response": {
                                    "modalities": ["text", "audio"],
                                    "instructions": f"Respond to the user's question \"{question}\" based on this information: {answer_message}. Be concise and friendly."
                                }
                            }))
    
                        except Exception as e:
                            print('Error processing question via Pinecone Assistant:', e)
                            await send_error_response(openai_ws)
                    elif function_name == 'schedule_meeting':
                        name = args.get('name')
                        email = args.get('email')
                        purpose = args.get('purpose')
                        datetime_param = args.get('datetime')
                        location = args.get('location')  # The user's selected location

                        # Calendar IDs for each location
                        calendars = {
                            "LOCATION1": "CALENDAR_EMAIL1",
                            "LOCATION2": "CALENDAR_EMAIL2",
                            "LOCATION3": "CALENDAR_EMAIL3",
                            # Add more locations as needed
                        }

                        try:
                            # Select the correct calendar based on location
                            calendar_id = calendars.get(location)
                            if not calendar_id:
                                raise ValueError(f"Invalid location: {location}")
                            data = json.dumps({
                                "name": name,
                                "email": email,
                                "purpose": purpose,
                                "datetime": datetime_param,
                                "calendar_id": calendar_id  
                            })

                            webhook_response = await send_to_webhook({
                                "route": "3",
                                "number": session.get('callerNumber', 'Unknown'),
                                "data": data
                            })
                            parsed_response = json.loads(webhook_response)
                            booking_message = parsed_response.get('message', "I'm sorry, I couldn't schedule the meeting at this time.")
                            
                            function_output_event = {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "role": "system",
                                    "output": booking_message
                                }
                            }
                            await openai_ws.send(json.dumps(function_output_event))
                            await openai_ws.send(json.dumps({
                                "type": "response.create",
                                "response": {
                                    "modalities": ["text", "audio"],
                                    "instructions": booking_message
                                }
                            }))
                        except Exception as e:
                            print('Error Schedule Meeting:', e)
                            await send_error_response(openai_ws)

                # Handle user starting to speak
                elif response.get('type') == 'input_audio_buffer.speech_started':
                    print("Speech Start:", response.get('type'))
                    # Clear any ongoing speech on Twilio side
                    await websocket.send_text(json.dumps({
                        "streamSid": stream_sid,
                        "event": "clear"
                    }))
                    print("Cancelling AI speech from the server")
                    # Send interrupt message to OpenAI to cancel ongoing response
                    interrupt_message = {
                        "type": "response.cancel"
                    }
                    await openai_ws.send(json.dumps(interrupt_message))

                # Log agent response
                elif response.get('type') == 'response.done':
                    response_output = response.get('response', {}).get('output', [])
                    if response_output and isinstance(response_output, list) and len(response_output) > 0:
                        output_item = response_output[0]
                        content_list = output_item.get('content', [])
                        if content_list and isinstance(content_list, list) and len(content_list) > 0:
                            content_item = content_list[0]
                            agent_message = content_item.get('transcript', 'Agent message not found')
                        else:
                            agent_message = 'Agent message not found'
                    else:
                        agent_message = 'Agent message not found'
                    session['transcript'] += f"Agent: {agent_message}\n"
                    print(f"Agent ({session_id}): {agent_message}")

                # Log user transcription
                elif response.get('type') == 'conversation.item.input_audio_transcription.completed' and response.get('transcript'):
                    user_message = response['transcript'].strip()
                    session['transcript'] += f"User: {user_message}\n"
                    print(f"User ({session_id}): {user_message}")

                # Log other relevant events
                elif response.get('type') in LOG_EVENT_TYPES:
                    print(f"Received event: {response.get('type')}", response)

        except Exception as e:
            print(f"Error in handle_openai: {e}")
            import traceback
            traceback.print_exc()

    async def send_error_response(openai_ws):
        await openai_ws.send(json.dumps({
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "instructions": "I apologize, but I'm having trouble processing your request right now. Is there anything else I can help you with?"
            }
        }))

    async def send_transcript_to_webhook(session):
        print('Full Transcript:')
        print(session['transcript'])
        print('Final Caller Number:', session.get('callerNumber', 'Unknown'))
        await send_to_webhook({
            "route": "2",
            "number": session.get('callerNumber', 'Unknown'),
            "data": session['transcript']
        })

    async def send_to_webhook(payload):
        print('Sending data to webhook:', json.dumps(payload, indent=2))
        try:
            response = requests.post(
                N8N_WEBHOOK_URL,
                headers={"Content-Type": "application/json"},
                json=payload
            )
            print('Webhook response status:', response.status_code)
            if response.ok:
                response_text = response.text
                print('Webhook response:', response_text)
                return response_text
            else:
                print(f"Failed to send data to webhook: {response.status_code}")
                raise Exception('Webhook request failed')
        except Exception as e:
            print('Error sending data to webhook:', e)
            raise e

    try:
        async with websockets.connect(openai_ws_url, extra_headers=openai_ws_headers) as openai_ws:
            openai_ws_ready = True
            await send_session_update(openai_ws)
            await send_first_message(openai_ws)

            # Start the tasks
            twilio_task = asyncio.create_task(handle_twilio(openai_ws))
            openai_task = asyncio.create_task(handle_openai(openai_ws))

            # Wait for both tasks to complete
            await asyncio.gather(twilio_task, openai_task)

    except Exception as e:
        print(f"Error in media_stream: {e}")
        import traceback
        traceback.print_exc()


# Start the FastAPI server using Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
