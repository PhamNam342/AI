-- Movie Recommender PostgreSQL schema.
-- Compatible with Neon and standard PostgreSQL 14+.

create extension if not exists pgcrypto;
create extension if not exists citext;

do $$
begin
    create type user_source as enum ('app', 'movielens', 'admin');
exception
    when duplicate_object then null;
end;
$$;

do $$
begin
    create type interaction_type as enum ('view', 'like', 'dislike', 'favorite', 'watchlist', 'skip');
exception
    when duplicate_object then null;
end;
$$;

do $$
begin
    create type training_status as enum ('queued', 'running', 'succeeded', 'failed');
exception
    when duplicate_object then null;
end;
$$;

create table app_users (
    id uuid primary key default gen_random_uuid(),
    email citext unique,
    username text unique,
    password_hash text,
    display_name text,
    source user_source not null default 'app',
    external_user_id text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint app_users_identity_check check (
        email is not null
        or username is not null
        or external_user_id is not null
    ),
    constraint app_users_password_check check (
        source <> 'app'
        or password_hash is not null
    )
);

create unique index app_users_source_external_user_id_idx
    on app_users (source, external_user_id)
    where external_user_id is not null;

create table movies (
    id uuid primary key default gen_random_uuid(),
    movielens_movie_id integer unique,
    title text not null,
    release_year integer,
    genres text[] not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index movies_title_idx on movies using gin (to_tsvector('english', title));
create index movies_genres_idx on movies using gin (genres);

create table user_ratings (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references app_users(id) on delete cascade,
    movie_id uuid not null references movies(id) on delete cascade,
    rating numeric(2, 1) not null,
    rated_at timestamptz not null default now(),
    source user_source not null default 'app',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint user_ratings_rating_check check (rating >= 0.5 and rating <= 5.0),
    constraint user_ratings_one_rating_per_movie unique (user_id, movie_id)
);

create index user_ratings_user_id_idx on user_ratings (user_id);
create index user_ratings_movie_id_idx on user_ratings (movie_id);
create index user_ratings_source_idx on user_ratings (source);

create table user_movie_interactions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references app_users(id) on delete cascade,
    movie_id uuid not null references movies(id) on delete cascade,
    interaction interaction_type not null,
    weight numeric(5, 2) not null default 1.0,
    metadata jsonb not null default '{}',
    occurred_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create index user_movie_interactions_user_time_idx
    on user_movie_interactions (user_id, occurred_at desc);

create index user_movie_interactions_movie_idx
    on user_movie_interactions (movie_id);

create index user_movie_interactions_type_idx
    on user_movie_interactions (interaction);

create table recommendation_runs (
    id uuid primary key default gen_random_uuid(),
    algorithm text not null,
    status training_status not null default 'queued',
    config jsonb not null default '{}',
    metrics jsonb not null default '{}',
    artifact_uri text,
    error_message text,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now()
);

create index recommendation_runs_algorithm_created_idx
    on recommendation_runs (algorithm, created_at desc);

create table recommendation_results (
    id uuid primary key default gen_random_uuid(),
    run_id uuid references recommendation_runs(id) on delete set null,
    user_id uuid not null references app_users(id) on delete cascade,
    movie_id uuid not null references movies(id) on delete cascade,
    rank integer not null,
    predicted_rating numeric(4, 3),
    score numeric(8, 5),
    reason jsonb not null default '{}',
    created_at timestamptz not null default now(),
    constraint recommendation_results_rank_check check (rank > 0)
);

create index recommendation_results_user_created_idx
    on recommendation_results (user_id, created_at desc);

create unique index recommendation_results_run_user_rank_idx
    on recommendation_results (run_id, user_id, rank)
    where run_id is not null;

create table user_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references app_users(id) on delete cascade,
    session_token_hash text not null unique,
    expires_at timestamptz not null,
    created_at timestamptz not null default now(),
    revoked_at timestamptz
);

create index user_sessions_user_id_idx on user_sessions (user_id);
create index user_sessions_expires_at_idx on user_sessions (expires_at);

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger set_app_users_updated_at
before update on app_users
for each row execute function set_updated_at();

create trigger set_movies_updated_at
before update on movies
for each row execute function set_updated_at();

create trigger set_user_ratings_updated_at
before update on user_ratings
for each row execute function set_updated_at();

create view movie_rating_stats as
select
    m.id as movie_id,
    m.movielens_movie_id,
    m.title,
    m.genres,
    count(r.id)::integer as rating_count,
    avg(r.rating)::numeric(4, 3) as average_rating
from movies m
left join user_ratings r on r.movie_id = m.id
group by m.id, m.movielens_movie_id, m.title, m.genres;

create view active_user_stats as
select
    u.id as user_id,
    u.email,
    u.username,
    u.source,
    count(r.id)::integer as rating_count,
    max(r.rated_at) as last_rating_at
from app_users u
left join user_ratings r on r.user_id = u.id
where u.is_active = true
group by u.id, u.email, u.username, u.source;
