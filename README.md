# CyberCast

<p align="center">
  <img src="docs/assets/logo.png" alt="CyberCast Logo" width="180" />
</p>

<p align="center">
  A modern cybersecurity learning and Capture The Flag platform.
</p>

## Overview

CyberCast is a modern cybersecurity learning platform built on top of CTFd and redesigned for long-term education, enterprise training, and collaborative learning.

Unlike traditional CTF platforms that focus on single competitions, CyberCast provides structured learning paths, organization management, team collaboration, and enterprise-oriented cybersecurity training.

## Features

- Learning Paths
- Organizations
- Team Finder
- Enterprise Bug Bounty
- CyberCast Theme
- Progress Tracking
- Plugin-based Architecture
- Team and Individual Competitions
- Dynamic Challenges
- Custom Challenge Types
- Docker Deployment

## Architecture

```text
CyberCast
│
├── Core Platform (CTFd)
│
├── Plugins
│   ├── ctfd_learning_paths
│   ├── ctfd_organizations
│   ├── ctfd_team_finder
│   ├── ctfd_bounty
│   └── ctfd_cybercast_theme
│
└── Future
    ├── Subscription
    ├── AI Assistant
    ├── Marketplace
    └── Analytics
```

## Installation

Clone the repository.

```bash
git clone https://github.com/meowlaxe/CyberCast-Platform.git
cd CyberCast
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Run locally.

```bash
python serve.py
```

Or run with Docker.

```bash
docker compose up
```

## Technologies

- Python
- Flask
- SQLAlchemy
- Docker
- Vue.js
- Bootstrap
- PostgreSQL
- CTFd Plugin System

## Roadmap

- [x] Organizations
- [x] Learning Paths
- [x] Team Finder
- [x] Enterprise Bug Bounty
- [x] CyberCast Theme
- [ ] Subscription
- [ ] AI Assistant
- [ ] Marketplace
- [ ] Mobile Application

## Acknowledgements

CyberCast is built upon the open-source CTFd framework.

Special thanks to the CTFd maintainers and contributors for providing the foundation that made this project possible.

Original project:

https://github.com/CTFd/CTFd

## License

CyberCast follows the license of the original CTFd project unless otherwise specified.
