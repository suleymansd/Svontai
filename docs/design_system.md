# SvontAI Design System Notes

## Design Tokens
Primary source of truth lives in:
- `frontend/src/app/globals.css` (CSS variables)
- `frontend/tailwind.config.ts` (theme extensions)

### Color Tokens
- Primary brand: `--primary` (SvontAI teal)
- Neutrals: `--background`, `--foreground`, `--muted`, `--border`
- Status: `--success`, `--warning`, `--info`, `--destructive`
- Surfaces: `--card`, `--popover`

### Typography
- Sans: `--font-sans` (Sora via `next/font/google`)
- Base sizes: `text-sm` → `text-base` → `text-lg`
- Display: `text-2xl` / `text-3xl` for page titles

### Spacing & Layout
- Page padding: `px-page` / `py-6`
- Section spacing: `space-y-6` or `space-y-8`
- Content container: `max-w-7xl`

### Radii & Shadows
- Radius: `--radius` (0.9rem)
- Shadows: `shadow-soft`, `shadow-elevated`

### Motion
- Subtle transitions: `duration-150/200`
- Entry: `animate-fade-in`, `animate-fade-in-down`

### Z-Index
- `dropdown` (50), `overlay` (60), `modal` (70), `toast` (80)

## Component Structure
- Base UI: `frontend/src/components/ui`
- Shared system components: `frontend/src/components/shared`

## Layout
- App shell: sidebar + topbar
- Content wrapper: `ContentContainer`
- Page headers: `PageHeader` + optional `Breadcrumbs`
