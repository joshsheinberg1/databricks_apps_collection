from flask import send_from_directory
from flask import Flask, render_template
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from pprint import pprint
from flask import request
import json
import os
app = Flask(__name__, template_folder='templates')
app.debug = True


def get_columns(table_full_name):
    statement = f"describe formatted {table_full_name}" 
    print(statement)
    response = w.statement_execution.execute_statement(statement, warehouse_id=warehouse_id)
    print("result:", response)

    if response.result is None:
        raise Exception(response.status.message)

    columns = []
    col_type = {}
    for row in response.result.data_array:
        if row[0]:
            columns.append(str(row[0]))
            col_type[str(row[0])] = row[1]
        else:
            break
    return columns, col_type

def get_data(table_full_name):
    statement = f"select * from {table_full_name} limit 100"
    print(statement)
    response = w.statement_execution.execute_statement(statement, warehouse_id=warehouse_id)
    data = response.result.data_array
    print("result:", data)

    return data if data is not None else []
        
def get_table_name(table_full_name):
    return table_full_name.split(".")[-1]

def generate_values_stm(data):    
    out_values = []
    for col in columns:
        val = data["name_" + col]
        if col_types[col] == "string":
            out_values.append(f"'{val}'")
        else:
            out_values.append(f"{val}")
    return ",".join(out_values)


def insert_data(table_full_name, data):
    print("insert data", columns)
    values = generate_values_stm(data)
    print("Values", values)
    cols = ",".join(columns)

    statement = f"INSERT INTO {table_full_name} ({cols}) VALUES({values})"
    print("st", statement)
    response = w.statement_execution.execute_statement(statement, warehouse_id=warehouse_id)
    print(response)
    return response

@app.route('/')
def edit_table():
    args = {"table_full_name": table_full_name,
            "table_name": get_table_name(table_full_name),
            "columns": columns,
            "col_types": col_types,
            "data": get_data(table_full_name),
            "description": {"Student_ID": "The id of the student"}}
    return render_template('index.html', **args)

@app.route('/view_table')
def show_table():
    args = {"table_full_name": table_full_name,
            "table_name": get_table_name(table_full_name),
            "columns": columns,
            "col_types": col_types,
            "data": get_data(table_full_name),
            "description": {"Student_ID": "The id of the student"}}
    return render_template('table.html', **args)

@app.route('/tables/<table_full_name_sent>', methods = ['POST'])
def table_save(table_full_name_sent):
    print(table_full_name_sent)
    print(request.form)
    ret = insert_data(table_full_name, request.form)
    print("ret:", ret)
    status = ret.status
    if status.state == StatementState.SUCCEEDED:
        return json.dumps({"status": str(status.state), "msg": "Data was appended to the table.", "code": str(0)})    
    else:
        return json.dumps({"status": str(status.state), "msg": status.error.message, "code": str(status.error.error_code)})


table_full_name = os.environ["TABLE_FULL_NAME"]
warehouse_id = os.environ["WAREHOUSE_ID"] 
w = WorkspaceClient()
print("my user", w.current_user.me().display_name)
columns, col_types = get_columns(table_full_name)