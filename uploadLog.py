import os
import requests

def uploadLog(dir_name, file_paths):
    # Server's upload URL
    ipv4 = '16.171.140.7'  # Replace with your server's IP address
    upload_url = f'http://{ipv4}:3000/upload'

    # Create a list of files for upload
    files = []
    for file_path in file_paths:
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Set MIME type based on the file extension
        if file_extension == '.jpg' or file_extension == '.jpeg':
            mime_type = 'image/jpeg'
        elif file_extension == '.png':
            mime_type = 'image/png'
        elif file_extension == '.gif':
            mime_type = 'image/gif'
        elif file_extension == '.webp':
            mime_type = 'image/webp'
        else:
            print(f"Unsupported file type: {file_extension}")
            continue

        files.append(('images', (os.path.basename(file_path), open(file_path, 'rb'), mime_type)))  # Use basename to keep the original filename

    # Send the directory name as part of the request payload
    data = {'directory': dir_name}

    try:
        # Make the POST request to upload the files along with the directory name
        response = requests.post(upload_url, files=files, data=data)

        # Check if the request was successful
        if response.status_code == 200:
            print(f"Files uploaded successfully: {response.json()}")
        else:
            print(f"Failed to upload the files. Error: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"An error occurred: {e}")