-- Run in a Hive environment after creating the target HDFS directory.
CREATE DATABASE IF NOT EXISTS socialpulse;
USE socialpulse;

CREATE EXTERNAL TABLE IF NOT EXISTS posts (
    post_id STRING,
    text STRING,
    platform STRING,
    sentiment STRING,
    topic STRING,
    brand STRING
)
PARTITIONED BY (event_date STRING)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/socialpulse/processed/posts';

-- Replace the partition path and values to match the imported date partition.
MSCK REPAIR TABLE posts;

SELECT sentiment, COUNT(*) AS post_count
FROM posts
GROUP BY sentiment
ORDER BY post_count DESC;

SELECT topic, event_date, COUNT(*) AS mentions
FROM posts
WHERE topic IS NOT NULL AND topic <> ''
GROUP BY topic, event_date
ORDER BY event_date, mentions DESC;

SELECT brand, sentiment, COUNT(*) AS post_count
FROM posts
WHERE brand IS NOT NULL AND brand <> ''
GROUP BY brand, sentiment
ORDER BY brand, post_count DESC;

-- Spark output paths in /socialpulse/output/spark-001 contain CSV headers.
CREATE EXTERNAL TABLE IF NOT EXISTS word_frequency (
    word STRING,
    frequency BIGINT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/socialpulse/output/spark-001/word_frequency'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS hashtag_frequency (
    hashtag STRING,
    frequency BIGINT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/socialpulse/output/spark-001/hashtag_frequency'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS sentiment_aggregation (
    sentiment STRING,
    post_count BIGINT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/socialpulse/output/spark-001/sentiment_aggregation'
TBLPROPERTIES ('skip.header.line.count'='1');

SELECT word, frequency FROM word_frequency
ORDER BY frequency DESC, word
LIMIT 25;

SELECT hashtag, frequency FROM hashtag_frequency
ORDER BY frequency DESC, hashtag
LIMIT 25;

SELECT sentiment, post_count FROM sentiment_aggregation
ORDER BY post_count DESC;
