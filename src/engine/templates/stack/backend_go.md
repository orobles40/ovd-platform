## Convenciones OVD — Go Backend (S58-pre)

### Infraestructura obligatoria — ORDEN DE ESCRITURA

1. **`go.mod`** — módulo y dependencias ← PRIMERO
2. **`main.go`** — entry point ← SEGUNDO
3. **Paquetes de tipos** (`internal/model/`) — antes de los que los usan ← TERCERO
4. **`<paquete>_test.go`** — tests en el mismo paquete ← OBLIGATORIO

**CHECKLIST:**
- [ ] `go.mod` con todas las dependencias usadas
- [ ] Cada paquete tiene su archivo `*_test.go`
- [ ] Errores retornados, no ignorados (`if err != nil`)
- [ ] Sin `panic()` en código de producción

### Estructura válida

```
proyecto/
├── go.mod
├── go.sum
├── main.go
└── internal/
    ├── model/
    │   ├── user.go
    │   └── user_test.go
    ├── service/
    │   ├── user_service.go
    │   └── user_service_test.go
    └── handler/
        ├── user_handler.go
        └── user_handler_test.go
```

### Manejo de errores — Go idiomático

```go
// ✅ CORRECTO — errores explícitos
func (s *UserService) Create(email, orgID string) (*User, error) {
    if !isValidEmail(email) {
        return nil, fmt.Errorf("invalid email: %s", email)
    }
    user, err := s.repo.Insert(email, orgID)
    if err != nil {
        return nil, fmt.Errorf("create user: %w", err)
    }
    return user, nil
}

// ❌ INCORRECTO — panic en producción
func (s *UserService) Create(email, orgID string) *User {
    user, err := s.repo.Insert(email, orgID)
    if err != nil {
        panic(err)  // NUNCA hacer esto
    }
    return user
}
```

### Tests Go — Formato obligatorio

```go:internal/service/user_service_test.go
package service_test

import (
    "testing"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestCreateUser_HappyPath(t *testing.T) {
    svc := NewUserService(mockRepo())
    user, err := svc.Create("test@example.com", "org-1")
    require.NoError(t, err)
    assert.Equal(t, "test@example.com", user.Email)
}

func TestCreateUser_InvalidEmail(t *testing.T) {
    svc := NewUserService(mockRepo())
    _, err := svc.Create("not-email", "org-1")
    assert.ErrorContains(t, err, "invalid email")
}
```

**Verificación:** `go test ./... → ok  github.com/repo/pkg`
