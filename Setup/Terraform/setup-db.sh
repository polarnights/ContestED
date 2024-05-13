DOCUMENT_API_ENDPOINT=$(echo "$(cat vars.json)" | jq -r .tasks_db_document_api_endpoint )

aws dynamodb create-table \
    --table-name problemset \
    --attribute-definitions \
      AttributeName=id,AttributeType=N \
      AttributeName=title,AttributeType=S \
      AttributeName=contest,AttributeType=S \
      AttributeName=task_num,AttributeType=N \
      AttributeName=image,AttributeType=S \
      AttributeName=video,AttributeType=S \
      AttributeName=description,AttributeType=S \
    --key-schema \
      AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "[
            {
                \"IndexName\": \"TaskFinderByContestIndex\",
                \"KeySchema\": [{\"AttributeName\":\"contest\",\"KeyType\":\"HASH\"}, {\"AttributeName\":\"task_num\",\"KeyType\":\"RANGE\"}],
                \"Projection\":{
                    \"ProjectionType\":\"ALL\"
                }                
            }
        ]" \
    --endpoint ${DOCUMENT_API_ENDPOINT}
