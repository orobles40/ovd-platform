## Convenciones OVD — React + TypeScript Frontend (S58-pre)

### Infraestructura obligatoria — ORDEN DE ESCRITURA

1. **`package.json`** — dependencias y scripts ← PRIMERO
2. **`tsconfig.json`** con `strict: true` ← SEGUNDO
3. **`vite.config.ts`** — configuración de Vite ← TERCERO
4. **`tailwind.config.ts`** — tokens de diseño ← CUARTO
5. **`src/index.css`** — variables CSS de shadcn/ui ← QUINTO
6. **`src/components/ui/`** — primitivos shadcn/ui (Button, Input, Card...) ← ANTES de los componentes que los usan
7. **`tests/*.test.tsx`** — tests Vitest ← OBLIGATORIO por componente

**CHECKLIST antes de entregar:**
- [ ] `package.json` con todas las dependencias usadas
- [ ] `tailwind.config.ts` generado
- [ ] `src/index.css` con variables CSS de shadcn/ui
- [ ] Cada hook generado es usado por al menos un componente
- [ ] Al menos un archivo de test por componente principal

---

### Sistema de diseño obligatorio — Tailwind CSS + shadcn/ui

**REGLA ABSOLUTA:** Todo el CSS debe usar **Tailwind CSS**. Está PROHIBIDO:
- CSS-in-JS (`styled-components`, `emotion`, `css` template literals)
- Clases CSS inventadas sin definición (`className="my-custom-btn"`)
- Estilos inline `style={{}}` salvo para valores dinámicos imposibles de expresar con Tailwind
- Archivos `.css` o `.scss` con clases custom (excepto `src/index.css` con variables CSS)

**Componentes shadcn/ui:** Usa shadcn/ui para todos los primitivos. NUNCA construyas desde cero:

```tsx
// ✅ CORRECTO — importar desde shadcn/ui
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

// ❌ INCORRECTO — nunca construyas botones/inputs/cards desde cero
const MyButton = ({ children }) => <button className="bg-blue-500 px-4 py-2">{children}</button>
```

### tailwind.config.ts mínimo

```ts:tailwind.config.ts
import type { Config } from "tailwindcss"

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
export default config
```

### src/index.css — variables CSS de shadcn/ui

```css:src/index.css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 221.2 83.2% 53.3%;
    --radius: 0.5rem;
  }
}

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
body { font-family: 'Inter', system-ui, sans-serif; }
```

---

### Tests Vitest — Formato obligatorio (S40-templates)

Para cada componente principal generado, incluye su archivo de test.

```tsx:tests/LoginForm.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { LoginForm } from '../src/components/LoginForm'

describe('LoginForm', () => {
  it('renders the form fields', () => {
    render(<LoginForm onSubmit={vi.fn()} />)
    expect(screen.getByLabelText(/rut/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/contraseña/i)).toBeInTheDocument()
  })

  it('shows validation error for invalid RUT', async () => {
    render(<LoginForm onSubmit={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/rut/i), { target: { value: '12.345.678-4' } })
    fireEvent.blur(screen.getByLabelText(/rut/i))
    await waitFor(() => {
      expect(screen.getByText(/rut inválido/i)).toBeInTheDocument()
    })
  })

  it('calls onSubmit with valid RUT', async () => {
    const onSubmit = vi.fn()
    render(<LoginForm onSubmit={onSubmit} />)
    fireEvent.change(screen.getByLabelText(/rut/i), { target: { value: '12.345.678-5' } })
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: 'pass123' } })
    fireEvent.submit(screen.getByRole('form'))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
  })
})
```

**Reglas:**
- Mínimo 2 tests por componente: smoke (renderiza sin error) + comportamiento
- Usa `@testing-library/react` + `@testing-library/user-event`
- Verificación: `vitest run → N/N passed`

---

### Validación de RUT chileno en React (TypeScript)

Cuando el FR pida validación de RUT en UI:

```typescript:src/utils/rut.ts
export function cleanRut(rut: string): string {
  return rut.replace(/[.\-]/g, '').trim().toUpperCase()
}

export function validateRut(rut: string): boolean {
  const cleaned = cleanRut(rut)
  if (!/^\d{7,8}[0-9K]$/.test(cleaned)) return false
  const body = cleaned.slice(0, -1)
  const dv = cleaned.slice(-1)
  let total = 0, factor = 2
  for (let i = body.length - 1; i >= 0; i--) {
    total += parseInt(body[i]) * factor
    factor = factor === 7 ? 2 : factor + 1
  }
  const remainder = 11 - (total % 11)
  const expected = remainder === 10 ? 'K' : remainder === 11 ? '0' : String(remainder)
  return dv === expected
}

export function formatRut(rut: string): string {
  const cleaned = cleanRut(rut)
  const body = cleaned.slice(0, -1)
  const dv = cleaned.slice(-1)
  return body.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + '-' + dv
}
```

**Regla de validación en tiempo real (inline feedback):**
```tsx
const [rutError, setRutError] = useState('')

const handleRutBlur = (value: string) => {
  if (value && !validateRut(value)) {
    setRutError('RUT inválido — verifica el dígito verificador')
  } else {
    setRutError('')
  }
}
```
