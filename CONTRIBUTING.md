# Contributing

Thanks for helping! There are only a few rules, and they keep the project easy to follow for everyone.

## The rules

### 1. Everything is in English

Code, comments, variable names, commit messages, docs, issues, pull requests, reviews: all in English.
We're a team project, but writing in English means anyone can read any part of the project.

### 2. Ask before you contribute to the codebase

Before you start, tell the team what you want to do: in the team chat, or by opening a GitHub issue.
Wait for a "yes" before starting.

**Why:** so two people don't build the same thing, and so nobody spends a day on something
that doesn't fit the plan. A quick question saves a lot of time.

### 3. Contributions aren't only code

All of these count, and they're all welcome:

| Kind | Example | How to share it |
|---|---|---|
| **Code** | a new feature, a bug fix | branch + pull request (see rule 4) |
| **Review** | reading someone's pull request and leaving comments | comment on the pull request |
| **Testing** | running the app, trying to break it, reporting what went wrong | open an issue |
| **New data** | a better energy factor with its source, building details | open an issue (or a pull request if it changes files) |
| **Suggestions** | "the building panel should also show…" | open an issue |

### 4. Code goes through a branch and a pull request, and only code does

- **Contributing code?** Create a branch, push it, and open a pull request.
  Never push code straight to `main`.
- **Not contributing code?** You don't need a branch. Use an issue or a comment instead (see the table above).

## How to contribute code, step by step

1. **Ask first** (rule 2).
2. **Get the latest `main`:**
   ```bash
   git checkout main
   git pull
   ```
3. **Make a branch** with a short name that says what it's for:
   ```bash
   git checkout -b add-water-tab
   ```
4. **Make your changes.** Keep them small and about one thing.
5. **Commit** with a short English message that says what changed:
   ```bash
   git add <files>
   git commit -m "Add water tab to building panel"
   ```
6. **Push your branch:**
   ```bash
   git push -u origin add-water-tab
   ```
7. **Open a pull request** on GitHub. In the description, say:
   - **what** you changed
   - **why** (link the issue or chat message where it was agreed)
   - **how you checked it works**
8. **Wait for a review.** Someone else reads it, may ask for changes, and then merges it.

## Not sure about something?

Ask. There are no silly questions here, and asking is always better than guessing.

To see how the app fits together before you start, read:
- [docs/dataflow.md](docs/dataflow.md)
- [docs/components.md](docs/components.md)
