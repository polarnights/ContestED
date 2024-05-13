CREATE TABLE Results
(
    task_id Utf8 NOT NULL,
    contest Utf8 NOT NULL,
    task_n Int32 NOT NULL,
    code_quality Int32,
    quality_comment Utf8,
    code_style Int32,
    style_comment Utf8,
    avg_time_usage Double,
    min_time_usage Double,
    max_time_usage Double,
    avg_memory_usage Double,
    min_memory_usage Double,
    max_memory_usage Double,
    INDEX contest_full GLOBAL ON (contest, task_n),
    PRIMARY KEY (task_id)
)
WITH (
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_BY_LOAD = DISABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048,
    AUTO_PARTITIONING_MIN_PARTITIONS_COUNT = 1,
    KEY_BLOOM_FILTER = DISABLED
);
