# Supabase deployment

CyberCast uses Supabase as the PostgreSQL database for CTFd. The Flask backend
connects directly to PostgreSQL; browser code must not receive a Supabase
service-role key or a database password.

## Configure the connection

1. In Supabase, create a project and open **Connect**.
2. Copy the PostgreSQL connection URI appropriate for your deployment network.
3. Copy `.env.example` to `.env` and replace `DATABASE_URL` with that URI.
   Use the `postgresql+psycopg2` driver and keep `sslmode=require`.
4. URL-encode special characters in the database password.

`docker compose up --build` reads the local `.env` file. The file is ignored by
Git and must never be committed.

## First start

Start with an empty Supabase database. CTFd runs its own migrations first,
creating the tables it needs for authentication, flags, challenges, and solves.
The `cybercast` plugin then runs its own migration and creates:

- `cybercast_user_profiles`
- `cybercast_challenge_profiles`
- `cybercast_working_rooms`
- `cybercast_room_members`
- `cybercast_room_submissions`

Set an account's CyberCast role through the authenticated CTFd admin API before
that account creates rooms:

```http
PATCH /api/v1/cybercast/users/USER_ID/role
Content-Type: application/json

{"role":"expert"}
```

CTFd administrators remain authoritative for administrative permissions. A
CyberCast `admin` role can manage rooms but does not grant CTFd administration.

## CyberCast API

All routes require a normal CTFd login session and CTFd's CSRF nonce for state
changing requests.

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/cybercast/rooms` | Expert or CTFd admin creates a room. |
| `GET` | `/api/v1/cybercast/rooms/<room_token>` | Member, owner, or admin reads a room. |
| `POST` | `/api/v1/cybercast/rooms/<room_token>/join` | Student joins an active room. |
| `POST` | `/api/v1/cybercast/rooms/<room_token>/submissions` | Member links their own CTFd submission. |
| `GET` | `/api/v1/cybercast/rooms/<room_token>/progress` | Member, owner, or admin reads progress. |
| `GET` | `/api/v1/cybercast/leaderboard` | Reads scores based on CTFd's `solves` table. |

Create a room with:

```json
{
  "challenge_id": 1,
  "room_token": "ROOM-ALPHA-2026"
}
```

The `room_token` is optional; the backend securely generates one when it is
omitted. To link a CTFd attempt to the room, submit the flag through CTFd first,
then send the returned CTFd submission ID:

```json
{
  "submission_id": 42
}
```

The backend verifies that the current user owns the submission, is a room
member, and submitted to the room's challenge before creating the link.
