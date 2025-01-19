from flask import Flask, request, jsonify
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceExistsError
import os
import json

app = Flask(__name__)

# Azure Storage Account details
connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING_1')
container_name = "task-box-storage"

# Initialize BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

# Ensure the container exists
try:
    container_client.create_container()
except ResourceExistsError:
    pass

@app.route('/check_blob', methods=['GET'])
def check_blob():
    """
    Checks if the user's blob exists.
    """
    username = request.args.get("username")
    if not username:
        return jsonify({"message": "Username is required"}), 400

    user_blob_name = f"{username}.json"
    blob_client = container_client.get_blob_client(user_blob_name)

    if blob_client.exists():
        return jsonify({"exists": True}), 200
    return jsonify({"exists": False}), 200

@app.route('/create_blob', methods=['POST'])
def create_blob():
    """
    Creates a blob for the user if it does not exist.
    """
    data = request.json
    username = data.get("username")
    if not username:
        return jsonify({"message": "Username is required"}), 400

    user_blob_name = f"{username}.json"
    blob_client = container_client.get_blob_client(user_blob_name)

    try:
        # Initialize the blob with an empty list of tasks
        blob_client.upload_blob(json.dumps([]), overwrite=False)
        return jsonify({"message": "Blob created successfully"}), 201
    except ResourceExistsError:
        return jsonify({"message": "Blob already exists"}), 400

@app.route('/add_task', methods=['POST'])
def add_task():
    """
    Adds a new task for the user.
    """
    task_data = request.json
    username = task_data.get("username")
    if not username:
        return jsonify({"message": "Username is required"}), 400

    user_blob_name = f"{username}.json"
    blob_client = container_client.get_blob_client(user_blob_name)

    # Check if the user's blob exists
    try:
        tasks_data = json.loads(blob_client.download_blob().readall().decode('utf-8'))
    except Exception:
        # Blob does not exist, create a new one
        tasks_data = []

    # Add new task
    new_task = {
        "id": len(tasks_data) + 1,
        "text": task_data["text"],
        "file_url": None,
        "completed": False
    }

    # Handle file upload (if exists)
    if 'file' in request.files:
        file = request.files['file']
        file_name = file.filename
        file_blob_client = container_client.get_blob_client(file_name)
        
        try:
            file_blob_client.upload_blob(file, overwrite=True)
            new_task['file_url'] = file_blob_client.url  # File URL from Azure Blob Storage
        except ResourceExistsError:
            return jsonify({"message": "File already exists"}), 400

    tasks_data.append(new_task)
    
    # Update the user's blob with the new task
    blob_client.upload_blob(json.dumps(tasks_data), overwrite=True)
    
    return jsonify({"message": "Task added successfully", "task": new_task}), 201

@app.route('/list_tasks', methods=['GET'])
def list_tasks():
    """
    Lists all tasks for the user.
    """
    username = request.args.get("username")
    if not username:
        return jsonify({"message": "Username is required"}), 400

    user_blob_name = f"{username}.json"
    blob_client = container_client.get_blob_client(user_blob_name)
    
    try:
        tasks_data = json.loads(blob_client.download_blob().readall().decode('utf-8'))
        return jsonify({"tasks": tasks_data})
    except Exception:
        return jsonify({"message": "No tasks found for this user"}), 404

@app.route('/mark_task_completed', methods=['POST'])
def mark_task_completed():
    """
    Marks a task as completed for the user.
    """
    task_data = request.json
    username = task_data.get("username")
    task_id = task_data.get("task_id")

    if not username or not task_id:
        return jsonify({"message": "Username and task ID are required"}), 400

    user_blob_name = f"{username}.json"
    blob_client = container_client.get_blob_client(user_blob_name)
    
    try:
        tasks_data = json.loads(blob_client.download_blob().readall().decode('utf-8'))
        task = next((t for t in tasks_data if t['id'] == task_id), None)
        if task:
            task['completed'] = True
            blob_client.upload_blob(json.dumps(tasks_data), overwrite=True)
            return jsonify({"message": "Task marked as completed", "task": task})
        else:
            return jsonify({"message": "Task not found"}), 404
    except Exception:
        return jsonify({"message": "No tasks found for this user"}), 404

if __name__ == '__main__':
    app.run(debug=True)
