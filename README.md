# Twilio AI Voice Assistant with OpenAI and Pinecone Integration

This project is a template for creating a voice AI assistant using Twilio's media streams, OpenAI's Realtime API, Pinecone and N8N. The assistant can answer customer questions and schedule meetings, providing a natural and interactive experience over a phone call.

## Introduction

This template allows you to set up a voice-based AI assistant that interacts with callers using natural language. It leverages:

- **Twilio**: To handle incoming calls and media streams.
- **OpenAI Realtime API**: For real-time AI interactions.
- **Pinecone**: For advanced question-answering capabilities.
- **N8N**: As a webhook endpoint for additional workflows (e.g., fetching personalized greetings, handling meeting scheduling).

By following this guide, you can customize the assistant to fit your specific use case, change variables, and get it running correctly.

## Prerequisites

Before you begin, ensure you have the following:

**Accounts:**
- OpenAI
- Pinecone
- Twilio
- Replit
- N8N

## Setup

### 1. Upload Files to Replit
- Sign in to your Replit account.
- Create a new Python Repl.
- Upload all the files inside the zip folder (`main.py`, `prompts.py`, `pyproject.toml`, `poetry.lock`...etc) to your Replit project.
Note: Dont add a Folder. Make sure to click Upload a File then highlight all the files inside the folder.

### 2. Install Dependencies

Replit automatically installs dependencies listed in or `pyproject.toml`. 

### 3. Configure Environment Variables and Secrets

Replit provides a Secrets management feature to securely store environment variables.

- In your Replit project, click on the Lock icon on the left sidebar to open the Secrets panel.
- Add the following secrets:

#### a. OpenAI API Key
- **What is it?** Your secret key for accessing OpenAI's API.
- **How to get it?**
  1. Sign up or log in to your OpenAI account.
  2. Navigate to the API Keys page.
  3. Click on "Create new secret key".
  4. Copy the key.
- **Set it in Replit Secrets:**
  - **Key:** `OPENAI_API_KEY`
  - **Value:** `your-openai-api-key`

#### b. Pinecone API Key
- **What is it?** Your secret key for accessing Pinecone's services.
- **How to get it?**
  1. Sign up or log in to your Pinecone account.
  2. Go to the API Keys section in the dashboard.
  3. Copy the key.
- **Set it in Replit Secrets:**
  - **Key:** `PINECONE_API_KEY`
  - **Value:** `your-pinecone-api-key`

#### c. N8N Webhook URL
- **What is it?** The URL endpoint of your N8N workflow webhook. Used for:
  - Fetching personalized first messages.
  - Handling meeting scheduling data.
  - Receiving call transcripts.
- **How to set up N8N Webhook:**
  1. Set up an N8N workflow that can handle the incoming requests.
  2. The webhook should accept POST requests with JSON payloads.
  3. Based on the "route" parameter in the payload, it should perform different actions:
     - **Route 1**: Return a personalized first message based on the caller's number.
     - **Route 2**: Receive and store the call transcript.
     - **Route 3**: Handle meeting scheduling data and return confirmation or suggestions.
- **Set it in Replit Secrets:**
  - **Key:** `N8N_WEBHOOK_URL`
  - **Value:** `https://your-n8n-instance.com/webhook/your-webhook-id`


#### d. REPL_PUBLIC_URL
- **What is it?** The public URL where your application is accessible. Twilio needs this to send requests to your application.
- **How to get it in Replit:**
  1. Run your application in Replit.
  2. Click on the Webview button (usually opens in a new tab).
  3. Copy the URL from the browser (e.g., `https://your-repl-name.your-username.repl.co`).
- **Set it in Replit Secrets:**
  - **Key:** `REPL_PUBLIC_URL`
  - **Value:** `https://your-repl-name.your-username.repl.co`

### 4. Set Up Twilio

You'll need a Twilio account and a phone number to receive calls.

#### a. Buy a Twilio Phone Number
- Log in to your Twilio Console.
- Navigate to **Phone Numbers > Buy a Number**.
- Purchase a phone number capable of handling voice calls.

#### b. Configure the Webhook URL
- Go to **Phone Numbers > Manage > Active Numbers**.
- Click on your purchased phone number.
- Scroll down to the **Voice & Fax** section.
- In the **A CALL COMES IN** field, select **Webhook**.
- Enter your webhook URL:
  ```
  https://your-repl-public-url/incoming-call
  ```
  Replace `https://your-repl-public-url` with your actual `REPL_PUBLIC_URL`.
- Set the HTTP method to **POST**.
- Save the configuration.

### 5. Running the Application

If you're using Replit, simply click the **Run** button.


## Understanding and Modifying Variables

### Voice Configuration
- **Variable:** `VOICE`
- **Location:** In `main.py`, near `VOICE = 'shimmer'`
- **Description:** Specifies the voice used for AI responses.
- **Options:** Depends on the voices supported by the OpenAI Realtime API.
- **How to Change:**
  ```python
  VOICE = 'your-desired-voice'
  ```

### System Message Customization
- **File:** `prompts.py`
- **Variable:** `SYSTEM_MESSAGE`
- **Description:** Defines the assistant's behavior, persona, and conversation guidelines.
- **How to Customize:**
  1. Open `prompts.py`.
  2. Modify the content within `SYSTEM_MESSAGE` to change the assistant's role, persona, and instructions.

  **Example:**
  ```python
  SYSTEM_MESSAGE = """
  ### Role
  You are an AI assistant named Alex, helping users with technical support.
  ### Persona
  - Friendly and helpful.
  - Simplifies complex technical terms.
  ### Conversation Guidelines
  - Always confirm if the user's issue is resolved.
  - Encourage users to ask follow-up questions.
  """
  ```

### Calendar Emails and Locations

The application can schedule meetings at different locations. You need to update the calendar emails and locations to match your own.

- **Location:** In `main.py`, within the `handle_openai` function, under the `schedule_meeting` function handling.
- **Variables to Modify:**
  ```python
  # Calendar IDs for each location
  calendars = {
      "LOCATION1": "CALENDAR_EMAIL1",
      "LOCATION2": "CALENDAR_EMAIL2",
      "LOCATION3": "CALENDAR_EMAIL3",
      # Add more locations as needed
  }
  ```
- **How to Change:**
  - Replace `LOCATION1`, `LOCATION2`, `LOCATION3` with your actual location names (e.g., "New York", "San Francisco").
  - Replace `CALENDAR_EMAIL1`, `CALENDAR_EMAIL2`, `CALENDAR_EMAIL3` with the email addresses of the calendars where meetings should be scheduled.

  **Example:**
  ```python
  calendars = {
      "New York": "ny-office-calendar@example.com",
      "San Francisco": "sf-office-calendar@example.com",
      "London": "london-office-calendar@example.com",
  }
  ```

## Testing the Application

1. **Make a Call:** Dial the Twilio phone number you configured.
2. **Interact with the Assistant:**
   - The assistant should greet you with a personalized message fetched via N8N.
   - Try asking questions or scheduling a meeting.
3. **Verify Functionality:**
   - Ensure that the assistant responds appropriately.
   - If you scheduled a meeting, check your N8N workflows or calendar to confirm the booking.
4. **Check Logs:**
   - In Replit, view the console logs to see the interactions and debug if necessary.
   - Ensure that transcripts and data are being sent to your N8N webhook.

## Troubleshooting

- **Issue:** Twilio says it cannot reach the webhook URL.
  - **Solution:** Ensure your application is running in Replit and publicly accessible. Double-check the `REPL_PUBLIC_URL` and that it's correctly entered in Twilio's settings.

- **Issue:** OpenAI API errors or timeouts.
  - **Solution:** Verify that your `OPENAI_API_KEY` is correct and that you have sufficient quota.

- **Issue:** Pinecone function calls not working.
  - **Solution:** Check that your `PINECONE_API_KEY` is correct. Ensure your Pinecone index and assistant are properly set up.

- **Issue:** N8N webhook not responding or returning errors.
  - **Solution:** Test your webhook URL separately using a tool like curl or Postman. Ensure your N8N workflow is activated and correctly handles the incoming data.

- **Issue:** Errors related to environment variables not found.
  - **Solution:** Make sure all required secrets are set in Replit's Secrets panel.

- **Issue:** Meeting scheduling not working or incorrect locations/emails used.
  - **Solution:** Double-check the `calendars` dictionary in `main.py` to ensure locations and calendar emails are correctly set. Ensure your N8N workflow is setup correctly

## Additional Notes

- **Session Management:** The application uses a `sessions` dictionary to manage ongoing calls. Ensure that your hosting solution (Replit) can handle this appropriately, especially if multiple calls occur simultaneously.

- **Security:** Never expose your API keys publicly. Use Replit's Secrets management to securely store environment variables.

- **Extensibility:** You can add more function tools or modify existing ones in the `send_session_update` function within `main.py`.

- **Logging:** The application prints logs to the console for debugging. You may want to implement a more robust logging mechanism for production use.

- **System Time:** The `prompts.py` file uses the current UTC time. Ensure your server time is correct if scheduling meetings based on time.

- **N8N Workflows:**
  - **Route 1:** Should return a personalized first message based on the caller's number.
  - **Route 2:** Should handle storing or processing the call transcript.
  - **Route 3:** Should handle meeting scheduling, check availability, and return confirmation or suggest alternative times.

## License

This project is licensed under the MIT License.

**Disclaimer:** This template is provided as-is and is meant for educational purposes. Ensure you comply with all relevant terms of service and legal requirements when using third-party APIs and services.
