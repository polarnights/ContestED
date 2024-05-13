export FOLDER_ID="<HIDDEN>"
export DOCUMENT_API_ENDPOINT="<HIDDEN>"


terraform apply -target=yandex_ydb_database_serverless.tasks_db

# tasks_db_document_api_endpoint = "https://docapi.serverless.yandexcloud.net/ru-central1/<HIDDEN>"
# tasks_db_path = "<HIDDEN>"

curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
aws configure

bash setup-db.sh 

aws dynamodb describe-table --table-name problemset --endpoint ${DOCUMENT_API_ENDPOINT}

export TELEGRAM_BOT_TOKEN="<HIDDEN>"
python 2-simple-tg-bot.py

yc ydb database list

export YDB_ENDPOINT=grpcs://ydb.serverless.yandexcloud.net:2135
export YDB_DATABASE="<HIDDEN>"

curl -sSL https://install.ydb.tech/cli | bash # Установка ydb cli

ydb \
--endpoint grpcs://ydb.serverless.yandexcloud.net:2135 \
--database "<HIDDEN>" \
--sa-key-file ../App/key.json \
discovery whoami \
--groups

# OLD MQ
# https://message-queue.api.cloud.yandex.net/b1g07pali5s6aacfs053/dj600000001jsdgb05ti/thesis-mq





#'''
# Пример функций для настройки 
echo "export YC_FOLDER_ID=$(yc config get folder-id)" >> ~/.bashrc && . ~/.bashrc
echo $YC_FOLDER_ID

echo "export YC_CLOUD_ID=$(yc config get cloud-id)" >> ~/.bashrc && . ~/.bashrc
echo $YC_CLOUD_ID

yc resource-manager folder add-access-binding $YC_FOLDER_ID \
--subject serviceAccount:$SERVICE_ACCOUNT_DEPLOY_ID \
--role functions.functionInvoker 

yc resource-manager folder add-access-binding $YC_FOLDER_ID \
--subject serviceAccount:$SERVICE_ACCOUNT_DEPLOY_ID \
--role serverless.functions.invoker 

yc resource-manager folder add-access-binding $YC_FOLDER_ID \
--subject serviceAccount:$SERVICE_ACCOUNT_DEPLOY_ID \
--role lockbox.payloadViewer

yc resource-manager folder add-access-binding $YC_FOLDER_ID \
--subject serviceAccount:$SERVICE_ACCOUNT_DEPLOY_ID \
--role storage.editor

yc resource-manager folder add-access-binding $YC_FOLDER_ID \
--subject serviceAccount:$SERVICE_ACCOUNT_DEPLOY_ID \
 --role editor
'''