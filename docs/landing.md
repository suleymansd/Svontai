# Marketing Landing Page Plan

## Routes
- `/`
- `/pricing`
- `/features`
- `/use-cases/[segment]`
- `/security`
- `/contact`
- `/docs` (public)

## Page Structure (Home)
1) **Hero**
   - Value proposition: “SvontAI is your automation operating system.”
   - Primary CTA: “Start free trial”
   - Secondary CTA: “Book a demo”
   - Animated gradient mesh + demo preview card

2) **How It Works**
   - Sticky left nav with 3 steps
   - Scroll-driven reveals (Intersection Observer)

3) **Tools Catalog Preview**
   - Curated grid with hover micro-interactions
   - Tags + “Included/Locked” status

4) **Automation + Support**
   - Split section: workflows on left, support on right
   - KPI badges: time saved, response speed

5) **Trust + Security**
   - Compliance summary
   - Uptime + audit log highlights

6) **CTA Footer**
   - “Start free trial” + email capture

## Motion & Interaction
- 150–200ms fades, slight translateY on reveal.
- No parallax or heavy 3D.
- CTA hover: subtle scale (1.01) + shadow.

## Performance Guidelines
- Compress images and use Next Image where possible.
- Avoid large JS on marketing routes.
- Keep animation observers minimal.

## Copy + Tone
- Confident, enterprise-grade, concise.
- Focus on clarity: automation, observability, support.
