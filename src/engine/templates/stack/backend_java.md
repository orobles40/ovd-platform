## Convenciones OVD — Java Backend (S58-pre)

### Infraestructura obligatoria — ORDEN DE ESCRITURA

1. **`pom.xml`** (Maven) o **`build.gradle`** (Gradle) ← PRIMERO
2. **`src/main/java/<package>/Application.java`** — entry point Spring Boot ← SEGUNDO
3. **Clases de modelo y DTOs** — antes de servicios y controllers ← TERCERO
4. **`src/test/java/<package>/`** — tests JUnit 5 ← OBLIGATORIO

**CHECKLIST:**
- [ ] `pom.xml` o `build.gradle` con todas las dependencias usadas
- [ ] Entry point `@SpringBootApplication` generado
- [ ] Al menos un archivo de test por servicio

### Estructura válida (Spring Boot)

```
proyecto/
├── pom.xml
└── src/
    ├── main/
    │   └── java/com/ejemplo/
    │       ├── Application.java
    │       ├── controller/
    │       ├── service/
    │       ├── repository/
    │       └── model/
    └── test/
        └── java/com/ejemplo/
            └── service/
                └── UserServiceTest.java
```

### Tests JUnit 5 — Formato obligatorio

```java:src/test/java/com/ejemplo/service/UserServiceTest.java
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class UserServiceTest {

    @Test
    void shouldCreateUserWithValidData() {
        // Arrange
        var service = new UserService();
        // Act
        var user = service.create("test@example.com", "org-1");
        // Assert
        assertEquals("test@example.com", user.getEmail());
    }

    @Test
    void shouldThrowOnInvalidEmail() {
        var service = new UserService();
        assertThrows(ValidationException.class,
            () -> service.create("invalid", "org-1"));
    }
}
```

### Manejo de errores Spring Boot

```java
@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(ValidationException.class)
    @ResponseStatus(HttpStatus.UNPROCESSABLE_ENTITY)
    public Map<String, String> handleValidation(ValidationException ex) {
        return Map.of("error", ex.getMessage());
    }
    // Nunca exponer stack traces al cliente
}
```
