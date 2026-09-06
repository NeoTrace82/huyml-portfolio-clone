# HUYML — portfolio direction

An original, single-page portfolio experience inspired by the editorial interaction language of [huyml.co](https://huyml.co): split-screen intro, oversized type, compact metadata, project rail, live preview, and panel-based navigation.

The implementation does not copy the reference site's proprietary artwork, code, or portfolio media. Project visuals are generated with CSS and open Unsplash imagery.

## Run locally

```bash
npm install
npm run dev
```

Then open the local Vite URL. The production build can be checked with:

```bash
npm run build
npm run preview
```

## Deployment

The site is deployed as a read-only Nginx container through Portainer and Nginx Proxy Manager at:

`https://testsite.digital-impressions.at`

The production image is published to GHCR for `linux/amd64` and `linux/arm64`. The Portainer stack definition is in `portainer-stack.yml`; it joins the shared `proxy` network and intentionally publishes no direct host port.

## Included interactions

- Animated split-screen intro with skip/enter control
- Hover and click project preview switching
- Next-project control and keyboard-accessible project links
- About and Contact slide-over panels
- Responsive layout for tablet and mobile widths
- Reduced-motion support
