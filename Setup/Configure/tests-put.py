import base

try:
    base.get_tests_table().put_item(
        Item={
            "test_id": "basic_1",
            "total": 2,
            "tl": 100,
            "ml": 1000,
        }
    )
    print("CFG | Put_item --> OK!")
except:
    # ...
    print("CFG | Put_item --> Already exists!")
