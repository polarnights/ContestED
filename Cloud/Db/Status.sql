CREATE TABLE Status
(
    user_id Int64 NOT NULL,
    state Utf8,
    PRIMARY KEY (user_id)
)
WITH (
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_BY_LOAD = DISABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048,
    AUTO_PARTITIONING_MIN_PARTITIONS_COUNT = 1,
    KEY_BLOOM_FILTER = DISABLED
);