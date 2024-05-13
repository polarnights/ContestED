SRC_URL=$(echo "$(cat action.json)" | jq -r .src_url )
COURSE=$(echo "$(cat action.json)" | jq -r .course )
CONTEST=$(echo "$(cat action.json)" | jq -r .contest )
LANGUAGE=$(echo "$(cat action.json)" | jq -r .language )
TASK_N=$(echo "$(cat action.json)" | jq -r .task_n )

# echo ${CONTEST}


curl "https://d5db9l2mvbtc273gdgdm.apigw.yandexcloud.net/check_disk?action=check_disk&src_url=${SRC_URL}&course=${COURSE}&language=${LANGUAGE}&task_n=${TASK_N}&contest=${CONTEST}"

# echo "\n"
# echo "https://d5db9l2mvbtc273gdgdm.apigw.yandexcloud.net/check_disk?action=check_disk&src_url=${SRC_URL}&course=${COURSE}&language=${LANGUAGE}&task_n=${TASK_N}&contest=${CONTEST}"