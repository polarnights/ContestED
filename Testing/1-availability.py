import requests
import time
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

file_handler = logging.FileHandler("App/Testing/results.logs")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

while True:
    try:
        # SETUP -- добавьте ваш IP
        response = requests.get("<YOUR IP>")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Caught this exception: {e}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"Caught HTTP error: {e}")
    else:
        logger.info(f"Finished. Status_code: {response.status_code}")

    time.sleep(0.01)  # 10 ms delay
