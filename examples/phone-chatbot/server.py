import os
import time
from fastapi import FastAPI, Request, Query, Form
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Gather

app = FastAPI()

# Call stats dictionary to track metrics
call_stats = {
    'silence_events': 0,
    'unanswered_prompts': 0,
    'call_start_time': None,
    'call_duration': 0,
}

MAX_UNANSWERED = 3  # Maximum allowed unanswered prompts

# Your ngrok base URL (no route included)
BASE_URL = os.getenv("BASE_URL", "https://f8e0-74-12-45-145.ngrok-free.app")


@app.post("/twilio-webhook")
async def twilio_webhook():
    """
    Initial webhook when call starts.
    Sends greeting and first Gather with attempt=0.
    """
    # Record call start time
    call_stats['call_start_time'] = time.time()

    response = VoiceResponse()

    # Greet the caller
    response.say("Hello, welcome to Pipecat! Please hold while we connect you.")

    # Build gather with absolute action URL
    gather_action_url = f"{BASE_URL}/process-input?attempt=0"
    gather = Gather(
        num_digits=1,
        action=gather_action_url,
        method="POST",
        timeout=10,
    )
    gather.say("Please press any key to continue.")
    response.append(gather)

    # If no input, continue with silence handling
    response.redirect(gather_action_url, method="POST")

    return HTMLResponse(content=str(response), status_code=200)


@app.post("/process-input")
async def process_input(request: Request, attempt: int = Query(0)):
    """
    Handle input after Gather timeout or digit pressed.
    If digit pressed - thank and hang up.
    If no input - increment attempt, retry or hang up after max attempts.
    """
    form = await request.form()
    digits = form.get("Digits")

    response = VoiceResponse()

    if digits:
        # User pressed a digit — reset counters, thank, and hang up
        response.say(f"You pressed {digits}. Thank you for your response!")
        response.say("We will now proceed with your request.")
        response.hangup()
    else:
        # No input received
        call_stats['silence_events'] += 1
        call_stats['unanswered_prompts'] += 1
        attempt += 1

        if attempt >= MAX_UNANSWERED:
            response.say("No input received multiple times. Goodbye.")
            response.hangup()
        else:
            # Retry the prompt
            gather_action_url = f"{BASE_URL}/process-input?attempt={attempt}"
            gather = Gather(
                num_digits=1,
                action=gather_action_url,
                method="POST",
                timeout=10,
            )
            gather.say("We did not receive your input. Please press any key to continue.")
            response.append(gather)
            response.redirect(gather_action_url, method="POST")

    return HTMLResponse(content=str(response), status_code=200)


@app.post("/call-status")
async def call_status(
    CallDuration: str = Form(...),
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
):
    """
    Handles call status updates (e.g., completed).
    Calculates call duration and logs call stats.
    """
    end_time = time.time()

    # Calculate and store duration
    call_stats['call_duration'] = int(CallDuration)

    # Log the call summary
    print("\n--- Call Summary ---")
    print(f"Call SID: {CallSid}")
    print(f"Status: {CallStatus}")
    print(f"Duration (seconds): {call_stats['call_duration']}")
    print(f"Silence events: {call_stats['silence_events']}")
    print(f"Unanswered prompts: {call_stats['unanswered_prompts']}")
    print("---------------------\n")

    # Reset stats after logging
    call_stats['silence_events'] = 0
    call_stats['unanswered_prompts'] = 0
    call_stats['call_start_time'] = None

    return {"message": "Call summary received"}
