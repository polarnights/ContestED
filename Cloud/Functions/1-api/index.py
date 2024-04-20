import json
import os
import subprocess
import uuid
from urllib.parse import urlencode
import setuptools

import boto3
import requests
import yandexcloud

from yandex.cloud.lockbox.v1.payload_service_pb2 import GetPayloadRequest
from yandex.cloud.lockbox.v1.payload_service_pb2_grpc import PayloadServiceStub

boto_session = None
storage_client = None
docapi_table = None
ymq_queue = None


def get_boto_session():
    global boto_session
    if boto_session is not None:
        return boto_session

    # initialize Lockbox and read secret value
    yc_sdk = yandexcloud.SDK()
    channel = yc_sdk._channels.channel("lockbox-payload")
    lockbox = PayloadServiceStub(channel)
    response = lockbox.Get(GetPayloadRequest(secret_id=os.environ["SECRET_ID"]))

    # extract values from secret
    access_key = None
    secret_key = None
    for entry in response.entries:
        if entry.key == "ACCESS_KEY_ID":
            access_key = entry.text_value
        elif entry.key == "SECRET_ACCESS_KEY":
            secret_key = entry.text_value

    if access_key is None or secret_key is None:
        raise Exception("Secrets required")

    print("Key id: " + access_key)

    # initialize boto session
    boto_session = boto3.session.Session(
        aws_access_key_id=access_key, aws_secret_access_key=secret_key
    )

    return boto_session


def get_ymq_queue():
    global ymq_queue
    if ymq_queue is not None:
        return ymq_queue

    ymq_queue = (
        get_boto_session()
        .resource(
            service_name="sqs",
            endpoint_url="https://message-queue.api.cloud.yandex.net",
            region_name="ru-central1",
        )
        .Queue(os.environ["YMQ_QUEUE_URL"])
    )

    return ymq_queue


def get_docapi_table():
    global docapi_table
    if docapi_table is not None:
        return docapi_table

    docapi_table = (
        get_boto_session()
        .resource(
            "dynamodb",
            endpoint_url=os.environ["DOCAPI_ENDPOINT"],
            region_name="ru-central1",
        )
        .Table("tasks")
    )

    return docapi_table


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


# -------


def create_task(src_url, course, contest, language, task_n):
    task_id = str(uuid.uuid4())

    get_docapi_table().put_item(Item={"task_id": task_id, "status": "NEW"})
    get_ymq_queue().send_message(
        MessageBody=json.dumps(
            {
                "task_id": task_id,
                "type": "standart",
                "src": src_url,
                "course": course,
                "contest": contest,
                "language": language,
                "task_n": task_n,
            }
        )
    )

    data = {"task_id": task_id}
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(data),
    }


def create_task_alternative(course, contest, language, task_n):
    task_id = str(uuid.uuid4())

    upload_here = generate_presigned_upload(task_id, course, contest, language, task_n)

    """
    get_ymq_queue().send_message(
        MessageBody=json.dumps({"task_id": task_id, "src": src_url, "model": model})
    )
    """

    get_docapi_table().put_item(
        Item={"task_id": task_id, "status": "WAITING_FOR_UPLOAD"}
    )

    # return {"task_id": task_id, "upload_here": upload_here}
    data = {"task_id": task_id, "upload_here": upload_here}
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(data),
    }


def generate_presigned_upload(task_id, course, contest, language, task_n):
    client = get_storage_client()
    bucket = "hw6-for-upload"
    content_type = (
        "application/zip"  # specify the content type of the object being uploaded
    )

    presigned_post = client.generate_presigned_post(
        Bucket=bucket,
        Key=task_id
        + "_"
        + course
        + "_"
        + contest
        + "_"
        + language
        + "_"
        + task_n
        + ".jpg",
        # Fields={"content-type": content_type},
        # Conditions=[
        #    {
        #        "content-length-range": 0, 5242880,
        #    },  # specify the maximum file size (5 MB)
        # ],
        ExpiresIn=100,
    )

    return presigned_post


def get_task_status(task_id):
    task = get_docapi_table().get_item(Key={"task_id": task_id})
    if task["Item"]["status"] == "DONE":
        data = {"status": "DONE", "info": task["Item"]["info"]}
        return {
            "statusCode": 200,
            "headers": {"content-type": "application/json"},
            "body": json.dumps(data),
        }

    data = {"status": task["Item"]["status"]}
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(data),
    }


# check_post -- проверка через presigned url
# check_disk -- проверка через загрузку с диска

# Параметры:

# 1) src_url -- Source URL -- откуда выгружать файл (нужна проверка, что он .zip)
# 2) task_id -- ID задачи (если смотрим статус) (!)
# 3) course -- название курса
# 4) contest -- номер контеста
# 5) language -- язык для тестирования
# 6) task_n -- номер задачи


def handle_api(event, context):
    print(event)
    action = event.get("action", event.get("params", {}).get("action", None))
    if action == "check_disk":
        src_url = event.get("params", event).get("src_url", None)
        course = event.get("params", event).get("course", None)
        contest = event.get("params", event).get("contest", None)
        language = event.get("params", event).get("language", None)
        task_n = event.get("params", event).get("task_n", None)
        if src_url and course and contest and language and task_n:
            return create_task(src_url, course, contest, language, task_n)
        else:
            return {"error": "Missing parameters!"}
    elif action == "get_task_status":
        task_id = event.get("params", event).get("task_id", None)
        if task_id:
            return get_task_status(task_id)
        else:
            return {"error": "Missing task_id in params"}
    elif action == "check_post":
        course = event.get("params", event).get("course", None)
        contest = event.get("params", event).get("contest", None)
        language = event.get("params", event).get("language", None)
        task_n = event.get("params", event).get("task_n", None)
        if course and contest and language and task_n:
            return create_task_alternative(course, contest, language, task_n)
        else:
            return {"error": "Missing parameters!"}
    elif action == "info":
        data = {
            "actions": {
                "check_post": {
                    "description": "Проверка с загрузкой файла через presigned url."
                },
                "check_disk": {
                    "description": "Проверка с загрузкой файла с Яндекс.Диска."
                },
                "get_task_status": {"description": "Узнать текущий статус задачи."},
                "check_disk": {
                    "description": "Проверка с загрузкой файла с Яндекс.Диска."
                },
                "info": {"description": "Получить список всех доступных комманд."},
            },
            "parameters": {
                "src_url": {
                    "description": "Ссылка на файл на Яндекс.Диске. Требуемый формат: '.zip'"
                },
                "task_id": {"description": "ID задачи для просмотра её статуса."},
                "course": {"description": "Название курса. Доступные варианты: TODO."},
                "contest": {"description": "Номер контеста."},
                "language": {"description": "Язык, на котором написано решение."},
                "task_n": {"description": "Номер задачи."},
            },
        }
        return {
            "statusCode": 200,
            "headers": {"content-type": "application/json"},
            "body": json.dumps(data),
        }
    else:
        return {"error": "Unknown action: " + action}
