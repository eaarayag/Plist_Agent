# Contributing to Plist_Agent

Thank you for your interest in contributing! Please follow these guidelines to keep the project organized and the codebase healthy.

## Getting Started

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd Plist_Agent
   ```
2. Create a new branch from `main` for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Branching Strategy

| Branch | Purpose |
|---|---|
| `main` | Stable, production-ready code. **Never push directly.** |
| `feature/*` | New features or enhancements |
| `bugfix/*` | Bug fixes |
| `docs/*` | Documentation updates |

## Making Changes

1. Keep commits small, focused, and well-described.
2. Write clear commit messages:
   ```
   Short summary (50 chars or less)

   Optional longer description explaining *why* the change was made.
   ```
3. Make sure your changes don't break existing functionality.

## Submitting a Pull Request

1. Push your branch to the remote:
   ```bash
   git push origin feature/your-feature-name
   ```
2. Open a Pull Request targeting `main`.
3. Fill in the PR description:
   - **What** changed and **why**.
   - Any related issues (use `Closes #123` to auto-link).
4. Request a review from **@eaarayag** (auto-assigned via CODEOWNERS).
5. Address all review comments before merging.

## Code Review Process

- All PRs require at least **1 approval** before merging.
- Reviewers may request changes — please address them promptly.
- Once approved and all checks pass, the PR author or maintainer will merge using **Squash and Merge**.

## Reporting Issues

- Use GitHub Issues to report bugs or request features.
- Include steps to reproduce, expected behavior, and actual behavior.

## Questions?

Reach out to **@eaarayag** if you have any questions about the contribution process.
