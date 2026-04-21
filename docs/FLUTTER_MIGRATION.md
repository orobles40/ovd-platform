# Migración Flutter — TUI + Dashboard unificados

**Estado:** Propuesta — pendiente de revisión e iteración  
**Fecha:** 2026-04-20  
**Autor:** Omar Robles  

---

## Resumen ejecutivo

Reemplazar el TUI Rust (5,003 líneas / ratatui) y el Dashboard React (3,000 LOC / Vite) por **una sola aplicación Flutter** que compile a web y escritorio desde el mismo código. Resultado: un único cliente que mantiene paridad de funcionalidades, comparte lógica de negocio, y elimina la carga de mantener dos stacks de UI con herramientas completamente distintas.

---

## Por qué Flutter sobre otras alternativas

| Criterio | Flutter | Tauri (Rust) | Electron | React Native Desktop |
|---|---|---|---|---|
| Web nativo (compilado) | Si (CanvasKit / HTML renderer) | Si | Si | No (experimental) |
| Desktop nativo | Si (macOS, Linux, **Windows**) | Si | Si (pesado) | Parcial |
| Un solo codebase real | Si | Parcial (UI en web) | Parcial | No |
| SSE / streaming HTTP | Si (dart:http streams) | Si | Si | Si |
| Curva de aprendizaje | Media (Dart) | Alta (Rust) | Baja (JS) | Media (RN) |
| Comunidad y paquetes | Grande | Pequeña para UI | Grande | Media |
| Rendimiento UI | Excelente (propio render) | Excelente | Pobre | Bueno |

**Argumento principal:** Tauri reutilizaría la experiencia Rust del TUI pero sigue requiriendo una capa web (HTML/CSS) para la UI, es decir, dos tecnologías. Flutter compila la UI desde Dart puro, sin DOM, lo que elimina la dualidad completamente.

**Argumento secundario:** La app actual ya tiene 15 páginas con gráficos, modales, formularios complejos y streaming en tiempo real. Flutter tiene paquetes maduros para todo esto (`fl_chart`, `riverpod`, `go_router`, `flutter_secure_storage`).

---

## Arquitectura propuesta

```
ovd_app/                          (Flutter monorepo)
├── lib/
│   ├── main.dart                 — entry point (responsive: web vs desktop)
│   ├── app.dart                  — GoRouter + ThemeData + ProviderScope
│   ├── core/
│   │   ├── api/                  — HTTP client + SSE client
│   │   ├── auth/                 — JWT storage + interceptor + refresh
│   │   ├── config/               — env vars + persistencia (shared_preferences)
│   │   └── models/               — Freezed DTOs (SDD, Session, Project, etc.)
│   ├── features/
│   │   ├── auth/                 — Login screen + AuthNotifier
│   │   ├── dashboard/            — KPIs + gráficos (fl_chart)
│   │   ├── fr_launcher/          — Formulario FR + adjuntar imagen + SSE stream
│   │   ├── approval/             — Panel SDD + iteración
│   │   ├── delivery/             — Artefactos + download + copy
│   │   ├── history/              — Lista sesiones + CycleDetail
│   │   ├── projects/             — CRUD proyectos + modal
│   │   ├── knowledge/            — Bootstrap RAG + fuentes web
│   │   ├── telemetry/            — Gráficos uso + costos
│   │   ├── model_dashboard/      — Estado modelos + circuit breaker
│   │   ├── org_chart/            — Pipeline viewer
│   │   ├── workspace/            — Configuración workspace
│   │   ├── admin/
│   │   │   ├── users/            — CRUD usuarios (admin only)
│   │   │   └── skills/           — Gestión repos externos
│   │   └── onboarding/           — Wizard primer uso (equivalente TUI)
│   └── shared/
│       ├── widgets/              — Sidebar, AppBar, Modal, CodeBlock
│       └── theme/                — Colores dark + tipografía monospace
├── web/                          — HTML shell web
├── macos/                        — Entrypoint nativo macOS
├── linux/                        — Entrypoint nativo Linux
└── test/                         — Widget tests + integration tests
```

---

## Pantallas Flutter (mapeo TUI + Dashboard)

### Pantallas del TUI que migran directamente

| TUI Screen | Flutter Screen | Ruta GoRouter |
|---|---|---|
| Onboarding | `OnboardingScreen` | `/onboarding` |
| Login | `LoginScreen` | `/login` |
| WorkspaceSelect | Integrado en `LoginScreen` (step 2) | `/login` |
| Dashboard | `DashboardScreen` | `/` |
| SessionForm | `FrLauncherScreen` | `/fr/new` |
| SessionStream | `SessionStreamScreen` (overlay/panel) | `/session/:id/stream` |
| ApprovalPanel | `ApprovalScreen` | `/session/:id/approval` |
| Delivery | `DeliveryScreen` | `/session/:id/delivery` |
| History | `HistoryScreen` | `/history` |
| Quota | Integrado en `DashboardScreen` (widget) | `/` |

### Pantallas del Dashboard que se agregan

| Dashboard Page | Flutter Screen | Ruta GoRouter |
|---|---|---|
| Cycles | `CyclesScreen` | `/cycles` |
| Projects | `ProjectsScreen` | `/projects` |
| WorkspaceConfig | `WorkspaceConfigScreen` | `/settings/workspace` |
| KnowledgeBootstrap | `KnowledgeScreen` | `/settings/knowledge` |
| Telemetry | `TelemetryScreen` | `/telemetry` |
| ModelDashboard | `ModelDashboardScreen` | `/settings/models` |
| OrgChart | `OrgChartScreen` | `/org-chart` |
| AdminUsers | `AdminUsersScreen` | `/admin/users` |
| SkillsManager | `AdminSkillsScreen` | `/admin/skills` |

**Total: 20 pantallas** (10 del TUI + 9 del Dashboard + 1 nueva fusión Quota/Dashboard).

---

## Navegación — GoRouter

```dart
// app.dart
final router = GoRouter(
  initialLocation: '/login',
  redirect: (context, state) {
    final isAuthenticated = ref.read(authProvider).isAuthenticated;
    if (!isAuthenticated && state.matchedLocation != '/login') return '/login';
    if (isAuthenticated && state.matchedLocation == '/login') return '/';
    return null;
  },
  routes: [
    GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
    GoRoute(path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
    ShellRoute(
      builder: (context, state, child) => AppShell(child: child),
      routes: [
        GoRoute(path: '/', builder: (_, __) => const DashboardScreen()),
        GoRoute(path: '/fr/new', builder: (_, __) => const FrLauncherScreen()),
        GoRoute(path: '/session/:id/stream', builder: (_, state) =>
            SessionStreamScreen(sessionId: state.pathParameters['id']!)),
        GoRoute(path: '/session/:id/approval', builder: (_, state) =>
            ApprovalScreen(sessionId: state.pathParameters['id']!)),
        GoRoute(path: '/session/:id/delivery', builder: (_, state) =>
            DeliveryScreen(sessionId: state.pathParameters['id']!)),
        GoRoute(path: '/history', builder: (_, __) => const HistoryScreen()),
        GoRoute(path: '/cycles', builder: (_, __) => const CyclesScreen()),
        GoRoute(path: '/projects', builder: (_, __) => const ProjectsScreen()),
        GoRoute(path: '/telemetry', builder: (_, __) => const TelemetryScreen()),
        GoRoute(path: '/settings/workspace', builder: (_, __) => const WorkspaceConfigScreen()),
        GoRoute(path: '/settings/knowledge', builder: (_, __) => const KnowledgeScreen()),
        GoRoute(path: '/settings/models', builder: (_, __) => const ModelDashboardScreen()),
        GoRoute(path: '/org-chart', builder: (_, __) => const OrgChartScreen()),
        GoRoute(path: '/admin/users', builder: (_, __) => const AdminUsersScreen()),
        GoRoute(path: '/admin/skills', builder: (_, __) => const AdminSkillsScreen()),
      ],
    ),
  ],
);
```

---

## Estado — Riverpod

Riverpod (v2 con `riverpod_generator`) sobre BLoC por:
- Sin boilerplate de Events/States para casos simples
- `AsyncNotifier` es natural para operaciones async (login, fetch, SSE)
- Testeable sin contexto (solo `ProviderContainer`)
- Compatible con `freezed` para modelos inmutables

```dart
// Ejemplo: auth_provider.dart
@riverpod
class AuthNotifier extends _$AuthNotifier {
  @override
  AuthState build() => const AuthState.unauthenticated();

  Future<void> login(String email, String password) async {
    state = const AuthState.loading();
    try {
      final tokens = await ref.read(apiClientProvider).login(email, password);
      await ref.read(tokenStorageProvider).save(tokens);
      state = AuthState.authenticated(tokens.user);
    } catch (e) {
      state = AuthState.error(e.toString());
    }
  }
}
```

### Providers clave

| Provider | Tipo | Responsabilidad |
|---|---|---|
| `authProvider` | `AuthNotifier` | JWT, login, logout, refresh token |
| `apiClientProvider` | `Provider` | HTTP client con interceptor de auth |
| `sessionStreamProvider(id)` | `StreamProvider` | SSE stream de un ciclo activo |
| `sessionsProvider` | `AsyncNotifier` | Lista de sesiones (History) |
| `projectsProvider` | `AsyncNotifier` | CRUD proyectos |
| `dashboardKpisProvider` | `FutureProvider` | KPIs con auto-refresh |
| `modelStatusProvider` | `AsyncNotifier` | Estado circuit breaker / modelos |

---

## SSE Streaming en Dart

El flujo SSE es el componente más crítico. Implementación con `dart:http` + `StreamController`:

```dart
// sse_client.dart
class SseClient {
  Stream<SseEvent> connect(String url, Map<String, String> headers) async* {
    final client = HttpClient();
    final request = await client.getUrl(Uri.parse(url));
    headers.forEach(request.headers.set);

    final response = await request.close();
    final buffer = StringBuffer();

    await for (final chunk in response.transform(utf8.decoder)) {
      buffer.write(chunk);
      final raw = buffer.toString();
      final events = _parseEvents(raw, buffer);
      for (final event in events) {
        yield event;
      }
    }
  }

  List<SseEvent> _parseEvents(String raw, StringBuffer buffer) {
    final events = <SseEvent>[];
    final lines = raw.split('\n\n');
    if (lines.length < 2) return events;

    for (int i = 0; i < lines.length - 1; i++) {
      final block = lines[i];
      String? eventType, data;
      for (final line in block.split('\n')) {
        if (line.startsWith('event:')) eventType = line.substring(6).trim();
        if (line.startsWith('data:')) data = line.substring(5).trim();
      }
      if (data != null) events.add(SseEvent(eventType ?? 'message', data));
    }
    buffer.clear();
    buffer.write(lines.last);
    return events;
  }
}
```

El `SessionStreamScreen` consume este stream via `StreamProvider.family(sessionId)`.

---

## Autenticación

```dart
// Almacenamiento seguro (desktop: Keychain/SecretService, web: IndexedDB cifrado)
final tokenStorageProvider = Provider((_) => TokenStorage(flutter_secure_storage));

// Interceptor HTTP — adjunta Bearer + refresca si 401
class AuthInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final token = tokenStorage.accessToken;
    if (token != null) options.headers['Authorization'] = 'Bearer $token';
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode == 401) {
      final refreshed = await _refreshToken();
      if (refreshed) {
        // Retry request con nuevo token
        handler.resolve(await _retry(err.requestOptions));
        return;
      }
      ref.read(authProvider.notifier).logout();
    }
    handler.next(err);
  }
}
```

---

## Responsividad — Web vs Desktop

La misma app se adapta al tamaño de pantalla con un `LayoutBuilder` central:

```dart
// app_shell.dart
class AppShell extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth >= 1024) {
          // Desktop / web ancho: sidebar fijo + contenido
          return Row(children: [
            const SidebarNav(width: 220),
            Expanded(child: child),
          ]);
        } else {
          // Web estrecho / móvil futuro: NavigationDrawer
          return Scaffold(
            drawer: const SidebarNav(isDrawer: true),
            body: child,
          );
        }
      },
    );
  }
}
```

**Comportamiento en desktop:** ventana nativa macOS/Linux, sidebar fijo, atajos de teclado (`Ctrl+N` nuevo FR, `Ctrl+H` historial, etc.).  
**Comportamiento en web:** misma UI, sidebar colapsa en pantallas < 1024px, funciona en Chrome/Firefox/Safari.

---

## Imágenes y adjuntos (integración visión qwen2-vl)

La propuesta de visión documentada en `docs/VISION_INTEGRATION.md` se implementa naturalmente en Flutter:

```dart
// En FrLauncherScreen
Future<void> _pickImage() async {
  // Web: html.FileUploadInputElement (dart:html)
  // Desktop: file_picker package
  final result = await FilePicker.platform.pickFiles(
    type: FileType.image,
    allowedExtensions: ['png', 'jpg', 'webp'],
    withData: true,
  );
  if (result != null) {
    final bytes = result.files.first.bytes!;
    setState(() {
      _imageBase64 = base64Encode(bytes);
      _imageName = result.files.first.name;
    });
  }
}
```

Ventaja vs TUI: preview visual real de la imagen adjunta (el TUI solo podía mostrar `[imagen: archivo.png ✓]`).

---

## Gráficos — fl_chart

Reemplaza Recharts del Dashboard:

| Dashboard (Recharts) | Flutter (fl_chart) |
|---|---|
| `LineChart` uso tokens/tiempo | `LineChart` |
| `BarChart` ciclos por proyecto | `BarChart` |
| `PieChart` distribución costo | `PieChart` |
| Gráficos de KPIs | `LineChart` con área |

`fl_chart` es la librería más madura para Flutter con soporte completo de animaciones, tooltips y responsive.

---

## Dependencias principales

```yaml
# pubspec.yaml
dependencies:
  flutter:
    sdk: flutter

  # Navegación
  go_router: ^14.0.0

  # Estado
  flutter_riverpod: ^2.6.0
  riverpod_annotation: ^2.6.0

  # HTTP + SSE
  dio: ^5.7.0               # HTTP client con interceptores
  http: ^1.2.0               # SSE raw stream

  # Modelos inmutables
  freezed_annotation: ^2.4.0
  json_annotation: ^4.9.0

  # Almacenamiento seguro
  flutter_secure_storage: ^9.2.0
  shared_preferences: ^2.3.0   # config no sensible

  # Gráficos
  fl_chart: ^0.70.0

  # Archivos
  file_picker: ^8.1.0

  # Código (syntax highlighting)
  flutter_highlight: ^0.7.0

  # Utilidades
  intl: ^0.19.0
  timeago: ^3.7.0

dev_dependencies:
  build_runner: ^2.4.0
  freezed: ^2.5.0
  json_serializable: ^6.8.0
  riverpod_generator: ^2.6.0
  flutter_test:
    sdk: flutter
  mocktail: ^1.0.3
```

---

## Diferencias de plataforma a gestionar

| Aspecto | Web | Desktop (macOS/Linux) |
|---|---|---|
| Token storage | `flutter_secure_storage` → IndexedDB cifrado | Keychain (macOS) / libsecret (Linux) |
| Config persistencia | `shared_preferences` → localStorage | `shared_preferences` → archivo local |
| File picker | `dart:html` input element | `file_picker` nativo |
| Window title/size | No aplica | `window_manager` package |
| Keyboard shortcuts | Estándar browser | `HardwareKeyboard` + `Focus` widgets |
| Deep links | URL nativa | No aplica |
| Tray icon | No aplica | Opcional (system_tray) |
| Build Windows (.exe) | No aplica | `flutter build windows` — requiere Visual Studio Build Tools en la máquina de build |

La diferencia principal es el storage de tokens. `flutter_secure_storage` abstrae ambos casos automáticamente.

---

## Lo que desaparece

| Componente | Tamaño | Por qué se elimina |
|---|---|---|
| `src/tui/` (Rust) | 5,003 líneas | Reemplazado por Flutter desktop |
| `src/dashboard/` (React) | ~3,000 LOC + 2,000 config | Reemplazado por Flutter web |
| `Cargo.toml` + toolchain Rust | — | Sin TUI no se necesita |
| `bun` + Vite + Tailwind | — | Sin dashboard no se necesita |
| `src/dashboard/Dockerfile` | — | Flutter web genera estáticos para Nginx/Caddy |

**Reducción de stacks**: de 3 lenguajes (Python + Rust + TypeScript) a 2 (Python + Dart).

---

## Esfuerzo estimado por componente

| Componente Flutter | Esfuerzo | Equivalente actual |
|---|---|---|
| Core: API client + SSE + auth | Medio | nats_client, api.py, fetch en TUI y Dashboard |
| Core: modelos Freezed (SDD, Session, etc.) | Bajo | Tipos TypeScript + structs Rust |
| Onboarding + Login | Bajo | TUI OnboardingScreen + LoginScreen |
| Dashboard KPIs + gráficos | Medio | Dashboard DashboardPage + Recharts |
| FrLauncher + image attach | Medio | TUI SessionFormScreen + Dashboard FrLauncher.tsx |
| SessionStream (SSE live) | Alto | TUI SessionStreamScreen (el más complejo) |
| ApprovalPanel + iteración | Medio | TUI ApprovalPanel + Dashboard Approval.tsx |
| Delivery (artefactos) | Bajo | TUI DeliveryScreen + Dashboard |
| History + CycleDetail modal | Bajo | TUI HistoryScreen + Dashboard History.tsx |
| Telemetry + charts | Medio | Dashboard Telemetry.tsx |
| ModelDashboard + OrgChart | Medio | Dashboard ModelDashboard.tsx + OrgChart.tsx |
| Admin: users + skills | Bajo | Dashboard AdminUsers.tsx + SkillsManager.tsx |
| Knowledge + WorkspaceConfig | Bajo | Dashboard KnowledgeBootstrap.tsx |
| AppShell (layout adaptativo) | Bajo | Dashboard Layout.tsx + TUI navegación |
| Tests (widget + integration) | Medio | — |
| Build pipeline web (Nginx/Caddy) | Bajo | Dockerfile del dashboard |
| Build pipeline desktop (macOS .app / Linux / Windows .exe) | Bajo | Cargo build del TUI |

**Esfuerzo total estimado:** Grande (proyecto completo de migración, no feature). El TUI y Dashboard actuales siguen funcionando durante la migración — no es un corte abrupto.

---

## Plan de migración por fases

### Fase 1 — Core sin UI (1-2 semanas)
- Proyecto Flutter nuevo: `src/flutter_app/`
- API client (Dio + interceptors)
- SSE client
- Modelos Freezed (SessionModel, SDDModel, ProjectModel, TokenUsageModel)
- AuthNotifier + flutter_secure_storage
- Tests unitarios del core

### Fase 2 — Flujo principal (2-3 semanas)
- Login, Dashboard básico, FrLauncher, SessionStream, ApprovalPanel, Delivery
- Estos 6 screens cubren el flujo crítico end-to-end
- Verificar SSE streaming con el engine real

### Fase 3 — Flujo secundario (1-2 semanas)
- History, Cycles, Projects, WorkspaceConfig
- Equivalente al TUI History + Dashboard secundario

### Fase 4 — Funcionalidad avanzada (2-3 semanas)
- Telemetry + gráficos (fl_chart)
- ModelDashboard + OrgChart
- Knowledge Bootstrap
- Admin: Users + Skills

### Fase 5 — Plataforma + polish (1 semana)
- Window manager desktop (tamaño inicial, título)
- Keyboard shortcuts nativos
- Build desktop .app (macOS) + web estáticos
- Integrar en docker-compose.prod.yml (Nginx sirve Flutter web)
- Deprecar `src/tui/` y `src/dashboard/`

---

## Integración con Docker (prod)

Flutter web compila a estáticos (`flutter build web`). Se integra al mismo Caddy/Nginx del dashboard actual:

```dockerfile
# Dockerfile.flutter
FROM ghcr.io/cirruslabs/flutter:stable AS build
WORKDIR /app
COPY src/flutter_app .
RUN flutter build web --release --no-tree-shake-icons

FROM nginx:alpine
COPY --from=build /app/build/web /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

No cambia la arquitectura del engine ni NATS — solo la capa de presentación.

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Flutter web lento en dispositivos viejos | Media | CanvasKit es pesado; usar HTML renderer para web si necesario |
| SSE en web bloqueado por CORS | Baja | CORS ya configurado en engine (OVD_CORS_ORIGINS) |
| Dart learning curve | Media | Dart es similar a TypeScript; curva de 1-2 semanas |
| Terminal no disponible en Flutter | N/A | TUI reemplazado completamente — no se necesita terminal |
| fl_chart menos potente que Recharts | Baja | fl_chart tiene paridad funcional para los casos de uso de OVD |
| Build desktop requiere XCode (macOS) | Baja | macOS ya es la plataforma de desarrollo |

---

## Ideas pendientes de evaluación (Omar)

> *Sección para agregar ideas antes de iniciar el desarrollo*

<!-- Agregar aquí ideas a evaluar -->

---

## Referencias internas

- `docs/VISION_INTEGRATION.md` — integración qwen2-vl:7b (imagen adjunta en FrLauncher)
- `src/tui/src/ui/` — código fuente del TUI a migrar
- `src/dashboard/src/pages/` — código fuente del dashboard a migrar
- `src/engine/api.py` — endpoints que consume el cliente Flutter
- `docs/ROADMAP.md` — roadmap general del proyecto
