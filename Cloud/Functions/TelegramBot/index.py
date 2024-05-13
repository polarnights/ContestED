import os
import requests
import json
import traceback
import boto3
import pathlib
import yandexcloud
import ydb
import ydb.iam

from yandex.cloud.lockbox.v1.payload_service_pb2 import GetPayloadRequest
from yandex.cloud.lockbox.v1.payload_service_pb2_grpc import PayloadServiceStub

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_ENDPOINT = "https://api.telegram.org/bot%s"
YDB_ENDPOINT = os.getenv("YDB_ENDPOINT")
YDB_DATABASE = os.getenv("YDB_DATABASE")

storage_client = None
driver = None
boto_session = None

try:
    driver = ydb.Driver(
        endpoint=YDB_ENDPOINT,
        database=YDB_DATABASE,
        credentials=ydb.iam.MetadataUrlCredentials(),
    )
    driver.wait(fail_fast=True, timeout=5)
    pool = ydb.SessionPool(driver)
except Exception as e:
    print(f"DEBUG | Error for driver in YDB! Error: {str(e)}")


def save_user_state(user_id, state):
    def run(session):
        query = """
        DECLARE $user_id AS Int64;
        DECLARE $state AS Utf8;

        UPSERT INTO Status (user_id, state) VALUES ($user_id, $state);
        """
        prepared_query = session.prepare(query)
        session.transaction(ydb.SerializableReadWrite()).execute(
            prepared_query, {"$user_id": user_id, "$state": state}, commit_tx=True
        )

    try:
        pool.retry_operation_sync(run)
    except Exception as e:
        print(f"DEBUG | Error in save_user_state! Error: {str(e)}")


def get_user_state(user_id):
    def run(session):
        query = """
        DECLARE $user_id AS Int64;

        SELECT state FROM Status WHERE user_id = $user_id;
        """
        prepared_query = session.prepare(query)
        result = session.transaction(ydb.SerializableReadWrite()).execute(
            prepared_query, {"$user_id": user_id}, commit_tx=True
        )
        if result[0].rows:
            return result[0].rows[0]["state"]
        return None

    try:
        return pool.retry_operation_sync(run)
    except Exception as e:
        print(f"DEBUG | Error in get_user_state! Error: {str(e)}")
        return None


def delete_user_state(user_id):
    def run(session):
        query = """
        DECLARE $user_id AS Int64;

        DELETE FROM Status WHERE user_id = $user_id;
        """
        prepared_query = session.prepare(query)
        session.transaction(ydb.SerializableReadWrite()).execute(
            prepared_query, {"$user_id": user_id}, commit_tx=True
        )

    try:
        pool.retry_operation_sync(run)
    except Exception as e:
        print(f"DEBUG | Error in delete_user_state! Error: {str(e)}")


def get_boto_session():
    global boto_session
    if boto_session is not None:
        return boto_session

    yc_sdk = yandexcloud.SDK()
    channel = yc_sdk._channels.channel("lockbox-payload")
    lockbox = PayloadServiceStub(channel)
    response = lockbox.Get(GetPayloadRequest(secret_id=os.environ["SECRET_ID"]))

    access_key = None
    secret_key = None
    for entry in response.entries:
        if entry.key == "ACCESS_KEY_ID":
            access_key = entry.text_value
        elif entry.key == "SECRET_ACCESS_KEY":
            secret_key = entry.text_value

    if access_key is None or secret_key is None:
        raise Exception("secrets required")

    print("DEBUG | Key_id = " + access_key)

    boto_session = boto3.session.Session(
        aws_access_key_id=access_key, aws_secret_access_key=secret_key
    )

    return boto_session


def get_storage_client():
    global storage_client
    if storage_client is not None:
        return storage_client

    storage_client = get_boto_session().client(
        service_name="s3",
        endpoint_url="https://storage.yandexcloud.net",
        region_name="ru-central1",
    )

    return storage_client


def download_from_bucket(bucket, object_name, d_path):
    try:
        pathlib.Path(d_path).parent.mkdir(parents=True, exist_ok=True)

        print("DEBUG | Created a libraries for temp files in a download from bucket!")
        client = get_storage_client()
        client.download_file(bucket, object_name, d_path)
        # client.download_file(bucket, object_name, f"/tmp/testing/{n}_out.txt")
        print("DEBUG | Download of object_name = ", object_name, " went successfully!")
    except Exception as e:
        print(f"DEBUG | Caught exception in download from bucket! Error: {str(e)}")
        return False


def send_message(chat_id, text, token=TELEGRAM_BOT_TOKEN, reply_markup=None):
    url = TELEGRAM_API_ENDPOINT % token + "/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    response = requests.post(url, json=data)
    print(response)
    return response


def send_image(chat_id, image_path, caption=None, token=TELEGRAM_BOT_TOKEN):
    url = TELEGRAM_API_ENDPOINT % token + "/sendPhoto"
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    with open(image_path, "rb") as image_file:
        files = {"photo": image_file}
        response = requests.post(url, data=data, files=files)
    # print(response)
    return response


def handle_message(sender, text):
    user_state = None
    try:
        user_state = get_user_state(sender)
        print(f"DEBUG | Sender = {sender}, user_state = {user_state}, flag={user_state == "awaiting_task_status"}")
    except Exception as e:
        print(f"Caught exception in get_user_state({sender}): {str(e)}")
    if user_state == "awaiting_task_status":
        task_id = text
        # delete_user_state(sender)
        print("DEBUG | Handling task_id started...")
        try:
            time_image_key = f"graphs/time_distribution/{task_id}.png"
            time_image_path = f"/tmp/{task_id}_time_distribution.png"
            download_from_bucket("hw-6", time_image_key, time_image_path)
            send_image(sender, time_image_path, caption="This is your runtime usage!")
            print("DEBUG | Successfully send image-1!")

            memory_image_key = f"graphs/memory_distribution/{task_id}.png"
            memory_image_path = f"/tmp/{task_id}_memory_distribution.png"
            download_from_bucket("hw-6", memory_image_key, memory_image_path)
            send_image(sender, memory_image_path, caption="This is your memory usage!")
            print("DEBUG | Successfully send image-2!")
            delete_user_state(sender)
            # for debug
            # response_text = f"Received your task_id = {task_id}!"
            # response = send_message(sender, response_text)
            # print(response)
        except Exception as e:
            print(f"DEBUG | Such `task_id` not found, try again!\n Error: {str(e)}")
            response_text = f"Such `task_id = {task_id}` not found, try again!\n Error: {str(e)}"
            response = send_message(sender, response_text)
            print(response)
    elif text == "/start":
        # Initial message with menu
        menu_text = "Choose an option:"
        reply_markup = {
            "inline_keyboard": [
                [{"text": "Task Conditions", "callback_data": "task_conditions"}],
                [{"text": "Solution Status", "callback_data": "solution_status"}],
            ]
        }
        response = send_message(sender, menu_text, reply_markup=reply_markup)
        print(response)
    else:
        print(f"DEBUG | Other messages handling...")
        # Handle regular text messages here
        pass


def handle_callback_query(callback_query):
    # Uncomment for debug
    print("Callback_query:")
    print(callback_query)
    query_data = callback_query["data"]
    chat_id = callback_query["message"]["chat"]["id"]

    if query_data == "task_conditions":
        # Send course selection menu
        course_text = "Choose a course:"
        reply_markup = {
            "inline_keyboard": [
                [{"text": "Basic", "callback_data": "course_basic"}],
                [{"text": "Advanced", "callback_data": "course_advanced"}],
            ]
        }
        response = send_message(chat_id, course_text, reply_markup=reply_markup)
        print(response)
    elif query_data == "solution_status":
        sender = callback_query["from"]["id"]
        print(f"DEBUG | For task status: sender={sender}, with type={type(sender)}!")
        save_user_state(sender, "awaiting_task_status")
        status_text = "Please enter your `task_id`:"
        response = send_message(chat_id, status_text)
        print(response)

    elif query_data.startswith("course_"):
        # Extract course name from query_data
        course_name = query_data.split("_")[1].capitalize()
        # Send contest selection menu
        contest_text = f"Choose a contest for {course_name} course:"
        reply_markup = {
            "inline_keyboard": [
                [{"text": "1 - Algorithms", "callback_data": "contest_algorithms"}],
                [{"text": "2 - Other", "callback_data": "contest_other"}],
            ]
        }
        response = send_message(chat_id, contest_text, reply_markup=reply_markup)
        print(response)
    elif query_data.startswith("contest_"):
        # Extract contest name from query_data
        contest_name = query_data.split("_")[1].capitalize()
        # Send task selection menu
        task_text = f"Choose a task for contest {contest_name}:"
        reply_markup = {
            "inline_keyboard": [
                [{"text": "Task 1", "callback_data": "task_1"}],
                [{"text": "Task 2", "callback_data": "task_2"}],
                [{"text": "Task 3", "callback_data": "task_3"}],
            ]
        }
        response = send_message(chat_id, task_text, reply_markup=reply_markup)
        print(response)
    elif query_data.startswith("task_"):
        # Extract task number from query_data
        task_number = query_data.split("_")[1]
        # Respond with the selected task
        task_text = f"You have selected Task {task_number}"
        response = send_message(chat_id, task_text)
        print(response)


def handler(event, context):
    try:
        body = json.loads(event["body"])

        if "message" in body:
            # Regular message handling
            message = body["message"]
            # Uncomment for debug
            print("Message:")
            print(message)
            sender = message["from"]["id"]
            text = message.get("text", "")
            handle_message(sender, text)
        elif "callback_query" in body:
            # Callback query handling
            callback_query = body["callback_query"]
            handle_callback_query(callback_query)

        return {"statusCode": 200, "body": "Message processed successfully"}
    except Exception as e:
        print("DEBUG | Error:", e)
        return {"statusCode": 500, "body": "Internal Server Error"}
