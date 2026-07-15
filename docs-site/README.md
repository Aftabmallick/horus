# Horus Documentation Site 📚

This directory contains the documentation website for the Horus ecosystem (including Agent Tracer Plus and the Agent Tracer Platform), built using [Docusaurus](https://docusaurus.io/).

## Prerequisites

- Node.js >= 20.0
- npm or yarn

## Installation

```bash
npm install
```

## Local Development

To start the local development server:

```bash
npm run start
```

This command starts a local development server and opens up a browser window. Most changes are reflected live without having to restart the server.

## Build

```bash
npm run build
```

This command generates static content into the `build` directory, which can be served using any static hosting service.

## Project Structure

- `docs/`: Markdown files for the main documentation.
- `blog/`: Markdown files for the blog.
- `src/`: React components and pages.
- `static/`: Static assets (images, etc.).
- `docusaurus.config.ts`: Main configuration file.
- `sidebars.ts`: Sidebar configuration for the docs.
