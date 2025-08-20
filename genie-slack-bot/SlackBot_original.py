import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import ssl
import slack_sdk
import os
from databricks.sdk import WorkspaceClient


def get_slack_auth():
    w = WorkspaceClient()
    token_app = w.dbutils.secrets.get(scope='slack-bot', key='slack_token_app')
    token_bot = w.dbutils.secrets.get(scope='slack-bot', key='slack_token_bot')
    token_app = os.environ["TOKEN_APP"]
    token_bot = os.environ["TOKEN_BOT"]
    space_id = os.environ["SPACE_ID"]
    return token_app, token_bot, space_id

def start_slack_client():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    client = slack_sdk.WebClient(token=token_bot, ssl=ssl_context)
    return App(client=client, process_before_response=False)

token_app, token_bot, space_id = get_slack_auth()
app = start_slack_client()
conversations = {}


def extract_text(message):
    msg = ""
    for block in message["blocks"]:
        for element in block["elements"]:
            msg += "".join([text["text"] if text["type"] else "" for text in element["elements"]])
    return msg

def query_genie(msg, user):
    w = WorkspaceClient()
    if user not in conversations:
        print("Starting converstion")
        reply = w.genie.start_conversation_and_wait(
            space_id=space_id,                     
            content=msg
        )
    else: 
        reply = w.genie.create_message_and_wait(
            space_id=space_id,
            conversation_id=conversations[user],
            content=msg,
        )
    print("Reply:", reply)
    conversations[user] = reply.conversation_id
    replies = []
    
    for att in reply.attachments:
        if att.text:
            replies.append(att.text.content)
        if att.query:
            replies.append("Description: " + att.query.description)
            replies.append("\nQuery: ```" + att.query.query + "```")

    return ' '.join(replies)

# Listens to incoming messages that contain "hello"
@app.event("message")
def message_hello(message, say):
    user = message['user']
    print("Received: ", message, type(message), "user: ", user)

    msg = extract_text(message)
    print("Msg:", msg)
    try:
        reply = query_genie(msg, user)
    except Exception as e:
        print("Error:", e)
        reply = "Sorry, I couldn't process your request."

    say(reply, thread_ts=message["event_ts"])

@app.event("assistant_thread_started")
def handle_assistant_thread_started_events(body, logger):
    logger.info(body)
    pass

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, token_app).start()


