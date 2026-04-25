# Task 22 — Auth API client + types

## Context

Sprint 5（前端）开始执行，Task 22 是前端认证模块的起点：为 `types/api.ts` 添加认证相关 TypeScript 类型，在 `api/client.ts` 添加 register/login/getMe 三个函数，并在 `api.test.ts` 追加对应的 3 个测试。

后端认证端点已在 Task 9 完成，路径为 `/api/v1/auth/`：
- `POST /register` → JSON body → 返回 `Token`（HTTP 201）
- `POST /login` → form-urlencoded (OAuth2 格式，字段名 `username`/`password`) → 返回 `Token`
- `GET /me` → `Authorization: Bearer {token}` header → 返回 `UserResponse`

## 修改文件

### 1. `frontend/src/types/api.ts` — 追加 4 个接口

```typescript
export interface UserCreate {
  email: string
  password: string
  tenant_name: string
}

export interface UserResponse {
  id: string
  email: string
  role: string
  tenant_id: string
  created_at: string
}

export interface Token {
  access_token: string
  token_type: string
}

export interface TenantCreate {
  name: string
}
```

### 2. `frontend/src/api/client.ts` — 追加 AUTH_BASE 常量和 3 个函数

在 `BASE` 常量后添加：
```typescript
const AUTH_BASE = `${API_ORIGIN}/api/v1/auth`
```

新增 3 个函数：
```typescript
export async function register(data: UserCreate): Promise<Token>
// POST JSON to AUTH_BASE/register

export async function login(email: string, password: string): Promise<Token>
// POST URLSearchParams (username=email, password=password) to AUTH_BASE/login

export async function getMe(token: string): Promise<UserResponse>
// GET AUTH_BASE/me with Authorization: Bearer {token}
```

- `register`：JSON body，`Content-Type: application/json`
- `login`：`URLSearchParams`（OAuth2 form-urlencoded），字段名 `username` = email
- `getMe`：接收 token 参数，附加 `Authorization: Bearer {token}` header

### 3. `frontend/src/__tests__/api.test.ts` — 追加 3 个测试

在文件末尾追加，import 中补充新函数和新类型：

```
describe('register')
  it('test_register_call') — POST /api/v1/auth/register, JSON body, 返回 Token

describe('login')  
  it('test_login_call') — POST /api/v1/auth/login, body 为 URLSearchParams 实例

describe('getMe')
  it('test_getMe_with_auth_header') — GET /api/v1/auth/me, 验证 Authorization header
```

测试模式与现有测试一致：`vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(...)`

## 关键注意事项

- `login` 使用 `URLSearchParams` 而非 `FormData`（form-urlencoded vs multipart）
- `login` 的 email 参数映射到 OAuth2 的 `username` 字段
- `getMe` 签名为 `getMe(token: string)` —— token 由调用方传入（Task 23 的 useAuth hook 负责管理）
- 测试中 URL 验证：因 `API_ORIGIN` 在测试环境为空字符串，期望路径为 `/api/v1/auth/...`

## 验证

```bash
cd frontend
npm run test
```

预期：原有测试全部通过 + 新增 3 个测试通过，无 TypeScript 编译错误。
