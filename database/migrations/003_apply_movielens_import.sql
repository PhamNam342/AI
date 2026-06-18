-- Move MovieLens data from staging tables into the normalized app schema.
-- Run this after importing CSV data into stg_movielens_movies and stg_movielens_ratings.

insert into movies (movielens_movie_id, title, release_year, genres)
select
    movie_id,
    title,
    nullif(substring(title from '\(([0-9]{4})\)$'), '')::integer,
    case
        when genres = '(no genres listed)' then '{}'
        else string_to_array(genres, '|')
    end
from stg_movielens_movies
on conflict (movielens_movie_id) do update
set
    title = excluded.title,
    release_year = excluded.release_year,
    genres = excluded.genres;

insert into app_users (source, external_user_id, username, display_name)
select
    'movielens'::user_source,
    user_id::text,
    'movielens_' || user_id::text,
    'MovieLens User ' || user_id::text
from (select distinct user_id from stg_movielens_ratings) users
on conflict (source, external_user_id) do nothing;

insert into user_ratings (user_id, movie_id, rating, rated_at, source)
select
    u.id,
    m.id,
    r.rating,
    to_timestamp(r.rating_timestamp),
    'movielens'::user_source
from stg_movielens_ratings r
join app_users u
    on u.source = 'movielens'
    and u.external_user_id = r.user_id::text
join movies m
    on m.movielens_movie_id = r.movie_id
on conflict (user_id, movie_id) do update
set
    rating = excluded.rating,
    rated_at = excluded.rated_at,
    source = excluded.source;
