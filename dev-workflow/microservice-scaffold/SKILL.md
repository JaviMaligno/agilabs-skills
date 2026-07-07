---
name: microservice-scaffold
description: Scaffold a TypeScript/Express REST microservice with clean controller/service/route separation, Jest+Supertest tests, a multi-stage Dockerfile, and generic Kubernetes manifests. Use when creating a new REST microservice, adding an endpoint to an existing Express service, or generating Docker/Kubernetes deployment configs for a Node.js API.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Microservice Scaffold Skill

## Overview

This skill scaffolds a production-shaped TypeScript/Express REST microservice: project
structure, a controller/service/route pattern, tests, a multi-stage Dockerfile, and
generic Kubernetes manifests. It works for brand-new services and for adding endpoints
to an existing one that already follows this layout.

**Key Capabilities:**
- Scaffold a new TypeScript/Express project by hand (no proprietary CLI required)
- Implement REST endpoints with a clean controller → service → route split
- Generate unit and integration tests (Jest + Supertest)
- Create a production-ready multi-stage Docker image
- Generate generic Kubernetes manifests (ConfigMap, Secret, Deployment, Service, Ingress)
  with liveness/readiness probes
- Produce a README skeleton covering setup, env vars, endpoints, and deployment

**When to Use This Skill:**
- "Scaffold a new microservice for..."
- "Add a `/search` endpoint to this service..."
- "Generate a Dockerfile and Kubernetes manifests for..."
- "Set up tests for this Express API..."

**Not covered:** any specific CI system, GitOps tooling, or cloud provider. Phase 5.4
below describes the generic mental model only — wire it to whatever CI/CD stack you
actually use.

## Workflow

### Phase 1: Discovery

**Objective:** Understand the environment and requirements before generating anything.

**Steps:**

1. **Detect environment:**
```bash
[ -f package.json ] && cat package.json
[ -f tsconfig.json ] && echo "TypeScript project already set up"
[ -d src ] && echo "existing src/ layout — treat as 'extend', not 'scaffold'"
```

2. **Gather requirements:**
   - Service name (used for `package.json` name, Docker image name, k8s resource names)
   - Endpoints needed (search, detail, create, verify, etc.)
   - Upstream data sources (external APIs, databases, queues)
   - Deployment target (local only, or also Docker/Kubernetes)

3. **Confirm approach:**
   - New microservice vs. extending an existing one
   - Testing requirements (unit + integration, coverage threshold)
   - Deployment needs (Docker, Kubernetes manifests, none)

**Validation Checkpoint:**
- [ ] Requirements clearly understood
- [ ] Environment detected (existing project vs. new)
- [ ] Approach confirmed with the user if ambiguous

---

### Phase 2: Scaffolding

**Objective:** Create the project structure.

1. **Create directories:**
```bash
mkdir -p src/api/{controllers,routes,services}
mkdir -p src/lib
mkdir -p __tests__/integration __tests__/unit
mkdir -p k8s
```

2. **Create `package.json`:**
```json
{
  "name": "<service-name>",
  "version": "1.0.0",
  "scripts": {
    "dev": "nodemon src/server.ts",
    "build": "tsc",
    "test": "jest",
    "test:coverage": "jest --coverage",
    "start": "node dist/server.js"
  },
  "dependencies": {
    "express": "^4.18.0",
    "express-validator": "^7.0.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@types/express": "^4.17.0",
    "@types/jest": "^29.0.0",
    "jest": "^29.0.0",
    "supertest": "^6.3.0",
    "ts-jest": "^29.0.0",
    "typescript": "^5.0.0",
    "nodemon": "^3.0.0"
  }
}
```

3. **Create `tsconfig.json`:**
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "__tests__"]
}
```

4. **Create `jest.config.js`:**
```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/__tests__'],
  testMatch: ['**/*.test.ts'],
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/server.ts',
    '!src/app.ts'
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  coverageReporters: ['text', 'lcov', 'html']
};
```

**Validation Checkpoint:**
- [ ] Project structure created
- [ ] Dependencies installed (`npm install`)
- [ ] TypeScript compiles (`npm run build`)

---

### Phase 3: Implementation

**Objective:** Implement endpoints following a consistent controller/service/route pattern.

#### 3.1 Logging, errors, and metrics — a swappable interface

Rather than hard-wiring a specific vendor library, define a small local interface for
logging, structured HTTP errors, and (optionally) metrics. Controllers and services only
ever depend on this interface — swap the implementation for `pino`, `winston`,
`prom-client`, your own internal package, or nothing at all, without touching the rest of
the codebase.

**Template: `src/lib/logging.ts`**
```typescript
export interface Logger {
  info(event: string, meta?: Record<string, unknown>): void;
  warn(event: string, meta?: Record<string, unknown>): void;
  error(event: string, meta?: Record<string, unknown>): void;
}

// Minimal default implementation — replace with pino/winston/etc. as needed.
export const logger: Logger = {
  info: (event, meta) => console.log(JSON.stringify({ level: 'info', event, ...meta })),
  warn: (event, meta) => console.warn(JSON.stringify({ level: 'warn', event, ...meta })),
  error: (event, meta) => console.error(JSON.stringify({ level: 'error', event, ...meta })),
};
```

**Template: `src/lib/errors.ts`**
```typescript
export class HttpError extends Error {
  constructor(
    public statusCode: number,
    public errorCode: string,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

export const ErrorCodes = {
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  INTERNAL_SERVER_ERROR: 'INTERNAL_SERVER_ERROR',
  UPSTREAM_API_ERROR: 'UPSTREAM_API_ERROR',
  UPSTREAM_API_UNAVAILABLE: 'UPSTREAM_API_UNAVAILABLE',
} as const;
```

**Template: `src/lib/metrics.ts`** (optional — a no-op default is fine if you don't need metrics)
```typescript
export interface Metrics {
  increment(name: string, labels?: Record<string, string>): void;
  startTimer(name: string): () => void;
}

// No-op default — swap for a prom-client-backed implementation if you export /metrics.
export const metrics: Metrics = {
  increment: () => {},
  startTimer: () => () => {},
};
```

#### 3.2 Controller Pattern

Controllers handle HTTP requests, validate input, call the service layer, and format
the response. They never make outbound network calls directly.

**Template: `SearchController.ts`**
```typescript
import { Request, Response } from 'express';
import { validationResult, Schema } from 'express-validator';
import { logger } from '../../lib/logging';
import { HttpError, ErrorCodes } from '../../lib/errors';
import { metrics } from '../../lib/metrics';
import * as DataService from '../services/DataService';

const validationRules: Schema = {
  query: {
    in: ['query'],
    isString: true,
    notEmpty: true,
    errorMessage: 'Query parameter is required'
  },
  limit: {
    in: ['query'],
    optional: true,
    isInt: { options: { min: 1, max: 100 } },
    toInt: true,
    errorMessage: 'Limit must be between 1 and 100'
  }
};

export default {
  validationRules,

  async search(req: Request, res: Response) {
    const requestId = req.headers['x-request-id'];

    logger.info('search_request_received', { requestId, query: req.query.query });

    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        throw new HttpError(400, ErrorCodes.VALIDATION_ERROR, 'Invalid input parameters', errors.array());
      }

      const results = await DataService.search({
        query: req.query.query as string,
        limit: req.query.limit ? parseInt(req.query.limit as string, 10) : 10
      });

      logger.info('search_request_completed', { requestId, resultCount: results.length });

      return res.json({
        success: true,
        data: results,
        count: results.length
      });

    } catch (error) {
      logger.error('search_request_failed', {
        requestId,
        error: error instanceof Error ? error.message : 'Unknown error'
      });

      if (error instanceof HttpError) {
        return res.status(error.statusCode).json({
          success: false,
          error: {
            code: error.errorCode,
            message: error.message,
            details: error.details
          }
        });
      }

      metrics.increment('unhandled_request_error');

      return res.status(500).json({
        success: false,
        error: {
          code: ErrorCodes.INTERNAL_SERVER_ERROR,
          message: 'Internal server error'
        }
      });
    }
  }
};
```

**Key Controller Principles:**
- Export a `validationRules` object for `express-validator`'s `checkSchema`
- Use structured logging with a request/correlation id
- Validate all inputs explicitly
- Call the service layer — never make HTTP calls directly in the controller
- Return a consistent response shape: `{ success, data | error }`
- Translate `HttpError` instances into the right status code
- Increment metrics on unhandled errors (if metrics are wired up)

#### 3.3 Service Pattern

Services own external API calls, data transformation, and business logic.

**Template: `DataService.ts`**
```typescript
import axios, { AxiosError } from 'axios';
import { logger } from '../../lib/logging';
import { HttpError, ErrorCodes } from '../../lib/errors';
import { metrics } from '../../lib/metrics';

interface SearchParams {
  query: string;
  limit: number;
}

interface SearchResult {
  id: string;
  name: string;
  description: string;
}

export const search = async (params: SearchParams): Promise<SearchResult[]> => {
  metrics.increment('upstream_request');
  const stopTimer = metrics.startTimer('upstream_request_duration');

  const upstreamApiUrl = process.env.UPSTREAM_API_URL || 'https://api.example.com';

  logger.info('upstream_call_started', { endpoint: '/search', params });

  try {
    const response = await axios.get(`${upstreamApiUrl}/search`, {
      params: {
        q: params.query,
        limit: params.limit
      },
      timeout: 10000,
      headers: {
        Accept: 'application/json',
        'User-Agent': '<service-name>/1.0'
      }
    });

    stopTimer();

    logger.info('upstream_call_completed', {
      statusCode: response.status,
      resultCount: response.data?.results?.length || 0
    });

    // Transform the upstream response into this service's own shape.
    return response.data.results.map((item: any) => ({
      id: item.id,
      name: item.title || item.name,
      description: item.summary || item.description
    }));

  } catch (error) {
    stopTimer();

    logger.error('upstream_call_failed', {
      error: error instanceof Error ? error.message : 'Unknown error',
      statusCode: (error as AxiosError).response?.status
    });

    if (axios.isAxiosError(error)) {
      if (error.response) {
        throw new HttpError(
          error.response.status,
          ErrorCodes.UPSTREAM_API_ERROR,
          `Upstream API error: ${error.message}`,
          error.response.data
        );
      } else if (error.request) {
        throw new HttpError(
          503,
          ErrorCodes.UPSTREAM_API_UNAVAILABLE,
          'Upstream API is unavailable'
        );
      }
    }

    throw new HttpError(
      500,
      ErrorCodes.INTERNAL_SERVER_ERROR,
      'Failed to fetch data from upstream API'
    );
  }
};
```

**Key Service Principles:**
- Include structured logging around outbound calls
- Set reasonable timeouts (10s default)
- Transform upstream responses into the service's own internal shape
- Convert `axios` errors into `HttpError` with the right status code
- Never leak raw upstream responses straight to the controller
- Metrics are optional — wire in a real backend only if you export `/metrics`

#### 3.4 Routes Configuration

**Template: `src/api/routes/index.ts`**
```typescript
import { Router } from 'express';
import { checkSchema } from 'express-validator';
import SearchController from '../controllers/SearchController';
import DetailController from '../controllers/DetailController';
// import { authenticate } from '../../lib/auth'; // plug in your own auth middleware

const router = Router();

// router.use(authenticate); // uncomment once auth middleware exists

router.get(
  '/api/v1/search',
  checkSchema(SearchController.validationRules),
  SearchController.search
);

router.get(
  '/api/v1/items/:id',
  checkSchema(DetailController.validationRules),
  DetailController.detail
);

export default router;
```

**Key Routing Principles:**
- Use `express-validator` with `checkSchema`
- Apply auth middleware globally once it exists — leave a clear placeholder if it doesn't yet
- Use a consistent, versioned URL prefix (e.g. `/api/v1/...`)
- Group related endpoints together

**Validation Checkpoint:**
- [ ] Controllers follow the template pattern
- [ ] Services handle errors and (optionally) metrics consistently
- [ ] Routes configured with validation
- [ ] TypeScript compiles without errors
- [ ] Code follows existing project conventions

---

### Phase 4: Testing

**Objective:** Create unit and integration tests alongside the implementation.

#### 4.1 Unit Tests for Services

**Template: `DataService.test.ts`**
```typescript
import axios from 'axios';
import { search } from '../DataService';
import { HttpError } from '../../../lib/errors';

jest.mock('axios');
jest.mock('../../../lib/logging', () => ({
  logger: { info: jest.fn(), warn: jest.fn(), error: jest.fn() }
}));
jest.mock('../../../lib/metrics', () => ({
  metrics: { increment: jest.fn(), startTimer: jest.fn(() => jest.fn()) }
}));

const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('DataService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('search', () => {
    it('should successfully fetch and transform search results', async () => {
      const mockResponse = {
        status: 200,
        data: {
          results: [
            { id: '1', title: 'Item A', summary: 'Description A' },
            { id: '2', title: 'Item B', summary: 'Description B' }
          ]
        }
      };
      mockedAxios.get.mockResolvedValue(mockResponse);

      const results = await search({ query: 'test', limit: 10 });

      expect(results).toHaveLength(2);
      expect(results[0]).toEqual({
        id: '1',
        name: 'Item A',
        description: 'Description A'
      });
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/search'),
        expect.objectContaining({
          params: { q: 'test', limit: 10 },
          timeout: 10000
        })
      );
    });

    it('should handle upstream API errors and throw HttpError', async () => {
      const apiError = {
        response: { status: 404, data: { message: 'Not found' } },
        isAxiosError: true,
        message: 'Request failed with status code 404'
      };
      mockedAxios.get.mockRejectedValue(apiError);
      mockedAxios.isAxiosError.mockReturnValue(true);

      await expect(search({ query: 'test', limit: 10 })).rejects.toThrow(HttpError);
      await expect(search({ query: 'test', limit: 10 })).rejects.toMatchObject({
        statusCode: 404
      });
    });

    it('should handle network timeouts', async () => {
      const timeoutError = {
        request: {},
        isAxiosError: true,
        message: 'timeout of 10000ms exceeded'
      };
      mockedAxios.get.mockRejectedValue(timeoutError);
      mockedAxios.isAxiosError.mockReturnValue(true);

      await expect(search({ query: 'test', limit: 10 })).rejects.toThrow(HttpError);
      await expect(search({ query: 'test', limit: 10 })).rejects.toMatchObject({
        statusCode: 503
      });
    });
  });
});
```

#### 4.2 Integration Tests for Controllers

**Template: `SearchController.test.ts`**
```typescript
import request from 'supertest';
import express, { Express } from 'express';
import { checkSchema } from 'express-validator';
import SearchController from '../controllers/SearchController';
import * as DataService from '../services/DataService';

jest.mock('../services/DataService');
jest.mock('../../../lib/logging', () => ({
  logger: { info: jest.fn(), warn: jest.fn(), error: jest.fn() }
}));
jest.mock('../../../lib/metrics', () => ({
  metrics: { increment: jest.fn(), startTimer: jest.fn(() => jest.fn()) }
}));

describe('SearchController Integration Tests', () => {
  let app: Express;

  beforeEach(() => {
    app = express();
    app.use(express.json());

    app.get(
      '/api/v1/search',
      checkSchema(SearchController.validationRules),
      SearchController.search
    );

    jest.clearAllMocks();
  });

  describe('GET /api/v1/search', () => {
    it('should return search results for a valid query', async () => {
      const mockResults = [{ id: '1', name: 'Test Item', description: 'A test item' }];
      (DataService.search as jest.Mock).mockResolvedValue(mockResults);

      const response = await request(app)
        .get('/api/v1/search')
        .query({ query: 'test', limit: '10' });

      expect(response.status).toBe(200);
      expect(response.body).toEqual({
        success: true,
        data: mockResults,
        count: 1
      });
      expect(DataService.search).toHaveBeenCalledWith({ query: 'test', limit: 10 });
    });

    it('should return 400 for a missing query parameter', async () => {
      const response = await request(app).get('/api/v1/search');

      expect(response.status).toBe(400);
      expect(response.body.success).toBe(false);
      expect(response.body.error.code).toContain('VALIDATION');
    });

    it('should return 400 for an invalid limit', async () => {
      const response = await request(app)
        .get('/api/v1/search')
        .query({ query: 'test', limit: '200' }); // exceeds max

      expect(response.status).toBe(400);
      expect(response.body.success).toBe(false);
    });

    it('should handle service errors gracefully', async () => {
      (DataService.search as jest.Mock).mockRejectedValue(new Error('Downstream failure'));

      const response = await request(app)
        .get('/api/v1/search')
        .query({ query: 'test' });

      expect(response.status).toBe(500);
      expect(response.body.success).toBe(false);
      expect(response.body.error.message).toBe('Internal server error');
    });
  });
});
```

**Testing Principles:**
- Mock all external dependencies (`axios`, the logging/errors/metrics modules)
- Unit tests exercise services in isolation
- Integration tests exercise controllers with `supertest`
- Coverage threshold: aim for 80%+ on all metrics
- Cover the happy path, edge cases, and error conditions
- Use descriptive test names: "should [expected behavior] when [condition]"

**Validation Checkpoint:**
- [ ] Unit tests written for all services
- [ ] Integration tests written for all controllers
- [ ] All tests pass (`npm test`)
- [ ] Coverage meets threshold (`npm run test:coverage`)
- [ ] Tests are independent and can run in any order

---

### Phase 5: Deployment

**Objective:** Create production-ready deployment configuration.

#### 5.1 Dockerfile (Multi-Stage)

**Template: `Dockerfile`**
```dockerfile
# Stage 1: Builder
FROM node:lts-bullseye as builder

WORKDIR /app

COPY package*.json ./
COPY tsconfig.json ./

RUN npm ci

COPY src ./src

RUN npm run build

# Stage 2: Production
FROM node:lts-slim

WORKDIR /app

COPY package*.json ./

RUN npm ci --only=production && npm cache clean --force

COPY --from=builder /app/dist ./dist

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD node -e "require('http').get('http://localhost:8000/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

CMD ["node", "dist/server.js"]
```

**Key Docker Principles:**
- Multi-stage build: builder stage + slim production stage
- `npm ci` for reproducible builds
- Production stage installs only production dependencies
- Runs as a non-root user
- `HEALTHCHECK` targets a `/health` endpoint the app must expose
- Keep layers minimal

#### 5.2 docker-compose.yml (Local Development)

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - NODE_ENV=development
      - UPSTREAM_API_URL=https://api.example.com
      - LOG_LEVEL=debug
    volumes:
      - ./src:/app/src
      - ./dist:/app/dist
    command: npm run dev
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

#### 5.3 Kubernetes Manifests

All examples use generic placeholders — replace `<namespace>`, `<registry>`,
`<service-name>`, and `<ingress-host>` with real values before applying.

**Template: `k8s/configmap.yaml`**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: <service-name>-config
  namespace: <namespace>
  labels:
    app: <service-name>
data:
  NODE_ENV: "production"
  LOG_LEVEL: "info"
  UPSTREAM_API_URL: "https://api.example.com"
  PORT: "8000"
```

**Template: `k8s/secret.yaml`**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: <service-name>-secrets
  namespace: <namespace>
  labels:
    app: <service-name>
type: Opaque
stringData:
  # IMPORTANT: replace these placeholders before deployment — never commit real values
  API_KEY: "$API_KEY"
  JWT_SECRET: "$JWT_SECRET"
  DATABASE_URL: "$DATABASE_URL"
```

**Template: `k8s/deployment.yaml`**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <service-name>
  namespace: <namespace>
  labels:
    app: <service-name>
spec:
  replicas: 2
  selector:
    matchLabels:
      app: <service-name>
  template:
    metadata:
      labels:
        app: <service-name>
    spec:
      imagePullSecrets:
      - name: <image-pull-secret-name>
      containers:
      - name: <service-name>
        image: <registry>/<service-name>:latest
        ports:
        - containerPort: 8000
          name: http
        envFrom:
        - configMapRef:
            name: <service-name>-config
        - secretRef:
            name: <service-name>-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
          timeoutSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
```

**Template: `k8s/service.yaml`**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: <service-name>
  namespace: <namespace>
  labels:
    app: <service-name>
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
    name: http
  selector:
    app: <service-name>
```

**Template: `k8s/ingress.yaml`**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: <service-name>
  namespace: <namespace>
  labels:
    app: <service-name>
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    # Adjust/remove annotations for your actual ingress controller (nginx, traefik, etc.)
spec:
  ingressClassName: <ingress-class-name>
  tls:
  - hosts:
    - <ingress-host>
    secretName: <service-name>-tls
  rules:
  - host: <ingress-host>
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: <service-name>
            port:
              number: 80
```

**Deployment Principles:**
- Multi-stage Docker builds for smaller images
- Kubernetes health probes (liveness + readiness) against `/health`
- Resource requests/limits to avoid resource exhaustion
- `ConfigMap` for non-sensitive config, `Secret` for credentials — never commit real secret values
- TLS via cert-manager (or your own certificate flow) at the ingress

**Validation Checkpoint:**
- [ ] Docker builds successfully (`docker build -t test .`)
- [ ] `docker-compose up` starts locally
- [ ] K8s manifests validate (`kubectl apply --dry-run=client -f k8s/`)
- [ ] All placeholders replaced with actual values
- [ ] Secrets handled securely (not committed to version control)

#### 5.4 CI/CD — the general mental model

This skill does not prescribe a specific CI system or GitOps tool. The shape that most
teams converge on for a containerized microservice looks like this:

```
code repo (this service)
   │  push / PR
   ▼
CI pipeline: install → build → test → build image
   │  push
   ▼
image registry (tagged, e.g. by commit SHA or semver)
   │  update image tag
   ▼
GitOps config repo (desired-state manifests per environment)
   │  sync (pull-based: Argo CD/Flux, or push-based: kubectl/helm from CI)
   ▼
Kubernetes cluster
```

Key points to adapt regardless of the specific tools:
- Run the test suite (Phase 4) before building the image — never build-then-test
- Tag images deterministically (commit SHA, semver) — never rely on `:latest` in production
- Keep "what should be running" (the GitOps config repo / manifests) separate from
  "how it gets built" (the CI pipeline) — this separation is what makes rollbacks and
  audits tractable
- Whatever tool syncs manifests to the cluster (Argo CD, Flux, a `kubectl apply` step,
  a Helm release) should be the *only* path that mutates cluster state in production

---

### Phase 6: Documentation

**Objective:** Document setup, deployment, and API usage.

#### 6.1 README.md

**Template sections to include:**

```markdown
# <Service Name>

> Brief description of what this microservice does

## Features

- Feature 1
- Feature 2
- Feature 3

## Prerequisites

- Node.js >= 18
- npm >= 9
- Docker (for containerized deployment)
- kubectl (for Kubernetes deployment)

## Installation

### Local Development

\`\`\`bash
npm install
npm run dev
npm test
npm run build
\`\`\`

### Docker

\`\`\`bash
docker build -t <service-name> .
docker run -p 8000:8000 <service-name>
\`\`\`

### Docker Compose

\`\`\`bash
docker-compose up
\`\`\`

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `NODE_ENV` | Environment (development/production) | No | development |
| `PORT` | Server port | No | 8000 |
| `UPSTREAM_API_URL` | Upstream API endpoint | Yes | - |
| `API_KEY` | Upstream API authentication key | Yes | - |
| `LOG_LEVEL` | Logging level (debug/info/warn/error) | No | info |

## API Endpoints

### Search
`GET /api/v1/search`

**Query Parameters:**
- `query` (required): Search query string
- `limit` (optional): Number of results (1-100, default 10)

**Response:**
\`\`\`json
{
  "success": true,
  "data": [
    { "id": "123", "name": "Item name", "description": "Item description" }
  ],
  "count": 1
}
\`\`\`

### Detail
`GET /api/v1/items/:id`

[Document other endpoints similarly]

## Deployment

### Kubernetes

\`\`\`bash
kubectl create secret generic <service-name>-secrets \
  --from-literal=API_KEY=<your-key> \
  --namespace=<namespace>

kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

kubectl get pods -n <namespace> -l app=<service-name>
\`\`\`

## Testing

\`\`\`bash
npm test
npm run test:coverage
npm test -- SearchController.test.ts
\`\`\`

## Monitoring

- **Health**: health check at `/health`
- **Metrics**: if wired up, exposed at `/metrics`
- **Logs**: structured JSON logs to stdout

## Troubleshooting

### Common Issues

**Issue**: Tests failing with timeout
**Solution**: Increase the Jest timeout in `jest.config.js`

**Issue**: Docker build fails
**Solution**: Check the Node version matches the Dockerfile

[Add more as needed]

## Contributing

1. Create a feature branch
2. Make changes with tests
3. Run `npm test` and `npm run build`
4. Open a pull request

## License

[Your license]
\`\`\`

#### 6.2 API Documentation (Optional)

If using OpenAPI/Swagger, create `swagger.yaml`:

```yaml
openapi: 3.0.0
info:
  title: <Service Name> API
  version: 1.0.0
  description: API for <service description>

servers:
  - url: https://<ingress-host>
    description: Production
  - url: http://localhost:8000
    description: Local

paths:
  /api/v1/search:
    get:
      summary: Search for records
      parameters:
        - name: query
          in: query
          required: true
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 10
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/SearchResult'
                  count:
                    type: integer

components:
  schemas:
    SearchResult:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        description:
          type: string
```

**Documentation Principles:**
- README covers installation, usage, and deployment
- All environment variables documented
- API endpoints documented with example requests/responses
- Troubleshooting section for common issues

**Validation Checkpoint:**
- [ ] README.md created with all sections
- [ ] Environment variables documented
- [ ] API endpoints documented
- [ ] Deployment instructions clear and tested

---

## Validation Checkpoints Summary

### After Scaffolding
- [ ] Project structure created
- [ ] Dependencies installed
- [ ] TypeScript compiles

### After Implementation
- [ ] Controllers follow the pattern
- [ ] Services handle errors (and metrics, if used) consistently
- [ ] Routes configured with validation
- [ ] Code follows conventions

### After Testing
- [ ] Unit tests for all services
- [ ] Integration tests for all controllers
- [ ] All tests pass
- [ ] Coverage >80%

### After Deployment Config
- [ ] Docker builds successfully
- [ ] `docker-compose` works locally
- [ ] K8s manifests validate
- [ ] Secrets handled securely

### After Documentation
- [ ] README complete
- [ ] Environment variables documented
- [ ] API endpoints documented
- [ ] Deployment tested

---

## Usage Examples

### Example 1: Create a New Microservice

**User Prompt:** "Scaffold a new microservice called `orders-api` with search and detail endpoints"

**Expected Actions:**
1. Create project structure manually (Phase 2)
2. Generate `SearchController` and `DetailController`
3. Generate an `OrdersService` with axios calls
4. Create unit tests for the service
5. Create integration tests for the controllers
6. Generate Dockerfile and K8s manifests
7. Update README with API documentation

### Example 2: Add an Endpoint to an Existing Service

**User Prompt:** "Add a `verify` endpoint to the existing `inventory-service` with tests"

**Expected Actions:**
1. Detect the existing service structure
2. Create `VerifyController.ts` following the pattern
3. Add a `verify()` method to the relevant service
4. Add the route in `routes/index.ts`
5. Create unit tests for the `verify` method
6. Create integration tests for `VerifyController`
7. Update README with the new endpoint's documentation

### Example 3: Generate Deployment Config for an Existing Service

**User Prompt:** "Generate Kubernetes manifests for `my-api` in the `my-team` namespace"

**Expected Actions:**
1. Create the `k8s/` directory
2. Generate `ConfigMap` with environment variables
3. Generate `Secret` template
4. Generate `Deployment` with health probes
5. Generate `Service` (ClusterIP)
6. Generate `Ingress` with TLS
7. Add deployment instructions to the README

---

## Notes

- **Adaptability**: detect whether this is a new project or an extension of an existing one
- **Testing mandatory**: don't consider the work done without passing tests
- **Conventions**: inspect existing code before generating new patterns, if extending a service
- **Validation**: checkpoints after each phase help catch gaps early

---

## Quick Reference

### Common Commands

```bash
# Setup
npm install
npm run dev
npm test
npm run test:coverage

# Build
npm run build
docker build -t <service-name> .
docker-compose up

# Deployment
kubectl apply -f k8s/
kubectl get pods -n <namespace>
kubectl logs -n <namespace> -l app=<service-name>
```

### File Structure Reference

```
<service-name>/
├── src/
│   ├── api/
│   │   ├── controllers/
│   │   │   ├── SearchController.ts
│   │   │   └── DetailController.ts
│   │   ├── routes/
│   │   │   └── index.ts
│   │   └── services/
│   │       └── DataService.ts
│   ├── lib/
│   │   ├── logging.ts
│   │   ├── errors.ts
│   │   └── metrics.ts
│   ├── app.ts
│   └── server.ts
├── __tests__/
│   ├── unit/
│   │   └── DataService.test.ts
│   └── integration/
│       └── SearchController.test.ts
├── k8s/
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── ingress.yaml
├── Dockerfile
├── docker-compose.yml
├── package.json
├── tsconfig.json
├── jest.config.js
└── README.md
```
