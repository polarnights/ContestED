import os
import time
from locust import HttpUser, task, between
from locust.stats import stats_history
import matplotlib.pyplot as plt


SRC_URL = "<YOUR IP>"  # SETUP -- добавить IP решения
COURSE = "course"
LANGUAGE = "C++"
TASK_N = "1"
CONTEST = "basic"
# TASK_ID = "b0e6c50b-e5f9-49a8-b974-dde0f9a5f86e"

# SETUP -- добавить ваш API Gateway id
url = f"https://<YOUR APIGW ID>.apigw.yandexcloud.net/check_disk?action=check_disk&src_url={SRC_URL}&course={COURSE}&language={LANGUAGE}&task_n={TASK_N}&contest={CONTEST}"


class LinearUser(HttpUser):
    wait_time = between(0.1, 1)

    @task(1)
    def check_disk(self):
        self.client.get(url)


class ConstantUser(HttpUser):
    wait_time = 0.5

    @task(1)
    def check_disk(self):
        self.client.get(url)


class UnlimitedUser(HttpUser):
    wait_time = 0

    @task(1)
    def check_disk(self):
        self.client.get(url)


def run_load_testing(scenario, num_users, spawn_rate, run_time):
    os.environ["LOCUST_RUN_TIME"] = str(run_time)
    scenario.run(num_users, spawn_rate)


linear_stats = run_load_testing(LinearUser, 10, 1, 60)
constant_stats = run_load_testing(ConstantUser, 10, 1, 60)
unlimited_stats = run_load_testing(UnlimitedUser, 10, 1, 60)

linear_quantiles = stats_history.get("check_disk", "response_time_percentiles")
constant_quantiles = stats_history.get("check_disk", "response_time_percentiles")
unlimited_quantiles = stats_history.get("check_disk", "response_time_percentiles")

linear_codes = stats_history.get("check_disk", "response_codes")
constant_codes = stats_history.get("check_disk", "response_codes")
unlimited_codes = stats_history.get("check_disk", "response_codes")


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
ax[0].set_title("Linear Load Testing - HTTP Codes")
ax[1].bar(constant_codes.keys(), constant_codes.values())
ax[1].set_title("Constant Load Testing - HTTP Codes")
ax[2].bar(unlimited_codes.keys(), unlimited_codes.values())
ax[2].set_title("Unlimited Load Testing - HTTP Codes")
plt.show()
