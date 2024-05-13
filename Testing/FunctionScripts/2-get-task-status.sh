TASK_ID=$(echo "$(cat action.json)" | jq -r .task_id )

# echo ${TASK_ID}

curl "https://d5db9l2mvbtc273gdgdm.apigw.yandexcloud.net/status?action=status&task_id=${TASK_ID}"