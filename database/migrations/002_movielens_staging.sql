-- Optional staging tables for importing the existing MovieLens CSV files.
-- These tables are useful with psql \copy.

create table if not exists stg_movielens_movies (
    movie_id integer primary key,
    title text not null,
    genres text not null
);

create table if not exists stg_movielens_ratings (
    user_id integer not null,
    movie_id integer not null,
    rating numeric(2, 1) not null,
    rating_timestamp bigint
);
