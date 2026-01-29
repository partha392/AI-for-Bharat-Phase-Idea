# Deployment Guide

## Quick Docker Deploy

```bash
# Build and run
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## AWS ECS Deploy

```bash
# Build and push to ECR
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.ap-south-1.amazonaws.com
docker build -t bharat-voice-assistant .
docker tag bharat-voice-assistant:latest <account>.dkr.ecr.ap-south-1.amazonaws.com/bharat-voice-assistant:latest
docker push <account>.dkr.ecr.ap-south-1.amazonaws.com/bharat-voice-assistant:latest
```

## Environment Variables

```bash
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=ap-south-1
DATABASE_URL=postgresql://user:pass@host:5432/db
```