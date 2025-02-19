import json
import boto3
from boto3.dynamodb.conditions import Key
import hashlib
import decimal

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')

# Define table mappings and user authentication table
TABLE_NAMES = {
    'Employees': 'Employees',
    'LeaveRequests': 'LeaveRequests',
    'Documents': 'Documents',
    'Payroll': 'Payroll',
    'Performance': 'Performance'
}
AUTH_TABLE_NAME = 'HRUsers'
auth_table = dynamodb.Table(AUTH_TABLE_NAME)

# Decimal to float conversion
def decimal_default(obj):
    """Convert Decimal types to float for JSON serialization."""
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError("Type not serializable")

def lambda_handler(event, context):
    try:
        # Parse input body
        if 'body' in event and isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event

        # Check for authentication action
        action = body.get('action')
        if action in ['login', 'register']:
            username = body.get('username')
            password = body.get('password')

            if not username or not password:
                return generate_response(400, {"message": "Username and password are required."})

            if action == 'login':
                return handle_login(username, password)
            elif action == 'register':
                return handle_register(username, password)

        # Check for CRUD operation
        operation = body.get('operation')
        table_name_key = body.get('table_name')

        if not operation or not table_name_key:
            raise ValueError("Missing required fields: 'operation' or 'table_name'.")

        table_name = TABLE_NAMES.get(table_name_key)
        if not table_name:
            raise ValueError(f"Invalid table name: {table_name_key}")

        if operation == 'POST':
            return post_item(table_name, body)
        elif operation == 'GET':
            return get_item(table_name, body)
        elif operation == 'PUT':
            return update_item(table_name, body)
        elif operation == 'DELETE':
            return delete_item(table_name, body)
        else:
            raise ValueError("Invalid operation. Supported operations are: POST, GET, PUT, DELETE.")

    except Exception as e:
        print(f"Error: {str(e)}")
        return generate_response(500, {"message": "Internal server error.", "error": str(e)})

# Authentication Handlers
def handle_login(username, password):
    response = auth_table.get_item(Key={'username': username})
    user = response.get('Item')

    if not user:
        return generate_response(401, {"message": "Invalid username or password."})

    # Hash the provided password
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

    if hashed_password == user['password']: 
        token = f"token-{username}"
        return generate_response(200, {"authenticated": True, "token": token})
    else:
        return generate_response(401, {"message": "Invalid username or password."})

def handle_register(username, password):
    response = auth_table.get_item(Key={'username': username})
    if 'Item' in response:
        return generate_response(400, {"message": "Username already exists."})

    # Hash the password before storing
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    auth_table.put_item(Item={'username': username, 'password': hashed_password})
    return generate_response(201, {"message": "User registered successfully."})

# CRUD Handlers
def post_item(table_name, body):
    table = dynamodb.Table(table_name)
    item = body.get('body')
    if not item:
        raise ValueError("Missing 'body' in request for POST operation.")
    table.put_item(Item=item)
    return success_response("Item added successfully!")

def get_item(table_name, body):
    table = dynamodb.Table(table_name)
    key = body.get('key')
    if not key:
        raise ValueError("Missing 'key' in request for GET operation.")
    response = table.get_item(Key=key)
    if 'Item' in response:
        # Convert Decimal values to float for JSON serialization
        return success_response(response['Item'])
    else:
        return generate_response(404, {"message": "Item not found."})

def update_item(table_name, body):
    table = dynamodb.Table(table_name)
    key = body.get('key')
    updates = body.get('updates')

    if not key or not updates:
        raise ValueError("Missing 'key' or 'updates' in request for PUT operation.")

    update_expression = "SET " + ", ".join(f"#{k} = :{k}" for k in updates.keys())
    expression_attribute_names = {f"#{k}": k for k in updates.keys()}
    expression_attribute_values = {f":{k}": v for k, v in updates.items()}

    table.update_item(
        Key=key,
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values
    )
    return success_response("Item updated successfully!")

def delete_item(table_name, body):
    table = dynamodb.Table(table_name)
    key = body.get('key')
    if not key:
        raise ValueError("Missing 'key' in request for DELETE operation.")
    table.delete_item(Key=key)
    return success_response("Item deleted successfully!")

# Response Generators
def success_response(message, status_code=200):
    return {
        "statusCode": status_code,
        "body": json.dumps({"message": message}, default=decimal_default)
    }

def generate_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body, default=decimal_default)
    }
