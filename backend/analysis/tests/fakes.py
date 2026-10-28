"""Builders the tests share.

pytest doesn't collect this module, because its name doesn't start with `test_`.
"""


def create_reports_table(ddb, name: str) -> None:
    """The reports table with its keys and `reportId-index`, as in the template."""
    ddb.create_table(
        TableName=name,
        AttributeDefinitions=[
            {"AttributeName": attribute, "AttributeType": "S"}
            for attribute in ("pk", "sk", "reportId")
        ],
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "reportId-index",
                "KeySchema": [{"AttributeName": "reportId", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 5},
    )
