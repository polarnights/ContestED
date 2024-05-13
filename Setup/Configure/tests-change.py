import base

test_id = "<YOUR TEST_ID>"
# Consists of {contest_name} + "_" + {task_number}

try:
    base.get_tests_table().update_item(
        Key={"test_id": test_id},
        AttributeUpdates={
            "test_id": {"Value": "basic_1", "Action": "PUT"},
            "total": {"Value": 2, "Action": "PUT"},
            "tl": {"Value": 100, "Action": "PUT"},
            "ml": {"Value": 1000, "Action": "PUT"},
        },
    )
    print("CFG | Update_item --> OK!")
except:
    # ...
    print("CFG | Update_item --> There is no such test, use `tests-put.py`!")
