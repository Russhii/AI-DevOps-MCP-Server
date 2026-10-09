# AWS deployment options (Phase 14)

Not deployed or tested from this repo. This is the plan to pick from.

| Option | Good for | Trade-off |
|---|---|---|
| **ECS Fargate + RDS + ALB** (recommended) | Containers without managing servers; fits `docker-compose` directly | More setup (VPC, task def, ALB) |
| App Runner + RDS | Simplest "run this container" | Less network control; needs VPC connector for private RDS |
| EC2 + Docker Compose | Cheapest, most hands-on | You patch and secure the box yourself |
| Lambda | Spiky traffic | Poor fit: Streamable HTTP sessions are stateful |

## Recommended shape

```
Client -> HTTPS -> ALB (public subnet, ACM certificate)
                    -> ECS Fargate task: MCP server (private subnet)
                        -> RDS PostgreSQL (private subnet, no public access)
```

- **Networking:** VPC with public subnets (ALB only) and private subnets (ECS, RDS). NAT gateway so tasks can reach GitHub.
- **Security groups:** ALB allows 443 from the internet; ECS allows 8000 only from the ALB group; RDS allows 5432 only from the ECS group. PostgreSQL is never public.
- **HTTPS:** ACM certificate on the ALB; the container speaks plain HTTP inside the VPC.
- **Secrets:** store `API_KEYS`, `GITHUB_TOKEN`, DB password in Secrets Manager; inject into the task definition as secrets (not plain env vars, not the image).
- **Env vars:** `DATABASE_URL`, `HOST=0.0.0.0`, `REQUIRE_AUTH=true`.
- **Logs:** container stdout goes to CloudWatch Logs via the `awslogs` driver (the per-tool log lines are already there).
- **Scaling:** ECS service auto-scaling on CPU/requests. Sessions are held in server memory; run multiple tasks with ALB stickiness or switch to stateless mode (`stateless_http=True` in `run`).
- **Migrations:** run `alembic upgrade head` as a one-off ECS task or at container start (as compose does).
