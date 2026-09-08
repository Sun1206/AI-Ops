# Backend Config

Copy `config.example.json` to `config.json` when local MySQL or Redis is needed.
`config.json` is ignored by git because it may contain passwords.

`database.type` can be `sqlite` or `mysql`.
When the database section is missing, AI Ops uses local SQLite at `backend/db.sqlite3`.

For MySQL:

- `database_name`: the MySQL database/schema name, for example `sxdevops`.
- `user`: the MySQL login user.
- `password`: the MySQL login password.
- `host` and `port`: the MySQL server address.

`cache.type` can be `redis`, `local`, or can be omitted.
When the cache section is missing, AI Ops uses Django in-memory cache.

For Redis:

- `redis_url`: Redis connection URL, for example `redis://127.0.0.1:6379/0`.
- `key_prefix`: prefix added to cache keys.
- `default_timeout_seconds`: default cache TTL.
- `ignore_redis_errors`: keep the app running if Redis is temporarily unavailable.
