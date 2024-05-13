import boto3
import os
import subprocess
import time
import json
import psutil
import zipfile
import shlex
import requests
import magic
from urllib.parse import urlencode
import yandexcloud
import io
import pathlib
import tempfile
import resource
import ydb
import ydb.iam
import matplotlib.pyplot as plt
import numpy as np

from yandex.cloud.lockbox.v1.payload_service_pb2 import GetPayloadRequest
from yandex.cloud.lockbox.v1.payload_service_pb2_grpc import PayloadServiceStub


# ---
# YC Integration
# ---

boto_session = None
storage_client = None
docapi_table = None
ymq_queue = None
tests_table = None
driver = None
ydb_session = None


def get_ydb_session():
    global driver
    global ydb_session
    if driver is not None and ydb_session is not None:
        return ydb_session
    driver = ydb.Driver(
        endpoint=os.getenv("YDB_ENDPOINT"),
        database=os.getenv("YDB_DATABASE"),
        credentials=ydb.iam.MetadataUrlCredentials(),
    )

    driver.wait(fail_fast=True, timeout=5)
    ydb_session = ydb.SessionPool(driver)
    return ydb_session


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

    print("DEBUG | Boto3 connection set with `key_id` = " + access_key)

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


def get_docapi_table(table):
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
        .Table(f"{table}")
    )

    return docapi_table


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


def upload_file_to_s3(file_obj, bucket, object_name):
    # Structure: path, bucket-name, path
    get_storage_client().upload_file(file_obj, bucket, object_name)


# ---
# Processing helpers
# ---


def validate_input(file_path, language, mode="unit"):
    if not os.path.isfile(file_path):
        print("DEBUG | Validation failed -- no such file!")
        return False

    directory = os.path.abspath(os.path.dirname(file_path))

    file_type = magic.from_file(file_path, mime=True)
    if file_type != "application/zip":
        print("DEBUG | Validation failed -- not a zip file!")
        return False

    file_size = os.path.getsize(file_path)
    if file_size > 5 * 1024 * 1024:
        print("DEBUG | Validation failed -- size exceeded!")
        return False

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        zip_ref.extractall(directory)

    if language not in ["python", "cpp"]:
        print("DEBUG |  Validation failed -- incorrect language: ", language)
        return False

    # Uncomment to enable single-file-only testing.
    """
    file_count = 0
    correct_file_count = 0
    for root, dirs, files in os.walk(directory):
        file_count += len(files)
        for file in files:
            if file.endswith(".zip"):
                continue
            if file.endswith(".py") if language == "python" else file.endswith(".cpp"):
                correct_file_count += 1
                if file_count > 1:
                    print("DEBUG | Validation failed -- more than 1 file")
                    # return False
                if file != "main.py" and language == "python":
                    os.rename(os.path.join(root, file), os.path.join(root, "main.py"))
                elif file != "main.cpp" and language == "cpp":
                    os.rename(os.path.join(root, file), os.path.join(root, "main.cpp"))

    if correct_file_count == 0:
        print("DEBUG | Validation failed -- no files found!")
        return False
    """

    print("DEBUG | Validating files in `DIRECTORY` = ", directory)
    path_test = directory + "/solution.py"
    print("DEBUG | Validating file with path `PATH_TEST` = ", path_test)
    print("DEBUG | Does the given file exist? :", os.path.exists(path_test))

    print("DEBUG | Validation has gone successfully!")
    return True


def download_from_bucket(object_name, n):
    try:
        pathlib.Path(f"/tmp/testing/{n}_in.txt").parent.mkdir(
            parents=True, exist_ok=True
        )
        pathlib.Path(f"/tmp/testing/{n}_out.txt").parent.mkdir(
            parents=True, exist_ok=True
        )

        print("DEBUG | Created a libraries for temp files in a download from bucket!")
        client = get_storage_client()
        bucket = "hw6-for-upload"
        client.download_file(
            bucket, object_name + f"_{n}_in.txt", f"/tmp/testing/{n}_in.txt"
        )
        client.download_file(
            bucket, object_name + f"_{n}_out.txt", f"/tmp/testing/{n}_out.txt"
        )
        print("DEBUG | Download of object_name = ", object_name, " went successfully!")
    except Exception as e:
        print(f"DEBUG | Caught exception in download from bucket! Error: {str(e)}")
        return False


def download_from_ya_disk(public_key, dst, language, mode="unit"):
    try:
        directory = os.path.dirname(dst)
        if not os.path.exists(directory):
            os.makedirs(directory)  # for missing dir fix

        api_call_url = (
            "https://cloud-api.yandex.net/v1/disk/public/resources/download?"
            + urlencode(dict(public_key=public_key))
        )
        response = requests.get(api_call_url)
        print(f"DEBUG | API call response: {response.json()}")
        if response.status_code != 200:
            raise Exception(f"Error in API call: {response.status_code}")

        download_url = response.json()["href"]
        print(f"DEBUG | Download URL: {download_url}")
        download_response = requests.get(download_url)
        print(f"DEBUG | Download response status code: {download_response.status_code}")
        print(f"DEBUG | Download response content: {download_response.content}")

        if download_response.status_code != 200:
            raise Exception(
                f"Error in download request: {download_response.status_code}"
            )

        with open(dst, "wb") as zip_file:
            zip_file.write(download_response.content)
            print("DEBUG | Downloaded successfully!")
    except Exception as e:
        print(f"DEBUG | Caught exception in download! Error: {str(e)}")
        return False
    return validate_input(dst, language, mode)


# ---


def run_cpp(tests, task_id):
    subprocess.run(["g++", "-o", "main", f"/tmp/{task_id}/main.cpp"])

    results = []
    for test in tests:
        # input_file = "input.txt"
        # output_file = "output.txt"
        # NOTE: filesystem is read-only!
        # Consider it if adding new code for your own tests
        # with open(input_file, "w") as f:
        #     f.write(test["input"])
        start_time = time.time()
        # TODO -- fix mess
        subprocess.run(["./main", "<", input_file, ">", output_file])
        end_time = time.time()
        with open(output_file, "r") as f:
            output = f.read()
        results.append(
            {
                "input": test["input"],
                "output": output,
                "expected_output": test["output"],
                "time": end_time - start_time,
                "memory_usage": get_memory_usage(),
            }
        )

    total_time = sum(result["time"] for result in results)
    total_memory_usage = sum(result["memory_usage"] for result in results)
    average_time = total_time / len(results)
    average_memory_usage = total_memory_usage / len(results)

    table = dynamodb.Table("results")
    table.put_item(
        Item={
            "id": event["code_id"],
            "results": results,
            "average_time": average_time,
            "average_memory_usage": average_memory_usage,
        }
    )

    return {"statusCode": 200, "statusMessage": "OK"}


def set_memory_limit(limit):
    # Convert limit from bytes MB + set mem_limit (also in MB)
    limit_bytes = limit * 1024 * 1024

    resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))


def plot_graphs(solutions, task_id, user_avg_time_usage, user_avg_memory_usage):

    # Uncomment for DB debug!
    """
    try:
        print(solutions)
    except Exception as e:
        print(
            f"DEBUG | Solutions were not found or can't be printed. Error here: {str(e)}"
        )
    """

    sorted_solutions_time = sorted(solutions, key=lambda x: x["avg_time_usage"])
    sorted_solutions_memory = sorted(solutions, key=lambda x: x["avg_memory_usage"])

    avg_time_usages = [sol["avg_time_usage"] for sol in sorted_solutions_time]
    avg_memory_usages = [sol["avg_memory_usage"] for sol in sorted_solutions_memory]

    # Time usage graph (1)
    plt.figure(figsize=(10, 5))
    plt.plot(avg_time_usages, marker="o")
    plt.scatter(
        avg_time_usages.index(user_avg_time_usage),
        user_avg_time_usage,
        color="red",
        zorder=5,
        label="Your solution!",
    )
    plt.xlabel("Percentage of solutions")
    plt.ylabel("Runtime (in ms)")
    plt.title("Average runtime usage distribution")
    plt.legend()
    # time_usage_file = io.BytesIO()
    # plt.savefig(time_usage_file, format='png')
    # time_usage_file.seek(0)
    pathlib.Path("/tmp/data/avg_time_usage.png").parent.mkdir(
        parents=True, exist_ok=True
    )
    plt.savefig("/tmp/data/avg_time_usage.png")
    upload_file_to_s3(
        "/tmp/data/avg_time_usage.png", "hw-6", f"graphs/time/{task_id}.png"
    )

    # Memory_usage graph (2)
    plt.figure(figsize=(10, 5))
    plt.plot(avg_memory_usages, marker="o")
    plt.scatter(
        avg_memory_usages.index(user_avg_memory_usage),
        user_avg_memory_usage,
        color="red",
        zorder=5,
        label="Your solution",
    )
    plt.xlabel("Percentage of solutions")
    plt.ylabel("Memory (in MB)")
    plt.title(f"Average memory usage distribution for task #.")
    plt.legend()
    pathlib.Path("/tmp/data/avg_memory_usage.png").parent.mkdir(
        parents=True, exist_ok=True
    )
    plt.savefig("/tmp/data/avg_memory_usage.png")
    upload_file_to_s3(
        "/tmp/data/avg_memory_usage.png", "hw-6", f"graphs/memory/{task_id}.png"
    )
    print("DEBUG | Uploads of graphs went successfully!")


def plot_graphs_alternative(
    solutions, task_id, user_avg_time_usage, user_avg_memory_usage, contest, task_n
):
    print("DEBUG | Plotting - 1 passed!")

    avg_time_usages = [sol["avg_time_usage"] for sol in solutions]
    avg_memory_usages = [sol["avg_memory_usage"] for sol in solutions]
    print("DEBUG | Plotting - 2 passed!")

    time_bins = np.linspace(min(avg_time_usages), max(avg_time_usages), 10)
    memory_bins = np.linspace(min(avg_memory_usages), max(avg_memory_usages), 10)
    print("DEBUG | Plotting - 3 passed!")

    time_histogram, _ = np.histogram(avg_time_usages, bins=time_bins)
    memory_histogram, _ = np.histogram(avg_memory_usages, bins=memory_bins)

    total_solutions = len(solutions)
    time_percentage = (time_histogram / total_solutions) * 100
    memory_percentage = (memory_histogram / total_solutions) * 100
    print("DEBUG | Plotting - 4 passed!")
    # Time usage graph (1)
    plt.figure(figsize=(10, 5))
    plt.bar(
        time_bins[:-1],
        time_percentage,
        width=np.diff(time_bins),
        align="edge",
        edgecolor="black",
    )
    plt.scatter(user_avg_time_usage, 0, color="red", label="Your solution", zorder=5)
    plt.xlabel("Average runtime usage (in MS)")
    plt.ylabel("Percentage of Solutions")
    plt.title(f"Runtime distribution for task {contest}#{task_n}.")
    plt.legend()
    print("DEBUG | Plotting - 5 passed!")
    pathlib.Path(f"/tmp/data/time_distribution_{task_id}.png").parent.mkdir(
        parents=True, exist_ok=True
    )
    plt.savefig(f"/tmp/data/time_distribution_{task_id}.png")
    print("DEBUG | Plotting - 6 passed!")
    upload_file_to_s3(
        f"/tmp/data/time_distribution_{task_id}.png",
        "hw-6",
        f"graphs/time_distribution/{task_id}.png",
    )
    print("DEBUG | Plotting - 7 passed!")

    # Memory usage graph (2)
    plt.figure(figsize=(10, 5))
    plt.bar(
        memory_bins[:-1],
        memory_percentage,
        width=np.diff(memory_bins),
        align="edge",
        edgecolor="black",
    )
    plt.scatter(user_avg_memory_usage, 0, color="red", label="Your solution", zorder=5)
    plt.xlabel("Average memory usage (in MB)")
    plt.ylabel("Percentage of solutions")
    plt.title(f"Memory usage distribution for task {contest}#{task_n}.")
    plt.legend()
    pathlib.Path(f"/tmp/data/memory_distribution_{task_id}.png").parent.mkdir(
        parents=True, exist_ok=True
    )
    plt.savefig(f"/tmp/data/memory_distribution_{task_id}.png")
    upload_file_to_s3(
        f"/tmp/data/memory_distribution_{task_id}.png",
        "hw-6",
        f"graphs/memory_distribution/{task_id}.png",
    )

    print("DEBUG | Uploads of graphs went successfully!")


def run_python(tests_response, task_id, key_test):
    time_limits = []
    memory_limits = []
    print(tests_response)
    tests_total = int(tests_response["total"])
    time_limit = int(tests_response["tl"])
    memory_limit = int(tests_response["ml"])
    for i in range(1, tests_total + 1):
        print(f"DEBUG | TEST_{i} started!")  # , tests_response[f"{str(i)}_in"])
        # test = tests_response[f"{str(i)}_in"]
        download_from_bucket(key_test, str(i))
        input_file_path = f"/tmp/testing/{str(i)}_in.txt"
        output_file_path = f"/tmp/testing/{str(i)}_out.txt"
        # NOTE: We work in read-only fs, so we use
        # temporary files

        try:
            # Run the program with a timeout and memory limit
            # NOTE: Comment for unlimited usage
            # set_memory_limit(memory_limit)
            memory_usage_before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss

            with tempfile.NamedTemporaryFile(delete=False) as output_temp:
                process = subprocess.Popen(
                    ["python3", f"/tmp/{task_id}/solution.py"],
                    stdin=open(input_file_path, "r"),
                    stdout=output_temp,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                output, error = process.communicate(timeout=time_limit)

                start_time = time.time()
                while True:
                    if process.poll() is not None:
                        break
                    if time.time() - start_time > time_limit:
                        process.kill()
                        raise subprocess.TimeoutExpired(
                            "Program took too long to run (time limit exceeded)",
                        )
                    time.sleep(0.1)

                end_time = time.time()
                elapsed_time = float(end_time - start_time)
                memory_usage_tmp = resource.getrusage(
                    resource.RUSAGE_CHILDREN
                ).ru_maxrss
                memory_usage = float(
                    max(memory_usage_tmp - memory_usage_before, 0) / 1024
                )
                time_limits.append(elapsed_time)
                memory_limits.append(memory_usage)

            with open(output_temp.name, "r") as f:
                program_output = f.read()

            with open(output_file_path, "r") as f:
                correct_output = f.read()

            if program_output.strip() != correct_output.strip():
                get_docapi_table("tasks").update_item(
                    Key={"task_id": task_id},
                    AttributeUpdates={
                        "status": {"Value": "DONE", "Action": "PUT"},
                        "result": {"Value": "WA", "Action": "PUT"},
                        "test_failed": {"Value": f"{i}", "Action": "PUT"},
                    },
                )
                return

        except subprocess.CalledProcessError as e:
            # Runtime error (non-zero exit code)
            get_docapi_table("tasks").update_item(
                Key={"task_id": task_id},
                AttributeUpdates={
                    "status": {"Value": "DONE", "Action": "PUT"},
                    "result": {"Value": "RE", "Action": "PUT"},
                    "test_failed": {"Value": f"{i}", "Action": "PUT"},
                    "output": {"Value": f"{str(e)}", "Action": "PUT"},
                },
            )
            """
            results.append(
                {
                "input": test["input"],
                "output": "",
                "expected_output": test["output"],
                "time": 0,
                "memory_usage": current_memory,
                "error": str(e),
                }
            )
            """
            return
        except MemoryError as e:
            # Memory limit
            get_docapi_table("tasks").update_item(
                Key={"task_id": task_id},
                AttributeUpdates={
                    "status": {"Value": "DONE", "Action": "PUT"},
                    "result": {"Value": "ML", "Action": "PUT"},
                    "test_failed": {"Value": f"{i}", "Action": "PUT"},
                    "output": {"Value": f"{str(e)}", "Action": "PUT"},
                },
            )
            return
        except subprocess.TimeoutExpired as e:
            # Time limit
            get_docapi_table("tasks").update_item(
                Key={"task_id": task_id},
                AttributeUpdates={
                    "status": {"Value": "DONE", "Action": "PUT"},
                    "result": {"Value": "TL", "Action": "PUT"},
                    "test_failed": {"Value": f"{i}", "Action": "PUT"},
                    "output": {"Value": f"{str(e)}", "Action": "PUT"},
                },
            )
            """
            results.append(
                {
                "input": test["input"],
                "output": "",
                "expected_output": test["output"],
                "time": 0,
                "memory_usage": current_memory,
                "error": f"Program took too long to run (time limit: {time_limit:.2f}s)",
                }
            )
            """
            return
        except Exception as e:
            # Other errors
            """
            results.append(
                {
                "input": test["input"],
                "output": "",
                "expected_output": test["output"],
                "time": 0,
                "memory_usage": current_memory,
                "error": str(e),
                }
            )
            """
            get_docapi_table("tasks").update_item(
                Key={"task_id": task_id},
                AttributeUpdates={
                    "status": {"Value": "DONE", "Action": "PUT"},
                    "result": {"Value": "UB", "Action": "PUT"},
                    "test_failed": {"Value": f"{i}", "Action": "PUT"},
                    "output": {"Value": f"{str(e)}", "Action": "PUT"},
                },
            )
            return
        else:
            print("DEBUG | Passed all tests, proceeding to ydb & graphs...")
            # Successful
            # output = output_data
            """
            results.append(
                {
                "input": test["input"],
                "output": output,
                "expected_output": test["output"],
                "time": time.time() - current_time,
                "memory_usage": memory_usage,
                }
            )
            """

            # os.remove(output_file)

            """
            correct_output = tests_response[f"{str(i)}_out"]

            if output != correct_output:
                get_docapi_table("tasks").update_item(
                    Key={"task_id": task_id},
                    AttributeUpdates={
                        "status": {"Value": "DONE", "Action": "PUT"},
                        "result": {"Value": "WA", "Action": "PUT"},
                        "test_failed": {"Value": f"{i}", "Action": "PUT"},
                        # "output": {"Value": f"{str(e)}", "Action": "PUT"},
                    },
                )
                return
            """
        # finally:
        # Restore original memory limit
        # set_memory_limit(resource.RLIM_INFINITY)
    # TODO -- avg memory usage
    avg_time_usage = sum(time_limits) / len(time_limits)
    avg_memory_usage = sum(memory_limits) / len(memory_limits)

    min_time_usage = min(time_limits)
    max_time_usage = max(time_limits)

    min_memory_usage = min(memory_limits)
    max_memory_usage = max(memory_limits)

    contest, task_n = key_test.split("_")
    task_n = int(task_n)

    yql = """
    DECLARE $task_id AS Utf8;
    DECLARE $contest AS Utf8;
    DECLARE $task_n AS Int32;
    DECLARE $code_quality AS Int32;
    DECLARE $quality_comment AS Utf8;
    DECLARE $code_style AS Int32;
    DECLARE $style_comment AS Utf8;
    DECLARE $avg_time_usage AS Double;
    DECLARE $min_time_usage AS Double;
    DECLARE $max_time_usage AS Double;
    DECLARE $avg_memory_usage AS Double;
    DECLARE $min_memory_usage AS Double;
    DECLARE $max_memory_usage AS Double;
    UPSERT INTO `Results` (`task_id`, `contest`, `task_n`, `code_quality`, `quality_comment`, `code_style`, `style_comment`, `avg_time_usage`, `min_time_usage`, `max_time_usage`, `avg_memory_usage`, `min_memory_usage`, `max_memory_usage`) 
    VALUES ($task_id, $contest, $task_n, $code_quality, $quality_comment, $code_style, $style_comment, $avg_time_usage, $min_time_usage, $max_time_usage, $avg_memory_usage, $min_memory_usage, $max_memory_usage);
    """

    # Yql params (change this + table + query_form for additional params)
    params = (
        task_id,
        contest,
        task_n,
        0,
        "_",
        0,
        "_",
        avg_time_usage,
        min_time_usage,
        max_time_usage,
        avg_memory_usage,
        min_memory_usage,
        max_memory_usage,
    )

    def add_another_test(session):
        prepared_yql = session.prepare(yql)
        tmp_result = session.transaction(ydb.SerializableReadWrite()).execute(
            prepared_yql,
            {
                "$task_id": params[0],
                "$contest": params[1],
                "$task_n": params[2],
                "$code_quality": params[3],
                "$quality_comment": params[4],
                "$code_style": params[5],
                "$style_comment": params[6],
                "$avg_time_usage": params[7],
                "$min_time_usage": params[8],
                "$max_time_usage": params[9],
                "$avg_memory_usage": params[10],
                "$min_memory_usage": params[11],
                "$max_memory_usage": params[12],
            },
            commit_tx=True,
            # For timeouts (in case of long query), remove for testing scenario
            settings=ydb.BaseRequestSettings()
            .with_timeout(3)
            .with_operation_timeout(2),
        )

        try:
            print("DEBUG | Showing result for transation exectuion: \n", tmp_result)
        except:
            print("DEBUG | Unable to show results for transaction execution")

    get_ydb_session().retry_operation_sync(add_another_test)

    # return result
    # Uncomment for query debug
    """
    try:
        print("DEBUG | Showing query results for UPSERT: \n", operation_status)
    except:
        print("DEBUG | Unable to show query results for UPSERT")
    """

    yql = """
        DECLARE $contest AS Utf8;
        DECLARE $task_n AS Int64;

        SELECT
            task_id,
            avg_time_usage,
            avg_memory_usage
        FROM Results
        WHERE contest = $contest AND task_n = $task_n;
    """

    params = (contest, task_n)

    def get_solutions(session):
        prepared_yql = session.prepare(yql)
        tmp_result = session.transaction(ydb.SerializableReadWrite()).execute(
            prepared_yql,
            {
                "$contest": contest,
                "$task_n": task_n,
            },
            commit_tx=True,
            settings=ydb.BaseRequestSettings()
            .with_timeout(3)
            .with_operation_timeout(2),
        )

        try:
            print("DEBUG | Showing result for transation-2 exectuion: \n", tmp_result)
        except:
            print("DEBUG | Unable to show results for transaction-2 execution")

        solutions = [
            {
                "avg_time_usage": row.avg_time_usage,
                "avg_memory_usage": row.avg_memory_usage,
                "task_id": row.task_id,
            }
            for row in tmp_result[0].rows
        ]

        return solutions

    solutions = get_ydb_session().retry_operation_sync(get_solutions)

    yql = """
        DECLARE $task_id AS String;

        SELECT
            avg_time_usage,
            avg_memory_usage
        FROM solutions
        WHERE task_id = $task_id;
    """

    # For monitoring mostly since here we have avg_X_metrics already!
    def get_user_solution(session):
        prepared_yql = session.prepare(yql)
        result = session.transaction(ydb.SerializableReadWrite()).execute(
            prepared_yql,
            {
                "$task_id": task_id,
            },
            commit_tx=True,
            settings=ydb.BaseRequestSettings()
            .with_timeout(3)
            .with_operation_timeout(2),
        )

        return result[0]

    # Uncomment for debug!
    # cur_solution = get_ydb_session().retry_operation_sync(get_user_solution)
    try:
        plot_graphs_alternative(
            solutions, task_id, avg_time_usage, avg_memory_usage, contest, task_n
        )
    except Exception as e:
        print(f"DEBUG | Countered error while plotting graphs, info: {str(e)}!")

    # Add or remove info for your system (if you need additional metrics)
    get_docapi_table("tasks").update_item(
        Key={"task_id": task_id},
        AttributeUpdates={
            "status": {"Value": "DONE", "Action": "PUT"},
            "result": {"Value": "OK", "Action": "PUT"},
            "avg_time_limit": {"Value": f"{avg_time_usage}", "Action": "PUT"},
            "avg_memory_limit": {"Value": f"{avg_memory_usage}", "Action": "PUT"},
            "min_time_limit": {"Value": f"{min_time_usage}", "Action": "PUT"},
            "min_memory_limit": {"Value": f"{min_memory_usage}", "Action": "PUT"},
            "max_time_limit": {"Value": f"{max_time_usage}", "Action": "PUT"},
            "max_memory_limit": {"Value": f"{max_memory_usage}", "Action": "PUT"},
            # "test_failed": {"Value": f"i", "Action": "PUT"},
            # "output": {"Value": f"{str(e)}", "Action": "PUT"},
        },
    )

    # Clean up the output file
    # os.remove(output_file)
    # return results
    return


def get_memory_usage():
    return psutil.Process().memory_info().rss


"""
def process_standart(task_json):
    # TODO -- rewrite into process_X (X = standart / presigned?)
    return
"""


def handler(event, context):
    for message in event["messages"]:
        print(message)
        task_json = None
        processing = "standart"
        try:
            task_json = json.loads(message["details"]["message"]["body"])
        except:
            print("DEBUG | Unknown message format, check YMQ docs!")
            return

        task_id = None
        src_url = None
        course = None
        contest = None
        language = None
        task_n = None
        if processing == "standart":
            task_id = task_json["task_id"]
            src_url = task_json["src_url"]
            course = task_json["course"]
            contest = task_json["contest"]
            language = task_json["language"]
            task_n = task_json["task_n"]
        else:
            return
            # TODO

        get_docapi_table("tasks").update_item(
            Key={"task_id": task_id},
            AttributeUpdates={
                "status": {"Value": "PROCESSING", "Action": "PUT"},
            },
        )

        path = f"/tmp/{task_id}/solution.zip"
        # path = "/tmp/solution.zip"

        is_input_valid = None
        if processing == "standart":
            is_input_valid = download_from_ya_disk(src_url, path, language)
            if not is_input_valid:
                get_docapi_table("tasks").update_item(
                    Key={"task_id": task_id},
                    AttributeUpdates={
                        "status": {"Value": "REQS_NOT_PASSED", "Action": "PUT"},
                    },
                )
                return
        else:
            # download_from_bucket(task_json)
            # is_input_valid = validate_input("/tmp/image.jpg")
            return

        try:
            test_id = "basic_1"
            get_tests_table().update_item(
                Key={"test_id": test_id},
                AttributeUpdates={
                    "total": {"Value": "2", "Action": "PUT"},
                    "tl": {"Value": "100", "Action": "PUT"},
                    "ml": {"Value": "1000", "Action": "PUT"},
                },
            )
            """
            Item={
                    "test_id": "basic_1",
                    "total": 2,
                    "tl": 100,
                    "ml": 1000,
                }
            """
            print("DEBUG| Put_item --> OK!")
        except:
            # ...
            print("DEBUG | Put_item --> Error!")

        key_test = str(contest) + "_" + str(task_n)
        tests_response = get_tests_table().get_item(Key={"test_id": key_test})["Item"]

        if language == "cpp":
            results = run_cpp(tests, task_id)
        elif language == "python":
            results = run_python(tests_response, task_id, key_test)
        else:
            raise ValueError("Unsupported language")

    return
