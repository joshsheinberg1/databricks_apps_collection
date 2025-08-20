import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import ssl
import slack_sdk
import os
from databricks.sdk import WorkspaceClient
import pandas as pd
from tabulate import tabulate


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


def format_table_as_ascii(data, max_rows=20):
    """
    Convert tabular data to ASCII table format for Slack
    """
    try:
        if not data or len(data) == 0:
            return "No data returned from query."
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(data)
        
        # Limit rows to prevent message from being too long
        if len(df) > max_rows:
            df_display = df.head(max_rows)
            truncated_msg = f"\n... (showing first {max_rows} of {len(df)} rows)"
        else:
            df_display = df
            truncated_msg = ""
        
        # Generate ASCII table using tabulate
        ascii_table = tabulate(
            df_display.values, 
            headers=df_display.columns, 
            tablefmt='grid',  # Use grid format for clean ASCII table
            maxcolwidths=[20] * len(df_display.columns),  # Limit column width
            stralign='left'
        )
        
        return f"```\n{ascii_table}{truncated_msg}\n```"
    
    except Exception as e:
        return f"Error formatting table: {str(e)}"


def get_query_result_data(w, space_id, conversation_id, message_id, attachment_id):
    """
    Fetch the actual tabular data from a Genie query result
    """
    try:
        # Get query results using the Databricks SDK
        result = w.genie.get_message_attachment_query_result(
            space_id=space_id,
            conversation_id=conversation_id, 
            message_id=message_id,
            attachment_id=attachment_id
        )
        
        # Extract data from the result
        if result and hasattr(result, 'data_array') and result.data_array:
            # Get column names
            columns = []
            if hasattr(result, 'manifest') and result.manifest and hasattr(result.manifest, 'schema'):
                columns = [col.name for col in result.manifest.schema.columns]
            
            # Create list of dictionaries for easier processing
            data_list = []
            for row in result.data_array:
                if columns:
                    row_dict = {columns[i]: row[i] if i < len(row) else None for i in range(len(columns))}
                else:
                    row_dict = {f'col_{i}': val for i, val in enumerate(row)}
                data_list.append(row_dict)
            
            return data_list
        
        return None
    
    except Exception as e:
        print(f"Error fetching query result data: {e}")
        return None


def query_genie(msg, user):
    w = WorkspaceClient()
    if user not in conversations:
        print("Starting conversation")
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
            replies.append("📊 **Query Description**: " + att.query.description)
            replies.append("```sql\n" + att.query.query + "\n```")
            
            # NEW: Fetch and format tabular data
            if hasattr(att, 'id') and att.id:
                query_data = get_query_result_data(
                    w, space_id, reply.conversation_id, reply.message_id, att.id
                )
                
                if query_data:
                    formatted_table = format_table_as_ascii(query_data)
                    replies.append("📋 **Query Results**:")
                    replies.append(formatted_table)
                else:
                    replies.append("⚠️ No tabular data available for this query.")

    return '\n\n'.join(replies) if replies else "I couldn't process your request."


token_app, token_bot, space_id = get_slack_auth()
app = start_slack_client()
conversations = {}


def extract_text(message):
    msg = ""
    for block in message["blocks"]:
        for element in block["elements"]:
            msg += "".join([text["text"] if text["type"] else "" for text in element["elements"]])
    return msg


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