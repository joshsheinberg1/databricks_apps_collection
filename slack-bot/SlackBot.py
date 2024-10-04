import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import ssl
import slack_sdk
import sqlglot
import os
from databricks.sdk import WorkspaceClient


def get_slack_auth():
    w = WorkspaceClient()
    token_app = w.dbutils.secrets.get(scope='slack-bot', key='slack_token_app')
    token_bot = w.dbutils.secrets.get(scope='slack-bot', key='slack_token_bot')
    return token_app, token_bot

def start_slack_client():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    client = slack_sdk.WebClient(token=token_bot, ssl=ssl_context)
    return App(client=client, process_before_response=False)

token_app, token_bot = get_slack_auth()
app = start_slack_client()

def extract_text(message):
    query = ""
    for block in message["blocks"]:
        for element in block["elements"]:
            query = "".join([text["text"] if text["type"] else "" for text in element["elements"]])
    return query

# Listens to incoming messages that contain "hello"
@app.event("message")
def message_hello(message, say):
    print("Received: ", message, type(message))    

    query = extract_text(message)
    try:
        print("Query input:", query)
        query = sqlglot.transpile(query, read="bigquery", write="databricks")[0]
        print("Query output:", query)    
    except:
        query="I am only a sql query converter bot! It looks like your input is not a query or may be wrong."
    say(query, thread_ts=message["event_ts"])


# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, token_app).start()


