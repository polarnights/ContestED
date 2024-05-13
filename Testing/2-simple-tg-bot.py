import requests

TELEGRAM_BOT_TOKEN = "<YOUR_TOKEN>"  # SETUP -- добавить токен для Telegram бота
TELEGRAM_BOT_URL = "https://<YOUR APIGW ID>.apigw.yandexcloud.net/test"  # SETUP -- добавить API Gateway id

url = "https://api.telegram.org/bot{token}/{method}".format(
    token=TELEGRAM_BOT_TOKEN,
    # method="setWebhook",
    # method="getWebhookinfo",
    # method = "deleteWebhook"
)

data = {"url": TELEGRAM_BOT_URL}


def main():
    r = requests.post(url, data=data)
    print(r.json())


if __name__ == "__main__":
    main()
