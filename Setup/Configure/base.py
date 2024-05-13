import magic
from urllib.parse import urlencode
import yandexcloud
import io
import pathlib
import tempfile
import resource
import boto3

from yandex.cloud.lockbox.v1.payload_service_pb2 import GetPayloadRequest
from yandex.cloud.lockbox.v1.payload_service_pb2_grpc import PayloadServiceStub


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

    print("Key id: " + access_key)

    boto_session = boto3.session.Session(
        aws_access_key_id=access_key, aws_secret_access_key=secret_key
    )

    return boto_session


def get_tests_table():
    global tests_table
    if tests_table is not None:
        return tests_table

    tests_table = (
        get_boto_session()
        .resource(
            "dynamodb",
            endpoint_url=os.environ["ENDPOINT_TESTS"],
            region_name="ru-central1",
        )
        .Table("tests")
    )

    return tests_table
