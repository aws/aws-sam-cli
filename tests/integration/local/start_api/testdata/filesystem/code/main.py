import json
import os

EFS_MOUNT = "/mnt/efs"


def handler(event, context):
    """
    Lambda handler for testing EFS filesystem mounting
    """
    path = event.get("path", "")

    if path == "/read-file":
        # Read a file from mounted EFS
        filename = event.get("queryStringParameters", {}).get("filename", "")
        try:
            filepath = os.path.join(EFS_MOUNT, filename)
            with open(filepath, "r") as f:
                content = f.read()
            return {
                "statusCode": 200,
                "body": json.dumps({"success": True, "content": content, "filename": filename}),
            }
        except Exception as e:
            return {"statusCode": 500, "body": json.dumps({"success": False, "error": str(e)})}

    elif path == "/write-file":
        # Write a file to mounted EFS
        try:
            body = json.loads(event.get("body", "{}"))
            filename = body.get("filename", "")
            content = body.get("content", "")

            filepath = os.path.join(EFS_MOUNT, filename)
            with open(filepath, "w") as f:
                f.write(content)

            return {"statusCode": 200, "body": json.dumps({"success": True, "filename": filename})}
        except Exception as e:
            return {"statusCode": 500, "body": json.dumps({"success": False, "error": str(e)})}

    elif path == "/list-files":
        # List files in mounted EFS
        try:
            files = os.listdir(EFS_MOUNT)
            return {"statusCode": 200, "body": json.dumps({"success": True, "files": files, "mount_path": EFS_MOUNT})}
        except Exception as e:
            return {"statusCode": 500, "body": json.dumps({"success": False, "error": str(e)})}

    return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}
