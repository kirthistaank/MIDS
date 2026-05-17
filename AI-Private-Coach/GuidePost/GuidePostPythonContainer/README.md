# Guidepost Python Container (FastAPI)

Backend API and **UI site** for the Guidepost coaching MVP. The image serves both the API and the built `ui` SPA on the same port.

`src/main.py` exposes endpoints for:
- Uploading an audio file
- Background diarization/transcription (+ optional initial analysis)
- Polling processing status
- Chatting with a coaching assistant grounded in the processed conversation


APP URL on ECS: mi-b37305cc803b45a8a2bc554a15355fb4.ecs.us-east-2.on.aws

## Requirements

- Docker (recommended path) **or** Python + Poetry (local dev)

## Run locally (recommended): Docker Compose

This repo includes a `docker-compose.yml` at the repo root that runs:
- **API + built UI** on `http://localhost:8000`
- **Postgres** for local development (service name `postgres`)

### 1) Make sure you have an .env file with all the environment variables

### 2) Start the stack

From the repo root:

```bash
docker compose up -d --build
```

To test quickly via FastAPI:
- **UI (site):** `http://localhost:8000/`
- **API docs:** `http://localhost:8000/docs`

To watch logs:

```bash
docker compose logs -f api
```

### 3) Stop the stack

```bash
docker compose down
```

If you want to delete local DB data/volumes:

```bash
docker compose down -v
```

## To open our app with the front-end

In another terminal from repo root:

```bash
cd ui
npm install
npm run dev
```

Then open the UI at:
- `http://localhost:5173`


## Running on AWS

- You'll need to set up access keys. I created a user called guidepost_team. The credentials are in the csv in our Slack chat.

```bash
aws configure set aws_access_key_id ACCESS_ID --profile default
aws configure set aws_secret_access_key SECRET_ACCESS_KEY --profile default
aws configure set region us-east-2 --profile default
```

- After that, you can verify that it's configured correctly

```bash
aws sts get-caller-identity
```

- Then you can login

```bash
aws ecr get-login-password --region us-east-2 \
| docker login --username AWS --password-stdin 468805747882.dkr.ecr.us-east-2.amazonaws.com
```

### Push a new image to ECR (recommended: ECS-compatible amd64 build)

From the repo root (context must be repo root so the UI can be built):

```bash
AWS_REGION=us-east-2
ACCOUNT_ID=468805747882
REPO=mids_guidepost
TAG=latest   # or e.g. TAG=$(git rev-parse --short HEAD)

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker buildx build \
  --provenance=false \
  --platform linux/amd64 \
  -f GuidePostPythonContainer/Dockerfile \
  -t "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO:$TAG" \
  --push \
  .
```

- To access the AWS console: https://468805747882.signin.aws.amazon.com/console