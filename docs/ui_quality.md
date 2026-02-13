# UI Quality Checklist

## Layout & Hierarchy
- [ ] Page uses `PageHeader` with title and description
- [ ] Content wrapped in `ContentContainer`
- [ ] Consistent spacing (`space-y-6/8`)
- [ ] Primary action visible at top

## Visual System
- [ ] Uses design tokens (no hard-coded colors)
- [ ] Buttons follow defined variants
- [ ] Cards use `border-border/70` and `shadow-soft`
- [ ] Icons from `lucide-react`

## Data States
- [ ] Skeleton shown during loading
- [ ] Empty state with CTA
- [ ] Error state with retry option where possible

## Accessibility
- [ ] Focus rings visible
- [ ] Icon buttons have `aria-label`
- [ ] Color contrast meets AA

## Dark Mode
- [ ] Background uses `--background`
- [ ] Borders visible but subtle
- [ ] Primary accent readable on dark

## Performance
- [ ] No heavy animations
- [ ] Transitions <= 200ms
- [ ] Tables paginate or virtualize if large
