import configparser

# CONFIG
config = configparser.ConfigParser()
config.read('dwh.cfg')

# DROP TABLES

staging_events_table_drop = "DROP TABLE IF EXISTS staging_events;"
staging_songs_table_drop = "DROP TABLE IF EXISTS staging_songs;"
songplay_table_drop = "DROP TABLE IF EXISTS songplays;"
user_table_drop = "DROP TABLE IF EXISTS users;"
song_table_drop = "DROP TABLE IF EXISTS songs;"
artist_table_drop = "DROP TABLE IF EXISTS artists;"
time_table_drop = "DROP TABLE IF EXISTS time;"

# CREATE TABLES

staging_songs_table_create = ("""
CREATE TABLE IF NOT EXISTS staging_songs
  ( num_songs        INTEGER
   ,artist_id        VARCHAR
   ,artist_latitude  DECIMAL
   ,artist_longitude DECIMAL
   ,artist_location  VARCHAR
   ,artist_name      VARCHAR
   ,song_id          VARCHAR
   ,title            VARCHAR
   ,duration         DECIMAL
   ,year             INTEGER
  );
""")

staging_events_table_create= ("""
CREATE TABLE IF NOT EXISTS staging_events
  ( artist        VARCHAR
   ,auth          VARCHAR
   ,firstName     VARCHAR
   ,gender        VARCHAR
   ,itemInSession INTEGER
   ,lastName      VARCHAR
   ,length        DECIMAL
   ,level         VARCHAR
   ,location      VARCHAR
   ,method        VARCHAR
   ,page          VARCHAR
   ,registration  VARCHAR
   ,sessionId     INTEGER
   ,song          VARCHAR
   ,status        INTEGER
   ,ts            BIGINT
   ,userAgent     VARCHAR
   ,user_Id       INTEGER
  );
""")

songplay_table_create = ("""
CREATE TABLE IF NOT EXISTS songplays
  ( songplay_id INTEGER identity(1,1)
   ,start_time  TIMESTAMP NOT NULL REFERENCES time(start_time)
   ,user_id     INTEGER NOT NULL REFERENCES users(user_id)
   ,level       VARCHAR
   ,song_id     VARCHAR NOT NULL REFERENCES songs(song_id)
   ,artist_id   VARCHAR NOT NULL REFERENCES artists(artist_id)
   ,session_id  INTEGER NOT NULL
   ,location    VARCHAR
   ,user_agent  VARCHAR
   ,PRIMARY KEY (songplay_id)
   ,UNIQUE (artist_id, song_id, user_id, session_id, start_time)
  )
SORTKEY (start_time);
""")

user_table_create = ("""
CREATE TABLE IF NOT EXISTS users
  ( user_id    INTEGER
   ,first_name VARCHAR
   ,last_name  VARCHAR
   ,gender     CHAR
   ,level      VARCHAR
   ,PRIMARY KEY (user_id)
  )
DISTSTYLE ALL
SORTKEY (user_id);
""")

song_table_create = ("""
CREATE TABLE IF NOT EXISTS songs
  ( song_id   VARCHAR
   ,title     VARCHAR
   ,artist_id VARCHAR NOT NULL REFERENCES artists(artist_id)
   ,year      SMALLINT
   ,duration  DECIMAL
   ,PRIMARY KEY (song_id)
  )
DISTSTYLE KEY
DISTKEY (song_id)
SORTKEY (song_id);
""")

artist_table_create = ("""
CREATE TABLE IF NOT EXISTS artists
  ( artist_id VARCHAR
   ,name      VARCHAR
   ,location  VARCHAR
   ,latitude  DECIMAL
   ,longitude DECIMAL
   ,PRIMARY KEY (artist_id)
  )
SORTKEY (artist_id);
""")

time_table_create = ("""
CREATE TABLE IF NOT EXISTS time
  ( start_time TIMESTAMP
   ,hour       SMALLINT
   ,day        SMALLINT
   ,week       SMALLINT
   ,month      SMALLINT
   ,year       SMALLINT
   ,weekday    VARCHAR
   ,PRIMARY KEY (start_time)
  )
SORTKEY (start_time);
""")

# STAGING TABLES

staging_events_copy = ("""
COPY staging_events
FROM '{}'
CREDENTIALS 'aws_iam_role={}'
FORMAT AS JSON '{}'
REGION '{}';
""").format(config['S3']['LOG_DATA'],config['IAM_ROLE']['ARN'],config['S3']['LOG_JSONPATH'],config['S3']['REGION'])

staging_songs_copy = ("""
COPY staging_songs
FROM '{}'
CREDENTIALS 'aws_iam_role={}'
FORMAT AS JSON '{}'
REGION '{}';
""").format(config['S3']['SONG_DATA'],config['IAM_ROLE']['ARN'],'auto',config['S3']['REGION'])

# FINAL TABLES

songplay_table_insert = ("""
INSERT INTO songplays
  ( start_time
   ,user_id
   ,level
   ,song_id
   ,artist_id
   ,session_id
   ,location
   ,user_agent
  )
SELECT
    timestamp 'epoch' + cast(cte.ts AS bigint)/1000 * interval '1 second' AS start_time
   ,cte.user_Id as user_id
   ,cte.level
   ,cte.song_id
   ,cte.artist_id
   ,cte.sessionId AS session_id
   ,cte.location
   ,cte.userAgent AS user_agent
FROM
  (
   SELECT
       se.ts
      ,se.user_Id
      ,se.level
      ,ss.song_id
      ,ss.artist_id
      ,se.sessionId
      ,se.location
      ,se.userAgent
      ,ROW_NUMBER() OVER(PARTITION BY
                             se.user_Id
                            ,ss.song_id
                            ,ss.artist_id
                            ,se.sessionId
                         ORDER BY se.ts DESC
                        ) AS row_num
   FROM staging_songs AS ss
   INNER JOIN staging_events AS se
       ON ss.artist_name = se.artist
       AND ss.title = se.song
   LEFT JOIN songplays AS sp
       ON se.user_Id = sp.user_id
       AND ss.song_id = sp.song_id
       AND ss.artist_id = sp.artist_id
       AND se.sessionId = sp.session_id
   WHERE se.page = 'NextSong'
     AND sp.start_time IS NULL
  )
AS cte
WHERE cte.row_num = 1;
""")

user_table_insert = ("""
INSERT INTO users
  ( user_id
   ,first_name
   ,last_name
   ,gender
   ,level
  )
SELECT
    user_Id AS user_id
   ,firstName AS first_name
   ,lastName AS last_name
   ,gender
   ,level
FROM
  (
   SELECT
       user_Id
      ,firstName
      ,lastName
      ,gender
      ,level
      ,ROW_NUMBER() OVER(PARTITION BY user_Id
                         ORDER BY ts DESC
                        ) AS row_num
   FROM staging_events
   WHERE user_Id IS NOT NULL
  )
AS staging_events
WHERE row_num = 1
  AND user_Id NOT IN (SELECT user_id FROM users);
""")

song_table_insert = ("""
INSERT INTO songs
  ( song_id
   ,title
   ,artist_id
   ,year
   ,duration
  )
SELECT
    song_id
   ,title
   ,artist_id
   ,year
   ,duration
FROM
  (
   SELECT
       song_id
      ,title
      ,artist_id
      ,year
      ,duration
      ,ROW_NUMBER() OVER(PARTITION BY song_id
                         ORDER BY year DESC
                        ) AS row_num
   FROM staging_songs
   WHERE song_id IS NOT NULL
  )
AS cte_staging_songs
WHERE row_num = 1
  AND song_id NOT IN (SELECT song_id FROM songs);
""")

artist_table_insert = ("""
INSERT INTO artists
  ( artist_id
   ,name
   ,location
   ,latitude
   ,longitude
  )
SELECT
    artist_id
   ,artist_name AS name
   ,artist_location AS location
   ,artist_latitude AS latitude
   ,artist_longitude AS longitude
FROM
  (
   SELECT
       artist_id
      ,artist_name
      ,artist_location
      ,artist_latitude
      ,artist_longitude
      ,ROW_NUMBER() OVER(PARTITION BY artist_id
                         ORDER BY year DESC
                        ) AS row_num
   FROM staging_songs
   WHERE artist_id IS NOT NULL
  )
AS cte_staging_songs
WHERE row_num = 1
  AND artist_id NOT IN (SELECT artist_id FROM artists);
""")

time_table_insert = ("""
INSERT INTO time
  ( start_time
   ,hour
   ,day
   ,week
   ,month
   ,year
   ,weekday
  )
SELECT DISTINCT
    start_time
   ,EXTRACT(hour FROM start_time) AS hour
   ,EXTRACT(day FROM start_time) AS day
   ,EXTRACT(weeks FROM start_time) AS week
   ,EXTRACT(month FROM start_time) AS month
   ,EXTRACT(year FROM start_time) AS year
   ,TRIM(TO_CHAR(start_time,'day')) AS weekday
FROM
  (
   SELECT timestamp 'epoch' + cast(ts AS bigint)/1000 * interval '1 second' AS start_time
   FROM staging_events
   WHERE ts IS NOT NULL
  )
AS cte_staging_events
WHERE start_time NOT IN (SELECT start_time FROM time);
""")

# QUERY LISTS

create_table_queries = [staging_songs_table_create, staging_events_table_create, user_table_create, artist_table_create, song_table_create, time_table_create, songplay_table_create]

drop_table_queries = [songplay_table_drop, user_table_drop, song_table_drop, artist_table_drop, time_table_drop, staging_events_table_drop, staging_songs_table_drop]

copy_table_queries = [staging_songs_copy, staging_events_copy]

insert_table_queries = [user_table_insert, artist_table_insert, song_table_insert, time_table_insert, songplay_table_insert]
