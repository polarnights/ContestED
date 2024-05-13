import os
import time
from locust import HttpUser, task, between
from locust.stats import stats_history
import matplotlib.pyplot as plt


# TASK_ID = "b0e6c50b-e5f9-49a8-b974-dde0f9a5f86e"
# Change to your task_id (for testing)


# SETUP -- добавить ваш API Gateway id
url = f"https://<YOUR APIGW ID>.apigw.yandexcloud.net/status?action=status&task_id={TASK_ID}"


class LinearUser(HttpUser):
    # SETUP -- добавить ваш API Gateway id
    host = "https://<YOUR APIGW ID>.apigw.yandexcloud.net"
    wait_time = between(0.1, 1)

    @task(1)
    def check_status(self):
        self.client.get(url)

    def __init__(self, HttpUser):
        self.user = HttpUser


class ConstantUser(HttpUser):
    # SETUP -- добавить ваш API Gateway id
    host = "https://<YOUR APIGW ID>.apigw.yandexcloud.net"
    wait_time = 0.5

    @task(1)
    def check_status(self):
        self.client.get(url)

    def __init__(self, HttpUser):
        self.user = HttpUser


class UnlimitedUser(HttpUser):
    # SETUP -- добавить ваш API Gateway id
    host = "https://<YOUR APIGW ID>.apigw.yandexcloud.net"
    wait_time = 0

    @task(1)
    def check_status(self):
        self.client.get(url)

    def __init__(self, HttpUser):
        self.user = HttpUser


def run_load_testing(scenario_class, num_users, spawn_rate, run_time):
    scenario = scenario_class()
    scenario.environment = scenario.create_environment()
    scenario.environment.create_web_ui(host="0.0.0.0", port=8089)
    scenario.environment.runner.start(
        num_users, spawn_rate=spawn_rate, run_time=run_time
    )


linear_stats = run_load_testing(LinearUser, 10, 1, 60)
constant_stats = run_load_testing(ConstantUser, 10, 1, 60)
unlimited_stats = run_load_testing(UnlimitedUser, 10, 1, 60)


linear_quantiles = stats_history.get("check_status", "response_time_percentiles")
constant_quantiles = stats_history.get("check_status", "response_time_percentiles")
unlimited_quantiles = stats_history.get("check_status", "response_time_percentiles")

linear_codes = stats_history.get("check_status", "response_codes")
constant_codes = stats_history.get("check_status", "response_codes")
unlimited_codes = stats_history.get("check_status", "response_codes")


fig, ax = plt.subplots(1, 3, figsize=(15, 5))
ax[0].plot(linear_quantiles)
ax[0].set_title("Linear Load Testing - Quantiles")
ax[1].plot(constant_quantiles)
ax[1].set_title("Constant Load Testing - Quantiles")
ax[2].plot(unlimited_quantiles)
ax[2].set_title("Unlimited Load Testing - Quantiles")
plt.show()


fig, ax = plt.subplots(1, 3, figsize=(15, 5))
ax[0].bar(linear_codes.keys(), linear_codes.values())
ax[0].set_title("Linear Load Testing - HTTPCodes")
ax[1].bar(constant_codes.keys(), constant_codes.values())
ax[1].set_title("Constant Load Testing - HTTP Codes")
ax[2].bar(unlimited_codes.keys(), unlimited_codes.values())
ax[2].set_title("Unlimited Load Testing - HTTP Codes")
plt.show()
