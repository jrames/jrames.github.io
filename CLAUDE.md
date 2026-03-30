# CLAUDE.md

## Project Overview

Personal blog for Jeff Rames, hosted on GitHub Pages at jefframes.com. Intentionally barebones — a simple Jekyll site for writing posts, not a complex web app.

## Tech Stack

- **Jekyll 4.4** static site generator with the **minima** theme
- GitHub Pages hosting (public repo required)
- Custom domain via CNAME (www.jefframes.com)
- GoatCounter for analytics
- Font Awesome 6.5 for social icons (loaded via CDN)

## Project Structure

- `_posts/` — Blog posts in markdown (GFM). Named `YYYY-MM-DD-slug.md`
- `_layouts/default.html` — Single custom layout (overrides minima)
- `_includes/head.html` — Custom head with CSS, Font Awesome, GoatCounter
- `assets/css/custom.css` — All custom styles, includes dark mode via `prefers-color-scheme`
- `assets/images/<post-slug>/` — Post images, organized by post
- `index.html` — Blog post listing (uses Liquid templates)
- `index.markdown` — Home layout entry point
- `about.markdown` — About page (still has default minima boilerplate)
- `_config.yml` — Site config, social links, build settings

## Local Development

```
bundle install
bundle exec jekyll serve
```

Site will be available at http://localhost:4000.

## Writing Posts

Posts go in `_posts/` as `YYYY-MM-DD-title-slug.md` with front matter:

```yaml
---
layout: default
title: "Post Title"
date: YYYY-MM-DD
tags: [Tag1, Tag2]
excerpt: "Short description for the post listing."
---
```

Images for a post go in `assets/images/YYYY-MM-DD-post-slug/`.

## Style Notes

- Image classes: `image-right` (float right), `image-inline` (300px default), `chart-image` (full-width chart)
- Clickable images use `<a>` wrapping with `target="_blank"`
- Captions use `<em>` immediately after an image link
- Video class: `video-right` (float right, 300px)

## Build Exclusions

The `_config.yml` excludes from the Jekyll build: README.md, Gemfile, Gemfile.lock, node_modules/, vendor/, .sass-cache/, .jekyll-cache/. Add any new non-content files to this list.
