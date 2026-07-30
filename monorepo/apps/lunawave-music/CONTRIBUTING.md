# Contributing to LunaWave

First off, thank you for considering contributing to LunaWave. It's people like you that make LunaWave such a great tool.

## Where do I go from here?

If you've noticed a bug or have a feature request, make sure to check our [Issues](https://github.com/monang404/lunawave/issues) to see if someone else has already created a ticket. If not, go ahead and make one!

## Fork & create a branch

If this is something you think you can fix, then fork LunaWave and create a branch with a descriptive name.

## Implementation Guidelines

- Ensure you adhere to the hexagonal architecture constraints as outlined in `docs/CONSTRAINTS.md`.
- All tests must pass before submitting a PR.
- Run `pytest` to execute backend tests.
- We use `ruff` for linting. Please ensure `ruff check .` passes without errors.

## Pull Request Process

1. Ensure any install or build dependencies are removed before the end of the layer when doing a build.
2. Update the README.md with details of changes to the interface, this includes new environment variables, exposed ports, useful file locations and container parameters.
3. You may merge the Pull Request in once you have the sign-off of two other developers, or if you do not have permission to do that, you may request the second reviewer to merge it for you.
